from app.db.database import engine
from sqlalchemy import text

new_columns = {
    "voltage_up_mv_list": "TEXT",
    "voltage_down_mv_list": "TEXT",
    "current_ua_list": "TEXT",
}

with engine.begin() as conn:
    query = text("ALTER TABLE iv_info ALTER COLUMN assembly_number TYPE VARCHAR")