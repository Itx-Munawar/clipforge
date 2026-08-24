"""Launch the ClipForge web app locally and open in browser."""

import os
import sys

# Force UTF-8 on Windows — must be done before any imports
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

import time
import webbrowser
import threading
import uvicorn

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"

def open_browser():
    """Wait for server to start, then open Chrome."""
    time.sleep(1.5)
    webbrowser.open(URL)

if __name__ == "__main__":
    print(f"\n  ClipForge — YouTube Shorts Maker")
    print(f"  Running on: {URL}")
    print(f"  Opening in browser...")
    print(f"  Press Ctrl+C to stop\n")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("web.app:app", host="127.0.0.1", port=PORT, reload=False)
