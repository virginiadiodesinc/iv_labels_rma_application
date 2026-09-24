"""
Adds indexes the seed scripts' lookups need to stay fast as these tables
grow. Safe to run anytime -- CREATE INDEX IF NOT EXISTS is idempotent, and
this doesn't touch any data. Just avoid running it while another process
has an open write transaction against these same tables.

Fixes the specific slowdown: IV_Info.iv_file_path has no index, so every
upsert-lookup in seed_iv_info.py was a full table scan, getting slower as
the table grew. build_parts.block_id / notes.block_id get the same
treatment since seed_build_info.py's replace-all pattern queries them the
same way.

Run:
    python add_seed_indexes.py
"""
from app.db.database import db_session
from sqlalchemy import text

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_iv_info_iv_file_path ON iv_info (iv_file_path)",
    "CREATE INDEX IF NOT EXISTS idx_build_parts_block_id ON build_parts (block_id)",
    "CREATE INDEX IF NOT EXISTS idx_notes_block_id ON notes (block_id)",
    "CREATE INDEX IF NOT EXISTS idx_iv_info_block_id ON iv_info (build_id)",
    "CREATE INDEX IF NOT EXISTS idx_block_engraving on build_info (block_engraving)",
    "CREATE INDEX IF NOT EXISTS idx_block_serial_number on build_info (block_serial_number)"
]


def main():
    for stmt in INDEX_STATEMENTS:
        print(f"Running: {stmt}")
        db_session.execute(text(stmt))
    db_session.commit()
    print("Done.")


if __name__ == "__main__":
    main()
