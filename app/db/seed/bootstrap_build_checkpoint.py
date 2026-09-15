"""
ONE-TIME helper: seeds seed_build_checkpoint.jsonl from whatever's ALREADY
seeded in Build_Info / Build_Parts / Notes by seed_build_info.py
specifically.

IMPORTANT DIFFERENCE from bootstrap_iv_checkpoint.py: a Build_Info row can
be created by EITHER seed_block_info.py OR seed_build_info.py -- so "does
this block_id exist in Build_Info" is NOT a safe signal that the BUILD
seed already ran on it. Only build_file_path is set exclusively by the
build seed (seed_block_info.py never touches it), so THAT'S what this
checks. Bootstrapping off mere row existence would falsely mark
block-only-seeded records as build-seeded, and they'd never get their
build-derived overwrites.

Run this after add_seed_indexes.py, before running the (now
checkpoint-aware) seed_build_info.py.

Run:
    python bootstrap_build_checkpoint.py
"""
from app.db.database import db_session
from app.db.models import Build_Info
from pathlib import Path
from sqlalchemy import select
import json

OUTPUT_DIR = Path("W:/Python3/IV and Labels/database/seed")
DB_READY_PATH = OUTPUT_DIR / "db_ready_build_records.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "seed_build_checkpoint.jsonl"


def latest_mtime_by_path():
    latest = {}
    with open(DB_READY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                record = json.loads(line)
                latest[record["source_path"]] = record["source_mtime"]
    return latest


def main():
    if not DB_READY_PATH.exists():
        raise SystemExit(f"{DB_READY_PATH} not found.")

    mtime_by_path = latest_mtime_by_path()

    # ONLY rows where build_file_path is set -- that's the build seed's
    # signature, not the block seed's.
    rows = db_session.execute(
        select(Build_Info.build_file_path).where(Build_Info.build_file_path.isnot(None))
    ).all()
    seeded_paths = {row[0] for row in rows}

    written = 0
    missing_mtime = []
    with open(CHECKPOINT_PATH, "a", encoding="utf-8") as f:
        for path in seeded_paths:
            mtime = mtime_by_path.get(path)
            if mtime is None:
                missing_mtime.append(path)
                continue
            f.write(json.dumps({"source_path": path, "source_mtime": mtime}) + "\n")
            written += 1

    print(f"Bootstrapped checkpoint with {written} already-build-seeded record(s) -> {CHECKPOINT_PATH}")
    if missing_mtime:
        print(f"WARNING: {len(missing_mtime)} build_file_path(s) had no match in db_ready_build_records.jsonl "
              f"(not bootstrapped -- will be reprocessed on next run, safe, just not skipped):")
        for path in missing_mtime[:10]:
            print(f"  {path}")


if __name__ == "__main__":
    main()
