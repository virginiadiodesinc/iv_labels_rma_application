from flask import Blueprint, request, render_template
from app.services.process_and_sanitize_entry import *


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
	#print("query execution initiated")
	block = retrieve_block_and_build_info(block_engraving, block_serial_number, block_revision)[0]
	#print("query executed")
	return render_template("partials/block-forms/block-and-build-population.html", block=block)

@db_bp.post("/save_inspection_info")
def save_inspection_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	inspection_date = request.form.get("inspection_date_input", "").strip()
	inspection_initials = request.form.get("inspection_initials_input", "").strip()