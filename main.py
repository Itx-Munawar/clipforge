#!/usr/bin/env python3
"""
YouTube Shorts Maker — Free, local AI clip maker
Turns any YouTube video into viral short clips with captions.

Usage:
    python main.py <youtube_url> [options]

Options:
    --clips N         Number of clips to generate (default: 5)
    --duration N      Max clip duration in seconds (default: 30)
    --model SIZE      Whisper model size: tiny/base/small/medium (default: base)
    --output DIR      Output directory (default: output)
    --caption-pos POS Caption position: center/bottom (default: center)
    --upload          Auto-upload clips to YouTube Shorts
    --schedule        Schedule uploads at specific times (requires --upload)
    --interval N      Minutes between scheduled uploads (default: 180)
    --start-time T    First publish time in ISO format (e.g. 2025-01-15T18:00:00Z)
    --privacy STATUS  Upload privacy: public/unlisted/private (default: unlisted)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from downloader import download_video
from transcriber import transcribe
from clip_finder import find_clips, Clip
from video_processor import (
    process_clip,
    add_subtitles_from_words,
    CaptionStyle,
)


def print_banner():
    print("")
    print("==========================================================")
    print("   YouTube Shorts Maker -- Free & Local")
    print("   AI-powered clip finder + captioner")
    print("==========================================================")
    print("")


def print_clips(clips):
    """Pretty-print detected clips."""
    print("")
    print("=" * 60)
    print(f"  Found {len(clips)} viral clips:")
    print("=" * 60)
    for i, clip in enumerate(clips, 1):
        duration = clip.end - clip.start
        print(f"\n  Clip #{i}  Score: {clip.score:.0f}  {duration:.1f}s")
        print(f"  [{clip.start:.1f}s -> {clip.end:.1f}s]")
        text_preview = clip.text[:80] + ("..." if len(clip.text) > 80 else "")
        print(f'  "{text_preview}"')
        print(f"  Reason: {clip.reason}")
    print("")
    print("=" * 60)
    print("")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Maker -- AI-powered clip maker"
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--clips", type=int, default=5, help="Number of clips (default: 5)")
    parser.add_argument("--duration", type=int, default=30, help="Max clip duration in seconds (default: 30)")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--output", default="output", help="Output directory (default: output)")
    parser.add_argument("--caption-pos", default="center", choices=["center", "bottom"],
                        help="Caption position (default: center)")
    parser.add_argument("--upload", action="store_true",
                        help="Auto-upload clips to YouTube Shorts")
    parser.add_argument("--schedule", action="store_true",
                        help="Schedule uploads at specific times (with --upload)")
    parser.add_argument("--interval", type=int, default=180,
                        help="Minutes between scheduled uploads (default: 180)")
    parser.add_argument("--start-time", type=str, default=None,
                        help="First publish time (ISO format, e.g. 2025-01-15T18:00:00Z)")
    parser.add_argument("--privacy", default="unlisted", choices=["public", "unlisted", "private"],
                        help="Upload privacy (default: unlisted)")

    args = parser.parse_args()

    print_banner()

    # Validate scheduling args
    if args.schedule and not args.upload:
        print("Error: --schedule requires --upload")
        sys.exit(1)

    if args.start_time:
        try:
            start_dt = datetime.fromisoformat(args.start_time.replace("Z", "+00:00"))
        except ValueError:
            print(f"Error: Invalid --start-time format. Use ISO format like: 2025-01-15T18:00:00Z")
            sys.exit(1)
    else:
        start_dt = None

    # Create output directory
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()

    # -- Step 1: Download --
    print("Step 1/4: Downloading video...")
    video_path = download_video(args.url, output_dir="temp")

    # -- Step 2: Transcribe --
    print("\nStep 2/4: Transcribing with AI...")
    segments = transcribe(video_path, model_size=args.model)

    # Save transcript
    transcript_path = os.path.join(output_dir, "transcript.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)
    print(f"   Saved transcript -> {transcript_path}")

    # -- Step 3: Find viral clips --
    print("\nStep 3/4: Finding viral moments...")
    clips = find_clips(
        segments,
        clip_duration=args.duration,
        max_clips=args.clips,
        min_score=10.0,
    )

    if not clips:
        print("No clips found! Try a different video or lower --duration.")
        sys.exit(1)

    print_clips(clips)

    # -- Step 4: Process clips --
    print("Step 4/4: Processing clips...")

    # Get all words for captioning
    all_words = []
    for seg in segments:
        all_words.extend(seg.get("words", []))

    caption_style = CaptionStyle(position=args.caption_pos)

    exported = []
    for i, clip in enumerate(clips, 1):
        clip_words = [
            w for w in all_words
            if w["start"] >= clip.start - 0.5 and w["end"] <= clip.end + 0.5
        ]
        captions = add_subtitles_from_words(clip_words, words_per_group=4)

        output_file = os.path.join(output_dir, f"clip_{i:02d}.mp4")

        try:
            process_clip(
                video_path=video_path,
                start=clip.start,
                end=clip.end,
                captions=captions,
                output_path=output_file,
                caption_style=caption_style,
            )
            exported.append(output_file)
        except Exception as e:
            print(f"Failed to process clip #{i}: {e}")

    # -- Step 5: Upload (optional) --
    if args.upload and exported:
        print(f"\n{'='*60}")

        if args.schedule:
            print(f"  Step 5: Scheduling uploads...")
        else:
            print(f"  Step 5: Uploading to YouTube Shorts...")

        print(f"{'='*60}")

        if args.schedule:
            # Use schedule_upload_batch for scheduled uploads
            from uploader import schedule_upload_batch, _generate_schedule, _format_schedule

            titles = [f"Clip {i}" for i in range(1, len(exported) + 1)]
            descriptions = []
            for clip in clips:
                descriptions.append(clip.text[:200] if clip.text else "")

            # Generate and display schedule first
            schedule = _generate_schedule(len(exported), start_dt, args.interval)
            print("")
            print(_format_schedule(schedule))
            print("")

            # Ask for confirmation
            try:
                confirm = input("  Proceed with this schedule? (y/n): ").strip().lower()
                if confirm not in ("y", "yes", ""):
                    print("  Schedule cancelled.")
                    return exported
            except (EOFError, KeyboardInterrupt):
                print("\n  Schedule cancelled.")
                return exported

            upload_results = schedule_upload_batch(
                video_paths=exported,
                start_time=start_dt,
                interval_minutes=args.interval,
                titles=titles,
                descriptions=descriptions,
                output_dir=output_dir,
            )
        else:
            # Immediate upload (no scheduling)
            from uploader import upload_short

            upload_results = []
            for i, clip_path in enumerate(exported, 1):
                print(f"\n  Uploading clip {i}/{len(exported)}...")

                clip_index = i - 1
                clip_desc = clips[clip_index].text[:200] if clip_index < len(clips) else ""

                try:
                    result = upload_short(
                        video_path=clip_path,
                        title=f"Clip {i}",
                        description=clip_desc,
                        privacy_status=args.privacy,
                    )
                    upload_results.append(result)
                    print(f"  {result['url']}")

                    if i < len(exported):
                        print("  Waiting 5s before next upload...")
                        time.sleep(5)

                except FileNotFoundError as e:
                    print(f"\n  {e}")
                    print("  Upload skipped. Set up YouTube API credentials first.")
                    break
                except Exception as e:
                    print(f"  Upload failed: {e}")
                    upload_results.append({"error": str(e)})

        # Save upload results
        upload_log = os.path.join(output_dir, "upload_results.json")
        with open(upload_log, "w", encoding="utf-8") as f:
            json.dump(upload_results, f, indent=2, ensure_ascii=False)
        print(f"\n  Upload results saved to {upload_log}")

    # -- Done --
    elapsed = time.time() - start_time
    print("")
    print("=" * 60)
    print(f"  Done! Generated {len(exported)} shorts in {elapsed:.1f}s")
    print(f"  Output folder: {output_dir}")
    print("=" * 60)

    # Cleanup temp files
    try:
        os.remove(video_path)
        print("Cleaned up temp files")
    except:
        pass

    return exported


if __name__ == "__main__":
    main()
