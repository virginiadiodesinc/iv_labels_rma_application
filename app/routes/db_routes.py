from flask import Blueprint, request
from app.services.process_feedback import process_and_save


db_bp = Blueprint("db", __name__)

@db_bp.post("/submit")
def submit():
	initials = request.form.get("User_Initials", "").strip()
	feedback = request.form.get("User_Feedback", "").strip()

	if not initials or not feedback: return "<p style='color:red;'>All fields are required.</p>"

	if len(initials) != 3: return "<p style='color:red;'>Initials must be exactly 3 characters.</p>"

	process_and_save(initials, feedback)
	return "<p>Feedback saved successfully.</p>"