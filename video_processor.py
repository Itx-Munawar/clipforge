"""Video processor — crop to vertical, add captions, export shorts."""

import os
import shutil
import subprocess
import json
from dataclasses import dataclass


@dataclass
class CaptionStyle:
    """Caption formatting options — CapCut modern style."""
    font_size: int = 62
    font_color: str = "white"
    font_name: str = "Arial"
    outline_color: str = "black"
    outline_width: int = 4
    position: str = "center"  # "center" or "bottom"
    shadow_color: str = "black"
    shadow_offset: int = 3


def _setup_font():
    """Copy a system font locally to avoid Windows C: colon issues."""
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/verdana.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    # Always use a relative path from the project root to avoid C: colon in paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    local_dir = os.path.join(project_root, "temp")
    os.makedirs(local_dir, exist_ok=True)
    local = os.path.join(local_dir, "caption_font.ttf")
    if os.path.exists(local):
        # Return relative path from project root for FFmpeg
        return "temp/caption_font.ttf"

    for p in candidates:
        if os.path.exists(p):
            shutil.copy2(p, local)
            return "temp/caption_font.ttf"
    return ""


def get_video_info(video_path):
    """Get video dimensions and duration."""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_streams", "-show_format", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            return {
                "width": int(s["width"]),
                "height": int(s["height"]),
                "duration": float(data["format"]["duration"]),
                "fps": eval(s.get("r_frame_rate", "30/1")),
            }
    raise Exception("No video stream found")


def _escape_drawtext(text):
    """Escape text for FFmpeg drawtext filter (used inside filter_script)."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    return text


def _build_enable(start, end):
    """Build FFmpeg enable expression with proper escaping for between()."""
    # In a filter_script file: between(t\,0.00\,5.00)
    # The \, means literal comma inside between()
    return "between(t\\," + f"{start:.2f}\\,{end:.2f}" + ")"


# Vibrant subtitle colors — rotates through these per word
SUBTITLE_COLORS = [
    "#FFFF00",  # Yellow
    "#FF00FF",  # Purple/Magenta
    "#FFFFFF",  # White
    "#00FF00",  # Green
    "#FF4444",  # Red
    "#00CCFF",  # Cyan
    "#FF8800",  # Orange
    "#FF69B4",  # Pink
    "#7CFC00",  # Lawn Green
    "#FFD700",  # Gold
    "#FF1493",  # Deep Pink
    "#00FF7F",  # Spring Green
]


def build_caption_filter(captions, style=None, offset=0.0, font_path=""):
    """Build FFmpeg drawtext filter — word-by-word with mixed colors."""
    if style is None:
        style = CaptionStyle()

    filters = []
    color_idx = 0

    for cap in captions:
        start = cap["start"] - offset
        end = cap["end"] - offset
        text = _escape_drawtext(cap["text"])
        if not text.strip():
            continue

        # Pick a rotating color for this word
        color = SUBTITLE_COLORS[color_idx % len(SUBTITLE_COLORS)]
        color_idx += 1

        y_pos = "(h-text_h)/2" if style.position == "center" else "h-text_h-80"
        enable = _build_enable(start, end)

        if font_path:
            # CapCut style: bold text + thick outline + shadow
            f = (f"drawtext=fontfile='{font_path}'"
                 f":text='{text}'"
                 f":fontcolor={color}"
                 f":fontsize={style.font_size}"
                 f":borderw={style.outline_width}"
                 f":bordercolor={style.outline_color}"
                 f":shadowcolor=black@0.6"
                 f":shadowx={style.shadow_offset}"
                 f":shadowy={style.shadow_offset}"
                 f":x=(w-text_w)/2"
                 f":y={y_pos}"
                 f":enable='{enable}'")
        else:
            f = (f"drawtext=text='{text}'"
                 f":fontcolor={color}"
                 f":fontsize={style.font_size}"
                 f":font='{style.font_name}'"
                 f":borderw={style.outline_width}"
                 f":bordercolor={style.outline_color}"
                 f":shadowcolor=black@0.6"
                 f":shadowx={style.shadow_offset}"
                 f":shadowy={style.shadow_offset}"
                 f":x=(w-text_w)/2"
                 f":y={y_pos}"
                 f":enable='{enable}'")
        filters.append(f)

    return ",".join(filters)


def process_clip(video_path, start, end, captions, output_path,
                 caption_style=None, target_width=1080, target_height=1920):
    """
    Process a video clip: cut, resize/pad to 9:16, burn captions, export MP4.
    Uses filter_script to avoid Windows command-line escaping issues.
    """
    duration = end - start
    font_path = _setup_font()

    # Build base filters
    vf = (f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
          f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
          f"format=yuv420p")

    # Add captions
    if captions and font_path:
        cap_filter = build_caption_filter(captions, caption_style,
                                          offset=start, font_path=font_path)
        if cap_filter:
            vf += "," + cap_filter

    # Write filter to a file (avoids shell escaping issues on Windows)
    project_root = os.path.dirname(os.path.abspath(__file__))
    filter_script = os.path.join(project_root, "temp", "filter_script.txt")
    with open(filter_script, "w") as f:
        f.write(vf)

    cmd = [
        "ffmpeg", "-i", video_path,
        "-ss", str(start), "-t", str(duration),
        "-filter_script:v", filter_script,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-y", output_path
    ]

    print(f"Processing: {os.path.basename(output_path)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg error:\n{result.stderr[-400:]}")
        raise Exception("Video processing failed")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Exported: {os.path.basename(output_path)} ({size_mb:.1f}MB)")
    return output_path


def add_subtitles_from_words(words, words_per_group=1, max_chars=40):
    """Create word-by-word captions — each word pops up individually."""
    if not words:
        return []
    captions = []
    for wi in words:
        word = wi["word"].strip()
        if not word:
            continue
        captions.append({
            "text": word,
            "start": wi["start"],
            "end": wi["end"],
        })
    return captions
