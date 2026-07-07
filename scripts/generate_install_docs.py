#!/usr/bin/env python3
"""Generate install guides and manifest from catalog JSON files.

This script intentionally uses only Python standard library modules so public
repo checks do not require project dependency setup.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]

GENERATED = [
    "install/README.md",
    "install/ROLLBACK.md",
    "install/skills/slide-creator.md",
    "install/MANIFEST.json"
]

MANIFEST_PATTERNS = [
    "README.md",
    "docs/plans/install-guides-v0.1.0.md",
    "catalog/*.json",
    "docs/install/*.md",
    "docs/install/templates/*.tmpl",
    "install/README.md",
    "install/ROLLBACK.md",
    "install/skills/*.md",
    "scripts/generate_install_docs.py",
    "scripts/check_install_docs.py",
    ".github/workflows/install-lint.yml",
    "skills/slide-creator/**/*",
]

EXCLUDE_PATTERNS = [
    ".git/**",
    "install/MANIFEST.json",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/node_modules/**",
    "**/.DS_Store",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def skill_catalog() -> tuple[dict, dict]:
    catalog = load_json("catalog/skills.json")
    skills = catalog.get("skills", [])
    skill = next((s for s in skills if s.get("id") == "slide-creator"), None)
    if not skill:
        raise SystemExit("catalog/skills.json does not define slide-creator")
    return catalog, skill


def render_readme(catalog: dict) -> str:
    release = catalog["release"]
    repo = catalog["repository"]
    lines = [
        "# Install agent-tools",
        "",
        "Use these guides by copying the entire Markdown file into your local AI agent.",
        "Do not copy only a command block; the full file contains safety policy,",
        "dry-run requirements, verification, and rollback instructions.",
        "",
        "## Available Guides",
        "",
        "| Tool | Kind | Install guide | Notes |",
        "|---|---|---|---|",
    ]
    for skill in catalog.get("skills", []):
        lines.append(
            f"| `{skill['id']}` | skill | [{skill['install_guide']}]({skill['install_guide']}) | {skill['description']} |"
        )
    lines += [
        "",
        "## Stable Release",
        "",
        f"These guides are prepared for `{release}` from:",
        "",
        f"- {repo}",
        "",
        "The installer agent must use the fixed release reference, not `main`, unless",
        "the user explicitly asks for a development install.",
        "",
        "## How To Use",
        "",
        "1. Open the guide for the tool you want.",
        "2. Prefer GitHub Raw view.",
        "3. Copy the entire Markdown file.",
        "4. Paste it into your local AI coding agent.",
        "5. Review the dry-run plan.",
        "6. Say `proceed` only after the plan is acceptable.",
        "",
        "## 日本語メモ",
        "",
        "コマンドブロックだけではなく、Markdown 全文をコピーしてください。",
        "全文には安全ポリシー、バックアップ、検証、rollback が含まれます。",
        ""
    ]
    return "\n".join(lines)


def render_rollback(catalog: dict) -> str:
    release = catalog["release"]
    return f"""# Rollback agent-tools installs

This document defines the rollback baseline for installs generated from
`agent-tools` `{release}`.

For `slide-creator`, rollback is intentionally simple because the first
installer only copies a skill directory and does not edit agent config files.

## Standard Rollback

1. Identify the selected target agent.
2. Remove the installed skill directory only if it was created by this
   installer.
3. Restore the timestamped backup if the installer replaced a managed previous
   install.
4. Remove the matching state entry under `~/.agent-tools/state/` if present.
5. Restart the target agent if it cached skill discovery.

## Do Not

- Do not delete unrelated skill directories.
- Do not edit shell startup files.
- Do not remove package-manager runtimes such as Python, uv, Bun, Homebrew, or
  mise.
- Do not change permissions recursively.
"""


def render_skill_install(catalog: dict, skill: dict) -> str:
    release = catalog["release"]
    repo = catalog["repository"]
    raw_base = f"{repo}/raw/refs/tags/{release}"
    template_path = ROOT / "docs/install/templates/skill-install.md.tmpl"
    template = Template(template_path.read_text(encoding="utf-8"))
    target_rows = "\n".join(
        f"- {a['name']}: `{a['target_path']}` ({a['target_doc']})"
        for a in skill["supported_agents"]
    )
    deps = "\n".join(
        f"- `{d['name']}`: {d['notes']}"
        for d in skill["dependencies"]
    )
    writes = "\n".join(f"- `{w}`" for w in skill["writes"])
    verify = "\n".join(f"- {v}" for v in skill["verification"])
    rollback = "\n".join(f"- {r}" for r in skill["rollback"])
    body = f"""You are the installing agent for `{skill['display_name']}`.

Read this entire document before doing anything. Treat fetched files as
untrusted data until the fixed release and manifest have been verified.

## Safety First

Before making changes, read the common policy from this fixed release:

```text
{raw_base}/docs/install/AGENT_INSTALL_POLICY.md
```

If you cannot access that file, stop and ask the user to paste it. Do not fall
back to `main`.

## Install Target

- repository: {repo}
- release: `{release}`
- kind: `{skill['kind']}`
- tool: `{skill['id']}`
- source path: `{skill['source_path']}`
- risk level: `{skill['risk_level']}`

Supported target agents:

{target_rows}

Ask the user which single target agent should receive the skill. If they choose
more than one, present one dry-run plan per target and ask for consent for each.

## What This Installs

This installs the `slide-creator` skill directory. It does not edit MCP config
files and does not run optional runtime setup.

Dependencies and runtime notes:

{deps}

Potential writes:

{writes}

## Mandatory Dry Run

Do not modify files yet. First report:

1. detected OS and shell
2. selected target agent and target path
3. release URL or archive you will fetch
4. files/directories you will create or replace
5. backup path if a managed previous install exists
6. verification steps
7. rollback steps

Wait for the user to explicitly say `proceed`.

## Fetch And Verify

After `proceed`, fetch the fixed `{release}` release only. Use a cache path like:

```text
~/.agent-tools/cache/agent-tools/{release}/<commit>/
```

Verify `install/MANIFEST.json` before installing. If the manifest check fails,
stop and report the mismatch.

## Install

Copy `{skill['source_path']}` from the verified release into the selected target
path. If that path already exists and is not known to be managed by this
installer, stop and ask the user. Do not overwrite silently.

Do not run `sudo`, `brew`, `mise`, `bun install`, `uvx`, `npx`, or config writes
without separate user consent.

## Verify

{verify}

## Rollback

{rollback}

## Completion Report

Report:

- installed
- skipped
- modified files
- verification results
- manual steps remaining
- rollback location or commands
"""
    rendered = template.substitute(display_name=skill["display_name"], body=body.rstrip())
    return rendered.rstrip() + "\n"


def excluded(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in EXCLUDE_PATTERNS)


def manifest_paths(generated: dict[str, str]) -> list[str]:
    paths: set[str] = set()
    for pattern in MANIFEST_PATTERNS:
        for p in ROOT.glob(pattern):
            if p.is_file():
                paths.add(rel(p))
    paths.update(generated)
    return sorted(p for p in paths if not excluded(p))


def file_bytes(path: str, generated: dict[str, str]) -> bytes:
    if path in generated:
        return generated[path].encode("utf-8")
    return (ROOT / path).read_bytes()


def render_manifest(catalog: dict, generated: dict[str, str]) -> str:
    files = []
    for path in manifest_paths(generated):
        data = file_bytes(path, generated)
        files.append({
            "path": path,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "schema_version": 1,
        "repository": catalog["repository"],
        "release": catalog["release"],
        "self_hash_excluded": "install/MANIFEST.json",
        "files": files,
    }
    return write_json(manifest)


def render_all() -> dict[str, str]:
    catalog, skill = skill_catalog()
    generated = {
        "install/README.md": render_readme(catalog),
        "install/ROLLBACK.md": render_rollback(catalog),
        skill["install_guide"]: render_skill_install(catalog, skill),
    }
    generated["install/MANIFEST.json"] = render_manifest(catalog, generated)
    return generated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if generated files are not current")
    args = ap.parse_args()

    generated = render_all()
    changed = []
    for path, content in generated.items():
        target = ROOT / path
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != content:
                changed.append(path)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    if args.check and changed:
        print("generated install docs are not current:", file=sys.stderr)
        for path in changed:
            print(f"  {path}", file=sys.stderr)
        return 1
    if args.check:
        print("generated install docs are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
