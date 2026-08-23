#!/usr/bin/env python3
"""
YouTube Shorts Maker — GUI Interface
A graphical interface for the AI-powered clip maker.

Run with: python gui.py
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime, timedelta, timezone

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class YouTubeShortsGUI:
    """Main GUI application."""

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Shorts Maker")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)
        self.root.configure(bg="#1e1e2e")

        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._setup_styles()

        # Variables
        self.url_var = tk.StringVar()
        self.clips_var = tk.IntVar(value=5)
        self.duration_var = tk.IntVar(value=30)
        self.model_var = tk.StringVar(value="base")
        self.output_var = tk.StringVar(value="output")
        self.caption_pos_var = tk.StringVar(value="center")
        self.upload_var = tk.BooleanVar(value=False)
        self.schedule_var = tk.BooleanVar(value=False)
        self.interval_var = tk.IntVar(value=180)
        self.start_time_var = tk.StringVar(value="")
        self.privacy_var = tk.StringVar(value="unlisted")

        self.is_running = False
        self.stop_flag = False

        self._build_ui()

    def _setup_styles(self):
        """Configure dark theme styles."""
        bg = "#1e1e2e"
        fg = "#cdd6f4"
        accent = "#89b4fa"
        surface = "#313244"
        overlay = "#45475a"

        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        self.style.configure("Accent.TButton", background=accent, foreground="#1e1e2e")
        self.style.configure("TCheckbutton", background=bg, foreground=fg, font=("Segoe UI", 10))
        self.style.configure("TCombobox", font=("Segoe UI", 10))
        self.style.configure("TEntry", font=("Segoe UI", 10))
        self.style.configure("TLabelframe", background=bg, foreground=fg, font=("Segoe UI", 11, "bold"))
        self.style.configure("TLabelframe.Label", background=bg, foreground=accent, font=("Segoe UI", 11, "bold"))
        self.style.configure("Header.TLabel", background=bg, foreground=accent, font=("Segoe UI", 18, "bold"))
        self.style.configure("Sub.TLabel", background=bg, foreground="#a6adc8", font=("Segoe UI", 9))
        self.style.configure("Status.TLabel", background=bg, foreground="#a6e3a1", font=("Segoe UI", 10, "bold"))
        self.style.configure("Error.TLabel", background=bg, foreground="#f38ba8", font=("Segoe UI", 10))

        # Notebook (tabs)
        self.style.configure("TNotebook", background=bg)
        self.style.configure("TNotebook.Tab", background=surface, foreground=fg,
                             font=("Segoe UI", 10), padding=[12, 6])
        self.style.map("TNotebook.Tab",
                       background=[("selected", accent)],
                       foreground=[("selected", "#1e1e2e")])

    def _build_ui(self):
        """Build the complete UI."""
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=20, pady=(15, 5))
        ttk.Label(header, text="YouTube Shorts Maker", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="AI-powered clip finder + captioner + uploader", style="Sub.TLabel").pack(anchor="w")

        # Notebook (tabs)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=15, pady=10)

        # Tab 1: Generate
        gen_frame = ttk.Frame(notebook)
        notebook.add(gen_frame, text="  Generate  ")
        self._build_generate_tab(gen_frame)

        # Tab 2: Upload
        upload_frame = ttk.Frame(notebook)
        notebook.add(upload_frame, text="  Upload  ")
        self._build_upload_tab(upload_frame)

        # Bottom: Log + Buttons
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Log output
        log_frame = ttk.LabelFrame(bottom, text="Output Log")
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, bg="#181825", fg="#cdd6f4",
            font=("Consolas", 9), insertbackground="#cdd6f4",
            relief="flat", borderwidth=0
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text.configure(state="disabled")

        # Buttons
        btn_frame = ttk.Frame(bottom)
        btn_frame.pack(fill="x", pady=(8, 0))

        self.run_btn = tk.Button(
            btn_frame, text="Generate Clips", font=("Segoe UI", 11, "bold"),
            bg="#89b4fa", fg="#1e1e2e", activebackground="#74c7ec",
            relief="flat", padx=20, pady=8, command=self._on_generate
        )
        self.run_btn.pack(side="left")

        self.upload_btn = tk.Button(
            btn_frame, text="Upload to YouTube", font=("Segoe UI", 11, "bold"),
            bg="#a6e3a1", fg="#1e1e2e", activebackground="#94e2d5",
            relief="flat", padx=20, pady=8, command=self._on_upload
        )
        self.upload_btn.pack(side="left", padx=(10, 0))

        self.stop_btn = tk.Button(
            btn_frame, text="Stop", font=("Segoe UI", 11, "bold"),
            bg="#f38ba8", fg="#1e1e2e", activebackground="#eba0ac",
            relief="flat", padx=20, pady=8, command=self._on_stop
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(btn_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side="right")

    def _build_generate_tab(self, parent):
        """Build the Generate tab."""
        # URL input
        url_frame = ttk.LabelFrame(parent, text="Video Source")
        url_frame.pack(fill="x", padx=10, pady=10)

        url_row = ttk.Frame(url_frame)
        url_row.pack(fill="x", padx=10, pady=8)
        ttk.Label(url_row, text="YouTube URL:").pack(side="left")
        url_entry = ttk.Entry(url_row, textvariable=self.url_var, font=("Segoe UI", 10))
        url_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # Settings grid
        settings_frame = ttk.LabelFrame(parent, text="Clip Settings")
        settings_frame.pack(fill="x", padx=10, pady=(0, 10))

        grid = ttk.Frame(settings_frame)
        grid.pack(fill="x", padx=10, pady=10)

        # Row 1
        ttk.Label(grid, text="Number of clips:").grid(row=0, column=0, sticky="w", pady=4)
        clips_spin = ttk.Spinbox(grid, from_=1, to=20, textvariable=self.clips_var, width=8)
        clips_spin.grid(row=0, column=1, sticky="w", padx=(10, 30))

        ttk.Label(grid, text="Max duration (sec):").grid(row=0, column=2, sticky="w", pady=4)
        dur_spin = ttk.Spinbox(grid, from_=5, to=60, textvariable=self.duration_var, width=8)
        dur_spin.grid(row=0, column=3, sticky="w", padx=(10, 0))

        # Row 2
        ttk.Label(grid, text="Whisper model:").grid(row=1, column=0, sticky="w", pady=4)
        model_combo = ttk.Combobox(grid, textvariable=self.model_var,
                                   values=["tiny", "base", "small", "medium"],
                                   state="readonly", width=8)
        model_combo.grid(row=1, column=1, sticky="w", padx=(10, 30))

        ttk.Label(grid, text="Caption position:").grid(row=1, column=2, sticky="w", pady=4)
        cap_combo = ttk.Combobox(grid, textvariable=self.caption_pos_var,
                                values=["center", "bottom"],
                                state="readonly", width=8)
        cap_combo.grid(row=1, column=3, sticky="w", padx=(10, 0))

        # Row 3
        ttk.Label(grid, text="Output folder:").grid(row=2, column=0, sticky="w", pady=4)
        out_entry = ttk.Entry(grid, textvariable=self.output_var, width=20)
        out_entry.grid(row=2, column=1, sticky="w", padx=(10, 30))

        # Model info
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill="x", padx=10)
        ttk.Label(info_frame, text="Model: tiny=fastest, base=balanced, small=better, medium=best",
                  style="Sub.TLabel").pack(anchor="w")

    def _build_upload_tab(self, parent):
        """Build the Upload tab."""
        # Upload settings
        upload_frame = ttk.LabelFrame(parent, text="Upload Settings")
        upload_frame.pack(fill="x", padx=10, pady=10)

        row1 = ttk.Frame(upload_frame)
        row1.pack(fill="x", padx=10, pady=8)
        ttk.Checkbutton(row1, text="Enable auto-upload to YouTube Shorts",
                       variable=self.upload_var).pack(side="left")

        row2 = ttk.Frame(upload_frame)
        row2.pack(fill="x", padx=10, pady=4)
        ttk.Label(row2, text="Privacy:").pack(side="left")
        priv_combo = ttk.Combobox(row2, textvariable=self.privacy_var,
                                  values=["public", "unlisted", "private"],
                                  state="readonly", width=12)
        priv_combo.pack(side="left", padx=(10, 0))

        # Schedule settings
        sched_frame = ttk.LabelFrame(parent, text="Schedule Settings")
        sched_frame.pack(fill="x", padx=10, pady=(0, 10))

        row3 = ttk.Frame(sched_frame)
        row3.pack(fill="x", padx=10, pady=8)
        ttk.Checkbutton(row3, text="Enable scheduled uploads",
                       variable=self.schedule_var).pack(side="left")

        row4 = ttk.Frame(sched_frame)
        row4.pack(fill="x", padx=10, pady=4)
        ttk.Label(row4, text="Interval (minutes):").pack(side="left")
        int_spin = ttk.Spinbox(row4, from_=10, to=1440, textvariable=self.interval_var, width=8)
        int_spin.pack(side="left", padx=(10, 30))

        ttk.Label(row4, text="Start time (ISO, optional):").pack(side="left")
        st_entry = ttk.Entry(row4, textvariable=self.start_time_var, width=25)
        st_entry.pack(side="left", padx=(10, 0))

        # Info
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill="x", padx=10)
        info_lines = [
            "Schedule: clips uploaded as private, auto-published at scheduled times.",
            "Start time: leave empty for now+10min. Format: 2025-01-15T18:00:00Z",
            "YouTube requires: min 10min between videos, max 60 days in future.",
        ]
        for line in info_lines:
            ttk.Label(info_frame, text=line, style="Sub.TLabel").pack(anchor="w")

    def _log(self, msg):
        """Append message to log."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def _set_status(self, msg, error=False):
        """Update status bar."""
        self.status_var.set(msg)
        self.status_label.configure(style="Error.TLabel" if error else "Status.TLabel")

    def _validate(self):
        """Validate inputs before running."""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return False
        if "youtube.com" not in url and "youtu.be" not in url:
            messagebox.showerror("Error", "Please enter a valid YouTube URL")
            return False
        if self.upload_var.get() and not os.path.exists("client_secret.json"):
            messagebox.showwarning("Warning",
                "client_secret.json not found.\n\n"
                "Upload will be skipped. Set up YouTube API first.\n"
                "See README.md for instructions.")
        return True

    def _on_generate(self):
        """Handle Generate button click."""
        if self.is_running:
            return
        if not self._validate():
            return

        self.is_running = True
        self.stop_flag = False
        self.run_btn.configure(state="disabled")
        self.upload_btn.configure(state="disabled")

        thread = threading.Thread(target=self._run_generate, daemon=True)
        thread.start()

    def _on_upload(self):
        """Handle Upload button click."""
        if self.is_running:
            return
        if not self._validate():
            return

        self.is_running = True
        self.stop_flag = False
        self.run_btn.configure(state="disabled")
        self.upload_btn.configure(state="disabled")

        thread = threading.Thread(target=self._run_upload, daemon=True)
        thread.start()

    def _on_stop(self):
        """Handle Stop button click."""
        self.stop_flag = True
        self._log("Stopping...")
        self._set_status("Stopping...")

    def _finish(self, success=True, msg="Done"):
        """Reset UI after operation."""
        self.is_running = False
        self.root.after(0, lambda: self.run_btn.configure(state="normal"))
        self.root.after(0, lambda: self.upload_btn.configure(state="normal"))
        if success:
            self.root.after(0, lambda: self._set_status(msg))
        else:
            self.root.after(0, lambda: self._set_status(msg, error=True))

    def _run_generate(self):
        """Run clip generation in background thread."""
        try:
            from downloader import download_video
            from transcriber import transcribe
            from clip_finder import find_clips
            from video_processor import process_clip, add_subtitles_from_words, CaptionStyle

            url = self.url_var.get().strip()
            output_dir = self.output_var.get().strip() or "output"
            os.makedirs(output_dir, exist_ok=True)

            # Step 1: Download
            self.root.after(0, lambda: self._log("Step 1/4: Downloading video..."))
            self.root.after(0, lambda: self._set_status("Downloading..."))
            video_path = download_video(url, output_dir="temp")
            self.root.after(0, lambda: self._log(f"Downloaded: {os.path.basename(video_path)}"))

            if self.stop_flag:
                self.root.after(0, lambda: self._log("Stopped by user."))
                self._finish(False, "Stopped")
                return

            # Step 2: Transcribe
            self.root.after(0, lambda: self._log("Step 2/4: Transcribing with AI..."))
            self.root.after(0, lambda: self._set_status("Transcribing..."))
            model = self.model_var.get()
            segments = transcribe(video_path, model_size=model)
            self.root.after(0, lambda: self._log(f"Transcribed {len(segments)} segments"))

            if self.stop_flag:
                self.root.after(0, lambda: self._log("Stopped by user."))
                self._finish(False, "Stopped")
                return

            # Step 3: Find clips
            self.root.after(0, lambda: self._log("Step 3/4: Finding viral moments..."))
            self.root.after(0, lambda: self._set_status("Finding clips..."))
            clips = find_clips(
                segments,
                clip_duration=self.duration_var.get(),
                max_clips=self.clips_var.get(),
                min_score=10.0,
            )

            if not clips:
                self.root.after(0, lambda: self._log("No clips found! Try a different video."))
                self._finish(False, "No clips found")
                return

            # Log clips
            for i, clip in enumerate(clips, 1):
                dur = clip.end - clip.start
                preview = clip.text[:60] + ("..." if len(clip.text) > 60 else "")
                self.root.after(0, lambda i=i, dur=dur, preview=preview, score=clip.score:
                    self._log(f"  Clip #{i}  Score:{score:.0f}  {dur:.1f}s  \"{preview}\""))

            if self.stop_flag:
                self.root.after(0, lambda: self._log("Stopped by user."))
                self._finish(False, "Stopped")
                return

            # Step 4: Process clips
            self.root.after(0, lambda: self._log("Step 4/4: Processing clips..."))
            self.root.after(0, lambda: self._set_status("Processing clips..."))

            all_words = []
            for seg in segments:
                all_words.extend(seg.get("words", []))

            caption_style = CaptionStyle(position=self.caption_pos_var.get())
            exported = []

            for i, clip in enumerate(clips, 1):
                if self.stop_flag:
                    break

                clip_words = [w for w in all_words
                             if w["start"] >= clip.start - 0.5 and w["end"] <= clip.end + 0.5]
                captions = add_subtitles_from_words(clip_words, words_per_group=4)
                output_file = os.path.join(output_dir, f"clip_{i:02d}.mp4")

                idx = i
                self.root.after(0, lambda idx=idx: self._set_status(f"Processing clip {idx}/{len(clips)}..."))

                try:
                    process_clip(
                        video_path=video_path, start=clip.start, end=clip.end,
                        captions=captions, output_path=output_file,
                        caption_style=caption_style,
                    )
                    exported.append(output_file)
                    self.root.after(0, lambda idx=idx: self._log(f"  Exported: clip_{idx:02d}.mp4"))
                except Exception as e:
                    self.root.after(0, lambda idx=idx, e=str(e): self._log(f"  Failed clip #{idx}: {e}"))

            # Cleanup
            try:
                os.remove(video_path)
            except:
                pass

            # Save transcript
            import json
            transcript_path = os.path.join(output_dir, "transcript.json")
            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(segments, f, indent=2, ensure_ascii=False)

            self.root.after(0, lambda: self._log(""))
            self.root.after(0, lambda: self._log(f"Done! Generated {len(exported)} shorts"))
            self.root.after(0, lambda: self._log(f"Output: {os.path.abspath(output_dir)}"))
            self._finish(True, f"Generated {len(exported)} shorts")

        except Exception as e:
            self.root.after(0, lambda: self._log(f"Error: {e}"))
            self._finish(False, f"Error: {e}")

    def _run_upload(self):
        """Run upload in background thread."""
        try:
            output_dir = self.output_var.get().strip() or "output"

            # Find clip files
            exported = []
            i = 1
            while True:
                path = os.path.join(output_dir, f"clip_{i:02d}.mp4")
                if os.path.exists(path):
                    exported.append(path)
                    i += 1
                else:
                    break

            if not exported:
                self.root.after(0, lambda: self._log("No clips found in output folder."))
                self.root.after(0, lambda: self._log("Generate clips first."))
                self._finish(False, "No clips to upload")
                return

            self.root.after(0, lambda: self._log(f"Found {len(exported)} clips to upload"))

            if self.schedule_var.get():
                # Scheduled upload
                from uploader import schedule_upload_batch, _generate_schedule, _format_schedule

                interval = self.interval_var.get()
                start_str = self.start_time_var.get().strip()
                start_dt = None
                if start_str:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

                schedule = _generate_schedule(len(exported), start_dt, interval)

                # Show schedule
                schedule_text = _format_schedule(schedule)
                self.root.after(0, lambda: self._log(""))
                self.root.after(0, lambda: self._log("Scheduled Uploads:"))
                for line in schedule_text.split("\n"):
                    self.root.after(0, lambda line=line: self._log(line))

                self.root.after(0, lambda: self._set_status("Uploading scheduled clips..."))

                titles = [f"Clip {i}" for i in range(1, len(exported) + 1)]
                results = schedule_upload_batch(
                    video_paths=exported,
                    start_time=start_dt,
                    interval_minutes=interval,
                    titles=titles,
                    output_dir=output_dir,
                )
            else:
                # Immediate upload
                from uploader import upload_short

                self.root.after(0, lambda: self._set_status("Uploading to YouTube..."))
                results = []

                for i, clip_path in enumerate(exported, 1):
                    if self.stop_flag:
                        break

                    self.root.after(0, lambda i=i, total=len(exported):
                        self._log(f"Uploading {i}/{total}..."))
                    self.root.after(0, lambda i=i, total=len(exported):
                        self._set_status(f"Uploading {i}/{total}..."))

                    try:
                        result = upload_short(
                            video_path=clip_path,
                            title=f"Clip {i}",
                            privacy_status=self.privacy_var.get(),
                        )
                        results.append(result)
                        url = result["url"]
                        self.root.after(0, lambda url=url: self._log(f"  {url}"))
                    except FileNotFoundError as e:
                        self.root.after(0, lambda: self._log("YouTube API not set up."))
                        self.root.after(0, lambda: self._log("See README.md for instructions."))
                        break
                    except Exception as e:
                        self.root.after(0, lambda e=str(e): self._log(f"  Failed: {e}"))

                    if i < len(exported):
                        import time
                        time.sleep(5)

            # Save results
            results_path = os.path.join(output_dir, "upload_results.json")
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            uploaded = sum(1 for r in results if "url" in r)
            self.root.after(0, lambda: self._log(""))
            self.root.after(0, lambda: self._log(f"Uploaded {uploaded}/{len(exported)} clips"))
            self._finish(True, f"Uploaded {uploaded} clips")

        except Exception as e:
            self.root.after(0, lambda: self._log(f"Error: {e}"))
            self._finish(False, f"Error: {e}")


def main():
    root = tk.Tk()
    app = YouTubeShortsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
