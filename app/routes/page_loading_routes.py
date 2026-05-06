from flask import Blueprint, render_template
from app import config

page_bp = Blueprint("page", __name__)
default_keithley_settings = config.default_keithley_settings

@page_bp.get("/")
def index():
	return render_template("base.html")

@page_bp.get("/build")
def get_build_page():
	return render_template("build-page.html")

@page_bp.get("/iv")
def get_iv_page():
	return render_template("iv-page.html", current_settings=default_keithley_settings)

@page_bp.get("/iv_and_build")
def get_iv_and_build_page():
	return render_template("iv-and-build-page.html", current_settings=default_keithley_settings)

@page_bp.get("/feedback")
def get_feedback_page():
	return render_template("feedback-page.html")