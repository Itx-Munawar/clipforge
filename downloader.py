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
        "--no-warnings",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to get video info: {result.stderr[:300]}")
    return json.loads(result.stdout)


def download_video(url: str, output_dir: str = "temp") -> str:
    """Download a YouTube video and return the file path."""
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    # Try multiple player clients — YouTube increasingly blocks the default
    player_clients = [
        "web_creator",
        "mweb",
        "tv",
        "web",
        "android",
    ]

    def _build_cmd(player_client: str) -> list[str]:
        cmd = [
            "yt-dlp",
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--no-playlist",
            "--no-warnings",
            "--extractor-args", f"youtube:player_client={player_client}",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            url
        ]
        # Check for cookies file
        cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
        if os.path.exists(cookies_file):
            cmd.insert(-1, "--cookies")
            cmd.insert(-1, cookies_file)
        return cmd

    cmd = _build_cmd(player_clients[0])

    print(f"Downloading video...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # If first attempt fails, try remaining player clients
    for client in player_clients[1:]:
        if result.returncode == 0:
            break
        stderr = result.stderr
        print(f"Retrying with player_client={client}... ({stderr[:120]})")
        cmd = _build_cmd(client)
        result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Download failed: {result.stderr[:500]}")

    # Find the downloaded file
    for f in os.listdir(output_dir):
        if f.endswith((".mp4", ".webm", ".mkv", ".mp3")) and not f.startswith("."):
            filepath = os.path.join(output_dir, f)
            if os.path.getsize(filepath) > 1000:  # At least 1KB
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
