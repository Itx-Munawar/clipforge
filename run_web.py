"""Launch the ClipForge web app locally and open in browser."""

import os
import sys
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
