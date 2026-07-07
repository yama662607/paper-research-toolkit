#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdfium2>=4.30.0", "pillow>=10.0"]
# ///
"""Render PPTX decks for visual QA via PowerPoint PDF export + PDFium.

This is the high-fidelity Mac path:
1. copy the PPTX into PowerPoint's sandbox container,
2. ask Microsoft PowerPoint for Mac to export that staged deck to PDF,
3. copy the PDF back to the requested output directory,
4. optionally rasterize the PDF pages with PDFium for local visual checks.

Staging avoids asking PowerPoint to read/write arbitrary project paths and
reduces macOS Office "Grant Access" prompts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import platform
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

DEFAULT_STAGING = (
    Path.home()
    / "Library/Containers/com.microsoft.Powerpoint/Data/Documents/slide-creator-export"
)


def apple_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-")
    return stem or "deck"


def deck_keys(paths: list[Path]) -> list[str]:
    seen: dict[str, int] = {}
    keys = []
    for path in paths:
        base = safe_stem(path)
        count = seen.get(base, 0) + 1
        seen[base] = count
        keys.append(base if count == 1 else f"{base}-{count}")
    return keys


def run_osascript(script: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-"],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


@contextmanager
def powerpoint_automation_lock(staging_root: Path):
    """Serialize PowerPoint automation across concurrent QA invocations."""
    import fcntl

    staging_root.mkdir(parents=True, exist_ok=True)
    lock_file = (staging_root / ".powerpoint-pdf-qa.lock").open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def export_error_message(raw: str) -> str:
    if "-9074" not in raw:
        return raw
    return (
        raw
        + "\nPowerPoint reported -9074. This usually means PowerPoint rejected "
        "the deck during open/export or its automation session is stale. Run "
        "verify_deck.py first, close any PowerPoint dialogs/windows, restart "
        "PowerPoint if necessary, then retry."
    )


def check_powerpoint_available() -> None:
    if platform.system() != "Darwin":
        sys.exit("error: PowerPoint PDF export requires macOS.")
    if not shutil.which("osascript"):
        sys.exit("error: osascript is required but was not found.")
    proc = subprocess.run(
        ["osascript", "-e", 'id of application "Microsoft PowerPoint"'],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip()
        sys.exit(f"error: Microsoft PowerPoint for Mac is not available: {msg}")


def export_pdf_with_powerpoint(
    pptx: Path,
    pdf: Path,
    key: str,
    staging_root: Path,
    timeout: int,
    delay: float,
    keep_staging: bool,
) -> dict[str, Any]:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = staging_root / f"{key}-{uuid.uuid4().hex[:8]}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_pptx = staging_dir / pptx.name
    staged_pdf = staging_dir / f"{key}.pdf"
    shutil.copy2(pptx, staged_pptx)
    staged_pdf.unlink(missing_ok=True)

    script = f"""
set pptxPath to POSIX file {apple_string(str(staged_pptx))}
set pdfPath to POSIX file {apple_string(str(staged_pdf))}
set expectedName to {apple_string(staged_pptx.name)}
set expectedFullName to {apple_string(str(staged_pptx))}
set openedPres to missing value
set openedName to ""
set openedFullName to ""
try
    tell application "Microsoft PowerPoint"
        activate
        set preflightCount to count presentations
        if preflightCount is greater than 0 then
            error "PowerPoint has " & preflightCount & " open presentation(s). Close them before running slide-creator PDF QA so the script cannot export the wrong active presentation." number -1728
        end if
        open pptxPath
        delay {delay}
        set postOpenCount to count presentations
        if postOpenCount is not 1 then
            error "PowerPoint opened " & postOpenCount & " presentations after opening the staged deck; refusing to guess the active document." number -1730
        end if
        set openedPres to presentation 1
        set openedName to name of openedPres
        try
            set openedFullName to full name of openedPres
        end try
        if openedName contains "Repaired" or openedName is not expectedName then
            close openedPres saving no
            set openedPres to missing value
            error "PowerPoint opened the deck under an unexpected name, usually because it repaired the file. Expected: " & expectedName & "; opened: " & openedName number -1729
        end if
        if openedFullName is not "" and openedFullName is not expectedFullName then
            close openedPres saving no
            set openedPres to missing value
            error "PowerPoint opened an unexpected file. Expected: " & expectedFullName & "; opened: " & openedFullName number -1731
        end if
        save openedPres in pdfPath as save as PDF
        close openedPres saving no
    end tell
    return openedName & linefeed & openedFullName
on error errMsg number errNum
    try
        tell application "Microsoft PowerPoint"
            if openedPres is not missing value then close openedPres saving no
        end tell
    end try
    error errMsg number errNum
end try
"""
    try:
        proc = run_osascript(script, timeout)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stage": "export",
            "error": f"PowerPoint export timed out after {timeout}s",
            "stagingDir": str(staging_dir),
        }

    if proc.returncode != 0:
        raw_error = proc.stderr.strip() or proc.stdout.strip() or "osascript failed"
        return {
            "ok": False,
            "stage": "export",
            "error": export_error_message(raw_error),
            "stagingDir": str(staging_dir),
            "openedName": proc.stdout.strip() or None,
        }
    stdout_lines = proc.stdout.splitlines()
    opened_name = stdout_lines[0].strip() if stdout_lines else ""
    opened_full_name = stdout_lines[1].strip() if len(stdout_lines) > 1 else ""
    if not staged_pdf.exists():
        return {
            "ok": False,
            "stage": "export",
            "error": (
                f"PowerPoint returned without creating {staged_pdf}. "
                f"Opened presentation: {opened_name or 'unknown'}. "
                "Run verify_deck.py first; if it passes, close/reopen "
                "PowerPoint and retry. Some deck content may still block "
                "PowerPoint PDF export."
            ),
            "stagingDir": str(staging_dir),
            "openedName": opened_name or None,
            "openedFullName": opened_full_name or None,
        }

    shutil.copy2(staged_pdf, pdf)
    result: dict[str, Any] = {
        "ok": True,
        "pdf": str(pdf.resolve()),
        "stagingDir": str(staging_dir),
        "openedName": opened_name or None,
        "openedFullName": opened_full_name or None,
    }
    if keep_staging:
        result["stagedPptx"] = str(staged_pptx)
        result["stagedPdf"] = str(staged_pdf)
    else:
        staged_pptx.unlink(missing_ok=True)
        staged_pdf.unlink(missing_ok=True)
        try:
            staging_dir.rmdir()
        except OSError:
            pass
    return result


def clear_old_slide_images(slides_dir: Path) -> None:
    slides_dir.mkdir(parents=True, exist_ok=True)
    for path in slides_dir.glob("slide-*.png"):
        path.unlink()


def white_rgb(image: Any) -> Any:
    from PIL import Image

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def render_pdf_with_pdfium(pdf: Path, slides_dir: Path, dpi: int) -> list[Path]:
    import pypdfium2 as pdfium

    clear_old_slide_images(slides_dir)
    document = pdfium.PdfDocument(str(pdf))
    paths: list[Path] = []
    scale = dpi / 72
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=scale)
            image = white_rgb(bitmap.to_pil())
            path = slides_dir / f"slide-{index + 1:02d}.png"
            image.save(path)
            paths.append(path)
    finally:
        document.close()
    return paths


def make_contact_sheet(slide_paths: list[Path], output: Path, columns: int = 3) -> None:
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    if not slide_paths:
        return
    thumb_w = 420
    gap = 24
    label_h = 24
    font = ImageFont.load_default()

    thumbs = []
    for index, path in enumerate(slide_paths, start=1):
        image = Image.open(path).convert("RGB")
        thumb_h = max(1, round(image.height * (thumb_w / image.width)))
        thumb = image.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        thumb = ImageOps.expand(thumb, border=1, fill=(180, 180, 180))
        canvas = Image.new("RGB", (thumb.width, thumb.height + label_h), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((4, 4), f"Slide {index}", fill=(40, 40, 40), font=font)
        canvas.paste(thumb, (0, label_h))
        thumbs.append(canvas)

    columns = max(1, min(columns, len(thumbs)))
    rows = (len(thumbs) + columns - 1) // columns
    cell_w = max(item.width for item in thumbs)
    cell_h = max(item.height for item in thumbs)
    sheet = Image.new(
        "RGB",
        (columns * cell_w + (columns + 1) * gap, rows * cell_h + (rows + 1) * gap),
        "white",
    )
    for index, thumb in enumerate(thumbs):
        col = index % columns
        row = index // columns
        x = gap + col * (cell_w + gap)
        y = gap + row * (cell_h + gap)
        sheet.paste(thumb, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def process_deck(
    pptx: Path,
    key: str,
    out_dir: Path,
    staging_root: Path,
    timeout: int,
    delay: float,
    dpi: int,
    keep_staging: bool,
    pdf_only: bool,
) -> dict[str, Any]:
    pptx = pptx.expanduser().resolve()
    if not pptx.exists():
        return {"ok": False, "deck": str(pptx), "error": "input PPTX does not exist"}
    if pptx.suffix.lower() != ".pptx":
        return {"ok": False, "deck": str(pptx), "error": "input must be a .pptx file"}

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / f"{key}.pdf"
    slides_dir = out_dir / "slides"
    contact_sheet = out_dir / "contact-sheet.png"

    item: dict[str, Any] = {
        "ok": False,
        "deck": str(pptx),
        "outDir": str(out_dir.resolve()),
        "dpi": dpi,
    }
    export_result = export_pdf_with_powerpoint(
        pptx, pdf, key, staging_root, timeout, delay, keep_staging
    )
    item["export"] = export_result
    if not export_result.get("ok"):
        item["error"] = export_result.get("error")
        return item

    if pdf_only:
        item.update(
            {
                "ok": True,
                "pdf": str(pdf.resolve()),
                "slideCount": None,
                "note": "PDF exported; raster images were skipped by --pdf-only.",
            }
        )
        manifest = out_dir / "manifest.json"
        manifest.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        item["manifest"] = str(manifest.resolve())
        return item

    try:
        slide_paths = render_pdf_with_pdfium(pdf, slides_dir, dpi)
        make_contact_sheet(slide_paths, contact_sheet)
    except Exception as exc:
        item["stage"] = "render"
        item["error"] = str(exc)
        return item

    item.update(
        {
            "ok": True,
            "pdf": str(pdf.resolve()),
            "slides": [str(path.resolve()) for path in slide_paths],
            "contactSheet": str(contact_sheet.resolve()),
            "slideCount": len(slide_paths),
        }
    )
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    item["manifest"] = str(manifest.resolve())
    return item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", nargs="+", type=Path, help="One or more .pptx decks")
    parser.add_argument("--out", type=Path, default=Path("qa/powerpoint-pdf"))
    parser.add_argument("--dpi", type=int, default=144, help="PDFium rasterization DPI")
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--timeout", type=int, default=180, help="PowerPoint export timeout per deck")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to wait after PowerPoint opens the deck")
    parser.add_argument("--keep-staging", action="store_true", help="Keep staged PPTX/PDF files for debugging")
    parser.add_argument("--pdf-only", action="store_true", help="Export PowerPoint PDFs only; skip PDFium PNG/contact-sheet rendering")
    args = parser.parse_args()

    check_powerpoint_available()
    out_root = args.out.expanduser().resolve()
    staging_root = args.staging_dir.expanduser().resolve()
    keys = deck_keys(args.pptx)
    multiple = len(args.pptx) > 1

    results = []
    with powerpoint_automation_lock(staging_root):
        for pptx, key in zip(args.pptx, keys, strict=True):
            deck_out = out_root / key if multiple else out_root
            result = process_deck(
                pptx,
                key,
                deck_out,
                staging_root,
                args.timeout,
                args.delay,
                args.dpi,
                args.keep_staging,
                args.pdf_only,
            )
            results.append(result)
            status = "ok" if result.get("ok") else "FAIL"
            print(f"{status}: {pptx} -> {result.get('outDir', deck_out)}")
            if result.get("ok"):
                if args.pdf_only:
                    print(f"  pdf: {result['pdf']}")
                else:
                    print(f"  contact sheet: {result['contactSheet']}")
            else:
                print(f"  error: {result.get('error')}")

    out_root.mkdir(parents=True, exist_ok=True)
    summary = out_root / "powerpoint-pdf-qa-results.json"
    summary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"results: {summary}")

    if not all(item.get("ok") for item in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
