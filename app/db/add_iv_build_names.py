from pathlib import Path
from sqlalchemy import update, bindparam
from app.db.database import db_session
from app.db.models import IV_Info

def extract_build_name(path):
    stem = Path(path).stem.split("_")[0]
    words = stem.split()          # splits on any whitespace, drops empties
    return words[0] if words else None

rows = db_session.query(IV_Info.iv_id, IV_Info.iv_file_path).all()

mappings = [
    {"b_id": pk, "b_name": extract_build_name(path)}
    for pk, path in rows
    if path
]

print(mappings[:5])  # sanity check

db_session.execute(
    update(IV_Info)
    .where(IV_Info.iv_id == bindparam("b_id"))
    .values(build_name=bindparam("b_name")),
    mappings,
)
db_session.commit()