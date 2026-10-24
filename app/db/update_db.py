from sqlalchemy import create_engine, inspect, text
from app.db.database import Base
from app.db.config import COMPONENT_DB_FILE
import app.db.models

engine = create_engine(f"sqlite:///{COMPONENT_DB_FILE}")  # adjust path

def add_missing_columns(engine, base):
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                print(f"Creating new table: {table.name}")
                table.create(conn)
                continue

            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue

                col_type = col.type.compile(dialect=engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
                print(ddl)
                conn.execute(text(ddl))

add_missing_columns(engine, Base)