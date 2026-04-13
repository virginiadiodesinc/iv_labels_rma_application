import subprocess
import time
import webview

print("Starting backend...")

# start backend
backend = subprocess.Popen(
	["python/python.exe", "main.py"],
	cwd=".",
)

# wait for server to come up
time.sleep(2)

# open desktop window pointing to Flask
webview.create_window("Component Tracker", "http://127.0.0.1:5000")
webview.start()

# cleanup
backend.terminate()