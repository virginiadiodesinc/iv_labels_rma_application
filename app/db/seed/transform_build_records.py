"""
Stage 2 (build files): TRANSFORM

Reads raw_build_records.jsonl (produced by parse_build_files.py) and, driven
by build_key_mapping.py, produces db_ready_build_records.jsonl -- one record
per line, each with THREE things a build file source turns into:

  - "fields": flat Build_Info columns -- same shape/logic as the block
    pipeline (key mapping, blank handling, date normalization).
  - "parts": a list of Build_Parts row-dicts (diode/circuit/filter/pcb/mmic
    fanned out), template-aware via old_style.
  - "notes": a list of Notes row-dicts (the raw "notes" list plus vbr /
    indium_info), type stored as the ENUM'S VALUE STRING ("generic") since
    JSON can't hold a Note_Type -- seed_build_info.py coerces it back to
    Note_Type right before insert, same pattern as dates.

Also writes build_transform_warnings.jsonl and a small random sample, same
as the block transform.

Run:
    python transform_build_records.py
    python transform_build_records.py --sample-size 50
"""

from collections import defaultdict
from pathlib import Path
import argparse
import datetime
import json
import random
import re

from app.db.seed import build_key_mapping as mapping
from app.services import string_utilities as su

OUTPUT_DIR = Path(__file__).resolve().parent
RAW_RECORDS_PATH = OUTPUT_DIR / "raw_build_records.jsonl"
DB_READY_PATH = OUTPUT_DIR / "db_ready_build_records.jsonl"
WARNINGS_PATH = OUTPUT_DIR / "build_transform_warnings.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "build_field_value_summary.json"
SAMPLE_PATH = OUTPUT_DIR / "build_sample.jsonl"

# Fallback only -- matches parse_build_files.py's own rule, used ONLY for
# raw records parsed before "old_style" started being persisted. New
# records always carry their own explicit old_style flag; that's preferred
# over recomputing from mtime, since mtimes aren't fully trustworthy (see
# the block-file file-discovery investigation).
NEWEST_TEMPLATE_DATE = datetime.date(2024, 5, 9)


def read_raw_records():
    with open(RAW_RECORDS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def resolve_old_style(raw_record):
    if "old_style" in raw_record:
        return raw_record["old_style"]
    # Fallback for records parsed before old_style was persisted.
    file_date = datetime.datetime.fromtimestamp(raw_record["source_mtime"]).date()
    return file_date < NEWEST_TEMPLATE_DATE


def apply_key_mapping(raw_fields):
    transformed = {}
    for raw_key, value in raw_fields.items():
        if raw_key in mapping.FIELD_NAME_MAP:
            transformed[mapping.FIELD_NAME_MAP[raw_key]] = value
        elif not mapping.DROP_UNMAPPED_KEYS:
            transformed[raw_key] = value
    return transformed


def apply_blank_handling(db_fields):
    cleaned = {}
    for key, value in db_fields.items():
        if mapping.is_blank(value):
            if key in mapping.BLANK_DEFAULTS:
                cleaned[key] = mapping.BLANK_DEFAULTS[key]
        else:
            cleaned[key] = value
    return cleaned


def parse_date_string(raw_value):
    text = re.sub(r"\s+", "", str(raw_value))
    for fmt in mapping.DATE_INPUT_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_dates(fields, source_mtime):
    normalized = {}
    unparseable = []
    for key, value in fields.items():
        if key in mapping.DATE_FIELDS:
            parsed = parse_date_string(value)
            if parsed is not None:
                normalized[key] = parsed.isoformat()
            elif mapping.DATE_PARSE_FALLBACK == "file_mtime":
                fallback_date = datetime.datetime.fromtimestamp(source_mtime).date()
                normalized[key] = fallback_date.isoformat()
                unparseable.append((key, value, True))
            else:
                unparseable.append((key, value, False))
        else:
            normalized[key] = value
    return normalized, unparseable


def extract_parts(raw_fields, old_style):
    """Returns (parts_list, quantity_warnings, fallback_notes). Blank part
    names (per is_blank -- "", "na", "n/a", etc) are skipped entirely, same
    as the original seed_build_files_post_template_change.py.

    For slots marked "ambiguous" (old-style slots historically used as a
    dumping ground -- see filter_2), the text is only treated as a part if
    separate_part_and_lot() actually finds a non-blank lot. Otherwise the
    raw text is returned in fallback_notes instead of being forced into a
    part row with a guessed part_type.
    """
    slots = mapping.PART_SLOTS_OLD_STYLE if old_style else mapping.PART_SLOTS_NEW_STYLE
    parts = []
    quantity_warnings = []
    fallback_notes = []

    for slot in slots:
        if "name_lot_key" in slot:
            full_text = raw_fields.get(slot["name_lot_key"], "")
            name, lot, extra = su.separate_part_and_lot(full_text)
        else:
            full_text = None
            name = raw_fields.get(slot["name_key"], "")
            lot = raw_fields.get(slot["lot_key"], "")

        if mapping.is_blank(name):
            continue

        if slot.get("ambiguous") and mapping.is_blank(lot):
            if full_text is not None and not mapping.is_blank(full_text):
                fallback_notes.append(full_text)
            continue

        if "quantity_key" in slot:
            raw_qty = raw_fields.get(slot["quantity_key"])
            try:
                quantity = int(str(raw_qty).strip())
            except (TypeError, ValueError):
                quantity = 1
                quantity_warnings.append((slot["part_type"], slot["quantity_key"], raw_qty))
        else:
            quantity = slot["quantity"]

        parts.append({
            "part_name": name,
            "part_lot": lot or "",
            "part_type": slot["part_type"],
            "quantity": quantity,
        })

    return parts, quantity_warnings, fallback_notes


def extract_notes(raw_fields):
    """Note type is stored as the Note_Type ENUM VALUE STRING ("generic"),
    not the enum itself -- JSON can't hold an enum. seed_build_info.py
    converts it back via Note_Type(value) right before insert."""
    notes = []
    for note_text in (raw_fields.get(mapping.NOTES_LIST_KEY) or []):
        if not mapping.is_blank(note_text):
            notes.append({"note": note_text, "type": "generic"})
    for key in mapping.EXTRA_NOTE_KEYS:
        value = raw_fields.get(key)
        if not mapping.is_blank(value):
            notes.append({"note": value, "type": "generic"})
    return notes


def find_warnings(db_fields):
    warnings = []
    for required_key in mapping.REQUIRED_DB_KEYS:
        if required_key not in db_fields or mapping.is_blank(db_fields.get(required_key)):
            warnings.append(f"missing or blank required field: {required_key}")
    non_blank_values = [v for v in db_fields.values() if not mapping.is_blank(v)]
    if not non_blank_values:
        warnings.append("all fields blank")
    return warnings


def update_field_summary(summary, db_fields):
    for key, value in db_fields.items():
        stats = summary[key]
        stats["total"] += 1
        if mapping.is_blank(value):
            stats["blank"] += 1
        else:
            stats["present"] += 1
            stats["example_values"].add(str(value)[:80])


def finalize_summary(summary):
    finalized = {}
    for key, stats in summary.items():
        finalized[key] = {
            "total": stats["total"],
            "present": stats["present"],
            "blank": stats["blank"],
            "distinct_example_values": sorted(stats["example_values"])[:10],
        }
    return finalized


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=25)
    args = parser.parse_args()

    if not RAW_RECORDS_PATH.exists():
        raise SystemExit(f"{RAW_RECORDS_PATH} not found -- run parse_build_files.py first.")

    field_summary = defaultdict(lambda: {"total": 0, "present": 0, "blank": 0, "example_values": set()})
    total = 0
    warning_count = 0
    total_parts = 0
    total_notes = 0
    all_transformed = []

    with open(DB_READY_PATH, "w", encoding="utf-8") as db_out, \
         open(WARNINGS_PATH, "w", encoding="utf-8") as warn_out:

        for raw_record in read_raw_records():
            total += 1
            old_style = resolve_old_style(raw_record)

            db_fields = apply_key_mapping(raw_record["raw_fields"])
            update_field_summary(field_summary, db_fields)

            cleaned_fields = apply_blank_handling(db_fields)
            cleaned_fields, unparseable_dates = normalize_dates(cleaned_fields, raw_record["source_mtime"])

            parts, quantity_warnings, fallback_notes = extract_parts(raw_record["raw_fields"], old_style)
            notes = extract_notes(raw_record["raw_fields"])
            for text in fallback_notes:
                notes.append({"note": text, "type": "generic"})
            total_parts += len(parts)
            total_notes += len(notes)

            output_record = {
                "source_path": raw_record["source_path"],
                "source_mtime": raw_record["source_mtime"],
                "old_style": old_style,
                "fields": cleaned_fields,
                "parts": parts,
                "notes": notes,
            }
            db_out.write(json.dumps(output_record, default=str) + "\n")
            all_transformed.append(output_record)

            warnings = find_warnings(cleaned_fields)
            for key, raw_value, fallback_applied in unparseable_dates:
                if fallback_applied:
                    warnings.append(f"unparseable date for {key!r} ({raw_value!r}) -- fell back to file mtime")
                else:
                    warnings.append(f"unparseable date for {key!r}: {raw_value!r} -- dropped")
            for part_type, qty_key, raw_qty in quantity_warnings:
                warnings.append(f"non-integer quantity for {part_type} ({qty_key}={raw_qty!r}) -- defaulted to 1")
            for text in fallback_notes:
                warnings.append(f"ambiguous slot didn't look like a part, filed as note: {text!r}")
            if not parts:
                warnings.append("no parts extracted")
            if warnings:
                warning_count += 1
                warn_out.write(json.dumps({
                    "source_path": raw_record["source_path"],
                    "old_style": old_style,
                    "warnings": warnings,
                    "fields": cleaned_fields,
                }, default=str) + "\n")

    with open(SUMMARY_PATH, "w", encoding="utf-8") as summary_out:
        json.dump(finalize_summary(field_summary), summary_out, indent=2, default=str)

    sample = random.sample(all_transformed, min(args.sample_size, len(all_transformed))) if all_transformed else []
    with open(SAMPLE_PATH, "w", encoding="utf-8") as sample_out:
        for record in sample:
            sample_out.write(json.dumps(record, default=str) + "\n")

    print(f"Transformed {total} records.")
    print(f"Total parts rows: {total_parts}  |  Total notes rows: {total_notes}")
    print(f"Flagged {warning_count} with warnings -> {WARNINGS_PATH}")
    print(f"DB-ready output -> {DB_READY_PATH}")
    print(f"Field value summary -> {SUMMARY_PATH}")
    print(f"Random sample ({len(sample)} records) -> {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
