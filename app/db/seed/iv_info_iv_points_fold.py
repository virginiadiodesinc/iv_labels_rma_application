from app.db.database import engine
from sqlalchemy import text

new_columns = {
    "voltage_up_mv": "STRING",
    "voltage_down_mv": "STRING",
    "current_ua": "STRING",
}

with engine.begin() as conn:
    for col_name, col_type in new_columns.items():
        conn.execute(text(f"ALTER TABLE iv_info ADD COLUMN {col_name} {col_type}"))