from sqlalchemy.orm import Session
from datetime import date
from app.db.models import Feedback
from app.db.database import db_session

def process_and_save(initials, feedback):
    try:
        new_entry = Feedback(
            user_initials=initials,
            user_feedback=feedback
        )

        db_session.add(new_entry)
        db_session.commit()

    except Exception as e:
        db_session.rollback()
        raise e

    finally:
        db_session.remove()