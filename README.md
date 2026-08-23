# ClipForge — AI YouTube Shorts Maker

Turn any YouTube video into viral Shorts, TikToks, and Reels — **100% free and local**.

![ClipForge](https://img.shields.io/badge/ClipForge-v2.0-purple)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## What It Does

1. **Download** any YouTube video
2. **Transcribe** with Whisper AI (word-level timestamps)
3. **Find viral moments** using smart engagement scoring
4. **Crop to 9:16** vertical format for Shorts/TikTok/Reels
5. **Burn captions** — auto-generated, perfectly timed
6. **Upload** directly to YouTube Shorts (with scheduling)

## Quick Start

### GUI (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the desktop GUI
python gui.py
```

### CLI

```bash
# Generate 5 clips from a YouTube video
python main.py "https://www.youtube.com/watch?v=VIDEO_ID"

# More options
python main.py URL --clips 10 --duration 45 --model small --upload
```

## Features

| Feature | Description |
|---------|-------------|
| 🎯 AI Clip Detection | Smart heuristics find viral-worthy moments |
| 📝 Auto Captions | Word-by-word captions burned into video |
| 📱 Vertical Cropping | Automatic 9:16 format for mobile |
| ⬆️ Auto Upload | One-click upload to YouTube Shorts |
| 📅 Scheduled Posts | Space out uploads throughout the day |
| 🔒 100% Private | Everything runs locally on your machine |
| 🖥️ Desktop GUI | Easy-to-use graphical interface |
| 💻 CLI Support | Full command-line interface |

## YouTube API Setup (for uploads)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **YouTube Data API v3**
3. Create **OAuth 2.0 Client ID** (Desktop app)
4. Download the JSON and save as `client_secret.json`
5. Run `python auth_helper.py` to authenticate

## Tech Stack

- **GUI**: tkinter Desktop Application
- **AI**: Whisper (faster-whisper) for transcription
- **Video**: FFmpeg for processing
- **Download**: yt-dlp for YouTube
- **Auth**: Google OAuth 2.0

## Project Structure

```
clipforge/
├── main.py                 # CLI entry point
├── gui.py                  # Desktop GUI
├── downloader.py           # YouTube video downloader
├── transcriber.py          # Whisper transcription
├── clip_finder.py          # AI clip detection
├── video_processor.py      # FFmpeg video processing
├── uploader.py             # YouTube upload
├── auth_helper.py          # OAuth authentication
└── requirements.txt        # Dependencies
```

## License

MIT — use it however you want.

---

Built with ❤️ by [Itx-Munawar](https://github.com/Itx-Munawar)
