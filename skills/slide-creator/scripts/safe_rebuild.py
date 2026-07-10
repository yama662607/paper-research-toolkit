#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Pre-rebuild safety gate for a live/master deck. Run this BEFORE any command
that overwrites a .pptx the user may have hand-edited in PowerPoint. It never
rebuilds anything itself; it only checks that overwriting is safe.

Checks, in order:

1. PowerPoint-open detection: if the "Microsoft PowerPoint" process is running
   AND PowerPoint's owner lock file (``~$<basename>``) sits next to the deck,
   the deck is likely open -> exit 2. Rebuilding over an open deck silently
   reverts unsaved manual edits (including swapped images).
2. Timestamped backup: copies the deck to
   ``<backup-dir>/<stem>_backup_<YYYYMMDD-HHMMSS-microseconds>[-N].pptx``
   (default: the deck's own
   directory) so the pre-rebuild state is always recoverable.
3. Untracked manual edits: with --reference, runs the sibling
   capture_edits.py to diff the live deck against a reference rebuilt from the
   current source. Any reported change -> exit 3, so the
   caller folds the manual edits into the build source before rebuilding.

Exit codes: 0 = safe to rebuild, 2 = PowerPoint has the deck open,
3 = untracked manual edits found, 1 = the gate itself could not run.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def powerpoint_running():
    """Return True/False, or None if process detection is unavailable."""
    if os.name == "nt":
        tasklist = shutil.which("tasklist")
        if tasklist is None:
            return None
        try:
            r = subprocess.run(
                [tasklist, "/FI", "IMAGENAME eq POWERPNT.EXE", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return None
        return r.returncode == 0 and "POWERPNT.EXE" in r.stdout.upper()

    if shutil.which("pgrep") is None:
        return None
    try:
        r = subprocess.run(["pgrep", "-x", "Microsoft PowerPoint"],
                           capture_output=True, timeout=10)
    except Exception:
        return None
    return r.returncode == 0


def check_powerpoint_open(deck: Path) -> bool:
    lock = deck.parent / f"~${deck.name}"
    lock_exists = lock.exists()
    running = powerpoint_running()
    if running is None:
        print("warning: pgrep unavailable; relying on the lock file alone")
        if lock_exists:
            print(f"lock file present: {lock}")
            return True
        return False
    print(f"PowerPoint process running: {'yes' if running else 'no'}; "
          f"lock file {lock.name}: {'present' if lock_exists else 'absent'}")
    return running and lock_exists


def make_backup(deck: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for sequence in range(1000):
        suffix = "" if sequence == 0 else f"-{sequence}"
        backup = backup_dir / f"{deck.stem}_backup_{stamp}{suffix}.pptx"
        try:
            dst = backup.open("xb")
        except FileExistsError:
            continue
        with deck.open("rb") as src, dst:
            shutil.copyfileobj(src, dst)
        break
    else:
        raise FileExistsError("could not allocate a unique backup name")
    shutil.copystat(deck, backup)
    return backup


def check_untracked_edits(
    reference: Path,
    deck: Path,
    allow_suspected_noise: bool = False,
) -> int:
    """Run capture_edits.py; return 0 if clean, 3 if edits found, 1 on failure."""
    if shutil.which("uv") is None:
        print("error: 'uv' not found; cannot run capture_edits.py to check for "
              "untracked manual edits. Install uv or run the check manually.",
              file=sys.stderr)
        return 1
    cmd = ["uv", "run", "--quiet", str(SCRIPTS_DIR / "capture_edits.py"),
           "--reference", str(reference), "--edited", str(deck),
           "--deep", "--json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"error: capture_edits.py failed (exit {r.returncode}):\n{r.stderr.strip()}",
              file=sys.stderr)
        return 1
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"error: could not parse capture_edits.py output:\n{r.stdout[:2000]}",
              file=sys.stderr)
        return 1
    changes = report.get("changes", [])
    if allow_suspected_noise:
        changes = [c for c in changes if not c.get("suspected_noise")]
    if not changes:
        print("No untracked manual edits detected.")
        return 0
    print(f"UNTRACKED MANUAL EDITS: {len(changes)} change(s) in the live deck "
          "are not in the source. Fold them into the build source before rebuilding:")
    for c in changes:
        bits = [f"slide {c.get('slide')}", c.get("kind", "?"),
                f"[{c.get('confidence', '?')}]"]
        if "text_from" in c:
            bits.append(f'"{c["text_from"][:40]}" -> "{c.get("text_to", "")[:40]}"')
        for d in c.get("deltas", []):
            bits.append(f'{d["prop"]} {d["from"]}->{d["to"]}')
        bits.append(c.get("reason", ""))
        print("  - " + "  ".join(str(b) for b in bits if b))
    return 3


def main():
    ap = argparse.ArgumentParser(
        description="Safety gate before overwriting a live/master deck: refuse if "
                    "PowerPoint has it open, back it up, and detect untracked manual "
                    "edits. Exit 0=safe, 2=PowerPoint open, 3=untracked edits.")
    ap.add_argument("--deck", required=True, help="the live/master .pptx about to be overwritten")
    ap.add_argument("--reference", required=True,
                    help="deck rebuilt from CURRENT source to a temporary path; "
                         "used to detect untracked edits")
    ap.add_argument("--backup-dir", help="where to write the timestamped backup "
                                         "(default: the deck's own directory)")
    ap.add_argument(
        "--allow-suspected-noise",
        action="store_true",
        help="after manually reviewing the full capture report, allow only changes "
             "marked suspected_noise; all other changes still block rebuilding",
    )
    a = ap.parse_args()

    deck = Path(a.deck).expanduser()
    if not deck.is_file():
        print(f"error: deck not found: {deck}", file=sys.stderr)
        sys.exit(1)

    if check_powerpoint_open(deck):
        print("PowerPoint appears to have this deck open — save and close it first, "
              "then re-run this gate. Rebuilding now would silently revert manual edits.")
        sys.exit(2)

    try:
        backup = make_backup(deck, Path(a.backup_dir).expanduser() if a.backup_dir else deck.parent)
    except OSError as exc:
        print(f"error: backup failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Backup written: {backup}")

    reference = Path(a.reference).expanduser()
    if not reference.is_file():
        print(f"error: reference deck not found: {reference}", file=sys.stderr)
        sys.exit(1)
    rc = check_untracked_edits(reference, deck, a.allow_suspected_noise)
    if rc != 0:
        sys.exit(rc)

    print("Safe to rebuild.")
    sys.exit(0)


if __name__ == "__main__":
    main()
