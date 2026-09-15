"""
Stage 3 (IV files): SEED IV_Info from db_ready_iv_records.jsonl

UPSERT IDENTITY: keyed by iv_file_path, NOT build_id -- IV_Info's real
primary key is the autoincrement iv_id, and build_id is just an FK column
on the row, not a usable upsert key. queries.upsert_table_entry() looks up
by primary key, so calling it with build_id would never find an existing
row and would always insert a duplicate. Instead this mirrors
db_service.stage_upsert_iv_info exactly: look up by iv_file_path, update by
the discovered iv_id if found, otherwise insert fresh. ("Same path" is
already the app's identity rule for an IV file.)

IDENTITY FIELDS (block_engraving / block_serial_number / block_revision)
are NOT columns on IV_Info -- they only exist in db_ready_iv_records.jsonl
so build_id can be computed here (via the same seed_shared.build_block_id
used for block/build seeding). They're stripped out of the kwargs before
anything gets passed to IV_Info(**data), or the ORM would raise on an
unexpected keyword argument.

BUILD_INFO EXISTENCE: build_id is a foreign key, but a missing target
isn't treated as fatal here -- the IV measurement still has value even if
its Build_Info row hasn't been seeded yet (or never will be, for old/bad
block data). A missing match is logged to seed_iv_missing_build_info.jsonl
as a soft warning; the insert is still attempted. If the DB actually
enforces the FK constraint, a genuinely broken reference will still raise
and get caught by the normal per-row error handling below -- this warning
log exists for the case where enforcement is off (common for SQLite) and
the mismatch would otherwise be invisible.

Run:
    python seed_iv_info.py --dry-run --limit 20
    python seed_iv_info.py
"""

from app.db.database import db_session
from app.db.models import IV_Info, Build_Info, Polarity
from app.db import queries
from pathlib import Path
from sqlalchemy import select
import argparse
import datetime
import json

from app.db.seed import iv_key_mapping as mapping
from app.db.seed import seed_shared

OUTPUT_DIR = Path("W:/Python3/IV and Labels/database/seed")
DB_READY_PATH = OUTPUT_DIR / "db_ready_iv_records.jsonl"
ERROR_LOG_PATH = OUTPUT_DIR / "seed_iv_errors.jsonl"
MISSING_BUILD_INFO_LOG_PATH = OUTPUT_DIR / "seed_iv_missing_build_info.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "seed_iv_checkpoint.jsonl"

IDENTITY_KEYS = ["block_engraving", "block_serial_number", "block_revision"]
IV_REQUIRED_FIELDS = [k for k in mapping.REQUIRED_DB_KEYS if k not in IDENTITY_KEYS]

BATCH_SIZE = 200

VALID_IV_INFO_COLUMNS = seed_shared.valid_columns(IV_Info)


def bulk_prefetch(batch):
    """ONE query for existing IV_Info rows (by iv_file_path) and ONE for
    Build_Info existence (by block_id), covering the WHOLE batch -- this
    replaces up to 2 round-trip queries PER RECORD with 2 queries per
    BATCH. At BATCH_SIZE=200 that's a ~400x reduction in round trips.

    Returns (existing_iv_by_path: dict[str, int], existing_build_ids: set[str]).
    """
    paths = [record["source_path"] for record in batch]
    block_ids = []
    for record in batch:
        identity, _ = extract_identity_and_iv_fields(record["fields"])
        if all(k in identity for k in IDENTITY_KEYS):
            block_ids.append(seed_shared.build_block_id(identity))

    existing_iv_by_path = {}
    if paths:
        rows = db_session.execute(
            select(IV_Info.iv_file_path, IV_Info.iv_id).where(IV_Info.iv_file_path.in_(paths))
        ).all()
        existing_iv_by_path = {row[0]: row[1] for row in rows}

    existing_build_ids = set()
    if block_ids:
        rows = db_session.execute(
            select(Build_Info.block_id).where(Build_Info.block_id.in_(block_ids))
        ).all()
        existing_build_ids = {row[0] for row in rows}

    return existing_iv_by_path, existing_build_ids


def read_db_ready_records():
    with open(DB_READY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def extract_identity_and_iv_fields(fields):
    """Splits the transformed fields dict into (identity, iv_fields).
    identity is used ONLY to compute build_id -- it's never passed to
    IV_Info(**data), since those three keys aren't IV_Info columns."""
    identity = {k: fields[k] for k in IDENTITY_KEYS if k in fields}
    iv_fields = {k: v for k, v in fields.items() if k not in IDENTITY_KEYS}
    return identity, iv_fields


def load_checkpoint():
    """Returns the set of source_paths already successfully seeded in a
    PRIOR run of this script. Only entries written after a successful
    commit end up here -- see append_checkpoint's call sites."""
    done = set()
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(json.loads(line)["source_path"])
    return done


def append_checkpoint(checkpoint_file, source_path):
    checkpoint_file.write(json.dumps({"source_path": source_path}) + "\n")
    checkpoint_file.flush()


def preflight_check(records):
    """Checks identity completeness, required-field completeness, and
    column validity -- all BEFORE any DB work. Returns (clean, problems)."""
    clean = []
    problems = []
    for record in records:
        identity, iv_fields = extract_identity_and_iv_fields(record["fields"])
        problems_for_record = []

        missing_identity = seed_shared.find_missing_required(identity, IDENTITY_KEYS)
        if missing_identity:
            problems_for_record.append(f"missing identity fields (can't compute build_id): {missing_identity}")

        missing_required = seed_shared.find_missing_required(iv_fields, IV_REQUIRED_FIELDS)
        if missing_required:
            problems_for_record.append(f"missing required IV_Info fields: {missing_required}")

        invalid_columns = seed_shared.find_invalid_columns(iv_fields, VALID_IV_INFO_COLUMNS)
        if invalid_columns:
            problems_for_record.append(f"invalid IV_Info columns: {invalid_columns}")

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


def coerce_polarity(fields):
    """Converts the "positive"/"negative" value-string transform wrote
    back into the real Polarity enum, same pattern as Note_Type on the
    build side."""
    coerced = dict(fields)
    if "polarity" in coerced:
        coerced["polarity"] = Polarity(coerced["polarity"])
    return coerced


def process_one_record(record, dry_run, missing_build_info_log, existing_iv_by_path, existing_build_ids):
    fields = coerce_dates(record["fields"])
    fields = coerce_polarity(fields)
    identity, iv_fields = extract_identity_and_iv_fields(fields)

    block_id = seed_shared.build_block_id(identity)
    iv_file_path = record["source_path"]

    if dry_run:
        return "would_upsert", block_id

    if block_id not in existing_build_ids:
        missing_build_info_log.write(json.dumps({
            "source_path": iv_file_path,
            "block_id": block_id,
        }) + "\n")

    iv_fields["build_id"] = block_id
    iv_fields["iv_file_path"] = iv_file_path

    existing_iv_id = existing_iv_by_path.get(iv_file_path)
    if existing_iv_id is not None:
        queries.update_table_entry(db_session, IV_Info, existing_iv_id, **iv_fields)
        return "updated", block_id
    else:
        queries.add_table_entry(db_session, IV_Info, **iv_fields)
        return "added", block_id


def run_batch(batch, dry_run, error_log, missing_build_info_log, checkpoint_file):
    added = updated = errors = 0
    existing_iv_by_path, existing_build_ids = ({}, set()) if dry_run else bulk_prefetch(batch)
    # NOTE: prefetched once, at batch start -- if the same iv_file_path
    # somehow appears twice within one batch, the second occurrence won't
    # see the first's insert as "existing" until the NEXT batch. Fine in
    # practice (iv_file_path is per-source-file, so duplicates within a
    # batch shouldn't occur), just not airtight in that edge case.

    try:
        for record in batch:
            status, block_id = process_one_record(
                record, dry_run, missing_build_info_log, existing_iv_by_path, existing_build_ids
            )
            if status in ("added", "would_upsert"):
                added += 1
            elif status == "updated":
                updated += 1
        if not dry_run:
            queries.commit_db_changes(db_session)
            for record in batch:
                append_checkpoint(checkpoint_file, record["source_path"])
        return added, updated, errors
    except Exception:
        if not dry_run:
            queries.roll_back_db_changes(db_session)
        added = updated = errors = 0
        for record in batch:
            try:
                status, block_id = process_one_record(
                    record, dry_run, missing_build_info_log, existing_iv_by_path, existing_build_ids
                )
                if status in ("added", "would_upsert"):
                    added += 1
                elif status == "updated":
                    updated += 1
                if not dry_run:
                    queries.commit_db_changes(db_session)
                    append_checkpoint(checkpoint_file, record["source_path"])
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
    parser.add_argument("--force", action="store_true", help="Ignore checkpoint, reprocess everything")
    args = parser.parse_args()

    if not DB_READY_PATH.exists():
        raise SystemExit(f"{DB_READY_PATH} not found -- run transform_iv_records.py first.")

    checkpoint_done = set() if args.force else load_checkpoint()
    if args.force and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    all_records = list(read_db_ready_records())

    if checkpoint_done:
        before_count = len(all_records)
        all_records = [r for r in all_records if r["source_path"] not in checkpoint_done]
        print(f"Skipping {before_count - len(all_records)} record(s) already seeded per checkpoint.")

    if args.limit is not None:
        all_records = all_records[: args.limit]

    clean_records, problems = preflight_check(all_records)

    if problems:
        print(f"PREFLIGHT: {len(problems)} record(s) have problems and will be SKIPPED entirely.")
        for p in problems[:5]:
            print(f"  {p}")
        print()

    total_added = total_updated = total_errors = 0

    with open(ERROR_LOG_PATH, "w", encoding="utf-8") as error_log, \
         open(MISSING_BUILD_INFO_LOG_PATH, "w", encoding="utf-8") as missing_build_info_log, \
         open(CHECKPOINT_PATH, "a", encoding="utf-8") as checkpoint_file:

        for i in range(0, len(clean_records), BATCH_SIZE):
            batch = clean_records[i : i + BATCH_SIZE]
            added, updated, errors = run_batch(batch, args.dry_run, error_log, missing_build_info_log, checkpoint_file)
            total_added += added
            total_updated += updated
            total_errors += errors
            print(f"Batch {i // BATCH_SIZE + 1}: +{added} added, {updated} updated, {errors} errors")

    label = "WOULD ADD" if args.dry_run else "ADDED"
    print()
    print(f"{label}: {total_added}")
    print(f"UPDATED (pre-existing iv_file_path): {total_updated}")
    print(f"ERRORS: {total_errors} -> {ERROR_LOG_PATH}")
    print(f"MISSING BUILD_INFO (inserted anyway, FK target not found): see {MISSING_BUILD_INFO_LOG_PATH}")
    if problems:
        print(f"PREFLIGHT PROBLEMS (never attempted): {len(problems)}")
    if args.dry_run:
        print()
        print("Dry run only -- nothing was committed to the database.")


if __name__ == "__main__":
    main()