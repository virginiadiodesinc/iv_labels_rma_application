from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session

from app.db.config import COMPONENT_DB_FILE

# SQLite db connection: tells SQLalchemy to use SQLite database at this path
engine = create_engine(f"sqlite:///{COMPONENT_DB_FILE}", echo=False)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class model for other models to inherit from
Base = declarative_base()

# Create a scoped session
db_session = scoped_session(SessionLocal)