"""YouTube Shorts uploader with scheduled upload support.

Uploads vertical videos (9:16) as YouTube Shorts.
Uses resumable upload for reliability with large files.

Scheduling:
- YouTube allows scheduling videos up to 60 days in the future
- Scheduled videos are uploaded as private, then auto-published at the specified time
- Minimum 10 minutes between now and publish time
- Videos must be scheduled at least 10 minutes apart from each other
"""

import os
import time
import random
import json
import httplib2
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from auth_helper import get_youtube_service

# YouTube API settings
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
MAX_RETRIES = 5

SCHEDULE_LOG = "schedule_log.json"


def _generate_schedule(
    num_videos: int,
    start_time: datetime = None,
    interval_minutes: int = 180,
) -> list[datetime]:
    """
    Generate a list of scheduled publish times.

    Args:
        num_videos: Number of videos to schedule
        start_time: When to publish the first video (default: now + 10 min)
        interval_minutes: Minutes between each publish (default: 180 = 3 hours)

    Returns:
        List of datetimes for each publish
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc) + timedelta(minutes=10)

    # Ensure start_time is at least 10 minutes from now
    min_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    if start_time < min_time:
        start_time = min_time

    # YouTube requires at least 10 minutes between scheduled videos
    if interval_minutes < 10:
        interval_minutes = 10

    schedule = []
    current = start_time
    for _ in range(num_videos):
        schedule.append(current)
        current += timedelta(minutes=interval_minutes)

    return schedule


def _format_schedule(schedule: list[datetime]) -> str:
    """Pretty-print a schedule for display."""
    lines = []
    for i, dt in enumerate(schedule, 1):
        local = dt.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"  Clip #{i}: {local}")
    return "\n".join(lines)


def _save_schedule(schedule: list[datetime], results: list[dict], output_dir: str = "output"):
    """Save schedule and upload results to a log file."""
    log_path = os.path.join(output_dir, SCHEDULE_LOG)
    data = {
        "schedule": [dt.isoformat() for dt in schedule],
        "uploads": results,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return log_path


def upload_short(
    video_path: str,
    title: str = "",
    description: str = "",
    tags: list[str] = None,
    category_id: str = "22",
    privacy_status: str = "public",
    publish_at: str = None,
) -> dict:
    """
    Upload a video as a YouTube Short.

    For a video to be recognized as a Short:
    - Must be vertical (9:16 aspect ratio)
    - Must be 60 seconds or less
    - Title should include #Shorts (added automatically)

    Args:
        video_path: Path to the MP4 file
        title: Video title (#Shorts appended automatically)
        description: Video description
        tags: List of tags
        category_id: YouTube category (22 = People & Blogs)
        privacy_status: public, unlisted, or private
        publish_at: ISO 8601 datetime for scheduled publish
                     (e.g. "2025-01-15T18:00:00Z")

    Returns:
        dict with video id, title, URL, and schedule info
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    creds = get_youtube_service()
    youtube = build("youtube", "v3", credentials=creds)

    # Default title from filename
    if not title:
        title = os.path.splitext(os.path.basename(video_path))[0]

    # Ensure #Shorts is in the title
    if "#shorts" not in title.lower():
        title = f"{title} #Shorts"

    if tags is None:
        tags = ["shorts", "short", "viral"]

    # Build request body
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Handle scheduling
    is_scheduled = False
    if publish_at:
        # Scheduled videos must be uploaded as private
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at
        is_scheduled = True

    # Create upload request
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=256 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # Display upload info
    print(f"Uploading: {os.path.basename(video_path)}")
    print(f"Title: {title}")
    if is_scheduled:
        # Parse and display the scheduled time
        dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
        print(f"Scheduled for: {dt.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"Privacy: private (auto-publishes at scheduled time)")
    else:
        print(f"Privacy: {privacy_status}")

    # Resumable upload with retry
    response = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                percent = int(status.progress() * 100)
                print(f"  Upload progress: {percent}%")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                retry += 1
                if retry > MAX_RETRIES:
                    raise
                wait = random.uniform(1, 2 ** retry)
                print(f"  Retriable error {e.resp.status}, waiting {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            retry += 1
            if retry > MAX_RETRIES:
                raise
            wait = random.uniform(1, 2 ** retry)
            print(f"  Network error, waiting {wait:.1f}s...")
            time.sleep(wait)

    if response and "id" in response:
        video_id = response["id"]
        video_url = f"https://youtube.com/shorts/{video_id}"
        print(f"\n  Uploaded successfully!")
        print(f"  Video ID: {video_id}")
        print(f"  URL: {video_url}")

        result = {
            "id": video_id,
            "title": title,
            "url": video_url,
            "privacy": "scheduled" if is_scheduled else privacy_status,
        }
        if is_scheduled:
            result["publish_at"] = publish_at
        return result
    else:
        raise Exception("Upload failed — no video ID in response")


def schedule_upload_batch(
    video_paths: list[str],
    start_time: datetime = None,
    interval_minutes: int = 180,
    titles: list[str] = None,
    descriptions: list[str] = None,
    tags: list[str] = None,
    output_dir: str = "output",
) -> list[dict]:
    """
    Schedule a batch of videos for upload at specific times.

    Args:
        video_paths: List of video file paths
        start_time: First video publish time (default: now + 10 min)
        interval_minutes: Minutes between each publish (default: 180 = 3 hours)
        titles: Optional list of titles (one per video)
        descriptions: Optional list of descriptions
        tags: Tags to apply to all videos
        output_dir: Where to save the schedule log

    Returns:
        List of upload results
    """
    num_videos = len(video_paths)
    if num_videos == 0:
        print("No videos to upload.")
        return []

    # Generate the schedule
    schedule = _generate_schedule(num_videos, start_time, interval_minutes)

    # Show the schedule
    print("")
    print("=" * 60)
    print(f"  Upload Schedule ({num_videos} videos, every {interval_minutes} min)")
    print("=" * 60)
    print(_format_schedule(schedule))
    print("=" * 60)
    print("")

    results = []
    for i, (video_path, publish_dt) in enumerate(zip(video_paths, schedule), 1):
        print(f"\n{'='*50}")
        print(f"  Uploading {i}/{num_videos}")
        print(f"{'='*50}")

        title = titles[i-1] if titles and i-1 < len(titles) else ""
        desc = descriptions[i-1] if descriptions and i-1 < len(descriptions) else ""
        publish_iso = publish_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            result = upload_short(
                video_path=video_path,
                title=title,
                description=desc,
                tags=tags,
                publish_at=publish_iso,
            )
            results.append(result)

            # Delay between uploads
            if i < len(video_paths):
                print("Waiting 5s before next upload...")
                time.sleep(5)

        except FileNotFoundError as e:
            print(f"\n  {e}")
            print("  Upload skipped. Set up YouTube API credentials first.")
            break
        except Exception as e:
            print(f"  Failed: {e}")
            results.append({"error": str(e), "path": video_path})

    # Save schedule log
    log_path = _save_schedule(schedule, results, output_dir)
    print(f"\n  Schedule log saved to: {log_path}")

    return results


def upload_multiple(videos: list[dict], **kwargs) -> list[dict]:
    """
    Upload multiple videos (no scheduling).

    Args:
        videos: List of dicts with 'path' and optional 'title', 'description'
        **kwargs: Default kwargs passed to upload_short

    Returns:
        List of upload results
    """
    results = []
    for i, video in enumerate(videos, 1):
        print(f"\n{'='*50}")
        print(f"  Uploading {i}/{len(videos)}")
        print(f"{'='*50}")

        try:
            result = upload_short(
                video_path=video["path"],
                title=video.get("title", ""),
                description=video.get("description", ""),
                tags=video.get("tags", kwargs.get("tags")),
                privacy_status=video.get("privacy", kwargs.get("privacy_status", "public")),
            )
            results.append(result)

            if i < len(videos):
                print("Waiting 5s before next upload...")
                time.sleep(5)

        except Exception as e:
            print(f"  Failed: {video['path']}: {e}")
            results.append({"error": str(e), "path": video["path"]})

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = upload_short(sys.argv[1], privacy_status="unlisted")
        print(f"\nResult: {result}")
    else:
        print("Usage: python uploader.py <video_path>")
