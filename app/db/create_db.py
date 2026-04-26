from app.db.database import engine, Base
import app.db.models

Base.metadata.create_all(bind=engine)
print("Database created.")