"""Hindi Movie Recap — Mute original audio and explain in Hindi.

Flow:
1. Download YouTube video
2. Transcribe with Whisper (word-level timestamps)
3. Chunk transcript into scenes (30-60s each)
4. Translate each chunk to Hindi
5. Generate Hindi TTS audio per chunk
6. Mute original audio and overlay Hindi narration
7. Export final video
"""

import os
import asyncio
import subprocess
import tempfile
import json
from dataclasses import dataclass


@dataclass
class RecapScene:
    """A scene with Hindi narration."""
    start: float
    end: float
    english_text: str
    hindi_text: str
    audio_path: str = ""


async def _generate_tts(text: str, output_path: str, voice: str = "hi-IN-MadhurNeural"):
    """Generate Hindi TTS audio using edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def translate_to_hindi(text: str) -> str:
    """Translate English text to Hindi using deep-translator."""
    from deep_translator import GoogleTranslator
    try:
        translated = GoogleTranslator(source="en", target="hi").translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"Translation failed: {e}")
        return text


def chunk_segments(segments: list[dict], chunk_duration: float = 45.0) -> list[dict]:
    """Group transcript segments into chunks of ~chunk_duration seconds."""
    chunks = []
    current_chunk = {"start": 0, "end": 0, "text": ""}

    for seg in segments:
        seg_text = seg.get("text", "").strip()
        if not seg_text:
            continue

        # Start a new chunk if this one would be too long
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


def generate_recap(
    video_path: str,
    output_path: str,
    transcript: list[dict],
    voice: str = "hi-IN-MadhurNeural",
    chunk_duration: float = 45.0,
    progress_callback=None,
) -> dict:
    """
    Generate a Hindi recap video.

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

    _progress(5, "Chunking transcript...")

    # Step 1: Chunk transcript into scenes
    chunks = chunk_segments(transcript, chunk_duration)
    if not chunks:
        raise Exception("No transcript segments found")

    _progress(10, f"Found {len(chunks)} scenes to narrate")

    # Step 2: Translate all chunks to Hindi
    _progress(15, "Translating to Hindi...")
    scenes = []
    for i, chunk in enumerate(chunks):
        pct = 15 + (i / len(chunks)) * 20
        _progress(pct, f"Translating scene {i+1}/{len(chunks)}...")
        hindi_text = translate_to_hindi(chunk["text"])
        scenes.append(RecapScene(
            start=chunk["start"],
            end=chunk["end"],
            english_text=chunk["text"],
            hindi_text=hindi_text,
        ))

    _progress(35, "Generating Hindi audio...")

    # Step 3: Generate TTS for each scene
    temp_dir = tempfile.mkdtemp(prefix="recap_")
    for i, scene in enumerate(scenes):
        pct = 35 + (i / len(scenes)) * 25
        _progress(pct, f"Generating audio {i+1}/{len(scenes)}...")

        audio_path = os.path.join(temp_dir, f"narration_{i:03d}.mp3")
        asyncio.run(_generate_tts(scene.hindi_text, audio_path, voice))
        scene.audio_path = audio_path

    _progress(60, "Creating silent base video...")

    # Step 4: Mute original audio
    silent_path = os.path.join(temp_dir, "silent.mp4")
    cmd_silent = [
        "ffmpeg", "-y", "-i", video_path,
        "-c:v", "copy",
        "-an",  # Remove audio
        silent_path
    ]
    subprocess.run(cmd_silent, capture_output=True, check=True)

    _progress(65, "Building narration timeline...")

    # Step 5: Build the narration audio track with proper timing
    # Create a silent base audio matching video duration
    # Get video duration
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", video_path
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(json.loads(probe_result.stdout)["format"]["duration"])

    # Generate silence for the full duration
    silence_path = os.path.join(temp_dir, "silence.wav")
    cmd_silence = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(duration),
        "-q:a", "9",
        silence_path
    ]
    subprocess.run(cmd_silence, capture_output=True, check=True)

    # Get durations of each narration audio
    narration_parts = []
    for i, scene in enumerate(scenes):
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", scene.audio_path
        ]
        r = subprocess.run(probe_cmd, capture_output=True, text=True)
        audio_dur = float(json.loads(r.stdout)["format"]["duration"])
        narration_parts.append({
            "index": i,
            "start": scene.start,
            "audio": scene.audio_path,
            "audio_dur": audio_dur,
            "scene_end": scene.end,
        })

    _progress(70, "Mixing narration into video...")

    # Build complex filter to place each narration at the right time
    inputs = ["-i", silence_path]
    for part in narration_parts:
        inputs.extend(["-i", part["audio"]])

    filter_parts = []
    for idx, part in enumerate(narration_parts):
        input_idx = idx + 1  # first input is silence
        # Delay each narration to start at scene time
        delay_ms = int(part["start"] * 1000)
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},apad[a{idx}]")

    # Mix all narration tracks with the silence base
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
        "-t", str(duration),
        narration_track
    ]
    subprocess.run(cmd_mix, capture_output=True, check=True)

    _progress(85, "Combining video + Hindi audio...")

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
        "duration": round(duration, 1),
        "scenes_detail": [
            {
                "start": round(s.start, 1),
                "end": round(s.end, 1),
                "english": s.english_text[:200],
                "hindi": s.hindi_text[:200],
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
