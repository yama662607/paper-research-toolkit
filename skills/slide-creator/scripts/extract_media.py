#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10.0"]
# ///
"""Extract embedded images/videos from one slide of a pptx to files, so a
user who swapped an image in PowerPoint can pull it back into their assets/
folder.

Pictures on the slide are ordered LEFT->RIGHT by x position and saved as
<prefix>_1.<ext>, <prefix>_2.<ext>, ... For a video picture the linked media
file is extracted (not the poster frame). Prints a table with the saved
filename, original media name, position in inches, byte size, and image
dimensions (via PIL when available). Read-only on the deck; OUT is created
if missing.

Usage: extract_media.py DECK.pptx --slide N --out DIR [--prefix NAME] [--overwrite]
"""
import argparse
import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
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


def geom_inches(pic) -> tuple[float | None, float | None,
                              float | None, float | None]:
    xfrm = pic.find(".//a:xfrm", NS)
    if xfrm is None:
        return None, None, None, None
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    x = int(off.get("x")) / EMU_PER_INCH if off is not None else None
    y = int(off.get("y")) / EMU_PER_INCH if off is not None else None
    w = int(ext.get("cx")) / EMU_PER_INCH if ext is not None else None
    h = int(ext.get("cy")) / EMU_PER_INCH if ext is not None else None
    return x, y, w, h


def fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "-"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract embedded media from one pptx slide (read-only).")
    ap.add_argument("deck", help="path to .pptx file")
    ap.add_argument("--slide", type=int, required=True,
                    help="1-based slide number")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--prefix", default="media",
                    help="output filename prefix (default: media)")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace existing output files (default: refuse before writing)")
    args = ap.parse_args()

    try:
        valid = zipfile.is_zipfile(args.deck)
    except OSError:
        valid = False
    if not valid:
        sys.exit(f"error: deck not found or not a valid .pptx (zip): {args.deck}")

    out_dir = Path(args.out)

    with zipfile.ZipFile(args.deck) as zf:
        parts = slide_parts_in_order(zf)
        if not 1 <= args.slide <= len(parts):
            print(f"error: --slide {args.slide} out of range "
                  f"(deck has {len(parts)} slides)", file=sys.stderr)
            return 1
        slide_part = parts[args.slide - 1]
        rels = slide_media_rels(zf, slide_part)
        root = ET.fromstring(zf.read(slide_part))

        entries = []
        for pic in root.iter(f"{{{P_NS}}}pic"):
            video = pic.find("p:nvPicPr/p:nvPr/a:videoFile", NS)
            if video is not None:
                rid = video.get(f"{{{R_NS}}}link")
            else:
                blip = pic.find(".//a:blip", NS)
                rid = blip.get(f"{{{R_NS}}}embed") if blip is not None else None
            media_part = rels.get(rid)
            if not media_part or media_part not in zf.namelist():
                continue
            x, y, w, h = geom_inches(pic)
            entries.append({"media_part": media_part, "x": x, "y": y,
                            "w": w, "h": h})

        if not entries:
            print(f"no embedded media found on slide {args.slide}")
            return 0

        entries.sort(key=lambda e: e["x"] if e["x"] is not None else -1.0)
        destinations = [
            out_dir / f"{args.prefix}_{i}{PurePosixPath(e['media_part']).suffix}"
            for i, e in enumerate(entries, 1)
        ]
        existing = [path for path in destinations if path.exists()]
        if existing and not args.overwrite:
            print("error: refusing to overwrite existing output file(s): "
                  + ", ".join(str(path) for path in existing), file=sys.stderr)
            print("rerun with --overwrite only after confirming those files are disposable",
                  file=sys.stderr)
            return 2
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"{'saved':<20} {'original':<24} {'x':>6} {'y':>6} "
              f"{'w':>6} {'h':>6} {'bytes':>10} dims")
        for i, (e, dest) in enumerate(zip(entries, destinations), 1):
            data = zf.read(e["media_part"])
            dest.write_bytes(data)
            dims = "-"
            if Image is not None:
                try:
                    with Image.open(io.BytesIO(data)) as img:
                        dims = f"{img.width}x{img.height}"
                except Exception:
                    dims = "-"  # video or unreadable format
            print(f"{dest.name:<20} {PurePosixPath(e['media_part']).name:<24} "
                  f"{fmt(e['x']):>6} {fmt(e['y']):>6} {fmt(e['w']):>6} "
                  f"{fmt(e['h']):>6} {len(data):>10} {dims}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
