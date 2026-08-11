import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import webview
import threading
import logging
import time
import requests
from app import create_app


logging.basicConfig(
	filename="app.log",
	level=logging.DEBUG,
	format="%(asctime)s %(levelname)s %(message)s"
)

def wait_for_server():
	"""Pings the server

	This function just pings the server until it is ready

	@return None Return value of type (None).
	"""
	for _ in range(100):
		try:
			r = requests.get("http://127.0.0.1:5000/iv_and_build")
			if r.status_code == 200:
				return True
		except:
			pass
		time.sleep(0.1)
	return False

# Start Flask in a thread
def run_flask():
	""" Runs Flask

	This is the function which creates the Flask app using create_app() defined in the app __init__

	@return None Return value of type (None).
	"""
	try:
		start = time.time()
		app = create_app()
		print(f"App created in {time.time() - start:.2f}s")
		app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
	except Exception:
		logging.exception("Flask thread crashed")
		print("Flask thread crashed - see app.log")

def main():
	""" Main function

	This is the true entry point to the app. Runs Flask in a thread, waits for the server to start up, 
	and opens a pywebview window to the URL of the app.

	@return None Return value of type (None).
	"""
	threading.Thread(target=run_flask, daemon=True).start()
	if not wait_for_server():
		print("Server never came up - check app.log / console for the crash above.")
		input("Press Enter to exit...")
		return
	
	# Disable automatic DevTools popup
	webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False

	webview.create_window("IV/Labels/Components", "http://127.0.0.1:5000/iv_and_build", maximized=True)
	webview.start(debug=True)

if __name__ == "__main__":
	main()