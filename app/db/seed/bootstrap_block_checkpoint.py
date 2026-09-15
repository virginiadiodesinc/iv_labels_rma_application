"""
ONE-TIME helper: seeds seed_block_checkpoint.jsonl from whatever's ALREADY
seeded by seed_block_info.py specifically -- checked via block_file_path,
which only the block seed ever sets (mirrors bootstrap_build_checkpoint.py's
reasoning: a Build_Info row's mere existence isn't enough signal, since
build seeding creates rows too).

Run:
    python bootstrap_block_checkpoint.py
"""
from app.db.database import db_session
from app.db.models import Build_Info
from pathlib import Path
from sqlalchemy import select
import json

OUTPUT_DIR = Path(__file__).resolve().parent
DB_READY_PATH = OUTPUT_DIR / "db_ready_block_records.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "seed_block_checkpoint.jsonl"


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

    rows = db_session.execute(
        select(Build_Info.block_file_path).where(Build_Info.block_file_path.isnot(None))
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

    print(f"Bootstrapped checkpoint with {written} already-block-seeded record(s) -> {CHECKPOINT_PATH}")
    if missing_mtime:
        print(f"WARNING: {len(missing_mtime)} block_file_path(s) had no match in db_ready_block_records.jsonl "
              f"(not bootstrapped -- will be reprocessed on next run, safe, just not skipped):")
        for path in missing_mtime[:10]:
            print(f"  {path}")


if __name__ == "__main__":
    main()
