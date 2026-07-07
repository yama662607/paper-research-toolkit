#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml>=5.0"]
# ///
"""Inspect a PPTX and sync safe PowerPoint edits back to a managed JS source.

This is intentionally conservative. It can round-trip stable-source-id shapes
for text and geometry; other objects are inventoried and preserved for review.

Source convention:
  - Put a strict JSON-compatible managed block in the build script:

    /* slide-creator:managed-deck:start */
    export const deckSpec = {
      "version": 1,
      "slides": [
        {"id": "s001", "shapes": [
          {"id": "title", "type": "text", "text": "Old", "x": 0.5, "y": 0.3}
        ]}
      ]
    };
    /* slide-creator:managed-deck:end */

  - When creating PPTX shapes, set the PowerPoint object name or alt text to
    a stable id such as "scid:s001.title".

Usage:
  uv run scripts/sync_from_pptx.py edited.pptx --inspect-only --out inspect.json
  uv run scripts/sync_from_pptx.py deck.pptx --source build_deck.mjs --init-state
  uv run scripts/sync_from_pptx.py edited.pptx --source build_deck.mjs --apply
  uv run scripts/sync_from_pptx.py edited.pptx --source build_deck.mjs \
    --apply --import-untagged --asset-dir assets/roundtrip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from lxml import etree

EMU_PER_INCH = 914400
START_MARKER = "/* slide-creator:managed-deck:start */"
END_MARKER = "/* slide-creator:managed-deck:end */"
SOURCE_ID_RE = re.compile(r"(?:^|[\s;|])scid:([A-Za-z0-9_.:-]+)")
IMAGE_EXTS = {".bmp", ".emf", ".gif", ".jpeg", ".jpg", ".png", ".svg",
              ".tif", ".tiff", ".webp", ".wmf"}
VIDEO_EXTS = {".avi", ".m4v", ".mov", ".mp4", ".mpeg", ".mpg", ".wmv"}
XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)
MAX_XML_PART_BYTES = 50 * 1024 * 1024
MAX_IMPORTED_ASSET_BYTES = 1024 * 1024 * 1024
MAX_HASHED_MEDIA_BYTES = 1024 * 1024 * 1024
MAX_HASHED_MEDIA_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_UNCOMPRESSED_PACKAGE_BYTES = 4 * 1024 * 1024 * 1024
MAX_COMPRESSED_PACKAGE_BYTES = 4 * 1024 * 1024 * 1024
MAX_ZIP_ENTRIES = 20000

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_zip_member(zf: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with zf.open(name) as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def human_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{n} B"
        value /= 1024
    return f"{n} B"


def require_zip_member_size(
    zf: zipfile.ZipFile, name: str, limit: int, label: str
) -> zipfile.ZipInfo:
    info = zf.getinfo(name)
    if info.file_size > limit:
        sys.exit(
            f"error: {label} too large: {name} is "
            f"{human_bytes(info.file_size)} > {human_bytes(limit)}"
        )
    return info


def inch(value: str | None) -> float | None:
    if value is None:
        return None
    return round(int(value) / EMU_PER_INCH, 4)


def local_name(el: etree._Element) -> str:
    return etree.QName(el).localname


def norm_path(base: str, target: str) -> str:
    target = unquote(target)
    raw = target.lstrip("/") if target.startswith("/") else f"{base}/{target}"
    parts: list[str] = []
    for seg in raw.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def rels_name_for(part: str) -> str:
    p = Path(part)
    return f"{p.parent}/_rels/{p.name}.rels"


@dataclass
class ManagedBlock:
    prefix: str
    body_prefix: str
    body_suffix: str
    suffix: str
    spec: dict[str, Any]


class PptxInspector:
    def __init__(self, path: Path):
        if not zipfile.is_zipfile(path):
            sys.exit(f"error: {path} is not a pptx/zip file")
        self.path = path
        self.member_hash_cache: dict[str, dict[str, Any]] = {}
        self.asset_copy_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.hashed_media_bytes = 0
        compressed = path.stat().st_size
        if compressed > MAX_COMPRESSED_PACKAGE_BYTES:
            sys.exit(
                "error: pptx file is too large for safe sync: "
                f"{human_bytes(compressed)} > {human_bytes(MAX_COMPRESSED_PACKAGE_BYTES)}"
            )
        self.zf = zipfile.ZipFile(path)
        infos = self.zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            sys.exit(
                "error: pptx has too many zip entries for safe sync: "
                f"{len(infos)} > {MAX_ZIP_ENTRIES}"
            )
        names = [info.filename for info in infos]
        duplicate_names = sorted(name for name, count in Counter(names).items()
                                 if count > 1)
        if duplicate_names:
            sample = ", ".join(duplicate_names[:5])
            sys.exit(f"error: pptx has duplicate zip entries: {sample}")
        self.names = set(names)
        total = sum(info.file_size for info in infos)
        if total > MAX_UNCOMPRESSED_PACKAGE_BYTES:
            sys.exit(
                "error: pptx uncompressed package is too large for safe sync: "
                f"{human_bytes(total)} > {human_bytes(MAX_UNCOMPRESSED_PACKAGE_BYTES)}"
            )

    def xml(self, name: str) -> etree._Element:
        require_zip_member_size(self.zf, name, MAX_XML_PART_BYTES, "XML part")
        return etree.fromstring(self.zf.read(name), parser=XML_PARSER)

    def member_inventory(self, name: str) -> dict[str, Any]:
        info = self.zf.getinfo(name)
        out: dict[str, Any] = {
            "size": info.file_size,
            "crc32": f"{info.CRC:08x}",
        }
        if name in self.member_hash_cache:
            out.update(self.member_hash_cache[name])
            return out
        if info.file_size > MAX_HASHED_MEDIA_BYTES:
            out["hashSkipped"] = "target-too-large"
            return out
        if self.hashed_media_bytes + info.file_size > MAX_HASHED_MEDIA_TOTAL_BYTES:
            out["hashSkipped"] = "total-hash-budget-exceeded"
            return out
        self.member_hash_cache[name] = {
            "sha256": sha256_zip_member(self.zf, name),
        }
        self.hashed_media_bytes += info.file_size
        out.update(self.member_hash_cache[name])
        return out

    def rels(self, rels_name: str) -> dict[str, dict[str, str]]:
        if rels_name not in self.names:
            return {}
        root = self.xml(rels_name)
        return {
            rel.get("Id"): {
                "type": rel.get("Type", ""),
                "target": rel.get("Target", ""),
                "mode": rel.get("TargetMode", "Internal"),
            }
            for rel in root.findall("rel:Relationship", namespaces=NS)
            if rel.get("Id")
        }

    def slide_order(self) -> list[str]:
        pres = self.xml("ppt/presentation.xml")
        rels = self.rels("ppt/_rels/presentation.xml.rels")
        out: list[str] = []
        sldlst = pres.find("p:sldIdLst", namespaces=NS)
        if sldlst is None:
            return out
        for sld in sldlst:
            rid = sld.get(f"{{{NS['r']}}}id")
            target = rels.get(rid, {}).get("target")
            if target:
                out.append(norm_path("ppt", target))
        return out

    def inspect(self) -> dict[str, Any]:
        slides = []
        for index, part in enumerate(self.slide_order(), 1):
            slides.append(self.inspect_slide(index, part))
        return {
            "version": 1,
            "pptx": {
                "path": str(self.path),
                "sha256": sha256_file(self.path),
            },
            "slides": slides,
        }

    def inspect_slide(self, index: int, part: str) -> dict[str, Any]:
        root = self.xml(part)
        rels = self.rels(rels_name_for(part))
        shapes = []
        for node in root.xpath(".//p:cSld/p:spTree/*", namespaces=NS):
            if local_name(node) in {"nvGrpSpPr", "grpSpPr"}:
                continue
            shape = self.inspect_shape(node, rels)
            if shape:
                shapes.append(shape)
        return {"index": index, "part": part, "shapes": shapes}

    def inspect_shape(
        self, node: etree._Element, rels: dict[str, dict[str, str]]
    ) -> dict[str, Any] | None:
        cnv = node.find(".//p:cNvPr", namespaces=NS)
        if cnv is None:
            return None
        name = cnv.get("name", "")
        descr = cnv.get("descr", "")
        title = cnv.get("title", "")
        source_id = find_source_id(name, descr, title)
        kind = shape_kind(node)
        geom = shape_geometry(node)
        text = shape_text(node)
        omml = shape_omml(node)

        rel_refs = []
        for el in node.xpath(".//*[@r:embed or @r:link or @r:id]", namespaces=NS):
            for attr in ("embed", "link", "id"):
                rid = el.get(f"{{{NS['r']}}}{attr}")
                if not rid:
                    continue
                rel = rels.get(rid, {})
                target = rel.get("target")
                mode = rel.get("mode", "Internal")
                resolved_target = ""
                if target:
                    resolved_target = (
                        target if mode == "External"
                        else norm_path("ppt/slides", target)
                    )
                rel_ref = {
                    "rid": rid,
                    "attr": attr,
                    "type": rel.get("type", ""),
                    "target": resolved_target,
                    "mode": mode,
                }
                if mode != "External" and resolved_target in self.names:
                    rel_ref.update(self.member_inventory(resolved_target))
                rel_refs.append(rel_ref)

        out: dict[str, Any] = {
            "sourceId": source_id,
            "kind": kind,
            "shapeId": cnv.get("id"),
            "name": name,
            "descr": descr,
            "title": title,
            "geometry": geom,
            "text": text,
            "rels": rel_refs,
            "features": shape_features(node),
        }
        if omml:
            out["omml"] = omml
        return out


def find_source_id(*values: str) -> str | None:
    for value in values:
        if not value:
            continue
        if value.startswith("scid:"):
            return value.removeprefix("scid:").split()[0]
        match = SOURCE_ID_RE.search(value)
        if match:
            return match.group(1)
    return None


def shape_kind(node: etree._Element) -> str:
    lname = local_name(node)
    if lname == "pic":
        return "picture"
    if lname == "graphicFrame":
        if node.find(".//a:tbl", namespaces=NS) is not None:
            return "table"
        if node.xpath(".//*[local-name()='chart']"):
            return "chart"
        return "graphicFrame"
    if lname == "cxnSp":
        return "connector"
    if node.find(".//p:txBody", namespaces=NS) is not None:
        return "text"
    return lname


def shape_geometry(node: etree._Element) -> dict[str, float | None]:
    xfrm = node.find(".//p:spPr/a:xfrm", namespaces=NS)
    if xfrm is None:
        xfrm = node.find(".//p:xfrm", namespaces=NS)
    if xfrm is None:
        xfrm = node.find(".//p:grpSpPr/a:xfrm", namespaces=NS)
    if xfrm is None:
        return {}
    off = xfrm.find("a:off", namespaces=NS)
    ext = xfrm.find("a:ext", namespaces=NS)
    return {
        "x": inch(off.get("x") if off is not None else None),
        "y": inch(off.get("y") if off is not None else None),
        "w": inch(ext.get("cx") if ext is not None else None),
        "h": inch(ext.get("cy") if ext is not None else None),
        "rot": xfrm.get("rot"),
    }


def shape_features(node: etree._Element) -> dict[str, bool]:
    features = {}
    if node.xpath(".//a:srcRect", namespaces=NS):
        features["crop"] = True
    for xfrm in node.xpath(".//a:xfrm | .//p:xfrm", namespaces=NS):
        if xfrm.get("flipH") in {"1", "true"}:
            features["flipH"] = True
        if xfrm.get("flipV") in {"1", "true"}:
            features["flipV"] = True
    if local_name(node) == "grpSp":
        features["group"] = True
    return features


def shape_text(node: etree._Element) -> str | None:
    body = node.find(".//p:txBody", namespaces=NS)
    if body is None:
        return None
    paras = []
    for para in body.findall("a:p", namespaces=NS):
        chunks = [t.text or "" for t in para.findall(".//a:t", namespaces=NS)]
        if chunks:
            paras.append("".join(chunks))
    return "\n".join(paras)


def shape_omml(node: etree._Element) -> list[str]:
    paras = node.xpath(".//m:oMathPara", namespaces=NS)
    if paras:
        return [etree.tostring(el, encoding="unicode") for el in paras]
    return [
        etree.tostring(el, encoding="unicode")
        for el in node.xpath(".//m:oMath", namespaces=NS)
    ]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def flatten_by_source_id(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for slide in inventory.get("slides", []):
        for shape in slide.get("shapes", []):
            sid = shape.get("sourceId")
            if not sid:
                continue
            item = dict(shape)
            item["slideIndex"] = slide.get("index")
            item["slidePart"] = slide.get("part")
            out[sid] = item
    return out


def duplicate_source_ids(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    locations: dict[str, list[dict[str, Any]]] = {}
    for slide in inventory.get("slides", []):
        for shape in slide.get("shapes", []):
            sid = shape.get("sourceId")
            if not sid:
                continue
            locations.setdefault(sid, []).append({
                "slideIndex": slide.get("index"),
                "shapeId": shape.get("shapeId"),
                "kind": shape.get("kind"),
                "name": shape.get("name"),
            })
    return [
        {"sourceId": sid, "locations": locs}
        for sid, locs in sorted(locations.items())
        if len(locs) > 1
    ]


def flatten_untagged_shapes(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for slide in inventory.get("slides", []):
        for shape in slide.get("shapes", []):
            if shape.get("sourceId"):
                continue
            item = dict(shape)
            item["slideIndex"] = slide.get("index")
            item["slidePart"] = slide.get("part")
            out.append(item)
    return out


def untagged_signature(shape: dict[str, Any]) -> str:
    geom = shape.get("geometry", {})
    payload = {
        "slideIndex": shape.get("slideIndex"),
        "kind": shape.get("kind"),
        "name": shape.get("name"),
        "text": shape.get("text"),
        "geometry": {k: geom.get(k) for k in ("x", "y", "w", "h", "rot")},
        "rels": rel_signature(shape),
        "omml": shape.get("omml", []),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def untagged_identity(shape: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (shape.get("slideIndex"), shape.get("shapeId"), shape.get("kind"))


def new_untagged_shapes(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    previous_identities = Counter(
        untagged_identity(shape) for shape in flatten_untagged_shapes(previous)
    )
    previous_signatures = Counter(
        untagged_signature(shape) for shape in flatten_untagged_shapes(previous)
    )
    out = []
    for shape in flatten_untagged_shapes(current):
        identity = untagged_identity(shape)
        if previous_identities[identity]:
            previous_identities[identity] -= 1
            continue
        sig = untagged_signature(shape)
        if previous_signatures[sig]:
            previous_signatures[sig] -= 1
            continue
        item = dict(shape)
        item["roundtripSignature"] = sig
        out.append(item)
    return out


def summarize_untagged_shape(shape: dict[str, Any]) -> dict[str, Any]:
    rel_targets = [r.get("target") for r in shape.get("rels", []) if r.get("target")]
    text = shape.get("text")
    if text and len(text) > 120:
        text = text[:117] + "..."
    return {
        "slideIndex": shape.get("slideIndex"),
        "shapeId": shape.get("shapeId"),
        "kind": shape.get("kind"),
        "name": shape.get("name"),
        "textPreview": text,
        "relTargets": rel_targets,
        "hasOmml": bool(shape.get("omml")),
        "roundtripSignature": shape.get("roundtripSignature"),
    }


def diff_inventory(
    current: dict[str, Any], previous: dict[str, Any], tolerance: float
) -> dict[str, Any]:
    cur = flatten_by_source_id(current)
    prev = flatten_by_source_id(previous)
    changes = []
    for sid, cur_shape in cur.items():
        prev_shape = prev.get(sid)
        if not prev_shape:
            changes.append({"sourceId": sid, "kind": "new-tagged-shape",
                            "current": cur_shape})
            continue
        shape_change: dict[str, Any] = {"sourceId": sid, "changes": {}}
        geom_delta = geometry_delta(
            cur_shape.get("geometry", {}),
            prev_shape.get("geometry", {}),
            tolerance,
        )
        if geom_delta:
            shape_change["changes"]["geometry"] = geom_delta
        if cur_shape.get("text") != prev_shape.get("text"):
            shape_change["changes"]["text"] = {
                "before": prev_shape.get("text"),
                "after": cur_shape.get("text"),
            }
        if not rels_equivalent(cur_shape, prev_shape):
            shape_change["changes"]["rels"] = {
                "before": rel_signature(prev_shape),
                "after": rel_signature(cur_shape),
            }
        if omml_signature(cur_shape) != omml_signature(prev_shape):
            shape_change["changes"]["omml"] = {
                "before_count": len(prev_shape.get("omml", [])),
                "after_count": len(cur_shape.get("omml", [])),
                "before": omml_signature(prev_shape),
                "after": omml_signature(cur_shape),
            }
        if shape_change["changes"]:
            changes.append(shape_change)

    deleted = sorted(set(prev) - set(cur))
    untagged = [
        {"slideIndex": slide["index"], "shapeId": shape.get("shapeId"),
         "kind": shape.get("kind"), "name": shape.get("name")}
        for slide in current.get("slides", [])
        for shape in slide.get("shapes", [])
        if not shape.get("sourceId")
    ]
    new_untagged = [
        summarize_untagged_shape(shape)
        for shape in new_untagged_shapes(current, previous)
    ]
    return {
        "changed": changes,
        "deletedSourceIds": deleted,
        "untaggedShapes": untagged,
        "newUntaggedShapes": new_untagged,
        "duplicateSourceIds": duplicate_source_ids(current),
    }


def geometry_delta(
    current: dict[str, Any], previous: dict[str, Any], tolerance: float
) -> dict[str, dict[str, float | None]]:
    out = {}
    for key in ("x", "y", "w", "h"):
        c = current.get(key)
        p = previous.get(key)
        if c is None and p is None:
            continue
        if c is None or p is None or abs(c - p) > tolerance:
            out[key] = {"before": p, "after": c}
    return out


def rel_signature(shape: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    return sorted((r.get("type", ""), r.get("target", ""),
                   r.get("mode", ""), r.get("sha256") or r.get("crc32", ""))
                  for r in shape.get("rels", []))


def rel_identity(rel: dict[str, Any]) -> tuple[str, str, str]:
    return (rel.get("type", ""), rel.get("target", ""), rel.get("mode", ""))


def rels_equivalent(current: dict[str, Any], previous: dict[str, Any]) -> bool:
    cur = sorted(current.get("rels", []), key=rel_identity)
    prev = sorted(previous.get("rels", []), key=rel_identity)
    if [rel_identity(r) for r in cur] != [rel_identity(r) for r in prev]:
        return False
    for c, p in zip(cur, prev, strict=True):
        if c.get("size") and p.get("size") and c.get("size") != p.get("size"):
            return False
        c_hash = c.get("sha256")
        p_hash = p.get("sha256")
        if c_hash and p_hash and c_hash != p_hash:
            return False
        c_crc = c.get("crc32")
        p_crc = p.get("crc32")
        if c_crc and p_crc and (c_crc != p_crc or c.get("size") != p.get("size")):
            return False
        c_skipped = bool(c.get("hashSkipped"))
        p_skipped = bool(p.get("hashSkipped"))
        if c_skipped != p_skipped and (c_hash or p_hash):
            return False
        if c_skipped or p_skipped:
            continue
        if (c_hash or c_crc) and (p_hash or p_crc):
            continue
        if c.get("mode") == "External" and p.get("mode") == "External":
            continue
        if c.get("target") or p.get("target"):
            return False
    return True


def canonical_xml_hash(xml: str) -> str:
    try:
        root = etree.fromstring(xml.encode("utf-8"), parser=XML_PARSER)
        raw = etree.tostring(root, method="c14n")
    except etree.XMLSyntaxError:
        raw = xml.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def omml_signature(shape: dict[str, Any]) -> list[str]:
    return [canonical_xml_hash(xml) for xml in shape.get("omml", [])]


def load_managed_block(source: Path) -> ManagedBlock:
    text = source.read_text(encoding="utf-8")
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        sys.exit(f"error: {source} has no slide-creator managed deck block")
    prefix = text[:start + len(START_MARKER)]
    body = text[start + len(START_MARKER):end]
    suffix = text[end:]
    first = body.find("{")
    last = body.rfind("}")
    if first == -1 or last == -1 or last <= first:
        sys.exit("error: managed deck block must contain a JSON object")
    body_prefix = body[:first]
    body_suffix = body[last + 1:]
    raw = body[first:last + 1]
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(
            "error: managed deck block must be strict JSON inside the JS "
            f"assignment (no trailing commas/comments): {e}"
        )
    return ManagedBlock(prefix, body_prefix, body_suffix, suffix, spec)


def write_managed_block(source: Path, block: ManagedBlock) -> None:
    write_target = source.resolve() if source.is_symlink() else source
    rendered = json.dumps(block.spec, ensure_ascii=False, indent=2)
    new_text = (
        block.prefix
        + block.body_prefix
        + rendered
        + block.body_suffix
        + block.suffix
    )
    write_target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8",
                                        dir=write_target.parent) as tmp:
            tmp.write(new_text)
            tmp_path = Path(tmp.name)
        if write_target.exists():
            os.chmod(tmp_path, write_target.stat().st_mode & 0o777)
        os.replace(tmp_path, write_target)
        tmp_path = None
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def source_index(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for slide in spec.get("slides", []):
        slide_id = slide.get("id")
        for shape in slide.get("shapes", []):
            sid = shape.get("sourceId")
            if not sid and slide_id and shape.get("id"):
                sid = f"{slide_id}.{shape['id']}"
                shape["sourceId"] = sid
            if sid:
                out[sid] = shape
    return out


def duplicate_source_ids_in_spec(spec: dict[str, Any]) -> set[str]:
    counts: Counter[str] = Counter()
    for slide in spec.get("slides", []):
        slide_id = slide.get("id")
        for shape in slide.get("shapes", []):
            sid = shape.get("sourceId")
            if not sid and slide_id and shape.get("id"):
                sid = f"{slide_id}.{shape['id']}"
            if sid:
                counts[sid] += 1
    return {sid for sid, count in counts.items() if count > 1}


def apply_changes_to_source(
    source: Path, diff: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    block = load_managed_block(source)
    idx = source_index(block.spec)
    cur = flatten_by_source_id(current)
    applied = []
    skipped = []
    duplicate_ids = {item["sourceId"] for item in diff.get("duplicateSourceIds", [])}
    duplicate_ids.update(duplicate_source_ids_in_spec(block.spec))
    for sid in sorted(duplicate_ids):
        skipped.append({"sourceId": sid, "reason": "duplicate source id"})

    for item in diff["changed"]:
        sid = item.get("sourceId")
        if sid in duplicate_ids:
            continue
        if item.get("kind") == "new-tagged-shape":
            skipped.append({"sourceId": sid, "reason": "new tagged shape; import not implemented"})
            continue
        shape = idx.get(sid)
        current_shape = cur.get(sid)
        if not shape or not current_shape:
            skipped.append({"sourceId": sid, "reason": "not found in source"})
            continue
        changes = item.get("changes", {})
        unsupported = sorted(set(changes) - {"geometry", "text", "omml"})
        for key in unsupported:
            skipped.append({"sourceId": sid, "reason": f"{key} sync not implemented"})
        touched = {}
        if "geometry" in changes:
            geom = current_shape.get("geometry", {})
            for key in ("x", "y", "w", "h"):
                if key in changes["geometry"] and geom.get(key) is not None:
                    shape[key] = geom[key]
                    touched[key] = geom[key]
        if "text" in changes and "text" in shape:
            shape["text"] = current_shape.get("text")
            touched["text"] = current_shape.get("text")
        elif "text" in changes:
            skipped.append({"sourceId": sid, "reason": "source has no text field"})
        if "omml" in changes and "omml" in shape:
            shape["omml"] = current_shape.get("omml", [])
            touched["omml"] = {
                "count": len(shape["omml"]),
                "sha256": omml_signature(current_shape),
            }
        elif "omml" in changes:
            skipped.append({"sourceId": sid, "reason": "source has no omml field"})
        if touched:
            applied.append({"sourceId": sid, "fields": touched})

    for sid in diff.get("deletedSourceIds", []):
        skipped.append({"sourceId": sid, "reason": "delete sync not implemented"})

    if applied:
        write_managed_block(source, block)
    return {"applied": applied, "skipped": skipped}


def resolve_asset_dir(asset_dir: Path | None, source: Path) -> Path:
    if asset_dir is None:
        return source.parent / "assets" / "roundtrip"
    if asset_dir.is_absolute():
        return asset_dir
    return source.parent / asset_dir


def source_relative_path(path: Path, source: Path) -> str:
    return Path(os.path.relpath(path, source.parent)).as_posix()


def sanitize_id(value: str | None, fallback: str) -> str:
    raw = value or fallback
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-").lower()
    return slug or fallback


def ensure_slide_for_index(spec: dict[str, Any], slide_index: int) -> dict[str, Any]:
    slides = spec.setdefault("slides", [])
    while len(slides) < slide_index:
        next_id = f"s{len(slides) + 1:03d}"
        slides.append({"id": next_id, "shapes": []})
    slide = slides[slide_index - 1]
    slide.setdefault("id", f"s{slide_index:03d}")
    slide.setdefault("shapes", [])
    return slide


def unique_shape_id(slide: dict[str, Any], base: str) -> str:
    used = {shape.get("id") for shape in slide.get("shapes", [])}
    if base not in used:
        return base
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    return f"{base}-{n}"


def geometry_for_import(shape: dict[str, Any]) -> dict[str, Any] | None:
    geom = shape.get("geometry", {})
    out = {k: geom.get(k) for k in ("x", "y", "w", "h")}
    if any(out[k] is None for k in ("x", "y", "w", "h")):
        return None
    if geom.get("rot") is not None:
        out["rot"] = geom.get("rot")
    return out


def media_kind_and_rel(shape: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    image_rel = None
    for rel in shape.get("rels", []):
        target = rel.get("target", "")
        ext = Path(target).suffix.lower()
        rel_type = rel.get("type", "").lower()
        if ext in VIDEO_EXTS or "video" in rel_type:
            return "video", rel
        if rel_type.endswith("/media") and ext not in IMAGE_EXTS:
            return "video", rel
    for rel in shape.get("rels", []):
        target = rel.get("target", "")
        ext = Path(target).suffix.lower()
        rel_type = rel.get("type", "").lower()
        if ext in IMAGE_EXTS or "image" in rel_type:
            image_rel = rel
            break
    if image_rel:
        return "image", image_rel
    return None, None


def copy_pptx_asset(
    inspector: PptxInspector, target: str, asset_dir: Path, source: Path
) -> dict[str, Any]:
    if not target or target not in inspector.names:
        raise ValueError(f"asset target not found in pptx: {target}")
    cache_key = (target, str(asset_dir.resolve()))
    if cache_key in inspector.asset_copy_cache:
        return dict(inspector.asset_copy_cache[cache_key])
    info = inspector.zf.getinfo(target)
    if info.file_size > MAX_IMPORTED_ASSET_BYTES:
        raise ValueError(
            f"asset target too large to import: {target} is "
            f"{human_bytes(info.file_size)} > {human_bytes(MAX_IMPORTED_ASSET_BYTES)}"
        )
    original = Path(target)
    name = sanitize_id(original.stem, "asset") + original.suffix.lower()
    asset_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=asset_dir) as tmp:
            tmp_path = Path(tmp.name)
            with inspector.zf.open(target) as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    h.update(chunk)
                    tmp.write(chunk)
    except Exception:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        raise
    digest_full = h.hexdigest()
    dest = asset_dir / f"{digest_full[:12]}-{name}"
    try:
        if not dest.exists():
            os.replace(tmp_path, dest)
            tmp_path = None
        else:
            tmp_path.unlink()
            tmp_path = None
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
    asset = {
        "path": source_relative_path(dest, source),
        "pptxTarget": target,
        "sha256": digest_full,
        "size": info.file_size,
    }
    inspector.asset_copy_cache[cache_key] = dict(asset)
    return asset


def existing_roundtrip_signatures(spec: dict[str, Any]) -> set[str]:
    out = set()
    for slide in spec.get("slides", []):
        for shape in slide.get("shapes", []):
            rt = shape.get("roundtrip", {})
            sig = rt.get("signature") if isinstance(rt, dict) else None
            if sig:
                out.add(sig)
    return out


def imported_shape_spec(
    shape: dict[str, Any],
    slide: dict[str, Any],
    inspector: PptxInspector,
    source: Path,
    asset_dir: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    if shape.get("kind") == "grpSp" or shape.get("features", {}).get("group"):
        return None, "group import not implemented"
    geom = geometry_for_import(shape)
    if geom is None:
        return None, "missing x/y/w/h geometry"

    slide_id = slide["id"]
    signature = shape["roundtripSignature"]
    base = sanitize_id(
        f"imported-{shape.get('kind')}-{shape.get('shapeId')}",
        f"imported-{len(slide.get('shapes', [])) + 1}",
    )
    shape_id = unique_shape_id(slide, base)
    spec: dict[str, Any] = {
        "id": shape_id,
        "sourceId": f"{slide_id}.{shape_id}",
        **geom,
        "roundtrip": {
            "origin": "manual-pptx",
            "signature": signature,
            "pptxShapeId": shape.get("shapeId"),
            "pptxName": shape.get("name"),
        },
    }

    if shape.get("omml"):
        spec.update({"type": "equation", "omml": shape["omml"]})
        if shape.get("text"):
            spec["text"] = shape["text"]
        return spec, None

    media_kind, rel = media_kind_and_rel(shape)
    if media_kind and rel:
        if media_kind == "image" and shape.get("features"):
            return None, "image has crop/flip/group features not represented"
        if media_kind == "video" and Path(rel.get("target", "")).suffix.lower() != ".mp4":
            return None, "video import only supports mp4 assets safely"
        try:
            asset = copy_pptx_asset(inspector, rel.get("target", ""), asset_dir, source)
        except ValueError as e:
            return None, str(e)
        spec.update({"type": media_kind, "path": asset["path"]})
        spec["asset"] = asset
        if media_kind == "image":
            spec["sizing"] = {"type": "contain"}
        return spec, None

    if shape.get("kind") == "text" and shape.get("text"):
        spec.update({"type": "text", "text": shape["text"]})
        return spec, None

    return None, f"unsupported untagged shape kind: {shape.get('kind')}"


def import_untagged_shapes(
    source: Path,
    current: dict[str, Any],
    previous: dict[str, Any],
    inspector: PptxInspector,
    asset_dir_arg: Path | None,
) -> dict[str, Any]:
    block = load_managed_block(source)
    asset_dir = resolve_asset_dir(asset_dir_arg, source)
    existing = existing_roundtrip_signatures(block.spec)
    imported = []
    skipped = []
    already_present = []

    for shape in new_untagged_shapes(current, previous):
        summary = summarize_untagged_shape(shape)
        signature = shape["roundtripSignature"]
        if signature in existing:
            already_present.append({**summary, "reason": "already present in source"})
            continue
        slide_index = int(shape.get("slideIndex") or 1)
        slide = ensure_slide_for_index(block.spec, slide_index)
        spec, reason = imported_shape_spec(shape, slide, inspector, source, asset_dir)
        if reason:
            skipped.append({**summary, "reason": reason})
            continue
        slide["shapes"].append(spec)
        existing.add(signature)
        imported.append({
            **summary,
            "sourceId": spec["sourceId"],
            "type": spec["type"],
            "path": spec.get("path"),
        })

    if imported:
        write_managed_block(source, block)

    return {
        "assetDir": str(asset_dir),
        "imported": imported,
        "skipped": skipped,
        "alreadyPresent": already_present,
    }


def save_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8",
                                    dir=path.parent) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    shutil.move(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--source", type=Path,
                        help="managed JS build source to patch")
    parser.add_argument("--state", type=Path, default=Path(".slide-creator/state.json"))
    parser.add_argument("--out", type=Path,
                        help="write inspect/diff report JSON here")
    parser.add_argument("--inspect-only", action="store_true",
                        help="inspect the PPTX and exit")
    parser.add_argument("--init-state", action="store_true",
                        help="write current PPTX inventory as the baseline state")
    parser.add_argument("--apply", action="store_true",
                        help="patch the managed JS block and update state")
    parser.add_argument("--import-untagged", action="store_true",
                        help="import new untagged text/image/video/equation shapes")
    parser.add_argument("--asset-dir", type=Path,
                        help="where copied PPTX media should live (relative to source)")
    parser.add_argument("--tolerance", type=float, default=0.01,
                        help="geometry tolerance in inches")
    args = parser.parse_args()

    if args.import_untagged and not args.apply:
        sys.exit("error: --import-untagged requires --apply")
    if args.asset_dir and not args.import_untagged:
        sys.exit("error: --asset-dir is only used with --import-untagged")

    inspector = PptxInspector(args.pptx)
    inventory = inspector.inspect()
    if args.source:
        inventory["source"] = {"path": str(args.source)}

    if args.inspect_only:
        if args.out:
            write_json(args.out, inventory)
        else:
            print(json.dumps(inventory, ensure_ascii=False, indent=2))
        return

    if args.init_state:
        save_atomic(args.state, inventory)
        print(f"ok: initialized state at {args.state}")
        return

    if not args.state.exists():
        sys.exit(f"error: state file not found: {args.state}; run --init-state first")

    previous = load_json(args.state)
    report = {
        "version": 1,
        "pptx": inventory["pptx"],
        "state": str(args.state),
        "diff": diff_inventory(inventory, previous, args.tolerance),
    }

    if args.apply:
        if not args.source:
            sys.exit("error: --apply requires --source")
        report["sourcePatch"] = apply_changes_to_source(args.source, report["diff"], inventory)
        if args.import_untagged:
            report["imports"] = import_untagged_shapes(
                args.source, inventory, previous, inspector, args.asset_dir
            )
        source_skipped = bool(report["sourcePatch"]["skipped"])
        import_report = report.get("imports", {})
        import_pending = any(import_report.get(key) for key in (
            "imported", "skipped", "alreadyPresent"
        ))
        unimported_manual = (
            bool(report["diff"].get("newUntaggedShapes"))
            and not args.import_untagged
        )
        if source_skipped or import_pending or unimported_manual:
            print("warning: state not updated because regeneration is needed "
                  "before this PPTX can be treated as the new baseline")
        else:
            save_atomic(args.state, inventory)
        imported_count = len(import_report.get("imported", []))
        import_skipped_count = len(import_report.get("skipped", []))
        print(
            "ok: applied "
            f"{len(report['sourcePatch']['applied'])} source-id change(s); "
            f"skipped {len(report['sourcePatch']['skipped'])}; "
            f"imported {imported_count} untagged shape(s); "
            f"import-skipped {import_skipped_count}"
        )
    else:
        n = len(report["diff"]["changed"])
        print(f"ok: found {n} changed source-id shape(s); use --apply to patch")

    if args.out:
        write_json(args.out, report)
        print(f"ok: wrote report {args.out}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
