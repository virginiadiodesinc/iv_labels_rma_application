from app.db.database import engine, Base
import app.db.models
def createDB():
    Base.metadata.create_all(bind=engine) #triggers DB creation if file doesn't already exist
    print("Database created.")
