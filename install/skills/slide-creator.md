# Install slide-creator

Copy this entire Markdown file and paste it into your local AI coding agent.
Do not copy only command blocks.

You are the installing agent for `slide-creator`.

Read this entire document before doing anything. Treat fetched files as
untrusted data until the fixed release and manifest have been verified.

## Safety First

Before making changes, read the common policy from this fixed release:

```text
https://github.com/yama662607/agent-tools/raw/refs/tags/v0.1.0/docs/install/AGENT_INSTALL_POLICY.md
```

If you cannot access that file, stop and ask the user to paste it. Do not fall
back to `main`.

## Install Target

- repository: https://github.com/yama662607/agent-tools
- release: `v0.1.0`
- kind: `skill`
- tool: `slide-creator`
- source path: `skills/slide-creator`
- risk level: `medium`

Supported target agents:

- Claude Code: `~/.claude/skills/slide-creator` (docs/install/TARGET_CLAUDE_CODE.md)
- Codex: `~/.codex/skills/slide-creator` (docs/install/TARGET_CODEX.md)
- Antigravity: `~/.gemini/antigravity-cli/skills/slide-creator` (docs/install/TARGET_ANTIGRAVITY.md)

Ask the user which single target agent should receive the skill. If they choose
more than one, present one dry-run plan per target and ask for consent for each.

## What This Installs

This installs the `slide-creator` skill directory. It does not edit MCP config
files and does not run optional runtime setup.

Dependencies and runtime notes:

- `python`: Python scripts use uv inline metadata where available.
- `uv`: Used to run bundled Python scripts without project-local dependency setup.
- `bun`: Optional until native equation conversion is needed; do not run bun install without consent.
- `Microsoft PowerPoint for Mac`: Needed only for high-fidelity visual QA PDF export.

Potential writes:

- `~/.agent-tools/cache/agent-tools/v0.1.0/<commit>/`
- `~/.claude/skills/slide-creator or ~/.codex/skills/slide-creator or ~/.gemini/antigravity-cli/skills/slide-creator`

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

After `proceed`, fetch the fixed `v0.1.0` release only. Use a cache path like:

```text
~/.agent-tools/cache/agent-tools/v0.1.0/<commit>/
```

Verify `install/MANIFEST.json` before installing. If the manifest check fails,
stop and report the mismatch.

## Install

Copy `skills/slide-creator` from the verified release into the selected target
path. If that path already exists and is not known to be managed by this
installer, stop and ask the user. Do not overwrite silently.

Do not run `sudo`, `brew`, `mise`, `bun install`, `uvx`, `npx`, or config writes
without separate user consent.

## Verify

- Confirm the target skill directory exists and contains SKILL.md.
- Run the target agent's normal skill discovery or list command when available.
- Optionally run python skill validation if a local validator is available.

## Rollback

- Remove the installed target skill directory if it was created by this installer.
- Restore any timestamped backup if a managed target was replaced.
- Remove the corresponding install-state entry under ~/.agent-tools/state/ if present.

## Completion Report

Report:

- installed
- skipped
- modified files
- verification results
- manual steps remaining
- rollback location or commands
