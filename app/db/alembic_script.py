from app.db.database import engine
from sqlalchemy import text



with engine.begin() as conn:
    query = text("ALTER TABLE build_info ADD COLUMN last_saved TYPE DATETIME")