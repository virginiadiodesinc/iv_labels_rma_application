from sqlalchemy.orm import Session
from datetime import date
from app.db.models import *
from app.db.database import db_session
from app.db.queries import *
import csv
from pathlib import Path

BLOCK_LIST_FILE = Path(__file__).parent / "block_engravings.csv"
BUILD_LIST_FILE = Path(__file__).parent / "build_list.csv"

def validate_block_info(block_engraving):
	block_engravings_file = open(BLOCK_LIST_FILE)
	block_engravings_reader = csv.reader(block_engravings_file)
	full_csv_list = list(block_engravings_reader)

	engravings_list = []
	for entry in full_csv_list:
		engravings_list.append(entry[0])

	if block_engraving.strip() in engravings_list:
		block_engravings_file.close()
		return True
	else:
		block_engravings_file.close()
		return False
	
def validate_build_info(build_name):
	build_names_file = open(BUILD_LIST_FILE)
	build_names_reader = csv.reader(build_names_file)
	full_csv_list = list(build_names_reader)

	names_list = []
	for entry in full_csv_list:
		names_list.append(entry[0])

	if build_name.strip() in names_list:
		build_names_file.close()
		return True
	else:
		build_names_file.close()
		return False

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