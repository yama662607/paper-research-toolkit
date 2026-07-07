#!/usr/bin/env python3
"""Validate generated install docs, manifest hashes, and safety text."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile("_auth" + "Token"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
]

LOCAL_PATTERNS = [
    re.compile(r"/Users/"),
    re.compile(r"GoogleDrive"),
    re.compile(r"gmail", re.IGNORECASE),
]

SCAN_PATHS = [
    "install",
    "docs/install",
    "skills/slide-creator",
]


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as f:
        return json.load(f)


def check_generated() -> int:
    return subprocess.run(
        [sys.executable, "scripts/generate_install_docs.py", "--check"],
        cwd=ROOT,
        check=False,
    ).returncode


def check_catalog() -> int:
    catalog = load_json("catalog/skills.json")
    if catalog.get("release") != "v0.1.0":
        return fail("catalog/skills.json release must be v0.1.0")
    skills = catalog.get("skills")
    if not isinstance(skills, list) or len(skills) != 1:
        return fail("catalog/skills.json must define exactly one initial skill")
    skill = skills[0]
    required = ["id", "source_path", "install_guide", "supported_agents", "verification", "rollback"]
    missing = [k for k in required if k not in skill]
    if missing:
        return fail(f"slide-creator catalog missing keys: {', '.join(missing)}")
    if skill["id"] != "slide-creator":
        return fail("initial skill must be slide-creator")
    if not (ROOT / skill["source_path"] / "SKILL.md").is_file():
        return fail("slide-creator source_path does not contain SKILL.md")
    for agent in skill["supported_agents"]:
        for key in ("id", "name", "target_path", "target_doc"):
            if key not in agent:
                return fail(f"supported agent missing {key}")
        if not (ROOT / agent["target_doc"]).is_file():
            return fail(f"missing target doc: {agent['target_doc']}")
    for path in ("catalog/mcp.json", "catalog/bundles.json"):
        load_json(path)
    return 0


def check_manifest() -> int:
    manifest = load_json("install/MANIFEST.json")
    if manifest.get("self_hash_excluded") != "install/MANIFEST.json":
        return fail("manifest must exclude itself")
    seen = set()
    for item in manifest.get("files", []):
        path = item.get("path")
        if not path or path in seen:
            return fail(f"bad or duplicate manifest path: {path}")
        seen.add(path)
        if path == "install/MANIFEST.json":
            return fail("manifest must not hash itself")
        full = ROOT / path
        if not full.is_file():
            return fail(f"manifest path missing: {path}")
        data = full.read_bytes()
        import hashlib
        if len(data) != item.get("size"):
            return fail(f"manifest size mismatch: {path}")
        if hashlib.sha256(data).hexdigest() != item.get("sha256"):
            return fail(f"manifest sha256 mismatch: {path}")
    required = {
        "install/README.md",
        "install/ROLLBACK.md",
        "install/skills/slide-creator.md",
        "docs/install/AGENT_INSTALL_POLICY.md",
        "skills/slide-creator/SKILL.md",
    }
    missing = sorted(required - seen)
    if missing:
        return fail(f"manifest missing required paths: {', '.join(missing)}")
    return 0


def check_install_guide() -> int:
    guide = (ROOT / "install/skills/slide-creator.md").read_text(encoding="utf-8")
    required_phrases = [
        "Copy this entire Markdown file",
        "Do not copy only command blocks",
        "untrusted data until the fixed release and manifest have been verified",
        "Wait for the user to explicitly say `proceed`",
        "Do not run `sudo`, `brew`, `mise`, `bun install`, `uvx`, `npx`, or config writes",
        "v0.1.0",
    ]
    for phrase in required_phrases:
        if phrase not in guide:
            return fail(f"install guide missing phrase: {phrase}")
    return 0


def check_no_node_modules() -> int:
    bad = list((ROOT / "skills/slide-creator").glob("**/node_modules/**"))
    if bad:
        return fail("node_modules must not be published under skills/slide-creator")
    return 0


def check_secret_scan() -> int:
    for base in SCAN_PATHS:
        root = ROOT / base
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if "__pycache__" in rel or rel.endswith(".pyc"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    return fail(f"secret-like pattern {pattern.pattern} in {rel}")
            for pattern in LOCAL_PATTERNS:
                if pattern.search(text):
                    return fail(f"local-path pattern {pattern.pattern} in {rel}")
    return 0


def main() -> int:
    checks = [
        check_generated,
        check_catalog,
        check_manifest,
        check_install_guide,
        check_no_node_modules,
        check_secret_scan,
    ]
    for check in checks:
        rc = check()
        if rc:
            return rc
    print("install docs checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
