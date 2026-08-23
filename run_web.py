"""Launch the ClipForge web app."""

import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"\n  ClipForge — YouTube Shorts Maker")
    print(f"  Running on: http://{host}:{port}")
    print(f"  Press Ctrl+C to stop\n")
    uvicorn.run("web.app:app", host=host, port=port, reload=False)
