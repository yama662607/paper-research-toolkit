#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""Normalize safe PPTX package metadata after a writer emits the file.

This is not a PowerPoint "repair". It only removes package metadata that
points at files that are not in the ZIP, de-duplicates package metadata, drops
directory entries, and recompresses the archive. It refuses to guess missing
content types for real package parts.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", CT_NS)


def content_type_extension(part_name: str) -> str:
    if part_name.endswith(".rels"):
        return "rels"
    return Path(part_name).suffix.lower().lstrip(".")


def normalize_content_types(ct_xml: bytes, file_names: set[str]) -> tuple[bytes, list[str]]:
    root = ET.fromstring(ct_xml)
    log: list[str] = []

    seen_defaults: dict[str, str] = {}
    seen_overrides: dict[str, str] = {}
    remove: list[ET.Element] = []

    for child in list(root):
        tag = child.tag.split("}", 1)[-1]
        if tag == "Default":
            ext = (child.get("Extension") or "").lower()
            ctype = child.get("ContentType") or ""
            if not ext:
                remove.append(child)
                log.append("removed default with empty extension")
            elif ext in seen_defaults:
                if seen_defaults[ext] != ctype:
                    raise SystemExit(
                        f"conflicting [Content_Types].xml defaults for .{ext}: "
                        f"{seen_defaults[ext]!r} vs {ctype!r}"
                    )
                remove.append(child)
                log.append(f"removed duplicate default for .{ext}")
            else:
                seen_defaults[ext] = ctype
        elif tag == "Override":
            part = (child.get("PartName") or "").lstrip("/")
            ctype = child.get("ContentType") or ""
            if not part:
                remove.append(child)
                log.append("removed override with empty PartName")
            elif part not in file_names:
                remove.append(child)
                log.append(f"removed stale override for missing part {part}")
            elif part in seen_overrides:
                if seen_overrides[part] != ctype:
                    raise SystemExit(
                        f"conflicting [Content_Types].xml overrides for {part}: "
                        f"{seen_overrides[part]!r} vs {ctype!r}"
                    )
                remove.append(child)
                log.append(f"removed duplicate override for {part}")
            else:
                seen_overrides[part] = ctype

    for child in remove:
        root.remove(child)

    missing_content_types = []
    for name in sorted(file_names):
        if name == "[Content_Types].xml":
            continue
        ext = content_type_extension(name)
        if name not in seen_overrides and ext not in seen_defaults:
            missing_content_types.append(name)
    if missing_content_types:
        raise SystemExit(
            "package parts without content type default/override; refusing to "
            f"guess: {missing_content_types}"
        )

    ET.indent(root, space="  ")
    return (
        ET.tostring(root, encoding="UTF-8", xml_declaration=True),
        log,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--out", type=Path, help="write to this file instead of modifying in place")
    args = parser.parse_args()

    src = args.pptx.expanduser().resolve()
    if not zipfile.is_zipfile(src):
        sys.exit(f"error: {src} is not a ZIP/PPTX archive")

    out = args.out.expanduser().resolve() if args.out else src
    with zipfile.ZipFile(src) as zin:
        entries = zin.infolist()
        names = [info.filename for info in entries if not info.filename.endswith("/")]
        counts = Counter(names)
        duplicate_names = sorted(name for name, count in counts.items() if count > 1)
        file_names = set(names)
        if "[Content_Types].xml" not in file_names:
            sys.exit("error: [Content_Types].xml missing at archive root")
        ct_xml, ct_log = normalize_content_types(zin.read("[Content_Types].xml"), file_names)
        payloads: dict[str, bytes] = {}
        for info in entries:
            name = info.filename
            if name.endswith("/") or name in payloads:
                continue
            payloads[name] = ct_xml if name == "[Content_Types].xml" else zin.read(info)

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=out.parent, suffix=".pptx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in sorted(payloads):
                zout.writestr(name, payloads[name])
        if out == src:
            shutil.move(str(tmp_path), src)
        else:
            shutil.move(str(tmp_path), out)
    finally:
        tmp_path.unlink(missing_ok=True)

    changes = []
    if duplicate_names:
        changes.append(f"removed duplicate ZIP entries: {duplicate_names}")
    changes.extend(ct_log)
    if changes:
        print(f"ok: normalized {out}")
        for change in changes:
            print(f"  - {change}")
    else:
        print(f"ok: {out} already normalized")


if __name__ == "__main__":
    main()
