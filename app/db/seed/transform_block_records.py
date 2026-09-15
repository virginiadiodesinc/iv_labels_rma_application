"""
Stage 2 of 2: TRANSFORM

Reads raw_block_records.jsonl (produced by parse_block_files.py) and, driven
by block_key_mapping.py, produces:

  - db_ready_block_records.jsonl : one record per line, ready for a DB seed
    script to upsert. Each record keeps `source_path` / `source_mtime` so the
    load step (and any future debugging) can always trace a DB row back to
    its origin file.

  - block_transform_warnings.jsonl : records that passed parsing without
    error but look suspicious for the DB (missing required fields, all
    values blank, etc). "No parse error" does not mean "correct data" --
    this file is where you go to spot-check that.

  - block_field_value_summary.json : per-field stats (how often each field
    is blank/present, distinct-value counts) across ALL records, so you can
    eyeball data quality without reading 25,000 lines.

  - block_sample.jsonl : a random sample of N transformed records, small
    enough to actually read.

This stage is intentionally cheap to rerun: it does no file-system parsing
of block files, no network/DB calls. If you change block_key_mapping.py,
just rerun this script -- no need to touch parse_block_files.py or your K:
drive at all.

Run:
    python transform_block_records.py
    python transform_block_records.py --sample-size 50
"""

from collections import defaultdict
from pathlib import Path
import argparse
import datetime
import json
import random
import re

from app.db.seed import block_key_mapping as mapping

OUTPUT_DIR = Path(__file__).resolve().parent
RAW_RECORDS_PATH = OUTPUT_DIR / "raw_block_records.jsonl"
DB_READY_PATH = OUTPUT_DIR / "db_ready_block_records.jsonl"
WARNINGS_PATH = OUTPUT_DIR / "block_transform_warnings.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "block_field_value_summary.json"
SAMPLE_PATH = OUTPUT_DIR / "block_sample.jsonl"


def read_raw_records():
    with open(RAW_RECORDS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def apply_key_mapping(raw_fields):
    """Renames keys per FIELD_NAME_MAP; drops unmapped keys unless configured
    to pass them through."""
    transformed = {}
    for raw_key, value in raw_fields.items():
        if raw_key in mapping.FIELD_NAME_MAP:
            transformed[mapping.FIELD_NAME_MAP[raw_key]] = value
        elif not mapping.DROP_UNMAPPED_KEYS:
            transformed[raw_key] = value
    return transformed


def apply_blank_handling(db_fields):
    """Drops blank-valued keys, except keys listed in BLANK_DEFAULTS, which
    get their configured default value instead of being dropped (e.g. a
    blank revision becomes "A" rather than vanishing)."""
    cleaned = {}
    for key, value in db_fields.items():
        if mapping.is_blank(value):
            if key in mapping.BLANK_DEFAULTS:
                cleaned[key] = mapping.BLANK_DEFAULTS[key]
            # else: drop -- blank and no default configured
        else:
            cleaned[key] = value
    return cleaned


def parse_date_string(raw_value):
    """Tries each configured format in order, after stripping ALL
    whitespace (not just leading/trailing) -- matches
    labview_date_to_iso()'s re.sub(r"\\s+", "", ...) behavior exactly.
    Returns a datetime.date, or None if nothing matched."""
    text = re.sub(r"\s+", "", str(raw_value))
    for fmt in mapping.DATE_INPUT_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_dates(fields, source_mtime):
    """For every key in DATE_FIELDS present in `fields`, parses the raw
    value and replaces it with a canonical ISO (YYYY-MM-DD) string.

    Fields that fail to parse are handled per mapping.DATE_PARSE_FALLBACK:
      - "warn_and_drop": field is removed from the output.
      - "file_mtime": field is set to source_mtime's date, matching the
        live app's fallback behavior.
    Either way, the failure is reported back to the caller so it shows up
    in block_transform_warnings.jsonl -- "file_mtime" fallback is still
    visible, just not dropped.

    Returns (normalized_fields, unparseable_list) where unparseable_list is
    a list of (key, raw_value, fallback_applied: bool) tuples.
    """
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
    """Returns a list of human-readable warning strings for a record, or an
    empty list if it looks clean. Extend this as you learn what "bad but no
    exception" looks like for your data."""
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
        raise SystemExit(f"{RAW_RECORDS_PATH} not found -- run parse_block_files.py first.")

    field_summary = defaultdict(lambda: {"total": 0, "present": 0, "blank": 0, "example_values": set()})
    total = 0
    warning_count = 0
    all_transformed = []

    with open(DB_READY_PATH, "w", encoding="utf-8") as db_out, \
         open(WARNINGS_PATH, "w", encoding="utf-8") as warn_out:

        for raw_record in read_raw_records():
            total += 1
            db_fields = apply_key_mapping(raw_record["raw_fields"])

            # Tally blank/present stats BEFORE dropping blanks, so the
            # summary still reflects true blank rates even though blank
            # fields (other than BLANK_DEFAULTS) won't appear in the
            # cleaned output below.
            update_field_summary(field_summary, db_fields)

            cleaned_fields = apply_blank_handling(db_fields)
            cleaned_fields, unparseable_dates = normalize_dates(cleaned_fields, raw_record["source_mtime"])

            output_record = {
                "source_path": raw_record["source_path"],
                "source_mtime": raw_record["source_mtime"],
                "fields": cleaned_fields,
            }
            db_out.write(json.dumps(output_record, default=str) + "\n")
            all_transformed.append(output_record)

            # Warnings are checked against the CLEANED fields, since that's
            # what actually ends up in the DB-ready output -- a required
            # field that got dropped for being blank should still surface
            # here as "missing".
            warnings = find_warnings(cleaned_fields)
            for key, raw_value, fallback_applied in unparseable_dates:
                if fallback_applied:
                    warnings.append(f"unparseable date for {key!r} ({raw_value!r}) -- fell back to file mtime")
                else:
                    warnings.append(f"unparseable date for {key!r}: {raw_value!r} -- dropped")
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