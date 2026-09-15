"""
These lines are called in create_app()
"""
from sqlalchemy import inspect
from app.db.database import engine, Base
import app.db.models

Base.metadata.create_all(bind=engine)
print("Database created.")

inspector = inspect(engine)

print("Database initialized.")
print("Tables:", inspector.get_table_names())
