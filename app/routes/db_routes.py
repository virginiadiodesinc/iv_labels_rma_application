from flask import Blueprint, request, render_template
from app.services.process_and_sanitize_entry import *
from app.services.date_converter import string_to_python_date


db_bp = Blueprint("db", __name__)

@db_bp.post("/submit_feedback")
def submit_feedback():
	initials = request.form.get("User_Initials", "").strip()
	feedback = request.form.get("User_Feedback", "").strip()

	if not initials or not feedback: return "<p style='color:red;'>All fields are required.</p>"

	if len(initials) != 3: return "<p style='color:red;'>Initials must be exactly 3 characters.</p>"

	sanitize_and_save_feedback(initials, feedback)
	return "<p>Feedback saved successfully.</p>"

@db_bp.post("/populate_block_info")
def populate_block_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != [] and retrieve_build_parts(block_engraving, block_serial_number, block_revision) == []:
		block = retrieve_build_info(block_engraving, block_serial_number, block_revision)[0]
		return render_template("partials/block-forms/block-and-build-population.html", block=block)
	elif retrieve_build_info(block_engraving, block_serial_number, block_revision) != [] and retrieve_build_parts(block_engraving, block_serial_number, block_revision) != []:
		block = retrieve_build_info(block_engraving, block_serial_number, block_revision)[0]
		items = retrieve_build_parts(block_engraving, block_serial_number, block_revision)
		return render_template("partials/block-forms/block-and-build-population.html", block=block, items=items)


@db_bp.post("/save_inspection_info") #add some intelligent return statements
def save_inspection_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	inspection_date = string_to_python_date(request.form.get("inspection-date-input", "")) if (request.form.get("inspection-date-input", "") != "") else None
	inspection_initials = request.form.get("inspection-initials-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
		updates = {
			"inspection_date": inspection_date,
			"inspection_initials": inspection_initials
		}
		update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
		
		return
	elif validate_block_info(block_engraving, block_serial_number, block_revision):
		new_entry = {
			"block_id": block_engraving+" "+block_serial_number+" "+block_revision,
			"block_engraving": block_engraving,
			"block_serial_number": block_serial_number,
			"block_revision": block_revision,
			"inspection_date": inspection_date,
			"inspection_initials": inspection_initials
		}
		print(new_entry)
		add_table_entry(db_session, Build_Info, **new_entry)
		
		return
	else:
		print("Invalid block information entered, no block information has been added.") #Remove this when sanitizing functionality is added.
		return
	
@db_bp.post("/save_pb1_info")
def save_pb1_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	pb1_build_name = request.form.get("pb1-build-name-input", "").strip()
	pb1_date = string_to_python_date(request.form.get("pb1-date-input", "")) if (request.form.get("pb1-date-input", "") != "") else None
	pb1_initials = request.form.get("pb1-initials-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
		updates = {
			"pb1_build_name": pb1_build_name,
			"pb1_date": pb1_date,
			"pb1_initials": pb1_initials
		}
		update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
		
		return
	elif validate_block_info(block_engraving, block_serial_number, block_revision):
		new_entry = {
			"block_id": block_engraving+" "+block_serial_number+" "+block_revision,
			"block_engraving": block_engraving,
			"block_serial_number": block_serial_number,
			"block_revision": block_revision,
			"pb1_build_name": pb1_build_name,
			"pb1_date": pb1_date,
			"pb1_initials": pb1_initials
		}
		add_table_entry(db_session, Build_Info, **new_entry)
		
		return
	else:
		print("Invalid block information entered, no block information has been added.") #Remove this when sanitizing functionality is added.
		return

@db_bp.post("/save_pb2_info")
def save_pb2_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	pb2_build_name = request.form.get("pb2-build-name-input", "").strip()
	pb2_date = string_to_python_date(request.form.get("pb2-date-input", "")) if (request.form.get("pb2-date-input", "") != "") else None
	pb2_initials = request.form.get("pb2-initials-input", "").strip()
	pb2_inspection_initials = request.form.get("pb2-inspection-initials-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
		updates = {
			"pb2_build_name": pb2_build_name,
			"pb2_date": pb2_date,
			"pb2_initials": pb2_initials,
			"pb2_inspection_initials": pb2_inspection_initials
		}
		update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
		
		return
	elif validate_block_info(block_engraving, block_serial_number, block_revision):
		new_entry = {
			"block_id": block_engraving+" "+block_serial_number+" "+block_revision,
			"block_engraving": block_engraving,
			"block_serial_number": block_serial_number,
			"block_revision": block_revision,
			"pb2_build_name": pb2_build_name,
			"pb2_date": pb2_date,
			"pb2_initials": pb2_initials,
			"pb2_inspection_initials": pb2_inspection_initials
		}
		add_table_entry(db_session, Build_Info, **new_entry)
		
		return
	else:
		print("Invalid block information entered, no block information has been added.") #Remove this when sanitizing functionality is added.
		return