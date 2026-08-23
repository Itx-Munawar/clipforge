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

### Web App (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the web app
python run_web.py

# Open http://localhost:8000
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
| 🌐 Web Interface | Beautiful, modern web UI |
| 💻 CLI Support | Full command-line interface |

## Web Interface

The app includes a full web interface with:

- **Landing page** — marketing page with features overview
- **App page** — full-featured clip generator with settings
- **Channel connection** — OAuth flow to connect your YouTube channel
- **Real-time progress** — live updates via WebSocket
- **Clip preview** — play and download clips directly
- **Auto upload** — upload with privacy and scheduling options

## Deployment

### Docker

```bash
docker build -t clipforge .
docker run -p 8000:8000 clipforge
```

### Render (Free)

1. Push to GitHub
2. Connect repo on [render.com](https://render.com)
3. Auto-deploys with `render.yaml`

### Railway

1. Push to GitHub
2. Connect repo on [railway.app](https://railway.app)
3. Auto-detects Dockerfile

## YouTube API Setup (for uploads)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **YouTube Data API v3**
3. Create **OAuth 2.0 Client ID** (Desktop app)
4. Download the JSON and save as `client_secret.json`
5. Run `python auth_helper.py` to authenticate

## Tech Stack

- **Backend**: FastAPI + Python
- **AI**: Whisper (faster-whisper) for transcription
- **Video**: FFmpeg for processing
- **Download**: yt-dlp for YouTube
- **Auth**: Google OAuth 2.0
- **Frontend**: Vanilla HTML/CSS/JS

## Project Structure

```
clipforge/
├── web/
│   ├── app.py              # FastAPI backend
│   └── templates/
│       ├── landing.html    # Marketing page
│       └── app.html        # Main application
├── main.py                 # CLI entry point
├── downloader.py           # YouTube video downloader
├── transcriber.py          # Whisper transcription
├── clip_finder.py          # AI clip detection
├── video_processor.py      # FFmpeg video processing
├── uploader.py             # YouTube upload
├── auth_helper.py          # OAuth authentication
├── gui.py                  # Desktop GUI
├── run_web.py              # Web app launcher
├── Dockerfile              # Docker deployment
├── render.yaml             # Render deployment
└── requirements.txt        # Dependencies
```

## License

MIT — use it however you want.

---

Built with ❤️ by [Itx-Munawar](https://github.com/Itx-Munawar)
