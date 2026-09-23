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

PROTECTION: an existing Build_Info row with from_file != True was last
saved through the app, so it is NOT overwritten -- and neither are its
Build_Parts/Notes (one build = one unit). Those records are written to
seed_build_protected.jsonl for review and deliberately never checkpointed.

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
from collections import defaultdict
from sqlalchemy import select
import argparse
import datetime
import json

from app.db.seed import build_key_mapping as mapping
from app.db.seed import seed_shared

OUTPUT_DIR = Path("W:/Python3/IV and Labels/database/seed")
DB_READY_PATH = OUTPUT_DIR / "db_ready_build_records.jsonl"
SKIPPED_LOG_PATH = OUTPUT_DIR / "seed_build_skipped.jsonl"
ERROR_LOG_PATH = OUTPUT_DIR / "seed_build_errors.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "seed_build_checkpoint.jsonl"
PROTECTED_PATH = OUTPUT_DIR / "seed_build_protected.jsonl"

REQUIRED_FIELDS = ["block_engraving", "block_serial_number", "block_revision"]
BATCH_SIZE = 100  # smaller than block's 200 -- each build record does more work (info + parts + notes)

VALID_BUILD_INFO_COLUMNS = seed_shared.valid_columns(Build_Info)
VALID_BUILD_PARTS_COLUMNS = seed_shared.valid_columns(Build_Parts)
VALID_NOTES_COLUMNS = seed_shared.valid_columns(Notes)


def build_block_id(fields):
    return seed_shared.build_block_id(fields)


def load_checkpoint():
    """(path, mtime)-keyed, same reasoning as seed_iv_info.py -- an edited
    build file must be reseeded, not skipped forever."""
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
    """ONE query each for existing Build_Info / Build_Parts / Notes rows
    covering the WHOLE batch, replacing 3 round-trip queries PER RECORD
    with 3 queries per BATCH. Returns (existing_from_file_by_block:
    dict[str, bool | None], existing_parts_by_block: dict[str, list],
    existing_notes_by_block: dict[str, list]).

    existing_from_file_by_block doubles as the existence check -- a
    block_id being a KEY means the row exists; its VALUE is that row's
    from_file, used by process_one_record to decide whether it's protected."""
    block_ids = [build_block_id(r["fields"]) for r in batch]  # block_id doesn't need date-coerced fields

    existing_from_file_by_block = {}
    if block_ids:
        rows = db_session.execute(select(Build_Info.block_id, Build_Info.from_file).where(Build_Info.block_id.in_(block_ids))).all()
        existing_from_file_by_block = {row[0]: row[1] for row in rows}

    existing_parts_by_block = defaultdict(list)
    existing_notes_by_block = defaultdict(list)
    if block_ids:
        for entry in db_session.execute(select(Build_Parts).where(Build_Parts.block_id.in_(block_ids))).scalars().all():
            existing_parts_by_block[entry.block_id].append(entry)
        for entry in db_session.execute(select(Notes).where(Notes.block_id.in_(block_ids))).scalars().all():
            existing_notes_by_block[entry.block_id].append(entry)

    return existing_from_file_by_block, existing_parts_by_block, existing_notes_by_block


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


def replace_parts_and_notes(block_id, parts, notes, existing_parts, existing_notes):
    """Delete-then-reinsert, matching
    db_service.stage_replace_build_parts_and_notes -- existing_parts /
    existing_notes are PREFETCHED (bulk_prefetch), not queried here."""
    for entry in existing_parts:
        queries.delete_table_entry(db_session, Build_Parts, entry.instance_id)
    for entry in existing_notes:
        queries.delete_table_entry(db_session, Notes, entry.note_id)

    for part in parts:
        queries.add_table_entry(db_session, Build_Parts, block_id=block_id, **part)
    for note in notes:
        queries.add_table_entry(db_session, Notes, block_id=block_id, **coerce_note(note))


def process_one_record(record, dry_run, existing_from_file_by_block, existing_parts_by_block, existing_notes_by_block):
    """Upserts Build_Info, then replaces its Build_Parts/Notes wholesale.
    Returns ("added" | "updated" | "protected" | "would_upsert", block_id).

    PROTECTED: if the existing Build_Info row was last written by the app
    (from_file is not True), the WHOLE record is skipped -- Build_Info,
    Build_Parts, and Notes alike. A build is treated as one cohesive unit,
    so the check happens before ANY write, not just the Build_Info one."""
    fields = coerce_dates(record["fields"])
    block_id = build_block_id(fields)

    if dry_run:
        return "would_upsert", block_id

    existed_before = block_id in existing_from_file_by_block

    if existed_before and seed_shared.is_protected(existing_from_file_by_block[block_id]):
        return "protected", block_id

    kwargs = dict(fields)
    kwargs["block_id"] = block_id
    kwargs["build_file_path"] = record["source_path"]  # NEVER block_file_path -- see module docstring
    kwargs["from_file"] = True

    if existed_before:
        queries.update_table_entry(db_session, Build_Info, block_id, **kwargs)
    else:
        queries.add_table_entry(db_session, Build_Info, **kwargs)

    replace_parts_and_notes(
        block_id,
        record.get("parts", []),
        record.get("notes", []),
        existing_parts_by_block.get(block_id, []),
        existing_notes_by_block.get(block_id, []),
    )

    return ("updated" if existed_before else "added"), block_id


def log_protected(protected_file, source_path, block_id):
    protected_file.write(json.dumps({"source_path": source_path, "block_id": block_id}) + "\n")
    protected_file.flush()


def run_batch(batch, dry_run, error_log, checkpoint_file, protected_file):
    """Protected records are LOGGED but never CHECKPOINTED -- so they get
    re-evaluated every run. If a reviewed row is flipped back to
    from_file = True, the next run picks the file up without needing
    --force or an mtime change."""
    added = updated = errors = protected = 0
    if dry_run:
        existing_from_file_by_block, existing_parts_by_block, existing_notes_by_block = {}, {}, {}
    else:
        existing_from_file_by_block, existing_parts_by_block, existing_notes_by_block = bulk_prefetch(batch)

    try:
        results = []
        for record in batch:
            status, block_id = process_one_record(
                record, dry_run, existing_from_file_by_block, existing_parts_by_block, existing_notes_by_block
            )
            results.append((record, status, block_id))
            if status == "added":
                added += 1
            elif status == "updated":
                updated += 1
            elif status == "would_upsert":
                added += 1  # dry-run: lumped together, doesn't distinguish add/update
            elif status == "protected":
                protected += 1
        if not dry_run:
            queries.commit_db_changes(db_session)
            # Logging/checkpointing happens only AFTER a successful commit,
            # so a mid-batch failure doesn't double-log in the fallback below.
            for record, status, block_id in results:
                if status == "protected":
                    log_protected(protected_file, record["source_path"], block_id)
                else:
                    append_checkpoint(checkpoint_file, record["source_path"], record["source_mtime"])
        return added, updated, errors, protected
    except Exception:
        if not dry_run:
            queries.roll_back_db_changes(db_session)
        added = updated = errors = protected = 0
        for record in batch:
            try:
                status, block_id = process_one_record(
                    record, dry_run, existing_from_file_by_block, existing_parts_by_block, existing_notes_by_block
                )
                if status == "added":
                    added += 1
                elif status == "updated":
                    updated += 1
                elif status == "would_upsert":
                    added += 1
                elif status == "protected":
                    protected += 1
                if not dry_run:
                    if status == "protected":
                        log_protected(protected_file, record["source_path"], block_id)
                    else:
                        queries.commit_db_changes(db_session)
                        append_checkpoint(checkpoint_file, record["source_path"], record["source_mtime"])
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
        return added, updated, errors, protected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Ignore checkpoint, reprocess everything")
    args = parser.parse_args()

    if not DB_READY_PATH.exists():
        raise SystemExit(f"{DB_READY_PATH} not found -- run transform_build_records.py first.")

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

    clean_records, problems = preflight_check(all_records)

    if problems:
        print(f"PREFLIGHT: {len(problems)} record(s) have column problems and will be SKIPPED entirely.")
        for p in problems[:5]:
            print(f"  {p}")
        print()

    total_added = total_updated = total_errors = total_protected = 0

    with open(ERROR_LOG_PATH, "w", encoding="utf-8") as error_log, \
         open(CHECKPOINT_PATH, "a", encoding="utf-8") as checkpoint_file, \
         open(PROTECTED_PATH, "w", encoding="utf-8") as protected_file:  # "w": never checkpointed, so rebuilt fresh each run
        for i in range(0, len(clean_records), BATCH_SIZE):
            batch = clean_records[i : i + BATCH_SIZE]
            added, updated, errors, protected = run_batch(batch, args.dry_run, error_log, checkpoint_file, protected_file)
            total_added += added
            total_updated += updated
            total_errors += errors
            total_protected += protected
            print(f"Batch {i // BATCH_SIZE + 1}: +{added} added, {updated} updated, {errors} errors, {protected} protected")

    label = "WOULD ADD" if args.dry_run else "ADDED"
    print()
    print(f"{label}: {total_added}")
    print(f"UPDATED (pre-existing block_id): {total_updated}")
    print(f"PROTECTED ENTRIES: {total_protected} -> {PROTECTED_PATH}")
    print(f"ERRORS: {total_errors} -> {ERROR_LOG_PATH}")
    if problems:
        print(f"PREFLIGHT PROBLEMS (never attempted): {len(problems)}")
    if args.dry_run:
        print()
        print("Dry run only -- nothing was committed to the database.")


if __name__ == "__main__":
    main()