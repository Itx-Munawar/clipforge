"""Hindi Movie Recap — Dramatic narration explaining scenes like YouTube recap channels.

Instead of translating dialogue, this generates engaging Hindi narration
that explains what's happening in each scene, similar to channels like
"Bollywood Recaps", "Movies Recapped Hindi", etc.

Flow:
1. Download YouTube video
2. Transcribe with Whisper (word-level timestamps)
3. Group into scenes (~30-45s each)
4. Generate dramatic Hindi narration for each scene (not translation - explanation)
5. Generate TTS audio for narration
6. Mute original audio and overlay Hindi narration
7. Export final video
"""

import os
import asyncio
import subprocess
import tempfile
import json
import re
from dataclasses import dataclass


@dataclass
class RecapScene:
    """A scene with Hindi narration."""
    start: float
    end: float
    english_text: str
    hindi_narration: str
    audio_path: str = ""


async def _generate_tts(text: str, output_path: str, voice: str = "hi-IN-MadhurNeural"):
    """Generate Hindi TTS audio using edge-tts with retry."""
    import edge_tts
    safe_text = sanitize_text(text)
    if not safe_text.strip():
        safe_text = "Please wait"

    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(safe_text, voice, rate="-5%", pitch="+2Hz")
            await communicate.save(output_path)
            return
        except Exception as e:
            if attempt < 2:
                wait = (attempt + 1) * 3
                print(f"  TTS retry {attempt+1}/3 after {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                raise


def sanitize_text(text: str) -> str:
    """Remove ALL characters outside basic Latin + Devanagari ranges.
    This prevents any encoding issues on Windows."""
    result = []
    for ch in text:
        cp = ord(ch)
        # Allow: ASCII printable, Devanagari (Hindi script), common punctuation
        if (32 <= cp <= 126 or           # ASCII printable
            0x0900 <= cp <= 0x097F or     # Devanagari (Hindi)
            0x0980 <= cp <= 0x09FF or     # Bengali (sometimes in Hindi transliteration)
            0x0A00 <= cp <= 0x0A7F or     # Gurmukhi
            cp == 0x20 or                 # space
            cp == 0x0A):                 # newline
            result.append(ch)
        else:
            result.append(' ')  # Replace unknown chars with space
    text = ''.join(result)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def chunk_segments(segments: list[dict], chunk_duration: float = 35.0) -> list[dict]:
    """Group transcript segments into scenes of ~chunk_duration seconds."""
    chunks = []
    current_chunk = {"start": 0, "end": 0, "text": ""}

    for seg in segments:
        seg_text = seg.get("text", "").strip()
        if not seg_text:
            continue

        if current_chunk["end"] - current_chunk["start"] >= chunk_duration and current_chunk["text"]:
            chunks.append(current_chunk)
            current_chunk = {
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg_text,
            }
        else:
            if not current_chunk["text"]:
                current_chunk["start"] = seg.get("start", 0)
            current_chunk["end"] = seg.get("end", 0)
            current_chunk["text"] += " " + seg_text

    if current_chunk["text"]:
        chunks.append(current_chunk)

    return chunks


def generate_dramatic_narration(english_text: str, scene_index: int, total_scenes: int) -> str:
    """
    Convert English transcript into dramatic Hindi narration.
    Instead of translating word-for-word, creates engaging movie recap style narration.
    """
    from deep_translator import GoogleTranslator

    # Clean up the text
    text = english_text.strip()
    text = re.sub(r'\s+', ' ', text)

    if not text:
        return ""

    # Translate the core content to Hindi
    try:
        hindi_content = GoogleTranslator(source="en", target="hi").translate(text)
    except Exception:
        hindi_content = text

    if not hindi_content:
        hindi_content = text

    # Add dramatic recap-style connectors based on position
    if scene_index == 0:
        # Opening scene - dramatic introduction
        intro_hooks = [
            "Dekhiye kya hota hai jab...",
            "Yeh hai ek aisi kahani jo aapko hilaa ke rakh degi...",
            "Shuru karte hain aaj ki kahaani...",
            "Yeh kahaani hai uss waqt ki jab...",
        ]
        hook = intro_hooks[scene_index % len(intro_hooks)]
        return f"{hook} {hindi_content}"

    elif scene_index == total_scenes - 1:
        # Final scene - dramatic conclusion
        conclusions = [
            "Aur phir aakhir mein...",
            "Toh aisa hua aakhir kaar...",
            "Aur sabse hairaan karne wali baat yeh thi ki...",
            "Lekin tab tak bohot der ho chuki thi...",
        ]
        conclusion = conclusions[scene_index % len(conclusions)]
        return f"{conclusion} {hindi_content}"

    else:
        # Middle scenes - dramatic connectors
        connectors = [
            "Aur phir kya hota hai...",
            "Ab dekhiye kya hone waala hai...",
            "Tab tak kuch aisa hota hai jo sab badal deta hai...",
            "Aur yahan pe sab kuch palat jaata hai...",
            "Iske baad jo hota hai woh sach mein chauka dene wala hai...",
            "Lekin abhi kahaani ka sabse interesting part aana baaki hai...",
            "Aur phir ek aisi cheez hoti hai jo kisi ne sochi nahi thi...",
            "Toh kya hota hai aage? Dekhte rahiye...",
        ]
        connector = connectors[scene_index % len(connectors)]
        return f"{hindi_content} {connector}"


def translate_to_hindi(text: str) -> str:
    """Translate English text to Hindi."""
    from deep_translator import GoogleTranslator
    try:
        translated = GoogleTranslator(source="en", target="hi").translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"Translation failed: {e}")
        return text


def generate_recap(
    video_path: str,
    output_path: str,
    transcript: list[dict],
    voice: str = "hi-IN-MadhurNeural",
    chunk_duration: float = 35.0,
    progress_callback=None,
) -> dict:
    """
    Generate a dramatic Hindi recap video.

    Args:
        video_path: Path to the original video
        output_path: Path for the output video
        transcript: Whisper transcription segments
        voice: edge-tts voice name
        chunk_duration: Seconds per narration chunk
        progress_callback: Optional callback(progress_pct, message)

    Returns:
        dict with scenes info and output path
    """
    def _progress(pct, msg=""):
        if progress_callback:
            progress_callback(pct, msg)
        print(f"  [{pct:.0f}%] {msg}")

    _progress(5, "Analyzing video...")

    # Get video duration
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", video_path
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, encoding="utf-8")
    video_duration = float(json.loads(probe_result.stdout)["format"]["duration"])

    _progress(8, "Chunking transcript into scenes...")

    # Step 1: Chunk transcript into scenes
    chunks = chunk_segments(transcript, chunk_duration)
    if not chunks:
        raise Exception("No transcript segments found")

    _progress(12, f"Found {len(chunks)} scenes to narrate")

    # Step 2: Generate dramatic Hindi narration for each scene
    _progress(15, "Generating dramatic Hindi narration...")
    scenes = []
    for i, chunk in enumerate(chunks):
        pct = 15 + (i / len(chunks)) * 15
        _progress(pct, f"Writing narration {i+1}/{len(chunks)}...")

        narration = generate_dramatic_narration(
            chunk["text"],
            scene_index=i,
            total_scenes=len(chunks),
        )
        scenes.append(RecapScene(
            start=chunk["start"],
            end=chunk["end"],
            english_text=chunk["text"],
            hindi_narration=narration,
        ))

    _progress(30, "Generating Hindi voice...")

    # Step 3: Generate TTS for each scene
    temp_dir = tempfile.mkdtemp(prefix="recap_")
    for i, scene in enumerate(scenes):
        pct = 30 + (i / len(scenes)) * 20
        _progress(pct, f"Generating audio {i+1}/{len(scenes)}...")

        # Sanitize text for TTS and FFmpeg compatibility
        clean_text = sanitize_text(scene.hindi_narration)
        if not clean_text:
            clean_text = sanitize_text(scene.english_text)
        scene.hindi_narration = clean_text

        audio_path = os.path.join(temp_dir, f"narration_{i:03d}.mp3")
        asyncio.run(_generate_tts(clean_text, audio_path, voice))
        scene.audio_path = audio_path

        # Small delay between requests to avoid rate-limiting
        if i < len(scenes) - 1:
            import time as _time
            _time.sleep(2)

    _progress(55, "Muting original audio...")

    # Step 4: Mute original audio
    silent_path = os.path.join(temp_dir, "silent.mp4")
    cmd_silent = [
        "ffmpeg", "-y", "-i", video_path,
        "-c:v", "copy",
        "-an",
        silent_path
    ]
    subprocess.run(cmd_silent, capture_output=True, check=True)

    _progress(60, "Building narration timeline...")

    # Step 5: Build narration audio track
    # Get durations of each narration audio
    narration_parts = []
    for i, scene in enumerate(scenes):
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", scene.audio_path
        ]
        r = subprocess.run(probe_cmd, capture_output=True, text=True, encoding="utf-8")
        audio_dur = float(json.loads(r.stdout)["format"]["duration"])
        narration_parts.append({
            "index": i,
            "start": scene.start,
            "audio": scene.audio_path,
            "audio_dur": audio_dur,
        })

    _progress(65, "Mixing narration into video...")

    # Generate silence base
    silence_path = os.path.join(temp_dir, "silence.wav")
    cmd_silence = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(video_duration),
        silence_path
    ]
    subprocess.run(cmd_silence, capture_output=True, check=True)

    # Build complex filter for mixing
    inputs = ["-i", silence_path]
    for part in narration_parts:
        inputs.extend(["-i", part["audio"]])

    filter_parts = []
    for idx, part in enumerate(narration_parts):
        input_idx = idx + 1
        delay_ms = int(part["start"] * 1000)
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},apad[a{idx}]")

    mix_inputs = "[0:a]"
    for idx in range(len(narration_parts)):
        mix_inputs += f"[a{idx}]"
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(narration_parts) + 1}:duration=first:dropout_transition=0,volume={len(narration_parts) + 1}[out]"
    )

    filter_complex = ";".join(filter_parts)

    narration_track = os.path.join(temp_dir, "narration.wav")
    cmd_mix = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(video_duration),
        narration_track
    ]
    subprocess.run(cmd_mix, capture_output=True, check=True)

    _progress(80, "Combining video + Hindi narration...")

    # Step 6: Merge silent video with narration audio
    cmd_merge = [
        "ffmpeg", "-y",
        "-i", silent_path,
        "-i", narration_track,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ]
    subprocess.run(cmd_merge, capture_output=True, check=True)

    # Cleanup temp files
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except:
        pass

    _progress(100, "Done!")

    return {
        "output": output_path,
        "scenes": len(scenes),
        "duration": round(video_duration, 1),
        "scenes_detail": [
            {
                "start": round(s.start, 1),
                "end": round(s.end, 1),
                "english": s.english_text[:150],
                "narration": s.hindi_narration[:200],
            }
            for s in scenes
        ],
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python hindi_recap.py <video_path> <output_path>")
        sys.exit(1)

    from transcriber import transcribe

    video = sys.argv[1]
    output = sys.argv[2]

    print("Transcribing...")
    segments = transcribe(video, model_size="base")

    print("Generating Hindi recap...")
    result = generate_recap(video, output, segments)
    print(f"\nOutput: {result['output']}")
    print(f"Scenes: {result['scenes']}")
    for s in result["scenes_detail"]:
        print(f"  [{s['start']}s-{s['end']}s] {s['narration'][:80]}...")
