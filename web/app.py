"""FastAPI backend for YouTube Shorts Maker — Full Website."""

import os
import sys
import json
import uuid
import asyncio
import shutil
import traceback
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shorts-maker")

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

CLIENT_SECRET_FILE = "client_secret.json"

app = FastAPI(title="ClipForge - YouTube Shorts Maker", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories — create all before anything else
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")

for _d in [STATIC_DIR, OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(_d, exist_ok=True)

# Mount static — guarded in case directory is missing
try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
except Exception:
    pass

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# Job tracking
jobs = {}
channel_info = {"connected": False, "title": "", "thumbnail": "", "channel_id": ""}


# --- Pages ----------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "landing.html")
    return FileResponse(html_path)


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "app.html")
    return FileResponse(html_path)


# --- Channel Connection ---------------------------------------------------

@app.get("/api/channel/status")
async def get_channel_status():
    return channel_info


@app.get("/api/channel/secret")
async def check_channel_secret():
    """Check if client_secret.json exists."""
    secret_path = os.path.join(PROJECT_ROOT, CLIENT_SECRET_FILE)
    return {"exists": os.path.exists(secret_path)}


@app.post("/api/channel/secret")
async def upload_channel_secret(file: UploadFile = File(...)):
    """Upload client_secret.json for YouTube OAuth."""
    try:
        content = await file.read()
        data = json.loads(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file — could not parse it")

    # Accept any valid JSON with OAuth keys
    valid_keys = {"installed", "web", "desktop"}
    if not valid_keys.intersection(data.keys()):
        raise HTTPException(
            status_code=400,
            detail=f"File is valid JSON but doesn't look like OAuth credentials. Expected one of: {', '.join(valid_keys)}"
        )

    secret_path = os.path.join(PROJECT_ROOT, CLIENT_SECRET_FILE)
    with open(secret_path, "wb") as f:
        f.write(content)
    logger.info(f"client_secret.json uploaded: {len(content)} bytes")
    return {"exists": True, "filename": file.filename}


@app.delete("/api/channel/secret")
async def remove_channel_secret():
    """Remove client_secret.json."""
    secret_path = os.path.join(PROJECT_ROOT, CLIENT_SECRET_FILE)
    if os.path.exists(secret_path):
        os.remove(secret_path)
    token_path = os.path.join(PROJECT_ROOT, "token.json")
    if os.path.exists(token_path):
        os.remove(token_path)
    return {"exists": False}


@app.post("/api/channel/connect")
async def connect_channel():
    global channel_info
    try:
        from auth_helper import get_youtube_service, CLIENT_SECRET_FILE, SCOPES
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json")
        creds = None

        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                from google_auth_oauthlib.flow import InstalledAppFlow
                if not os.path.exists(os.path.join(PROJECT_ROOT, CLIENT_SECRET_FILE)):
                    return {"connected": False, "error": "client_secret.json not found"}
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.path.join(PROJECT_ROOT, CLIENT_SECRET_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0, prompt="consent")

            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        youtube = build("youtube", "v3", credentials=creds)
        result = youtube.channels().list(part="snippet", mine=True).execute()

        if result.get("items"):
            ch = result["items"][0]
            channel_info.update({
                "connected": True,
                "title": ch["snippet"]["title"],
                "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
                "channel_id": ch["id"],
            })
            return channel_info
        return {"connected": False, "error": "No channel found"}
    except Exception as e:
        logger.error(f"Channel connection error: {e}")
        return {"connected": False, "error": str(e)}


@app.post("/api/channel/disconnect")
async def disconnect_channel():
    global channel_info
    channel_info = {"connected": False, "title": "", "thumbnail": "", "channel_id": ""}
    token_file = os.path.join(PROJECT_ROOT, "token.json")
    if os.path.exists(token_file):
        os.remove(token_file)
    return {"connected": False}


# --- Cookies -------------------------------------------------------------

@app.get("/api/cookies")
async def get_cookies_status():
    """Check if cookies file exists and parse expiry info."""
    cookies_path = os.path.join(PROJECT_ROOT, "cookies.txt")
    if os.path.exists(cookies_path):
        size = os.path.getsize(cookies_path)
        mtime = os.path.getmtime(cookies_path)
        now = time.time()
        age_hours = round((now - mtime) / 3600, 1)
        modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

        # Parse Netscape cookie file for expiry timestamps
        nearest_expiry = None
        expired_count = 0
        total_cookies = 0
        try:
            with open(cookies_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        try:
                            exp = int(parts[4])
                            if exp > 0:
                                total_cookies += 1
                                if exp < now:
                                    expired_count += 1
                                else:
                                    if nearest_expiry is None or exp < nearest_expiry:
                                        nearest_expiry = exp
                        except (ValueError, IndexError):
                            pass
        except Exception:
            pass

        hours_left = None
        status = "fresh"
        if nearest_expiry is not None:
            hours_left = round((nearest_expiry - now) / 3600, 1)
            if hours_left <= 0:
                status = "expired"
            elif hours_left < 1:
                status = "expiring_soon"
            elif hours_left < 6:
                status = "aging"
        elif total_cookies > 0 and expired_count == total_cookies:
            status = "expired"
            hours_left = 0

        return {
            "loaded": True,
            "size": size,
            "modified": modified,
            "age_hours": age_hours,
            "hours_left": hours_left,
            "status": status,
            "total_cookies": total_cookies,
            "expired_cookies": expired_count,
        }
    return {"loaded": False}


@app.post("/api/cookies")
async def upload_cookies(file: UploadFile = File(None)):
    """Upload a cookies.txt file for yt-dlp authentication."""
    if file is not None:
        content = await file.read()
        cookies_path = os.path.join(PROJECT_ROOT, "cookies.txt")
        with open(cookies_path, "wb") as f:
            f.write(content)
        logger.info(f"Cookies uploaded: {len(content)} bytes")
        return {"loaded": True, "size": len(content), "filename": file.filename or "pasted.txt"}
    raise HTTPException(status_code=400, detail="No file provided")


@app.post("/api/cookies/text")
async def upload_cookies_text(request: Request):
    """Paste cookie text directly (Netscape cookie format)."""
    body = await request.body()
    data = json.loads(body)
    text = data.get("cookies", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No cookie text provided")
    cookies_path = os.path.join(PROJECT_ROOT, "cookies.txt")
    with open(cookies_path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info(f"Cookies pasted: {len(text)} chars")
    return {"loaded": True, "size": len(text.encode("utf-8")), "filename": "pasted.txt"}


@app.delete("/api/cookies")
async def delete_cookies():
    """Remove cookies file."""
    cookies_path = os.path.join(PROJECT_ROOT, "cookies.txt")
    if os.path.exists(cookies_path):
        os.remove(cookies_path)
    return {"loaded": False}


# --- Job Generation -------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0", "channel": channel_info.get("connected", False)}


@app.post("/api/generate")
async def start_generate(
    url: str = Form(...),
    clips: int = Form(5),
    duration: int = Form(30),
    model: str = Form("base"),
    caption_pos: str = Form("center"),
):
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "step": "",
        "logs": [],
        "clips": [],
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    import threading
    thread = threading.Thread(
        target=_run_generate,
        args=(job_id, url, clips, duration, model, caption_pos),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id, "status": "started"}


def _run_generate(job_id, url, num_clips, duration, model, caption_pos):
    job = jobs[job_id]
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        from downloader import download_video
        from transcriber import transcribe
        from clip_finder import find_clips
        from video_processor import process_clip, add_subtitles_from_words, CaptionStyle

        job["status"] = "running"

        job["step"] = "Downloading video..."
        job["progress"] = 10
        job["logs"].append("Downloading video...")
        video_path = download_video(url, output_dir=TEMP_DIR)
        job["logs"].append(f"Downloaded: {os.path.basename(video_path)}")
        job["progress"] = 25

        job["step"] = "Transcribing with AI..."
        job["progress"] = 30
        job["logs"].append("Transcribing (this may take a while)...")
        segments = transcribe(video_path, model_size=model)
        job["logs"].append(f"Transcribed {len(segments)} segments")
        job["progress"] = 55

        with open(os.path.join(output_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(segments, f, indent=2, ensure_ascii=False)

        job["step"] = "Finding viral moments..."
        job["progress"] = 60
        job["logs"].append("Finding viral moments...")
        clips_list = find_clips(segments, clip_duration=duration, max_clips=num_clips, min_score=10.0)

        if not clips_list:
            job["status"] = "failed"
            job["error"] = "No clips found"
            job["logs"].append("No clips found!")
            return

        for i, c in enumerate(clips_list, 1):
            preview = c.text[:60] + ("..." if len(c.text) > 60 else "")
            job["logs"].append(f"Clip #{i} (score:{c.score:.0f}): {preview}")

        job["progress"] = 65
        job["step"] = "Processing clips..."
        all_words = []
        for seg in segments:
            all_words.extend(seg.get("words", []))

        caption_style = CaptionStyle(position=caption_pos)
        exported = []

        for i, clip in enumerate(clips_list, 1):
            job["logs"].append(f"Processing clip {i}/{len(clips_list)}...")
            job["progress"] = 65 + int((i / len(clips_list)) * 30)
            clip_words = [w for w in all_words if w["start"] >= clip.start - 0.5 and w["end"] <= clip.end + 0.5]
            captions = add_subtitles_from_words(clip_words, words_per_group=4)
            output_file = os.path.join(output_dir, f"clip_{i:02d}.mp4")
            try:
                process_clip(video_path=video_path, start=clip.start, end=clip.end,
                             captions=captions, output_path=output_file, caption_style=caption_style)
                exported.append({
                    "filename": f"clip_{i:02d}.mp4",
                    "url": f"/output/{job_id}/clip_{i:02d}.mp4",
                    "score": round(float(clip.score), 1),
                    "text": clip.text[:200],
                    "start": round(float(clip.start), 2),
                    "end": round(float(clip.end), 2),
                    "duration": round(float(clip.end - clip.start), 1),
                    "size": os.path.getsize(output_file),
                })
                job["logs"].append(f"  Exported: clip_{i:02d}.mp4")
            except Exception as e:
                logger.error(f"Job {job_id}: Failed clip {i}: {e}")
                job["logs"].append(f"  Failed clip #{i}: {e}")

        try:
            os.remove(video_path)
        except:
            pass

        job["clips"] = exported
        job["progress"] = 100
        job["step"] = "Done!"
        job["status"] = "completed"
        job["logs"].append(f"Done! Generated {len(exported)} shorts")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Job {job_id} failed: {e}\n{tb}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["logs"].append(f"Error: {e}")


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "job_id": job_id, "status": job["status"], "progress": job["progress"],
        "step": job["step"], "logs": job["logs"], "clips": job["clips"], "error": job["error"],
    }


@app.websocket("/ws/job/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    sent_log_count = 0
    try:
        while True:
            if job_id not in jobs:
                try:
                    await websocket.send_json({"error": "Job not found", "status": "failed"})
                except:
                    pass
                break
            job = jobs[job_id]
            new_logs = job["logs"][sent_log_count:]
            sent_log_count = len(job["logs"])
            payload = {
                "status": job["status"], "progress": job["progress"], "step": job["step"],
                "logs": new_logs, "clips": job["clips"], "error": job["error"],
            }
            try:
                await websocket.send_json(payload)
            except:
                break
            if job["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")


@app.get("/api/clips/{job_id}")
async def list_clips(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"clips": jobs[job_id]["clips"]}


@app.get("/api/download/{job_id}/{filename}")
async def download_clip(job_id: str, filename: str):
    filepath = os.path.join(OUTPUT_DIR, job_id, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, media_type="video/mp4", filename=filename)


@app.get("/api/download-all/{job_id}")
async def download_all_clips(job_id: str):
    if job_id not in jobs or not jobs[job_id]["clips"]:
        raise HTTPException(status_code=404, detail="No clips found")
    zip_dir = os.path.join(OUTPUT_DIR, job_id)
    zip_path = os.path.join(OUTPUT_DIR, f"{job_id}_clips")
    shutil.make_archive(zip_path, "zip", zip_dir)
    return FileResponse(f"{zip_path}.zip", media_type="application/zip", filename=f"clips_{job_id}.zip")


@app.post("/api/upload/{job_id}")
async def upload_to_youtube(
    job_id: str,
    privacy: str = Form("unlisted"),
    schedule: bool = Form(False),
    interval: int = Form(180),
    start_time: Optional[str] = Form(None),
):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if not job["clips"]:
        raise HTTPException(status_code=400, detail="No clips to upload")

    clip_paths = [os.path.join(OUTPUT_DIR, job_id, c["filename"]) for c in job["clips"]]

    import threading
    def do_upload():
        try:
            if schedule:
                from uploader import schedule_upload_batch
                start_dt = None
                if start_time:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                schedule_upload_batch(video_paths=clip_paths, start_time=start_dt,
                                      interval_minutes=interval, output_dir=os.path.join(OUTPUT_DIR, job_id))
            else:
                from uploader import upload_short
                for i, path in enumerate(clip_paths, 1):
                    upload_short(video_path=path, title=f"Clip {i}", privacy_status=privacy)
            job["logs"].append("Upload complete!")
        except Exception as e:
            job["logs"].append(f"Upload error: {e}")

    threading.Thread(target=do_upload, daemon=True).start()
    return {"status": "upload_started", "clips": len(clip_paths)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
