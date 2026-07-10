import importlib.util
import datetime
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "slide-creator"
    / "scripts"
    / "safe_rebuild.py"
)
SPEC = importlib.util.spec_from_file_location("safe_rebuild", SCRIPT)
safe_rebuild = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(safe_rebuild)


class PowerPointProcessTests(unittest.TestCase):
    def test_windows_detects_powerpoint(self):
        result = subprocess.CompletedProcess([], 0, '"POWERPNT.EXE","123"\n', "")
        with (
            mock.patch.object(safe_rebuild.os, "name", "nt"),
            mock.patch.object(safe_rebuild.shutil, "which", return_value="tasklist"),
            mock.patch.object(safe_rebuild.subprocess, "run", return_value=result) as run,
        ):
            self.assertTrue(safe_rebuild.powerpoint_running())
        self.assertEqual(run.call_args.args[0][0], "tasklist")

    def test_windows_without_tasklist_is_unknown(self):
        with (
            mock.patch.object(safe_rebuild.os, "name", "nt"),
            mock.patch.object(safe_rebuild.shutil, "which", return_value=None),
        ):
            self.assertIsNone(safe_rebuild.powerpoint_running())

    def test_posix_uses_pgrep(self):
        result = subprocess.CompletedProcess([], 0, b"123\n", b"")
        with (
            mock.patch.object(safe_rebuild.os, "name", "posix"),
            mock.patch.object(safe_rebuild.shutil, "which", return_value="pgrep"),
            mock.patch.object(safe_rebuild.subprocess, "run", return_value=result) as run,
        ):
            self.assertTrue(safe_rebuild.powerpoint_running())
        self.assertEqual(run.call_args.args[0], ["pgrep", "-x", "Microsoft PowerPoint"])


class BackupTests(unittest.TestCase):
    def test_backup_never_reuses_an_existing_name(self):
        class FixedDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 7, 10, 14, 25, 8, 740506, tzinfo=tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deck = root / "deck.pptx"
            deck.write_bytes(b"deck")
            with mock.patch.object(safe_rebuild.datetime, "datetime", FixedDatetime):
                first = safe_rebuild.make_backup(deck, root / "backups")
                second = safe_rebuild.make_backup(deck, root / "backups")
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"deck")
            self.assertEqual(second.read_bytes(), b"deck")


class EditGateTests(unittest.TestCase):
    def test_edit_check_uses_deep_and_keeps_low_confidence(self):
        result = subprocess.CompletedProcess([], 0, '{"changes": []}', "")
        with (
            mock.patch.object(safe_rebuild.shutil, "which", return_value="uv"),
            mock.patch.object(safe_rebuild.subprocess, "run", return_value=result) as run,
        ):
            self.assertEqual(
                safe_rebuild.check_untracked_edits(Path("ref.pptx"), Path("deck.pptx")),
                0,
            )
        command = run.call_args.args[0]
        self.assertIn("--deep", command)
        self.assertNotIn("--hide-low-confidence", command)

    def test_suspected_noise_requires_explicit_allowance(self):
        report = '{"changes": [{"slide": 1, "kind": "added_in_edited", "confidence": "low", "suspected_noise": true}]}'
        result = subprocess.CompletedProcess([], 0, report, "")
        with (
            mock.patch.object(safe_rebuild.shutil, "which", return_value="uv"),
            mock.patch.object(safe_rebuild.subprocess, "run", return_value=result),
        ):
            self.assertEqual(
                safe_rebuild.check_untracked_edits(Path("ref.pptx"), Path("deck.pptx")),
                3,
            )
            self.assertEqual(
                safe_rebuild.check_untracked_edits(
                    Path("ref.pptx"), Path("deck.pptx"), allow_suspected_noise=True
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
