#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdfium2>=4.30", "pillow>=10.0"]
# ///
"""APPROXIMATE render of specific slides to PNG via LibreOffice + PDFium.

Fallback for when the high-fidelity path (powerpoint_pdf_qa.py, which needs
Microsoft PowerPoint and refuses to run while PowerPoint has a presentation
open) is unavailable and you just need to eyeball a few slides. LibreOffice
rendering is NOT PowerPoint fidelity: fonts, spacing, equations, and effects
can drift. Read-only on the input deck (LibreOffice only converts; it never
re-saves the pptx).

Usage:
  render_slides.py DECK.pptx --slides 2,7,12 --out DIR [--scale 1.7]
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOFFICE_APP = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


def find_soffice() -> str:
    if SOFFICE_APP.is_file():
        return str(SOFFICE_APP)
    on_path = shutil.which("soffice")
    if on_path:
        return on_path
    sys.exit(
        "error: LibreOffice (soffice) not found. Install LibreOffice or put "
        "'soffice' on PATH (tried /Applications/LibreOffice.app and PATH)."
    )


def parse_slides(spec: str) -> list[int]:
    try:
        slides = sorted({int(s) for s in spec.split(",") if s.strip()})
    except ValueError:
        sys.exit(f"error: --slides must be comma-separated integers, got {spec!r}")
    if not slides or any(n < 1 for n in slides):
        sys.exit("error: slide numbers are 1-indexed positive integers")
    return slides


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("deck", type=Path, help="input .pptx (never modified)")
    ap.add_argument("--slides", required=True,
                    help="comma-separated 1-indexed slide numbers, e.g. 2,7,12")
    ap.add_argument("--out", required=True, type=Path,
                    help="output directory for slide<N>.png files")
    ap.add_argument("--scale", type=float, default=1.7,
                    help="PDFium render scale (default 1.7 ≈ 1224px wide for 16:9)")
    args = ap.parse_args()

    if not args.deck.is_file():
        sys.exit(f"error: deck not found: {args.deck}")
    slides = parse_slides(args.slides)
    soffice = find_soffice()
    args.out.mkdir(parents=True, exist_ok=True)

    import pypdfium2 as pdfium

    with tempfile.TemporaryDirectory(prefix="render_slides_") as tmp:
        proc = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", tmp, str(args.deck)],
            capture_output=True, text=True, timeout=300,
        )
        pdf_path = Path(tmp) / (args.deck.stem + ".pdf")
        if proc.returncode != 0 or not pdf_path.is_file():
            detail = (proc.stderr or proc.stdout or "").strip()[:300]
            sys.exit(f"error: LibreOffice PDF conversion produced no PDF. {detail}")

        pdf = pdfium.PdfDocument(pdf_path)
        try:
            n_pages = len(pdf)
            written, skipped = [], []
            for n in slides:
                if n > n_pages:
                    skipped.append(n)
                    continue
                bitmap = pdf[n - 1].render(scale=args.scale)
                out_png = args.out / f"slide{n}.png"
                bitmap.to_pil().save(out_png)
                written.append(out_png)
        finally:
            pdf.close()

    for p in written:
        print(f"wrote {p}")
    if skipped:
        print(f"warning: skipped slide(s) {skipped} — PDF has only {n_pages} page(s)",
              file=sys.stderr)
    print("NOTE: images are APPROXIMATE (LibreOffice render, not PowerPoint "
          "fidelity). Fonts/equations/effects may drift; videos show poster "
          "frames only. Use powerpoint_pdf_qa.py for final visual QA.")
    if not written:
        sys.exit(1)


if __name__ == "__main__":
    main()
