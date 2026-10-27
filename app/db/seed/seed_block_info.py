"""
Stage 3 (block files): SEED Build_Info from db_ready_block_records.jsonl

STUB ROWS: seed_iv_info.py creates a placeholder Build_Info row when an IV
file shows up for a block/build with no info yet (uprevs). A stub is
from_file=True with no block_file_path and no build_file_path
(seed_shared.is_stub_row). When the real block record arrives, a stub is
FILLED IN (status "filled_stub") instead of skipped. Every other existing
row is still skipped as before.

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
from sqlalchemy import select
import argparse
import datetime
import json
from collections import Counter

from app.db.seed import block_key_mapping as mapping
from app.db.seed import seed_shared

OUTPUT_DIR = Path("W:/Python3/IV and Labels/database/seed")
DB_READY_PATH = OUTPUT_DIR / "db_ready_block_records.jsonl"
SKIPPED_LOG_PATH = OUTPUT_DIR / "seed_block_skipped.jsonl"
ERROR_LOG_PATH = OUTPUT_DIR / "seed_block_errors.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "seed_block_checkpoint.jsonl"

REQUIRED_FIELDS = ["block_engraving", "block_serial_number", "block_revision"]
BATCH_SIZE = 200

VALID_BUILD_INFO_COLUMNS = seed_shared.valid_columns(Build_Info)


def build_block_id(fields):
    """Delegates to seed_shared -- see that module for why this can't be a
    local copy. PLACEHOLDER until the real field_registry.build_block_id()
    logic replaces seed_shared.build_block_id()."""
    return seed_shared.build_block_id(fields)


def load_checkpoint():
    """(path, mtime)-keyed, same reasoning as seed_iv_info.py."""
    done = {}
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    done[entry["source_path"]] = entry["source_mtime"]
    return done


def already_seeded(checkpoint_done, source_path, source_mtime):
    prior_mtime = checkpoint_done.get(source_path)
    return prior_mtime is not None and prior_mtime == source_mtime


def append_checkpoint(checkpoint_file, source_path, source_mtime):
    checkpoint_file.write(json.dumps({"source_path": source_path, "source_mtime": source_mtime}) + "\n")
    checkpoint_file.flush()


def bulk_prefetch(batch):
    """ONE query covering the WHOLE batch. Returns
    {block_id: (from_file, block_file_path, build_file_path)} -- enough to
    tell "exists" from "exists but is only an IV-created stub"."""
    block_ids = [build_block_id(r["fields"]) for r in batch]
    existing = {}
    if block_ids:
        rows = db_session.execute(
            select(Build_Info.block_id, Build_Info.from_file, Build_Info.block_file_path, Build_Info.build_file_path)
            .where(Build_Info.block_id.in_(block_ids))
        ).all()
        existing = {row[0]: (row[1], row[2], row[3]) for row in rows}
    return existing


def read_db_ready_records():
    with open(DB_READY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def preflight_check(records):
    """Scans ALL records for column-name problems before any DB work
    happens. Returns (clean_records, problem_records)."""
    clean = []
    problems = []
    for record in records:
        fields = record["fields"]
        invalid_columns = seed_shared.find_invalid_columns(fields, VALID_BUILD_INFO_COLUMNS)
        missing_required = seed_shared.find_missing_required(fields, REQUIRED_FIELDS)
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


def insert_one(record, dry_run, existing_rows):
    """Returns ("added" | "filled_stub" | "skipped", block_id). Dry run
    reports the same statuses but writes nothing."""
    fields = coerce_dates(record["fields"])
    block_id = build_block_id(fields)
    last_save_date = seed_shared.compute_last_save_date(fields, record.get("source_mtime"))

    existing = existing_rows.get(block_id)
    if existing is not None:
        if not seed_shared.is_stub_row(*existing):
            return "skipped", block_id
        if not dry_run:
            queries.update_table_entry(
                db_session, Build_Info, block_id,
                block_file_path=record["source_path"],
                from_file=True,
                last_save_date=last_save_date,
                **fields,
            )
        return "filled_stub", block_id

    if not dry_run:
        queries.add_table_entry(
            db_session,
            Build_Info,
            block_id=block_id,
            block_file_path=record["source_path"],
            from_file=True,
            last_save_date=last_save_date,
            **fields,
        )
    return "added", block_id


def run_batch(batch, dry_run, skipped_log, error_log, checkpoint_file):
    """Attempts the whole batch, commits once on success. On failure, rolls
    back and retries row-by-row so only the true offender gets logged.
    Returns a Counter of statuses (+ "error")."""
    counts = Counter()
    existing_rows = bulk_prefetch(batch)  # read-only, so safe in dry run too

    def finish(record, status, block_id):
        if status == "skipped":
            skipped_log.write(json.dumps({"block_id": block_id, "source_path": record["source_path"]}) + "\n")
        append_checkpoint(checkpoint_file, record["source_path"], record["source_mtime"])

    try:
        results = []
        for record in batch:
            status, block_id = insert_one(record, dry_run, existing_rows)
            results.append((record, status, block_id))
            counts[status] += 1
        if not dry_run:
            queries.commit_db_changes(db_session)
            for record, status, block_id in results:
                finish(record, status, block_id)
        return counts
    except Exception:
        if not dry_run:
            queries.roll_back_db_changes(db_session)
        counts = Counter()
        for record in batch:
            try:
                status, block_id = insert_one(record, dry_run, existing_rows)
                if not dry_run:
                    queries.commit_db_changes(db_session)
                    finish(record, status, block_id)
                counts[status] += 1
            except Exception as row_error:
                if not dry_run:
                    queries.roll_back_db_changes(db_session)
                counts["error"] += 1
                error_log.write(json.dumps({
                    "source_path": record["source_path"],
                    "error": str(row_error),
                    "error_type": type(row_error).__name__,
                    "fields": record["fields"],
                }, default=str) + "\n")
        return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Compute block_ids and report what would happen, without touching the DB")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N records (for testing)")
    parser.add_argument("--force", action="store_true", help="Ignore checkpoint, reprocess everything")
    args = parser.parse_args()

    if not DB_READY_PATH.exists():
        raise SystemExit(f"{DB_READY_PATH} not found -- run transform_block_records.py first.")

    checkpoint_done = set() if args.force else load_checkpoint()
    if args.force and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    all_records = list(read_db_ready_records())

    if checkpoint_done:
        before_count = len(all_records)
        all_records = [
            r for r in all_records
            if not already_seeded(checkpoint_done, r["source_path"], r["source_mtime"])
        ]
        print(f"Skipping {before_count - len(all_records)} record(s) already seeded per checkpoint.")

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

    totals = Counter()

    with open(SKIPPED_LOG_PATH, "w", encoding="utf-8") as skipped_log, \
         open(ERROR_LOG_PATH, "w", encoding="utf-8") as error_log, \
         open(CHECKPOINT_PATH, "a", encoding="utf-8") as checkpoint_file:

        for i in range(0, len(clean_records), BATCH_SIZE):
            batch = clean_records[i : i + BATCH_SIZE]
            counts = run_batch(batch, args.dry_run, skipped_log, error_log, checkpoint_file)
            totals.update(counts)
            print(f"Batch {i // BATCH_SIZE + 1}: +{counts['added']} added, {counts['filled_stub']} stubs filled, "
                  f"{counts['skipped']} skipped, {counts['error']} errors")

    prefix = "WOULD BE " if args.dry_run else ""
    print()
    print(f"{prefix}ADDED: {totals['added']}")
    print(f"{prefix}STUBS FILLED (placeholder from an IV seed, now has real block data): {totals['filled_stub']}")
    print(f"SKIPPED (already existed): {totals['skipped']}")
    print(f"ERRORS: {totals['error']} -> {ERROR_LOG_PATH}")
    print(f"SKIPPED LOG: {SKIPPED_LOG_PATH}")
    if column_problems:
        print(f"PREFLIGHT PROBLEMS (never attempted): {len(column_problems)}")
    if args.dry_run:
        print()
        print("Dry run only -- nothing was committed to the database.")


if __name__ == "__main__":
    main()