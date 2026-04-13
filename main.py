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
	for _ in range(100):
		try:
			r = requests.get("http://127.0.0.1:5000/build")
			if r.status_code == 200:
				return
		except:
			pass
		time.sleep(0.1)

# Start Flask in a thread
def run_flask():
	start = time.time()
	app = create_app()
	print(f"App created in {time.time() - start:.2f}s")
	app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

def main():
	threading.Thread(target=run_flask, daemon=True).start()
	wait_for_server()
	# Disable automatic DevTools popup
	webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False

	webview.create_window("IV/Labels/Components", "http://127.0.0.1:5000/build", maximized=True)
	webview.start(debug=True)

if __name__ == "__main__":
	main()