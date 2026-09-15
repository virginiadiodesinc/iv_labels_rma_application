import subprocess
import sys
import time
import webview

print("Starting backend...")

# start backend, capture its output so we can inspect it if it dies
backend = subprocess.Popen(
    ["python/python.exe", "main.py"],
    cwd=".",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# give it a moment, then check if it already crashed
time.sleep(2)

if backend.poll() is not None:
    # process already exited -- it crashed on startup
    print("Backend exited early! Output:")
    print(backend.stdout.read())
    input("Press Enter to close...")
    sys.exit(1)

try:
    webview.create_window("Component Tracker", "http://127.0.0.1:5000")
    webview.start()
except Exception as e:
    print(f"webview error: {e}")
    input("Press Enter to close...")
finally:
    backend.terminate()
    # if backend already died, print whatever it wrote
    remaining_output = backend.stdout.read() if backend.stdout else ""
    if remaining_output:
        print("Backend output:")
        print(remaining_output)