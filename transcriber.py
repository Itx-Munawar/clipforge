"""Transcribe video audio using faster-whisper."""

import os
import subprocess

# Lazy import to avoid slow startup
_model = None


def get_model(model_size: str = "base"):
    """Load or return cached Whisper model."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"Loading Whisper model ({model_size})...")
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Model loaded!")
    return _model


def extract_audio(video_path: str, audio_path: str = None) -> str:
    """Extract audio from video file."""
    if audio_path is None:
        audio_path = video_path.rsplit(".", 1)[0] + ".wav"

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-y", audio_path
    ]

    subprocess.run(cmd, capture_output=True, check=True)
    return audio_path


def transcribe(video_path: str, model_size: str = "base") -> list[dict]:
    """
    Transcribe video and return word-level timestamps.
    
    Returns list of segments:
    [
        {"start": 0.0, "end": 2.5, "text": "Hello world"},
        {"start": 2.5, "end": 5.1, "text": "This is a test"},
        ...
    ]
    """
    # Extract audio
    print("Extracting audio...")
    audio_path = extract_audio(video_path)

    # Transcribe
    print("Transcribing...")
    model = get_model(model_size)

    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        beam_size=5,
        vad_filter=False,
    )

    result = []
    for segment in segments:
        words_data = []
        if segment.words:
            words_data = [
                {"word": w.word, "start": round(w.start, 2), "end": round(w.end, 2)}
                for w in segment.words
            ]

        result.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": words_data
        })

    # Cleanup temp audio
    try:
        os.remove(audio_path)
    except:
        pass

    print(f"Transcribed {len(result)} segments ({info.language})")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        segments = transcribe(sys.argv[1])
        for s in segments:
            print(f"[{s['start']:.1f}s - {s['end']:.1f}s] {s['text']}")
    else:
        print("Usage: python transcriber.py <video_path>")
