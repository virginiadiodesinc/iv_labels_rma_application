import os
from flask import Flask
from app.db.models import *

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def create_app():
	"""Creates the Flask app.

	This is the function which actually creates the Flask app.
	This sets up the blueprints (the routes/urls), initializes/checks the DB, and closes down the app on exit.

	@return app Return value of type (Flask).
	"""
	UPLOAD_FOLDER = 'uploads'

	app = Flask(
	__name__,
	template_folder=os.path.join(BASE_DIR, "templates"),
	static_folder=os.path.join(BASE_DIR, "static"),
	)

	app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

	from app.routes import build_routes, db_routes, file_handling_routes, iv_routes, jb2_routes, page_loading_routes, printing_routes, save_routes
	
	app.register_blueprint(build_routes.build_bp)
	app.register_blueprint(db_routes.db_bp)
	app.register_blueprint(file_handling_routes.file_bp)
	app.register_blueprint(iv_routes.iv_bp)
	app.register_blueprint(jb2_routes.jb2_bp)
	app.register_blueprint(page_loading_routes.page_bp)
	app.register_blueprint(printing_routes.print_bp)
	app.register_blueprint(save_routes.save_bp)

	from app.db.database import db_session, engine, Base
	from sqlalchemy import inspect

	Base.metadata.create_all(bind=engine)
	print("Database created.")

	inspector = inspect(engine)

	print("Database initialized.")
	print("Tables:", inspector.get_table_names())

	# session teardown
	@app.teardown_appcontext
	def shutdown_session(exception=None):
		db_session.remove()

	return app

