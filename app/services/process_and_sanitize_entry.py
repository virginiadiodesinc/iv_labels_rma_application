from sqlalchemy.orm import Session
from datetime import date
from app.db.models import *
from app.db.database import db_session
from app.db.queries import *

def sanitize_and_save_feedback(initials, feedback):
	data = {
		"user_initials": initials,
		"user_feedback": feedback
	}
	add_table_entry(
		db_session,
		Feedback,
		**data
	)


def retrieve_block_and_build_info(block_engraving, block_serial_number, block_revision):
	print("in query 1")
	filters = {
		"block_engraving": block_engraving,
		"block_serial_number": block_serial_number,
		"block_revision": block_revision
	}
	result = get_table_entries(db_session, Build_Info,**filters)
	print("in query 2")

	return result