#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10.0"]
# ///
"""One-command READ-ONLY report of an existing .pptx deck, for understanding a
hand-made deck (no build script) BEFORE improving it.

Combines, per slide: the text (paragraph by paragraph), the shape-layout table
(kind, text preview, x/y/w/h in inches, rotation, picture sha1 — same columns
as dump_layout.py), and a media inventory (name, sha1, byte size, image dims
via PIL, video duration via ffprobe when available). The deck summary counts
slides, native equations (m:oMath), embedded videos, charts, tables, and
images. Everything is parsed straight from the pptx ZIP — no LibreOffice
needed. --render OUTDIR additionally shells out to the sibling
render_slides.py for APPROXIMATE PNG thumbnails (needs LibreOffice). The input
deck is never modified.

Usage: ingest_deck.py DECK.pptx [--slide N] [--json] [--render OUTDIR]
"""
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"a": A_NS, "p": P_NS, "r": R_NS}
EMU_PER_INCH = 914400.0

try:
    from PIL import Image
except ImportError:  # pragma: no cover - degrade gracefully
    Image = None


def slide_parts_in_order(zf: zipfile.ZipFile) -> list[str]:
    """Return slide part names (ppt/slides/slideN.xml) in presentation order."""
    pres_rels = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
    rid_to_target = {
        rel.get("Id"): rel.get("Target")
        for rel in pres_rels.findall(f"{{{REL_NS}}}Relationship")
    }
    pres = ET.fromstring(zf.read("ppt/presentation.xml"))
    parts = []
    for sld_id in pres.findall("p:sldIdLst/p:sldId", NS):
        target = rid_to_target.get(sld_id.get(f"{{{R_NS}}}id"))
        if target:
            parts.append(str(PurePosixPath("ppt") / PurePosixPath(target)))
    return parts


def slide_media_rels(zf: zipfile.ZipFile, slide_part: str) -> dict[str, str]:
    """Map rId -> media part name (ppt/media/...) for one slide."""
    p = PurePosixPath(slide_part)
    rels_part = str(p.parent / "_rels" / (p.name + ".rels"))
    if rels_part not in zf.namelist():
        return {}
    out = {}
    root = ET.fromstring(zf.read(rels_part))
    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        target = rel.get("Target", "")
        if rel.get("TargetMode") != "External" and "/media/" in target:
            resolved = PurePosixPath("ppt/slides") / PurePosixPath(target)
            parts: list[str] = []
            for seg in resolved.parts:
                if seg == "..":
                    if parts:
                        parts.pop()
                else:
                    parts.append(seg)
            out[rel.get("Id")] = "/".join(parts)
    return out


def xfrm_geom(el) -> tuple[float | None, float | None, float | None,
                           float | None, float]:
    """(x, y, w, h) in inches and rotation in degrees, from a:xfrm."""
    xfrm = el.find(".//a:xfrm", NS)
    if xfrm is None:
        return None, None, None, None, 0.0
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    x = int(off.get("x")) / EMU_PER_INCH if off is not None else None
    y = int(off.get("y")) / EMU_PER_INCH if off is not None else None
    w = int(ext.get("cx")) / EMU_PER_INCH if ext is not None else None
    h = int(ext.get("cy")) / EMU_PER_INCH if ext is not None else None
    rot = int(xfrm.get("rot", "0")) / 60000.0
    return x, y, w, h, rot


def shape_text(el) -> str:
    return "".join(t.text or "" for t in el.findall(".//a:t", NS))


def shape_rows(root, rels: dict[str, str], names: set[str],
               zf: zipfile.ZipFile) -> list[dict]:
    """Per-shape layout table for one slide (same columns as dump_layout.py)."""
    sp_tree = root.find("p:cSld/p:spTree", NS)
    rows = []
    for el in sp_tree:
        tag = el.tag.split("}")[1]
        if tag == "sp":
            kind = "TEXT" if shape_text(el).strip() else "AUTO_SHAPE"
        elif tag == "pic":
            has_video = el.find("p:nvPicPr/p:nvPr/a:videoFile", NS) is not None
            kind = "MEDIA" if has_video else "PICTURE"
        elif tag == "graphicFrame":
            kind = "GRAPHIC_FRAME"
        elif tag == "cxnSp":
            kind = "CONNECTOR"
        elif tag == "grpSp":
            kind = "GROUP"
        else:
            continue

        x, y, w, h, rot = xfrm_geom(el)
        sha1 = ""
        if tag == "pic":
            blip = el.find(".//a:blip", NS)
            rid = blip.get(f"{{{R_NS}}}embed") if blip is not None else None
            media_part = rels.get(rid)
            if media_part and media_part in names:
                sha1 = hashlib.sha1(zf.read(media_part)).hexdigest()[:12]
        rows.append({
            "kind": kind,
            "text": shape_text(el)[:40],
            "x": x, "y": y, "w": w, "h": h,
            "rot": rot,
            "sha1": sha1,
        })
    rows.sort(key=lambda r: (r["y"] if r["y"] is not None else -1.0,
                             r["x"] if r["x"] is not None else -1.0))
    return rows


def video_duration(data: bytes, suffix: str) -> float | None:
    """Container duration in seconds via ffprobe, or None if unavailable."""
    if shutil.which("ffprobe") is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=suffix or ".mp4") as tmp:
        tmp.write(data)
        tmp.flush()
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-of", "json", tmp.name],
            capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return None
    duration = json.loads(proc.stdout).get("format", {}).get("duration")
    try:
        return round(float(duration), 2) if duration else None
    except ValueError:
        return None


def media_entries(root, rels: dict[str, str], names: set[str],
                  zf: zipfile.ZipFile, dur_cache: dict) -> list[dict]:
    """Media inventory for one slide: images + videos, with sha1/dims/duration."""
    entries = []
    for pic in root.iter(f"{{{P_NS}}}pic"):
        video = pic.find("p:nvPicPr/p:nvPr/a:videoFile", NS)
        if video is not None:
            rid = video.get(f"{{{R_NS}}}link")
            kind = "video"
        else:
            blip = pic.find(".//a:blip", NS)
            rid = blip.get(f"{{{R_NS}}}embed") if blip is not None else None
            kind = "image"
        part = rels.get(rid)
        if not part or part not in names:
            continue
        data = zf.read(part)
        entry = {
            "kind": kind,
            "name": PurePosixPath(part).name,
            "sha1": hashlib.sha1(data).hexdigest()[:12],
            "bytes": len(data),
            "dims": None,
            "duration_s": None,
        }
        if kind == "image" and Image is not None:
            try:
                with Image.open(io.BytesIO(data)) as img:
                    entry["dims"] = f"{img.width}x{img.height}"
            except Exception:
                pass  # unreadable format — leave dims unknown
        if kind == "video":
            if part not in dur_cache:
                dur_cache[part] = video_duration(
                    data, PurePosixPath(part).suffix)
            entry["duration_s"] = dur_cache[part]
        entries.append(entry)
    return entries


def analyze_slide(zf: zipfile.ZipFile, slide_part: str, names: set[str],
                  dur_cache: dict) -> dict:
    root = ET.fromstring(zf.read(slide_part))
    rels = slide_media_rels(zf, slide_part)

    text = []
    for para in root.iter(f"{{{A_NS}}}p"):
        t = "".join(node.text or "" for node in
                    para.findall(".//a:t", NS)).strip()
        if t:
            text.append(t)

    equations = sum(1 for el in root.iter() if el.tag == f"{{{M_NS}}}oMath")
    charts = tables = 0
    for gf in root.iter(f"{{{P_NS}}}graphicFrame"):
        gd = gf.find("a:graphic/a:graphicData", NS)
        uri = gd.get("uri", "") if gd is not None else ""
        if uri.endswith("/chart"):
            charts += 1
        elif uri.endswith("/table"):
            tables += 1

    media = media_entries(root, rels, names, zf, dur_cache)
    return {
        "text": text,
        "shapes": shape_rows(root, rels, names, zf),
        "media": media,
        "equations": equations,
        "charts": charts,
        "tables": tables,
        "images": sum(1 for m in media if m["kind"] == "image"),
        "videos": sum(1 for m in media if m["kind"] == "video"),
    }


def fmt(v: float | None) -> str:
    return f"{v:7.2f}" if v is not None else "      -"


def print_slide(n: int, s: dict) -> None:
    print(f"--- slide {n} ---")
    if s["text"]:
        print("text:")
        for line in s["text"]:
            print(f"  | {line}")
    print(f"shapes: ({len(s['shapes'])})")
    print(f"  {'kind':<14} {'x in':>7} {'y in':>7} {'w in':>7} {'h in':>7} "
          f"{'rot':>6} {'sha1':<12} text")
    for r in s["shapes"]:
        print(f"  {r['kind']:<14} {fmt(r['x'])} {fmt(r['y'])} "
              f"{fmt(r['w'])} {fmt(r['h'])} {r['rot']:6.1f} "
              f"{r['sha1']:<12} {r['text']}")
    if s["media"]:
        print("media:")
        for m in s["media"]:
            extra = m["dims"] or (
                f"{m['duration_s']}s" if m["duration_s"] is not None else "-")
            print(f"  {m['kind']:<6} {m['name']:<24} sha1={m['sha1']} "
                  f"{m['bytes']:>10} bytes  {extra}")
    counts = ", ".join(f"{k}: {s[k]}" for k in ("equations", "charts", "tables")
                       if s[k])
    if counts:
        print(f"contains {counts}")
    print()


def run_render(deck: str, slide_nums: list[int], out_dir: str) -> None:
    """Shell out to the sibling render_slides.py for approximate thumbnails."""
    script = Path(__file__).resolve().parent / "render_slides.py"
    spec = ",".join(str(n) for n in slide_nums)
    proc = subprocess.run(
        ["uv", "run", str(script), deck, "--slides", spec, "--out", out_dir],
        capture_output=True, text=True, timeout=600)
    out = (proc.stdout or "").strip()
    if out:
        print(out, file=sys.stderr)
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()[:300]
        print(f"warning: render_slides.py failed (thumbnails skipped): "
              f"{detail}", file=sys.stderr)
    else:
        print(f"thumbnails written to {out_dir} — APPROXIMATE "
              "(LibreOffice render, not PowerPoint fidelity)", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="One-command read-only report of an existing pptx deck "
                    "(text + layout + media + equation/video/chart summary).")
    ap.add_argument("deck", help="path to .pptx file (never modified)")
    ap.add_argument("--slide", type=int, default=None,
                    help="1-based slide number (default: all slides)")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit the whole report as one JSON object")
    ap.add_argument("--render", metavar="OUTDIR", default=None,
                    help="also write approximate PNG thumbnails via "
                         "render_slides.py (needs LibreOffice)")
    args = ap.parse_args()

    try:
        valid = zipfile.is_zipfile(args.deck)
    except OSError:
        valid = False
    if not valid:
        sys.exit(f"error: deck not found or not a valid .pptx (zip): {args.deck}")

    with zipfile.ZipFile(args.deck) as zf:
        names = set(zf.namelist())
        if "ppt/presentation.xml" not in names:
            sys.exit(f"error: not a .pptx (no ppt/presentation.xml): {args.deck}")
        parts = slide_parts_in_order(zf)
        if args.slide is not None and not 1 <= args.slide <= len(parts):
            print(f"error: --slide {args.slide} out of range "
                  f"(deck has {len(parts)} slides)", file=sys.stderr)
            return 1

        dur_cache: dict = {}
        slides = {n: analyze_slide(zf, part, names, dur_cache)
                  for n, part in enumerate(parts, 1)}

    summary = {
        "slide_count": len(parts),
        "equations": sum(s["equations"] for s in slides.values()),
        "videos": sum(s["videos"] for s in slides.values()),
        "charts": sum(s["charts"] for s in slides.values()),
        "tables": sum(s["tables"] for s in slides.values()),
        "images": sum(s["images"] for s in slides.values()),
        "slides_with_equations": [n for n, s in slides.items() if s["equations"]],
        "slides_with_videos": [n for n, s in slides.items() if s["videos"]],
    }
    selected = ([args.slide] if args.slide is not None
                else sorted(slides))

    if args.as_json:
        report = {
            "deck": str(args.deck),
            "summary": summary,
            "slides": [{"slide": n, **slides[n]} for n in selected],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"deck: {args.deck}")
        print(f"slides: {summary['slide_count']} | "
              f"equations: {summary['equations']} | "
              f"videos: {summary['videos']} | "
              f"charts: {summary['charts']} | "
              f"tables: {summary['tables']} | "
              f"images: {summary['images']}")
        if summary["slides_with_equations"]:
            print("slides with equations: "
                  + ",".join(map(str, summary["slides_with_equations"])))
        if summary["slides_with_videos"]:
            print("slides with videos: "
                  + ",".join(map(str, summary["slides_with_videos"])))
        print()
        for n in selected:
            print_slide(n, slides[n])

    if args.render:
        run_render(args.deck, selected, args.render)
    return 0


if __name__ == "__main__":
    sys.exit(main())
