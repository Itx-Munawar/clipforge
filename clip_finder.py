"""AI-powered clip finder — detects viral moments from transcript."""

import re
from dataclasses import dataclass, field


@dataclass
class Clip:
    """A detected short clip."""
    start: float
    end: float
    text: str
    score: float = 0.0
    reason: str = ""


# --- Viral signal patterns ---

# High-engagement words that signal exciting/emotional moments
VIRAL_KEYWORDS = {
    # Surprise/shock
    "shocking", "unbelievable", "insane", "crazy", "wow", "oh my god",
    "no way", "wait what", "what", "omg", "bro", "dude",
    # Humor
    "hilarious", "funny", "laughing", "lmao", "rofl", "joke",
    # Drama
    "drama", "fight", "argument", "called out", "exposed", "destroyed",
    "roasted", "slammed", "fired",
    # Motivation
    "success", "million", "billion", "secret", "hack", "trick",
    "nobody tells you", "truth", "real", "honest",
    # Questions (engagement drivers)
    "why", "how", "what if", "did you know", "ever wondered",
    # Story hooks
    "so then", "and then", "suddenly", "out of nowhere", "turns out",
    "the problem is", "here's the thing", "listen",
    # Numbers/Lists
    "top", "best", "worst", "first", "last", "only", "never", "always",
    "three things", "five ways", "number one",
}

# Patterns that signal high-energy moments
EXCITEMENT_PATTERNS = [
    r"!{2,}",           # Multiple exclamation marks
    r"\?{2,}",          # Multiple question marks
    r"oh+ my+ god+",    # Oh my god variations
    r"no+\s+way",       # No way
    r"holy\s+\w+",     # Holy ...
    r"what\s+the",     # What the
    r"let's\s+go",     # Let's go
    r"hold\s+on",      # Hold on
    r"wait\s+for\s+it", # Wait for it
]

# Question patterns (drive engagement)
QUESTION_PATTERN = r"\b(why|how|what if|did you know|ever wondered|want to know|guess what)\b"


def score_segment(segment: dict) -> tuple[float, str]:
    """Score a transcript segment for viral potential."""
    text = segment["text"].lower()
    reasons = []
    score = 0.0

    # 1. Keyword matching (up to 30 points)
    keyword_hits = sum(1 for kw in VIRAL_KEYWORDS if kw in text)
    if keyword_hits > 0:
        kw_score = min(keyword_hits * 6, 30)
        score += kw_score
        reasons.append(f"keywords({keyword_hits})")

    # 2. Excitement patterns (up to 20 points)
    pattern_hits = sum(1 for p in EXCITEMENT_PATTERNS if re.search(p, text))
    if pattern_hits > 0:
        score += min(pattern_hits * 10, 20)
        reasons.append(f"excitement({pattern_hits})")

    # 3. Questions drive engagement (up to 15 points)
    if re.search(QUESTION_PATTERN, text):
        score += 15
        reasons.append("question")

    # 4. Short, punchy statements are more viral (up to 15 points)
    words = text.split()
    word_count = len(words)
    if 5 <= word_count <= 25:
        score += 15
        reasons.append("punchy")
    elif 3 <= word_count <= 5:
        score += 10
        reasons.append("short")

    # 5. Emotional intensity (caps, exclamation)
    caps_ratio = sum(1 for c in segment["text"] if c.isupper()) / max(len(segment["text"]), 1)
    if caps_ratio > 0.3:
        score += 10
        reasons.append("intensity")

    # 6. Pause/drama before or after (silence = tension)
    duration = segment["end"] - segment["start"]
    if 2.0 <= duration <= 8.0:
        score += 10
        reasons.append("good_duration")

    return score, ", ".join(reasons)


def find_clips(
    segments: list[dict],
    clip_duration: float = 30.0,
    max_clips: int = 10,
    min_score: float = 15.0,
) -> list[Clip]:
    """
    Find the best viral clips from transcript segments.

    Strategy:
    1. Score each segment individually
    2. Group consecutive high-scoring segments into clips
    3. Rank and return top N clips
    """
    if not segments:
        return []

    # Score all segments
    scored = []
    for seg in segments:
        score, reason = score_segment(seg)
        scored.append({**seg, "score": score, "reason": reason})

    # Find clip candidates by sliding window
    clips = []
    used_ranges = []

    # Strategy 1: Find the highest-scoring single segments and expand them
    sorted_segs = sorted(enumerate(scored), key=lambda x: x[1]["score"], reverse=True)

    for idx, seg in sorted_segs:
        if seg["score"] < min_score:
            break

        # Expand from this high-score point
        clip_start = seg["start"]
        clip_end = seg["end"]

        # Expand backwards to fill clip_duration
        remaining_before = (clip_duration - (clip_end - clip_start)) / 2
        remaining_after = (clip_duration - (clip_end - clip_start)) / 2

        # Find segments before
        for s in reversed(scored[:idx]):
            if s["start"] >= clip_start - remaining_before:
                clip_start = min(clip_start, s["start"])
            else:
                break

        # Find segments after
        for s in scored[idx + 1:]:
            if s["end"] <= clip_end + remaining_after:
                clip_end = max(clip_end, s["end"])
            else:
                break

        # Clamp to clip_duration
        if clip_end - clip_start > clip_duration:
            clip_end = clip_start + clip_duration

        # Check overlap with existing clips
        overlap = False
        for used_start, used_end in used_ranges:
            if not (clip_end <= used_start or clip_start >= used_end):
                overlap = True
                break

        if overlap:
            continue

        # Collect text for this clip
        clip_text = " ".join(
            s["text"] for s in scored
            if s["start"] >= clip_start - 0.5 and s["end"] <= clip_end + 0.5
        )

        clip = Clip(
            start=round(clip_start, 2),
            end=round(clip_end, 2),
            text=clip_text.strip(),
            score=seg["score"],
            reason=seg["reason"]
        )
        clips.append(clip)
        used_ranges.append((clip_start, clip_end))

        if len(clips) >= max_clips:
            break

    # If we don't have enough clips, lower threshold and fill with best remaining
    if len(clips) < max_clips and segments:
        # Use remaining segments sorted by duration as fallback
        fallback_segs = sorted(enumerate(scored), key=lambda x: x[1]["score"], reverse=True)
        for idx, seg in fallback_segs:
            if len(clips) >= max_clips:
                break
            clip_start = seg["start"]
            clip_end = min(seg["start"] + clip_duration, seg["end"] + 5)

            # Check overlap
            overlap = False
            for used_start, used_end in used_ranges:
                if not (clip_end <= used_start or clip_start >= used_end):
                    overlap = True
                    break
            if overlap:
                continue

            clip_text = " ".join(
                s["text"] for s in scored
                if s["start"] >= clip_start - 0.5 and s["end"] <= clip_end + 0.5
            )
            clip = Clip(
                start=round(clip_start, 2),
                end=round(clip_end, 2),
                text=clip_text.strip() or seg["text"],
                score=seg["score"],
                reason=seg["reason"] or "fallback"
            )
            clips.append(clip)
            used_ranges.append((clip_start, clip_end))

    # Sort by start time
    clips.sort(key=lambda c: c.start)

    return clips[:max_clips]


def split_sequential_clips(
    video_duration: float,
    transcript: list[dict],
    clip_duration: float = 30.0,
    max_clips: int = 10,
) -> list[Clip]:
    """Split video into sequential clips: 0-30s, 31-60s, 61-90s, etc."""
    clips = []
    start = 0.0

    for i in range(max_clips):
        end = min(start + clip_duration, video_duration)
        if start >= video_duration:
            break

        # Collect transcript text for this time range
        text = " ".join(
            seg["text"].strip() for seg in transcript
            if seg.get("start", 0) >= start - 0.5 and seg.get("end", 0) <= end + 0.5
        )

        clips.append(Clip(
            start=round(start, 2),
            end=round(end, 2),
            text=text.strip(),
            score=0,
            reason="sequential",
        ))

        start = end

    return clips


if __name__ == "__main__":
    # Test with sample data
    test_segments = [
        {"start": 0, "end": 3, "text": "So here's the thing about AI..."},
        {"start": 3, "end": 6, "text": "Nobody tells you this but it's insane"},
        {"start": 6, "end": 10, "text": "Oh my god this changed everything"},
        {"start": 10, "end": 14, "text": "The secret is actually very simple"},
        {"start": 14, "end": 18, "text": "And then suddenly it all made sense"},
    ]
    clips = find_clips(test_segments)
    for c in clips:
        print(f"[{c.start:.1f}s - {c.end:.1f}s] score={c.score:.0f} | {c.text}")
