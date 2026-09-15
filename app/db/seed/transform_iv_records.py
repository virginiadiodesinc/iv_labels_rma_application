"""
Stage 2 (IV files): TRANSFORM

Reads raw_iv_records.jsonl (produced by parse_iv_files.py) and, driven by
iv_key_mapping.py, produces db_ready_iv_records.jsonl -- one record per
line, with:

  - "fields": db-ready IV_Info columns. Diode/circuit lots are split out
    here (su.separate_part_and_lot, same helper as build's parts
    extraction), voltage/current point lists are joined into strings,
    numeric fields are coerced to real int/float (JSON holds these fine,
    so no need to defer to seed the way dates/enums are), and polarity is
    normalized to its Enum VALUE STRING ("positive"/"negative") -- seed
    coerces that back to Polarity(...) right before insert.

Also writes iv_transform_warnings.jsonl and a small random sample, same
shape as the block/build transforms.

Run:
    python transform_iv_records.py
    python transform_iv_records.py --sample-size 50
"""

from collections import defaultdict
from pathlib import Path
import argparse
import datetime
import json
import random
import re

from app.db.seed import iv_key_mapping as mapping
from app.services import string_utilities as su

OUTPUT_DIR = Path(__file__).resolve().parent
RAW_RECORDS_PATH = OUTPUT_DIR / "raw_iv_records.jsonl"
DB_READY_PATH = OUTPUT_DIR / "db_ready_iv_records.jsonl"
WARNINGS_PATH = OUTPUT_DIR / "iv_transform_warnings.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "iv_field_value_summary.json"
SAMPLE_PATH = OUTPUT_DIR / "iv_sample.jsonl"


def read_raw_records():
    with open(RAW_RECORDS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def apply_key_mapping(raw_fields):
    transformed = {}
    for raw_key, value in raw_fields.items():
        if raw_key in mapping.FIELD_NAME_MAP:
            transformed[mapping.FIELD_NAME_MAP[raw_key]] = value
        elif not mapping.DROP_UNMAPPED_KEYS:
            transformed[raw_key] = value
    return transformed


def split_name_lot_fields(raw_fields, db_fields):
    """Reads the RAW combined "name_lot" values (e.g. raw "diode") and adds
    the split name/lot pair into db_fields under their db-ready keys (e.g.
    "diode" / "diode_lot"). Operates on raw_fields, not the already-mapped
    db_fields, since the combined field and its two split outputs share a
    name in one case (diode -> diode, diode_lot)."""
    updated = dict(db_fields)
    for raw_key, (name_key, lot_key) in mapping.NAME_LOT_SPLITS.items():
        full_text = raw_fields.get(raw_key, "")
        name, lot, extra = su.separate_part_and_lot(full_text)
        updated[name_key] = name
        updated[lot_key] = lot
        if not updated[lot_key]:
            updated[lot_key] = "Unknown"

    return updated


def join_list_fields(fields):
    """Runs BEFORE blank-handling -- an empty list becomes "" here, then
    flows through the normal blank/required-field logic instead of needing
    a separate check."""
    joined = dict(fields)
    for key in mapping.LIST_JOIN_FIELDS:
        value = joined.get(key)
        if isinstance(value, list):
            joined[key] = ",".join(str(v) for v in value)
    return joined


def apply_blank_handling(db_fields):
    cleaned = {}
    for key, value in db_fields.items():
        if mapping.is_blank(value):
            if key in mapping.BLANK_DEFAULTS:
                cleaned[key] = mapping.BLANK_DEFAULTS[key]
        else:
            cleaned[key] = value
    return cleaned


def coerce_numeric_fields(fields):
    """float()/int() -- handles E-notation natively, nothing special
    needed for it. Returns (fields, numeric_warnings); a field that fails
    to coerce is DROPPED (same drop-if-bad philosophy as blanks) rather
    than left as an unusable string."""
    coerced = dict(fields)
    warnings = []

    for key in mapping.FLOAT_FIELDS:
        if key in coerced:
            try:
                coerced[key] = float(str(coerced[key]).strip())
            except (TypeError, ValueError):
                warnings.append(f"non-numeric value for {key!r}: {coerced[key]!r} -- dropped")
                del coerced[key]

    for key in mapping.INT_FIELDS:
        if key in coerced:
            try:
                coerced[key] = int(float(str(coerced[key]).strip()))
            except (TypeError, ValueError):
                warnings.append(f"non-integer value for {key!r}: {coerced[key]!r} -- dropped")
                del coerced[key]

    return coerced, warnings


def normalize_polarity(fields):
    """Raw "+"/"-" (or whatever POLARITY_MAP covers) -> the Polarity enum's
    VALUE STRING. JSON can't hold an Enum, so seed_iv_info.py converts this
    back via Polarity(value) right before insert, same pattern as
    Note_Type on the build side."""
    updated = dict(fields)
    if "polarity" in updated:
        raw_value = str(updated["polarity"]).strip()
        if raw_value in mapping.POLARITY_MAP:
            updated["polarity"] = mapping.POLARITY_MAP[raw_value]
            return updated, None
        else:
            del updated["polarity"]
            return updated, f"unrecognized polarity value: {raw_value!r} -- dropped"
    return updated, None


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
        raise SystemExit(f"{RAW_RECORDS_PATH} not found -- run parse_iv_files.py first.")

    field_summary = defaultdict(lambda: {"total": 0, "present": 0, "blank": 0, "example_values": set()})
    total = 0
    warning_count = 0
    all_transformed = []

    with open(DB_READY_PATH, "w", encoding="utf-8") as db_out, \
         open(WARNINGS_PATH, "w", encoding="utf-8") as warn_out:

        for raw_record in read_raw_records():
            total += 1
            raw_fields = raw_record["raw_fields"]

            db_fields = apply_key_mapping(raw_fields)
            db_fields = split_name_lot_fields(raw_fields, db_fields)
            db_fields = join_list_fields(db_fields)

            update_field_summary(field_summary, db_fields)

            cleaned_fields = apply_blank_handling(db_fields)
            cleaned_fields, unparseable_dates = normalize_dates(cleaned_fields, raw_record["source_mtime"])
            cleaned_fields, numeric_warnings = coerce_numeric_fields(cleaned_fields)
            cleaned_fields, polarity_warning = normalize_polarity(cleaned_fields)

            output_record = {
                "source_path": raw_record["source_path"],
                "source_mtime": raw_record["source_mtime"],
                "fields": cleaned_fields,
            }
            db_out.write(json.dumps(output_record, default=str) + "\n")
            all_transformed.append(output_record)

            warnings = find_warnings(cleaned_fields)
            for key, raw_value, fallback_applied in unparseable_dates:
                if fallback_applied:
                    warnings.append(f"unparseable date for {key!r} ({raw_value!r}) -- fell back to file mtime")
                else:
                    warnings.append(f"unparseable date for {key!r}: {raw_value!r} -- dropped")
            warnings.extend(numeric_warnings)
            if polarity_warning:
                warnings.append(polarity_warning)
            if warnings:
                warning_count += 1
                warn_out.write(json.dumps({
                    "source_path": raw_record["source_path"],
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
    print(f"Flagged {warning_count} with warnings -> {WARNINGS_PATH}")
    print(f"DB-ready output -> {DB_READY_PATH}")
    print(f"Field value summary -> {SUMMARY_PATH}")
    print(f"Random sample ({len(sample)} records) -> {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
