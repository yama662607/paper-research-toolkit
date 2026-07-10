#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Probe embedded (or standalone) video for completeness.

verify_deck.py only checks codec health via ffprobe — it cannot tell that a
video was TRUNCATED (render died before the animation/graph finished). This
script prints duration/frames/codec/size for each video and, with --thumb,
extracts each video's LAST frame so a human can confirm it plays to the end
(the last frame should show the finished state). Read-only on the input deck.

Usage:
  check_video.py DECK.pptx [--slide N] [--thumb DIR]
  check_video.py clip.mp4 --thumb DIR       # standalone video file
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".avi", ".wmv", ".mpg", ".mpeg", ".webm"}


def ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        sys.exit(f"error: ffprobe failed on {path.name}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout)


def report(name: str, path: Path, thumb_dir: Path | None) -> None:
    info = ffprobe(path)
    vstreams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    duration = info.get("format", {}).get("duration")
    print(f"\n{name}")
    print(f"  duration:   {float(duration):.2f} s" if duration else "  duration:   (unknown)")
    if vstreams:
        v = vstreams[0]
        print(f"  nb_frames:  {v.get('nb_frames', '(not in container)')}")
        print(f"  codec_name: {v.get('codec_name', '?')}")
        print(f"  size:       {v.get('width', '?')}x{v.get('height', '?')}")
    else:
        print("  WARNING: no video stream found")
    if thumb_dir is not None:
        thumb_dir.mkdir(parents=True, exist_ok=True)
        out = thumb_dir / f"{Path(name).stem}_last.png"
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-sseof", "-0.1", "-i", str(path),
             "-frames:v", "1", "-update", "1", "-y", str(out)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0 and out.is_file():
            print(f"  last frame: {out}  <- confirm this shows the FINISHED state")
        else:
            print(f"  WARNING: last-frame extraction failed: {proc.stderr.strip()[:200]}")


def slide_video_names(zf: zipfile.ZipFile, slide: int) -> set[str]:
    """Media basenames referenced by slide N's relationships."""
    rels = f"ppt/slides/_rels/slide{slide}.xml.rels"
    try:
        xml = zf.read(rels).decode("utf-8", errors="replace")
    except KeyError:
        sys.exit(f"error: {rels} not found — does slide {slide} exist?")
    names = set()
    for target in re.findall(r'Target="([^"]+)"', xml):
        p = Path(target)
        if "media" in target and p.suffix.lower() in VIDEO_EXTS:
            names.add(p.name)
    return names


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path, help=".pptx deck or standalone video file")
    ap.add_argument("--slide", type=int, default=None,
                    help="only check video(s) referenced by this slide (1-indexed)")
    ap.add_argument("--thumb", type=Path, default=None,
                    help="also extract each video's LAST frame as PNG into this dir")
    args = ap.parse_args()

    if not args.input.is_file():
        sys.exit(f"error: input not found: {args.input}")
    for tool in ("ffprobe",) + (("ffmpeg",) if args.thumb else ()):
        if shutil.which(tool) is None:
            sys.exit(
                f"error: {tool} not found on PATH. Install ffmpeg with the "
                "OS-appropriate package manager after user consent."
            )

    if args.input.suffix.lower() in VIDEO_EXTS:
        report(args.input.name, args.input, args.thumb)
        return

    if not zipfile.is_zipfile(args.input):
        sys.exit(f"error: not a video and not a valid .pptx (zip): {args.input}")
    with zipfile.ZipFile(args.input) as zf:
        media = [n for n in zf.namelist()
                 if n.startswith("ppt/media/")
                 and Path(n).suffix.lower() in VIDEO_EXTS]
        if args.slide is not None:
            wanted = slide_video_names(zf, args.slide)
            media = [n for n in media if Path(n).name in wanted]
            if not media:
                sys.exit(f"error: slide {args.slide} references no embedded video")
        if not media:
            sys.exit("error: no embedded video found under ppt/media/")

        with tempfile.TemporaryDirectory(prefix="check_video_") as tmp:
            for name in sorted(media):
                dst = Path(tmp) / Path(name).name
                dst.write_bytes(zf.read(name))
                report(Path(name).name, dst, args.thumb)

    print("\nReminder: a sane duration alone does not prove completeness — "
          "check the last frame shows the animation/graph fully finished.")


if __name__ == "__main__":
    main()
