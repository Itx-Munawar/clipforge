"""Track which clips have been uploaded to YouTube."""

import os
import json
from datetime import datetime

TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upload_history.json")


def _load_history() -> dict:
    """Load upload history from disk."""
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_history(data: dict):
    """Save upload history to disk."""
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mark_uploaded(job_id: str, clip_filename: str, youtube_url: str = ""):
    """Mark a clip as uploaded."""
    history = _load_history()
    key = f"{job_id}/{clip_filename}"
    history[key] = {
        "uploaded_at": datetime.now().isoformat(),
        "youtube_url": youtube_url,
    }
    _save_history(history)


def mark_uploaded_batch(job_id: str, clip_filenames: list, youtube_urls: list = None):
    """Mark multiple clips as uploaded."""
    history = _load_history()
    for i, filename in enumerate(clip_filenames):
        key = f"{job_id}/{filename}"
        url = youtube_urls[i] if youtube_urls and i < len(youtube_urls) else ""
        history[key] = {
            "uploaded_at": datetime.now().isoformat(),
            "youtube_url": url,
        }
    _save_history(history)


def is_uploaded(job_id: str, clip_filename: str) -> bool:
    """Check if a clip has been uploaded."""
    history = _load_history()
    key = f"{job_id}/{clip_filename}"
    return key in history


def get_upload_status(job_id: str, clip_filenames: list) -> dict:
    """Get upload status for a list of clips.
    Returns dict mapping filename -> {uploaded: bool, uploaded_at: str, youtube_url: str}
    """
    history = _load_history()
    result = {}
    for filename in clip_filenames:
        key = f"{job_id}/{filename}"
        if key in history:
            result[filename] = {
                "uploaded": True,
                "uploaded_at": history[key].get("uploaded_at", ""),
                "youtube_url": history[key].get("youtube_url", ""),
            }
        else:
            result[filename] = {"uploaded": False}
    return result


def get_pending_clips(job_id: str, clip_filenames: list) -> list:
    """Return list of clip filenames that haven't been uploaded yet."""
    return [f for f in clip_filenames if not is_uploaded(job_id, f)]
