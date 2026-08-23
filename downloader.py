"""Download YouTube videos using yt-dlp."""

import os
import subprocess
import json
from pathlib import Path


def get_video_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to get video info: {result.stderr}")
    return json.loads(result.stdout)


def download_video(url: str, output_dir: str = "temp") -> str:
    """Download a YouTube video and return the file path."""
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-playlist",
        url
    ]

    print(f"Downloading video...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Download failed: {result.stderr}")

    # Find the downloaded file
    for f in os.listdir(output_dir):
        if f.endswith((".mp4", ".webm", ".mkv")):
            filepath = os.path.join(output_dir, f)
            print(f"Downloaded: {f}")
            return filepath

    raise Exception("Download completed but file not found")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = download_video(sys.argv[1])
        print(f"Saved to: {path}")
    else:
        print("Usage: python downloader.py <youtube_url>")
