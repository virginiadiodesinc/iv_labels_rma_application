import os
import sys
from flask import Flask, app

#import app.db.models #REGISTERING TABLES FOR TESTING FEEDBACK SUBMISSION
#from app.db.database import engine, Base #REGISTERING TABLES FOR TESTING FEEDBACK SUBMISSION

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def create_app():
	UPLOAD_FOLDER = 'uploads'

	app = Flask(
	__name__,
	template_folder=os.path.join(BASE_DIR, "templates"),
	static_folder=os.path.join(BASE_DIR, "static"),
	)

	#Base.metadata.create_all(bind=engine) #REGISTERING TABLES FOR TESTING FEEDBACK SUBMISSION

	app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

	from .routes.routes import bp
	app.register_blueprint(bp)

	from .db.database import db_session

	# session teardown
	@app.teardown_appcontext
	def shutdown_session(exception=None):
		db_session.remove()

	return app

