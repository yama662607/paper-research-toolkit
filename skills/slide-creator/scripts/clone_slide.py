#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-pptx>=0.6.23", "lxml>=5.0"]
# ///
"""Slide-level surgery that python-pptx doesn't provide.

Subcommands:
  clone   duplicate a slide (media references, rels, Content_Types and
          presentation.xml wiring handled; the naive deepcopy idiom breaks
          exactly here)
  delete  remove a slide from the deck (then sweeps orphans)
  clean   remove orphaned slide parts and unreferenced media

Slide numbers are 1-based *presentation order* (what you see in PowerPoint),
not XML part numbers. Cloned slides keep pointing at the same media parts —
media is not duplicated. Speaker notes are NOT carried over to clones.
"""
import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
SLIDE_CT = ("application/vnd.openxmlformats-officedocument"
            ".presentationml.slide+xml")
SLIDE_RELTYPE = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                 "relationships/slide")
NOTES_RELTYPE_SUFFIX = "/notesSlide"


class Package:
    """A pptx as an in-memory dict of part-name -> bytes."""

    def __init__(self, path: Path):
        self.path = path
        with zipfile.ZipFile(path) as zf:
            self.parts: dict[str, bytes] = {n: zf.read(n) for n in zf.namelist()}

    def xml(self, name: str) -> etree._Element:
        return etree.fromstring(self.parts[name])

    def put(self, name: str, root: etree._Element) -> None:
        self.parts[name] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True)

    def save(self) -> None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in self.parts.items():
                zf.writestr(name, data)
        shutil.move(tmp.name, self.path)

    # ---- presentation-level lookups ------------------------------------

    def pres_rels(self) -> etree._Element:
        return self.xml("ppt/_rels/presentation.xml.rels")

    def slide_order(self) -> list[tuple[str, str]]:
        """[(rId, part_name), ...] in presentation order."""
        pres = self.xml("ppt/presentation.xml")
        rels = {r.get("Id"): r.get("Target")
                for r in self.pres_rels()}
        out = []
        sldlst = pres.find(f"{{{NS['p']}}}sldIdLst")
        if sldlst is None:
            sys.exit("error: presentation has no slide list")
        for sld in sldlst:
            rid = sld.get(f"{{{NS['r']}}}id")
            target = rels[rid]  # e.g. slides/slide2.xml
            out.append((rid, "ppt/" + target.lstrip("/")))
        return out


def resolve_slide(pkg: Package, pos: int) -> tuple[str, str]:
    order = pkg.slide_order()
    if not (1 <= pos <= len(order)):
        sys.exit(f"error: slide {pos} out of range (deck has {len(order)})")
    return order[pos - 1]


def next_free(pattern: str, names) -> int:
    used = {int(m.group(1)) for n in names
            if isinstance(n, str) and (m := re.fullmatch(pattern, n))}
    return max(used, default=0) + 1


def verify(path: Path) -> None:
    from pptx import Presentation
    Presentation(str(path))  # raises on breakage


# --------------------------------------------------------------- clone

def cmd_clone(args) -> None:
    pkg = Package(Path(args.pptx))
    src_rid, src_part = resolve_slide(pkg, args.slide)

    new_num = next_free(r"ppt/slides/slide(\d+)\.xml", pkg.parts)
    new_part = f"ppt/slides/slide{new_num}.xml"
    pkg.parts[new_part] = pkg.parts[src_part]

    # rels: copy, but strip notesSlide references (notes are not cloned)
    src_rels_name = f"ppt/slides/_rels/{Path(src_part).name}.rels"
    new_rels_name = f"ppt/slides/_rels/slide{new_num}.xml.rels"
    if src_rels_name in pkg.parts:
        rels_root = pkg.xml(src_rels_name)
        for rel in list(rels_root):
            if rel.get("Type", "").endswith(NOTES_RELTYPE_SUFFIX):
                rels_root.remove(rel)
        pkg.put(new_rels_name, rels_root)

    # Content_Types: register the new slide part
    ct = pkg.xml("[Content_Types].xml")
    override = etree.SubElement(ct, f"{{{NS['ct']}}}Override")
    override.set("PartName", f"/{new_part}")
    override.set("ContentType", SLIDE_CT)
    pkg.put("[Content_Types].xml", ct)

    # presentation.xml.rels: new relationship
    prels = pkg.pres_rels()
    new_rid_num = next_free(r"rId(\d+)", [r.get("Id") for r in prels])
    new_rid = f"rId{new_rid_num}"
    rel = etree.SubElement(prels, f"{{{NS['rel']}}}Relationship")
    rel.set("Id", new_rid)
    rel.set("Type", SLIDE_RELTYPE)
    rel.set("Target", f"slides/slide{new_num}.xml")
    pkg.put("ppt/_rels/presentation.xml.rels", prels)

    # presentation.xml: insert into sldIdLst
    pres = pkg.xml("ppt/presentation.xml")
    sldlst = pres.find(f"{{{NS['p']}}}sldIdLst")
    max_id = max((int(s.get("id")) for s in sldlst), default=255)
    new_sld = etree.Element(f"{{{NS['p']}}}sldId")
    new_sld.set("id", str(max(max_id + 1, 256)))
    new_sld.set(f"{{{NS['r']}}}id", new_rid)
    insert_after = args.after if args.after is not None else args.slide
    insert_after = max(0, min(insert_after, len(sldlst)))
    sldlst.insert(insert_after, new_sld)
    pkg.put("ppt/presentation.xml", pres)

    pkg.save()
    verify(pkg.path)
    print(f"ok: slide {args.slide} cloned -> position {insert_after + 1} "
          f"(part slide{new_num}.xml) in {args.pptx}")
    print("note: speaker notes are not carried over; animation spids inside "
          "the clone still target the cloned slide's own shapes (same ids).")


# --------------------------------------------------------------- delete

def cmd_delete(args) -> None:
    pkg = Package(Path(args.pptx))
    rid, part = resolve_slide(pkg, args.slide)

    pres = pkg.xml("ppt/presentation.xml")
    sldlst = pres.find(f"{{{NS['p']}}}sldIdLst")
    for sld in list(sldlst):
        if sld.get(f"{{{NS['r']}}}id") == rid:
            sldlst.remove(sld)
    pkg.put("ppt/presentation.xml", pres)

    prels = pkg.pres_rels()
    for rel in list(prels):
        if rel.get("Id") == rid:
            prels.remove(rel)
    pkg.put("ppt/_rels/presentation.xml.rels", prels)

    sweep(pkg)
    pkg.save()
    verify(pkg.path)
    print(f"ok: slide {args.slide} deleted (was {part}); orphans swept")


# ---------------------------------------------------------------- clean

def sweep(pkg: Package) -> list[str]:
    removed = []
    live_slides = {part for _, part in pkg.slide_order()}

    # orphaned slide parts (+ their rels + Content_Types overrides)
    for name in [n for n in list(pkg.parts)
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]:
        if name not in live_slides:
            pkg.parts.pop(name)
            pkg.parts.pop(f"ppt/slides/_rels/{Path(name).name}.rels", None)
            removed.append(name)
    if removed:
        ct = pkg.xml("[Content_Types].xml")
        gone = {f"/{n}" for n in removed}
        for ov in list(ct):
            if ov.get("PartName") in gone:
                ct.remove(ov)
        pkg.put("[Content_Types].xml", ct)

    # notesSlides whose slide is gone
    for name in [n for n in list(pkg.parts)
                 if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]:
        rels_name = f"ppt/notesSlides/_rels/{Path(name).name}.rels"
        if rels_name not in pkg.parts:
            continue
        targets = [
            ("ppt/notesSlides/" + rel.get("Target", "")).replace(
                "ppt/notesSlides/../", "ppt/")
            for rel in pkg.xml(rels_name)
            if rel.get("TargetMode") != "External"
        ]
        slide_refs = [t for t in targets if "/slides/" in t]
        if slide_refs and all(t not in pkg.parts for t in slide_refs):
            pkg.parts.pop(name)
            pkg.parts.pop(rels_name, None)
            removed.append(name)
    if removed:
        ct = pkg.xml("[Content_Types].xml")
        gone = {f"/{n}" for n in removed}
        for ov in list(ct):
            if ov.get("PartName") in gone:
                ct.remove(ov)
        pkg.put("[Content_Types].xml", ct)

    # media referenced by no remaining rels
    referenced = set()
    for name in pkg.parts:
        if name.endswith(".rels"):
            base = Path(name).parent.parent
            for rel in pkg.xml(name):
                if rel.get("TargetMode") == "External":
                    continue
                target = (base / rel.get("Target", "")).as_posix()
                parts = []
                for seg in target.split("/"):
                    if seg == "..":
                        parts and parts.pop()
                    elif seg not in (".", ""):
                        parts.append(seg)
                referenced.add("/".join(parts))
    for name in [n for n in list(pkg.parts) if n.startswith("ppt/media/")]:
        if name not in referenced:
            pkg.parts.pop(name)
            removed.append(name)
    return removed


def cmd_clean(args) -> None:
    pkg = Package(Path(args.pptx))
    removed = sweep(pkg)
    pkg.save()
    verify(pkg.path)
    if removed:
        print("ok: removed " + ", ".join(removed))
    else:
        print("ok: nothing orphaned")


# ----------------------------------------------------------------- main

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("clone", help="duplicate a slide")
    c.add_argument("pptx")
    c.add_argument("--slide", type=int, required=True,
                   help="1-based presentation-order position to copy")
    c.add_argument("--after", type=int,
                   help="insert after this position (default: after source)")
    c.set_defaults(fn=cmd_clone)

    d = sub.add_parser("delete", help="remove a slide and sweep orphans")
    d.add_argument("pptx")
    d.add_argument("--slide", type=int, required=True)
    d.set_defaults(fn=cmd_delete)

    cl = sub.add_parser("clean", help="sweep orphaned slides/media")
    cl.add_argument("pptx")
    cl.set_defaults(fn=cmd_clean)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
