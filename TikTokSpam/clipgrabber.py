# clip_grabber.py
# Interactive YouTube clipper: download -> optional trim -> title + tags -> file+json in tagged folder
# Requires: yt-dlp, ffmpeg on PATH

import os
import re
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from yt_dlp import YoutubeDL
except Exception:
    raise SystemExit("yt-dlp not found. Install with:  py -m pip install yt-dlp")

# ---------------- CONFIG ----------------
VIDEOS_ROOT = Path("videos")   # base folder where clips go
VIDEOS_ROOT.mkdir(parents=True, exist_ok=True)

# If any of these tags appear, their FIRST match decides the primary subfolder
# (order matters). Example: tags: ["shane", "smosh"] -> videos/smosh/
IMPORTANT_TAG_DIRS = [
    "smosh",
    "shane",
    "spencer",
    "damien",
    "ify",
    "podcast",
    "standup",
]

# Output quality when trimming (re-encode for accuracy).
# Change to "copy" for very fast but less accurate cuts on non-keyframes.
FFMPEG_VIDEO_CODEC = "libx264"
FFMPEG_AUDIO_CODEC = "aac"
FFMPEG_CRF = "18"
FFMPEG_PRESET = "veryfast"
TARGET_CONTAINER = "mp4"

# ----------------------------------------

SAFE_CHARS = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def sanitize_filename(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    return "".join(c for c in name if c in SAFE_CHARS).strip()

def parse_timestamp(ts: str) -> Optional[float]:
    """
    Accepts: ss | mm:ss | hh:mm:ss (also allows decimals like 01:23.5)
    Returns seconds (float) or None for blank.
    """
    if not ts:
        return None
    ts = ts.strip()
    if not ts:
        return None
    parts = ts.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            m = int(parts[0])
            s = float(parts[1])
            return m * 60 + s
        elif len(parts) == 3:
            h = int(parts[0]); m = int(parts[1]); s = float(parts[2])
            return h * 3600 + m * 60 + s
        else:
            return None
    except ValueError:
        return None

def ask(prompt: str, default: Optional[str] = None) -> str:
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
        return default if val == "" else val
    return input(f"{prompt}: ").strip()

def choose_primary_dir(tags: List[str]) -> Path:
    tag_set = {t.lower() for t in tags}
    for key in IMPORTANT_TAG_DIRS:
        if key.lower() in tag_set:
            p = VIDEOS_ROOT / key
            p.mkdir(parents=True, exist_ok=True)
            return p
    return VIDEOS_ROOT

def extract_info(url: str) -> dict:
    ydl_opts = {"quiet": True, "skip_download": True}
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_best(url: str, tmp_dir: Path) -> Path:
    """
    Download to a temp file (best mp4 if possible). Returns the media file path.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(tmp_dir / "%(title)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "merge_output_format": TARGET_CONTAINER,
        "quiet": False,
        "format": "bv*+ba/b",
        "noprogress": False,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # yt-dlp returns the final filename this way:
        filename = ydl.prepare_filename(info)
        # ensure extension is container if merged
        path = Path(filename)
        if path.suffix.lower() != f".{TARGET_CONTAINER}" and (path.with_suffix(f".{TARGET_CONTAINER}")).exists():
            path = path.with_suffix(f".{TARGET_CONTAINER}")
        return path

def ffmpeg_trim(src: Path, dst: Path, start: float, end: float) -> None:
    """
    Accurate re-encode trim. If you want a fast (keyframe) cut, replace codecs with -c copy.
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        raise ValueError("End must be greater than start for trimming.")
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-c:v", FFMPEG_VIDEO_CODEC, "-crf", FFMPEG_CRF, "-preset", FFMPEG_PRESET,
        "-c:a", FFMPEG_AUDIO_CODEC,
        str(dst),
    ]
    print("Running:", " ".join(shlex.quote(x) for x in cmd))
    subprocess.run(cmd, check=True)

def write_sidecar_json(video_path: Path, tags: List[str]) -> None:
    data = {"tags": tags}
    video_path.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")

def loop():
    print("\nYouTube Clip Grabber — paste a link to begin. Press Enter on an empty prompt to exit.\n")
    while True:
        url = ask("YouTube URL (empty to quit)")
        if not url:
            print("Goodbye.")
            return

        try:
            info = extract_info(url)
            suggested_title = info.get("title") or ""
        except Exception as e:
            print(f"Could not fetch info ({e}). You can still try to download.")
            suggested_title = ""

        # Download first (so we can preview duration if needed)
        tmp_dir = Path(".tmp_dl")
        try:
            media_path = download_best(url, tmp_dir)
        except Exception as e:
            print(f"Download failed: {e}")
            continue

        # Ask for title and tags
        title = ask("Clip title", default=suggested_title) or suggested_title or "untitled"
        title = sanitize_filename(title)

        raw_tags = ask("Tags (comma/space separated, e.g. 'shane, smosh')")
        # split on comma OR spaces
        tag_list = [t.strip().lower() for t in re.split(r"[,\s]+", raw_tags) if t.strip()]
        if not tag_list:
            tag_list = ["untagged"]

        # Optional trim
        print("Optional: trim with start/end timestamps. Formats: ss | mm:ss | hh:mm:ss (blank = full video)")
        t1s = ask("Start time", default="")
        t2s = ask("End time", default="")
        t1 = parse_timestamp(t1s)
        t2 = parse_timestamp(t2s)

        # Decide destination directory
        dest_dir = choose_primary_dir(tag_list)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Build filename with [tags]
        tag_bracket = "[" + ", ".join(tag_list) + "]" if tag_list else ""
        base_name = (title + (" " + tag_bracket if tag_bracket else "")).strip()
        out_path = dest_dir / f"{base_name}.{TARGET_CONTAINER}"

        try:
            if t1 is not None and t2 is not None:
                # Trim to new file in dest_dir
                ffmpeg_trim(media_path, out_path, min(t1, t2), max(t1, t2))
                # remove temp download to save space
                try: media_path.unlink()
                except Exception: pass
            else:
                # No trim: move the original
                shutil.move(str(media_path), str(out_path))
        except subprocess.CalledProcessError as e:
            print("FFmpeg failed. Keeping original in .tmp_dl for inspection.")
            print(e)
            continue

        # Sidecar tags
        write_sidecar_json(out_path, tag_list)

        print(f"Saved: {out_path}")
        print(f"Tags JSON: {out_path.with_suffix('.json')}\n")

        # Clean tmp dir if empty
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

def main():
    # quick ffmpeg presence check
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception:
        print("FFmpeg not found on PATH. Install it and make sure 'ffmpeg' is callable.")
        return
    loop()

if __name__ == "__main__":
    while True:
        main()
        ans = input("\nGenerate more renditions? (Y/n): ").strip().lower()
        if ans.startswith("n"):
            print("Exiting generator.")
            break
