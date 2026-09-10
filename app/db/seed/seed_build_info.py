"""
Stage 3 (build files): SEED Build_Info / Build_Parts / Notes from
db_ready_build_records.jsonl

Behavior for this pass: UPSERT Build_Info (unusual, but possible, for a
build file to exist with no prior block-file row -- handled the same as any
other upsert: created fresh). Build_Parts and Notes are REPLACED WHOLESALE
per block_id (delete existing, insert fresh) -- same pattern as
db_service.stage_replace_build_parts_and_notes, since their real identity
is "all rows for this block_id," not any single row.

IMPORTANT: only build_file_path is ever passed in the Build_Info kwargs --
block_file_path is never touched here, so an existing block-seeded value is
never overwritten by this pass. (And vice versa: seed_block_info.py never
passes build_file_path.)

>>> block_id construction is shared with seed_block_info.py via
>>> seed_shared.py -- see that module. Still a PLACEHOLDER pending the real
>>> field_registry.build_block_id() logic.

Run:
    python seed_build_info.py --dry-run --limit 20
    python seed_build_info.py
"""

from app.db.database import db_session
from app.db.models import Build_Info, Build_Parts, Notes, Note_Type
from app.db import queries
from pathlib import Path
import argparse
import datetime
import json

from app.db.seed import build_key_mapping as mapping
from app.db.seed import seed_shared

OUTPUT_DIR = Path(__file__).resolve().parent
DB_READY_PATH = OUTPUT_DIR / "db_ready_build_records.jsonl"
SKIPPED_LOG_PATH = OUTPUT_DIR / "seed_build_skipped.jsonl"
ERROR_LOG_PATH = OUTPUT_DIR / "seed_build_errors.jsonl"

REQUIRED_FIELDS = ["block_engraving", "block_serial_number", "block_revision"]
BATCH_SIZE = 100  # smaller than block's 200 -- each build record does more work (info + parts + notes)

VALID_BUILD_INFO_COLUMNS = seed_shared.valid_columns(Build_Info)
VALID_BUILD_PARTS_COLUMNS = seed_shared.valid_columns(Build_Parts)
VALID_NOTES_COLUMNS = seed_shared.valid_columns(Notes)


def build_block_id(fields):
    return seed_shared.build_block_id(fields)


def read_db_ready_records():
    with open(DB_READY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def preflight_check(records):
    """Checks Build_Info fields, AND every part/note dict's keys, against
    their actual model columns. Returns (clean_records, problem_records)."""
    clean = []
    problems = []
    for record in records:
        fields = record["fields"]
        problems_for_record = []

        invalid_info_columns = seed_shared.find_invalid_columns(fields, VALID_BUILD_INFO_COLUMNS)
        missing_required = seed_shared.find_missing_required(fields, REQUIRED_FIELDS)
        if invalid_info_columns:
            problems_for_record.append(f"invalid Build_Info columns: {invalid_info_columns}")
        if missing_required:
            problems_for_record.append(f"missing required Build_Info fields: {missing_required}")

        for i, part in enumerate(record.get("parts", [])):
            invalid = seed_shared.find_invalid_columns(part, VALID_BUILD_PARTS_COLUMNS)
            if invalid:
                problems_for_record.append(f"parts[{i}] invalid columns: {invalid}")

        for i, note in enumerate(record.get("notes", [])):
            invalid = seed_shared.find_invalid_columns(note, VALID_NOTES_COLUMNS)
            if invalid:
                problems_for_record.append(f"notes[{i}] invalid columns: {invalid}")

        if problems_for_record:
            problems.append({"source_path": record["source_path"], "problems": problems_for_record})
        else:
            clean.append(record)
    return clean, problems


def coerce_dates(fields):
    coerced = dict(fields)
    for key in mapping.DATE_FIELDS:
        if key in coerced:
            coerced[key] = datetime.date.fromisoformat(coerced[key])
    return coerced


def coerce_note(note):
    """Converts the "generic" value-string transform wrote back into the
    real Note_Type enum -- JSON can't hold an enum, same pattern as dates."""
    coerced = dict(note)
    coerced["type"] = Note_Type(coerced["type"])
    return coerced


def replace_parts_and_notes(block_id, parts, notes):
    """Delete-then-reinsert, matching
    db_service.stage_replace_build_parts_and_notes exactly, just without
    needing a `canonical` dict / field_registry -- block_id is already
    known here."""
    existing_parts = queries.get_table_entries(db_session, Build_Parts, block_id=block_id)
    for entry in existing_parts:
        queries.delete_table_entry(db_session, Build_Parts, entry.instance_id)

    existing_notes = queries.get_table_entries(db_session, Notes, block_id=block_id)
    for entry in existing_notes:
        queries.delete_table_entry(db_session, Notes, entry.note_id)

    for part in parts:
        queries.add_table_entry(db_session, Build_Parts, block_id=block_id, **part)
    for note in notes:
        queries.add_table_entry(db_session, Notes, block_id=block_id, **coerce_note(note))


def process_one_record(record, dry_run):
    """Upserts Build_Info, then replaces its Build_Parts/Notes wholesale.
    Returns ("added" | "updated" | "would_upsert", block_id)."""
    fields = coerce_dates(record["fields"])
    block_id = build_block_id(fields)

    if dry_run:
        return "would_upsert", block_id

    existed_before = db_session.get(Build_Info, block_id) is not None

    kwargs = dict(fields)
    kwargs["block_id"] = block_id
    kwargs["build_file_path"] = record["source_path"]  # NEVER block_file_path -- see module docstring
    queries.upsert_table_entry(db_session, Build_Info, block_id, **kwargs)

    replace_parts_and_notes(block_id, record.get("parts", []), record.get("notes", []))

    return ("updated" if existed_before else "added"), block_id


def run_batch(batch, dry_run, error_log):
    added = updated = errors = 0

    try:
        for record in batch:
            status, block_id = process_one_record(record, dry_run)
            if status == "added":
                added += 1
            elif status == "updated":
                updated += 1
            elif status == "would_upsert":
                added += 1  # dry-run: lumped together, doesn't distinguish add/update
        if not dry_run:
            queries.commit_db_changes(db_session)
        return added, updated, errors
    except Exception:
        if not dry_run:
            queries.roll_back_db_changes(db_session)
        added = updated = errors = 0
        for record in batch:
            try:
                status, block_id = process_one_record(record, dry_run)
                if status == "added":
                    added += 1
                elif status == "updated":
                    updated += 1
                elif status == "would_upsert":
                    added += 1
                if not dry_run:
                    queries.commit_db_changes(db_session)
            except Exception as row_error:
                if not dry_run:
                    queries.roll_back_db_changes(db_session)
                errors += 1
                error_log.write(json.dumps({
                    "source_path": record["source_path"],
                    "error": str(row_error),
                    "error_type": type(row_error).__name__,
                    "fields": record["fields"],
                }, default=str) + "\n")
        return added, updated, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not DB_READY_PATH.exists():
        raise SystemExit(f"{DB_READY_PATH} not found -- run transform_build_records.py first.")

    all_records = list(read_db_ready_records())
    if args.limit is not None:
        all_records = all_records[: args.limit]

    clean_records, problems = preflight_check(all_records)

    if problems:
        print(f"PREFLIGHT: {len(problems)} record(s) have column problems and will be SKIPPED entirely.")
        for p in problems[:5]:
            print(f"  {p}")
        print()

    total_added = total_updated = total_errors = 0

    with open(ERROR_LOG_PATH, "w", encoding="utf-8") as error_log:
        for i in range(0, len(clean_records), BATCH_SIZE):
            batch = clean_records[i : i + BATCH_SIZE]
            added, updated, errors = run_batch(batch, args.dry_run, error_log)
            total_added += added
            total_updated += updated
            total_errors += errors
            print(f"Batch {i // BATCH_SIZE + 1}: +{added} added, {updated} updated, {errors} errors")

    label = "WOULD ADD" if args.dry_run else "ADDED"
    print()
    print(f"{label}: {total_added}")
    print(f"UPDATED (pre-existing block_id): {total_updated}")
    print(f"ERRORS: {total_errors} -> {ERROR_LOG_PATH}")
    if problems:
        print(f"PREFLIGHT PROBLEMS (never attempted): {len(problems)}")
    if args.dry_run:
        print()
        print("Dry run only -- nothing was committed to the database.")


if __name__ == "__main__":
    main()
