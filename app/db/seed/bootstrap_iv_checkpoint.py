"""
ONE-TIME helper: seeds seed_iv_checkpoint.jsonl from whatever's ALREADY in
IV_Info. Only useful once, right after switching from the old (non-
checkpointed) seed_iv_info.py to the new one -- without this, the new
script's checkpoint starts empty and would re-touch every already-seeded
record once (harmless, since it's all upserts, but slow at ~78,000 rows).

Run this AFTER stopping the old run and AFTER add_seed_indexes.py, BEFORE
starting the new seed_iv_info.py.

Run:
    python bootstrap_iv_checkpoint.py
"""
from app.db.database import db_session
from app.db.models import IV_Info
from pathlib import Path
from sqlalchemy import select
import json

OUTPUT_DIR = Path(__file__).resolve().parent
CHECKPOINT_PATH = OUTPUT_DIR / "seed_iv_checkpoint.jsonl"


def main():
    rows = db_session.execute(select(IV_Info.iv_file_path)).all()
    count = 0
    with open(CHECKPOINT_PATH, "a", encoding="utf-8") as f:
        for (path,) in rows:
            f.write(json.dumps({"source_path": path}) + "\n")
            count += 1
    print(f"Bootstrapped checkpoint with {count} already-seeded record(s) -> {CHECKPOINT_PATH}")


if __name__ == "__main__":
    main()
