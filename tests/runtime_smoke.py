#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-pptx>=1.0", "pillow>=10.0"]
# ///
"""Cross-platform smoke test for slide-creator's read-only utility scripts."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Inches


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "slide-creator" / "scripts"


def run(script: str, *args: object, expected: int = 0) -> subprocess.CompletedProcess:
    command = ["uv", "run", "--quiet", str(SCRIPTS / script), *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != expected:
        raise AssertionError(
            f"{script} returned {result.returncode}, expected {expected}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def build_fixture(path: Path, image_path: Path) -> None:
    Image.new("RGB", (32, 24), "#3A6B5C").save(image_path)
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.7), Inches(0.5), Inches(5), Inches(0.6))
    box.text_frame.paragraphs[0].text = "Runtime fixture"
    slide.shapes.add_picture(
        str(image_path), Inches(1), Inches(1.5), width=Inches(2), height=Inches(1.5)
    )
    prs.save(path)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="slide-creator-runtime-") as tmp:
        root = Path(tmp)
        deck = root / "fixture.pptx"
        image = root / "fixture.png"
        build_fixture(deck, image)

        run("verify_deck.py", deck)

        ingest = run("ingest_deck.py", deck, "--json")
        summary = json.loads(ingest.stdout)["summary"]
        assert summary["slide_count"] == 1

        layout = run("dump_layout.py", deck, "--slide", 1, "--json")
        assert json.loads(layout.stdout)["1"]

        out = root / "media"
        run("extract_media.py", deck, "--slide", 1, "--out", out)
        assert list(out.glob("media_1.*"))
        run("extract_media.py", deck, "--slide", 1, "--out", out, expected=2)
        run("extract_media.py", deck, "--slide", 1, "--out", out, "--overwrite")

        diff = run(
            "capture_edits.py",
            "--reference",
            deck,
            "--edited",
            deck,
            "--deep",
            "--json",
        )
        assert json.loads(diff.stdout)["changes"] == []

        report = root / "inspect.json"
        run("sync_from_pptx.py", deck, "--inspect-only", "--out", report)
        assert len(json.loads(report.read_text(encoding="utf-8"))["slides"]) == 1

        run("safe_rebuild.py", "--deck", deck, expected=2)
        backups = root / "backups"
        run(
            "safe_rebuild.py",
            "--deck",
            deck,
            "--reference",
            deck,
            "--backup-dir",
            backups,
        )
        assert len(list(backups.glob("fixture_backup_*.pptx"))) == 1

    print("slide-creator runtime smoke tests passed")


if __name__ == "__main__":
    main()
