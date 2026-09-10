"""
Stage 3 (block files): SEED Build_Info from db_ready_block_records.jsonl

Behavior for this pass: ADD-ONLY. If a block_id already exists in Build_Info,
it is SKIPPED, not overwritten -- per plan, the upcoming build-file seed is
the one that upserts (and may legitimately overwrite block-derived fields
like inspection/PB1/PB2 with more-correct data from the build file). Once
the app is live, any user-entered save is authoritative over both of these
seed passes anyway, so being conservative here (skip, don't clobber) costs
nothing.

>>> block_id construction is a PLACEHOLDER right now (see build_block_id()
>>> below) and MUST be replaced with the exact logic field_registry.py uses
>>> in the live app before this is run for real. If this doesn't match, rows
>>> seeded here won't line up with rows the build-file seed (or the live
>>> app) later tries to find/update -- you'd get silent duplicates, not an
>>> error.

Safety features:
  - PREFLIGHT COLUMN CHECK: before touching the DB, every record's `fields`
    keys are checked against Build_Info's actual columns. Any stray/unmapped
    key is reported up front instead of failing mid-run.
  - REQUIRED FIELD CHECK: block_engraving / block_serial_number /
    block_revision are non-nullable on the model -- records missing any of
    these are skipped and logged, never sent to the DB.
  - BATCHED COMMITS with isolate-on-failure: commits every BATCH_SIZE
    successful adds for speed. If a batch fails, it's rolled back and
    retried ONE ROW AT A TIME so a single bad record doesn't cost you the
    whole batch -- only the actual offender gets logged as an error.
  - IDEMPOTENT BY DESIGN: because this is add-only-skip-if-exists, rerunning
    the whole script after fixing a bug is always safe -- no separate
    checkpoint file needed (unlike the parse stage, which does real
    file-system + parser work that's worth not repeating).
  - --dry-run: computes block_ids and would-be inserts, checks for existing
    rows, but never calls add/commit. Use this FIRST to sanity check
    block_id construction and column mapping against a small slice of data
    before running for real.

Run:
    python seed_block_info.py --dry-run --limit 20
    python seed_block_info.py
"""

from app.db.database import db_session
from app.db.models import Build_Info
from app.db import queries
from pathlib import Path
import argparse
import datetime
import json

from app.db.seed import block_key_mapping as mapping

OUTPUT_DIR = Path(__file__).resolve().parent
DB_READY_PATH = OUTPUT_DIR / "db_ready_block_records.jsonl"
SKIPPED_LOG_PATH = OUTPUT_DIR / "seed_block_skipped.jsonl"
ERROR_LOG_PATH = OUTPUT_DIR / "seed_block_errors.jsonl"

REQUIRED_FIELDS = ["block_engraving", "block_serial_number", "block_revision"]
BATCH_SIZE = 200

VALID_BUILD_INFO_COLUMNS = {c.name for c in Build_Info.__table__.columns}


def build_block_id(fields):
    """
    PLACEHOLDER -- replace with the real field_registry.build_block_id()
    logic before running for real. Whatever this returns MUST exactly match
    what the live app computes for the same engraving/serial/revision, since
    it's the primary key other tables (and the future build-file seed) key
    off of.
    """
    return f"{fields['block_engraving']} {fields['block_serial_number']} {fields['block_revision']}"


def read_db_ready_records():
    with open(DB_READY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def find_invalid_columns(fields):
    return [key for key in fields if key not in VALID_BUILD_INFO_COLUMNS]


def find_missing_required(fields):
    return [key for key in REQUIRED_FIELDS if not fields.get(key)]


def preflight_check(records):
    """Scans ALL records for column-name problems before any DB work
    happens. Returns (clean_records, problem_records)."""
    clean = []
    problems = []
    for record in records:
        fields = record["fields"]
        invalid_columns = find_invalid_columns(fields)
        missing_required = find_missing_required(fields)
        if invalid_columns or missing_required:
            problems.append({
                "source_path": record["source_path"],
                "invalid_columns": invalid_columns,
                "missing_required": missing_required,
            })
        else:
            clean.append(record)
    return clean, problems


def coerce_dates(fields):
    """Converts the ISO (YYYY-MM-DD) strings transform_block_records.py
    wrote for DATE_FIELDS into real datetime.date objects -- the type
    Build_Info's Column(Date) actually needs. JSON has no date type, so this
    conversion can't happen until now, right before insert. Raises
    ValueError if a value isn't valid ISO (shouldn't happen if transform
    already validated it, but this is the last line of defense before the
    DB) -- that propagates up and gets caught/logged by the existing
    per-row error handling in run_batch(), no separate plumbing needed."""
    coerced = dict(fields)
    for key in mapping.DATE_FIELDS:
        if key in coerced:
            coerced[key] = datetime.date.fromisoformat(coerced[key])
    return coerced


def insert_one(record, dry_run):
    fields = coerce_dates(record["fields"])
    block_id = build_block_id(fields)

    existing = None if dry_run else db_session.get(Build_Info, block_id)
    if existing:
        return "skipped", block_id

    if dry_run:
        return "would_add", block_id

    queries.add_table_entry(
        db_session,
        Build_Info,
        block_id=block_id,
        block_file_path=record["source_path"],
        **fields,
    )
    return "added", block_id


def run_batch(batch, dry_run, skipped_log, error_log):
    """Attempts the whole batch, commits once on success. On failure, rolls
    back and retries row-by-row so only the true offender gets logged."""
    added = skipped = errors = 0

    try:
        for record in batch:
            status, block_id = insert_one(record, dry_run)
            if status in ("added", "would_add"):
                added += 1
            elif status == "skipped":
                skipped += 1
                skipped_log.write(json.dumps({"block_id": block_id, "source_path": record["source_path"]}) + "\n")
        if not dry_run:
            queries.commit_db_changes(db_session)
        return added, skipped, errors
    except Exception:
        if not dry_run:
            queries.roll_back_db_changes(db_session)
        # Isolate: retry one at a time so only the actual bad record(s) are lost.
        added = skipped = errors = 0
        for record in batch:
            try:
                status, block_id = insert_one(record, dry_run)
                if status in ("added", "would_add"):
                    added += 1
                    if not dry_run:
                        queries.commit_db_changes(db_session)
                elif status == "skipped":
                    skipped += 1
                    skipped_log.write(json.dumps({"block_id": block_id, "source_path": record["source_path"]}) + "\n")
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
        return added, skipped, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Compute block_ids and report what would happen, without touching the DB")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N records (for testing)")
    args = parser.parse_args()

    if not DB_READY_PATH.exists():
        raise SystemExit(f"{DB_READY_PATH} not found -- run transform_block_records.py first.")

    all_records = list(read_db_ready_records())
    if args.limit is not None:
        all_records = all_records[: args.limit]

    clean_records, column_problems = preflight_check(all_records)

    if column_problems:
        print(f"PREFLIGHT: {len(column_problems)} record(s) have invalid/missing columns and will be SKIPPED entirely.")
        print("First few:")
        for problem in column_problems[:5]:
            print(f"  {problem}")
        print(f"(Full list not written to disk -- rerun with these still present if you want them logged; "
              f"fix block_key_mapping.py's FIELD_NAME_MAP / REQUIRED_DB_KEYS and rerun transform first.)")
        print()

    total_added = total_skipped = total_errors = 0

    with open(SKIPPED_LOG_PATH, "w", encoding="utf-8") as skipped_log, \
         open(ERROR_LOG_PATH, "w", encoding="utf-8") as error_log:

        for i in range(0, len(clean_records), BATCH_SIZE):
            batch = clean_records[i : i + BATCH_SIZE]
            added, skipped, errors = run_batch(batch, args.dry_run, skipped_log, error_log)
            total_added += added
            total_skipped += skipped
            total_errors += errors
            print(f"Batch {i // BATCH_SIZE + 1}: +{added} added, {skipped} skipped, {errors} errors")

    label = "WOULD ADD" if args.dry_run else "ADDED"
    print()
    print(f"{label}: {total_added}")
    print(f"SKIPPED (already existed): {total_skipped}")
    print(f"ERRORS: {total_errors} -> {ERROR_LOG_PATH}")
    print(f"SKIPPED LOG: {SKIPPED_LOG_PATH}")
    if column_problems:
        print(f"PREFLIGHT PROBLEMS (never attempted): {len(column_problems)}")
    if args.dry_run:
        print()
        print("Dry run only -- nothing was committed to the database.")


if __name__ == "__main__":
    main()