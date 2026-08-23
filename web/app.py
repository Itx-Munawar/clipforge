"""FastAPI backend for YouTube Shorts Maker — Full Website."""

import os
import sys
import json
import uuid
import asyncio
import shutil
import traceback
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shorts-maker")

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from downloader import download_video
from transcriber import transcribe
from clip_finder import find_clips
from video_processor import process_clip, add_subtitles_from_words, CaptionStyle

app = FastAPI(title="ClipForge — YouTube Shorts Maker", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# Job tracking
jobs = {}
# Channel connection status
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
    """Check if a YouTube channel is connected."""
    return channel_info


@app.post("/api/channel/connect")
async def connect_channel():
    """Start YouTube OAuth flow and connect channel."""
    global channel_info
    try:
        from auth_helper import get_youtube_service, CLIENT_SECRET_FILE, SCOPES

        if not os.path.exists(os.path.join(PROJECT_ROOT, CLIENT_SECRET_FILE)):
            raise HTTPException(
                status_code=400,
                detail="YouTube API credentials not found. Please place client_secret.json in the project root."
            )

        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
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
            channel_info = {
                "connected": True,
                "title": ch["snippet"]["title"],
                "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
                "channel_id": ch["id"],
            }
            logger.info(f"Channel connected: {channel_info['title']}")
            return channel_info
        else:
            return {"connected": False, "error": "No YouTube channel found for this account"}

    except Exception as e:
        logger.error(f"Channel connection error: {e}")
        return {"connected": False, "error": str(e)}


@app.post("/api/channel/disconnect")
async def disconnect_channel():
    """Disconnect the YouTube channel."""
    global channel_info
    channel_info = {"connected": False, "title": "", "thumbnail": "", "channel_id": ""}
    token_file = os.path.join(PROJECT_ROOT, "token.json")
    if os.path.exists(token_file):
        os.remove(token_file)
    return {"connected": False}


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

    logger.info(f"Job {job_id} started for URL: {url}")
    return {"job_id": job_id, "status": "started"}


def _run_generate(job_id, url, num_clips, duration, model, caption_pos):
    """Run clip generation in background."""
    job = jobs[job_id]
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        job["status"] = "running"

        # Step 1: Download
        job["step"] = "Downloading video..."
        job["progress"] = 10
        job["logs"].append("Downloading video...")
        logger.info(f"Job {job_id}: Downloading...")

        video_path = download_video(url, output_dir=TEMP_DIR)

        job["logs"].append(f"Downloaded: {os.path.basename(video_path)}")
        job["progress"] = 25
        logger.info(f"Job {job_id}: Downloaded to {video_path}")

        # Step 2: Transcribe
        job["step"] = "Transcribing with AI..."
        job["progress"] = 30
        job["logs"].append("Transcribing (this may take a while)...")
        segments = transcribe(video_path, model_size=model)

        job["logs"].append(f"Transcribed {len(segments)} segments")
        job["progress"] = 55
        logger.info(f"Job {job_id}: Transcribed {len(segments)} segments")

        # Save transcript
        with open(os.path.join(output_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(segments, f, indent=2, ensure_ascii=False)

        # Step 3: Find clips
        job["step"] = "Finding viral moments..."
        job["progress"] = 60
        job["logs"].append("Finding viral moments...")
        clips_list = find_clips(
            segments, clip_duration=duration,
            max_clips=num_clips, min_score=10.0,
        )

        if not clips_list:
            job["status"] = "failed"
            job["error"] = "No clips found"
            job["logs"].append("No clips found!")
            return

        for i, c in enumerate(clips_list, 1):
            preview = c.text[:60] + ("..." if len(c.text) > 60 else "")
            job["logs"].append(f"Clip #{i} (score:{c.score:.0f}): {preview}")

        job["progress"] = 65

        # Step 4: Process clips
        job["step"] = "Processing clips..."
        all_words = []
        for seg in segments:
            all_words.extend(seg.get("words", []))

        caption_style = CaptionStyle(position=caption_pos)
        exported = []

        for i, clip in enumerate(clips_list, 1):
            job["logs"].append(f"Processing clip {i}/{len(clips_list)}...")
            job["progress"] = 65 + int((i / len(clips_list)) * 30)

            clip_words = [w for w in all_words
                         if w["start"] >= clip.start - 0.5 and w["end"] <= clip.end + 0.5]
            captions = add_subtitles_from_words(clip_words, words_per_group=4)
            output_file = os.path.join(output_dir, f"clip_{i:02d}.mp4")

            try:
                process_clip(
                    video_path=video_path, start=clip.start, end=clip.end,
                    captions=captions, output_path=output_file,
                    caption_style=caption_style,
                )
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
                logger.info(f"Job {job_id}: Exported clip {i}")
            except Exception as e:
                logger.error(f"Job {job_id}: Failed clip {i}: {e}")
                job["logs"].append(f"  Failed clip #{i}: {e}")

        # Cleanup temp
        try:
            os.remove(video_path)
        except:
            pass

        job["clips"] = exported
        job["progress"] = 100
        job["step"] = "Done!"
        job["status"] = "completed"
        job["logs"].append(f"Done! Generated {len(exported)} shorts")
        logger.info(f"Job {job_id}: Completed with {len(exported)} clips")

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
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "step": job["step"],
        "logs": job["logs"],
        "clips": job["clips"],
        "error": job["error"],
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
            all_logs = job["logs"]
            new_logs = all_logs[sent_log_count:]
            sent_log_count = len(all_logs)

            payload = {
                "status": job["status"],
                "progress": job["progress"],
                "step": job["step"],
                "logs": new_logs,
                "clips": job["clips"],
                "error": job["error"],
            }

            try:
                await websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"WebSocket send failed for job {job_id}: {e}")
                break

            if job["status"] in ("completed", "failed"):
                break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
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
    return FileResponse(
        f"{zip_path}.zip",
        media_type="application/zip",
        filename=f"clips_{job_id}.zip",
    )


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

    clip_paths = [
        os.path.join(OUTPUT_DIR, job_id, c["filename"])
        for c in job["clips"]
    ]

    import threading

    def do_upload():
        try:
            if schedule:
                from uploader import schedule_upload_batch
                start_dt = None
                if start_time:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                schedule_upload_batch(
                    video_paths=clip_paths,
                    start_time=start_dt,
                    interval_minutes=interval,
                    output_dir=os.path.join(OUTPUT_DIR, job_id),
                )
            else:
                from uploader import upload_short
                for i, path in enumerate(clip_paths, 1):
                    upload_short(video_path=path, title=f"Clip {i}", privacy_status=privacy)
            job["logs"].append("Upload complete!")
        except Exception as e:
            job["logs"].append(f"Upload error: {e}")
            logger.error(f"Upload error for job {job_id}: {e}")

    thread = threading.Thread(target=do_upload, daemon=True)
    thread.start()
    return {"status": "upload_started", "clips": len(clip_paths)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
