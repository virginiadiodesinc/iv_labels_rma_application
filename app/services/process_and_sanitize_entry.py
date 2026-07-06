from sqlalchemy.orm import Session
from datetime import date
from app.db.models import *
from app.db.database import db_session
from app.db.queries import *

def validate_block_info(block_engraving, block_serial_number, block_revision): #add regular expressions to limit or flag entries
	engraving_pass = True
	sn_pass = True
	revision_pass = True
	if (engraving_pass and sn_pass and revision_pass) == True:
		return True

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

def retrieve_build_info(block_engraving, block_serial_number, block_revision):
	filters = {
		"block_engraving": block_engraving,
		"block_serial_number": block_serial_number,
		"block_revision": block_revision
	}
	result = get_table_entries(db_session, Build_Info,**filters)

	return result

def retrieve_build_parts(block_engraving, block_serial_number, block_revision):
	filters = {
		"block_id": block_engraving+" "+block_serial_number+" "+block_revision
	}
	result = get_table_entries(db_session, Build_Parts,**filters)

	return result