#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Dump every shape on a slide (or all slides) as a table so a human can
precisely capture manual layout edits made in PowerPoint.

For each shape: kind (TEXT / PICTURE / MEDIA / AUTO_SHAPE / ...), text
(truncated), position x/y/w/h in inches, rotation in degrees, and for pictures
the sha1 (first 12 hex chars) of the embedded image bytes so identical-looking
images can be told apart. Rows are sorted by y then x. Read-only: the input
deck is never modified.

Usage: dump_layout.py DECK.pptx [--slide N] [--json]
"""
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": A_NS, "p": P_NS, "r": R_NS}
EMU_PER_INCH = 914400.0


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


def slide_rels(zf: zipfile.ZipFile, slide_part: str) -> dict[str, str]:
    """Map rId -> media part name for one slide."""
    p = PurePosixPath(slide_part)
    rels_part = str(p.parent / "_rels" / (p.name + ".rels"))
    if rels_part not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read(rels_part))
    out = {}
    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        target = rel.get("Target", "")
        if rel.get("TargetMode") != "External" and "/media/" in target:
            resolved = PurePosixPath("ppt/slides") / PurePosixPath(target)
            # collapse ../ segments
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


def dump_slide(zf: zipfile.ZipFile, slide_part: str) -> list[dict]:
    root = ET.fromstring(zf.read(slide_part))
    rels = slide_rels(zf, slide_part)
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
            if media_part and media_part in zf.namelist():
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


def fmt(v: float | None) -> str:
    return f"{v:7.2f}" if v is not None else "      -"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Dump shape layout of a pptx slide (read-only).")
    ap.add_argument("deck", help="path to .pptx file")
    ap.add_argument("--slide", type=int, default=None,
                    help="1-based slide number (default: all slides)")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit JSON instead of a table")
    args = ap.parse_args()

    try:
        valid = zipfile.is_zipfile(args.deck)
    except OSError:
        valid = False
    if not valid:
        sys.exit(f"error: deck not found or not a valid .pptx (zip): {args.deck}")

    with zipfile.ZipFile(args.deck) as zf:
        parts = slide_parts_in_order(zf)
        if args.slide is not None:
            if not 1 <= args.slide <= len(parts):
                print(f"error: --slide {args.slide} out of range "
                      f"(deck has {len(parts)} slides)", file=sys.stderr)
                return 1
            selected = [(args.slide, parts[args.slide - 1])]
        else:
            selected = list(enumerate(parts, 1))

        result = {n: dump_slide(zf, part) for n, part in selected}

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    for n, rows in result.items():
        print(f"--- slide {n} ({len(rows)} shapes) ---")
        print(f"{'kind':<14} {'x in':>7} {'y in':>7} {'w in':>7} {'h in':>7} "
              f"{'rot':>6} {'sha1':<12} text")
        for r in rows:
            print(f"{r['kind']:<14} {fmt(r['x'])} {fmt(r['y'])} "
                  f"{fmt(r['w'])} {fmt(r['h'])} {r['rot']:6.1f} "
                  f"{r['sha1']:<12} {r['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
