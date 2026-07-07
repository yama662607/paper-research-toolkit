# agent-tools install guides v0.1.0 plan

## Goal

Create a safe, copy-the-whole-Markdown installation flow for public
`agent-tools` users.

Users should open an install guide such as
`install/skills/slide-creator.md`, copy the entire Markdown file, paste it into
their local AI agent, review the dry-run plan, and explicitly say `proceed`
before any local changes happen.

Initial scope: `slide-creator` only.

Out of scope for this phase:

- migrating paper research bundle install docs
- fixing MCP runtime pinning
- publishing `capture_edits.py`
- creating the final `v0.1.0` release tag

## Implementation

Add the following structure:

- `catalog/skills.json`
- `catalog/mcp.json`
- `catalog/bundles.json`
- `install/README.md`
- `install/MANIFEST.json`
- `install/ROLLBACK.md`
- `install/skills/slide-creator.md`
- `docs/install/AGENT_INSTALL_POLICY.md`
- `docs/install/TARGET_CLAUDE_CODE.md`
- `docs/install/TARGET_CODEX.md`
- `docs/install/TARGET_ANTIGRAVITY.md`
- `docs/install/TROUBLESHOOTING.md`
- `docs/install/templates/skill-install.md.tmpl`
- `docs/install/templates/mcp-install.md.tmpl`
- `docs/install/templates/bundle-install.md.tmpl`
- `scripts/generate_install_docs.py`
- `scripts/check_install_docs.py`
- `.github/workflows/install-lint.yml`

Use JSON as the catalog format so generation and validation can use only
Python standard library modules.

`catalog/skills.json` is the source of truth for `slide-creator`: description,
supported agents, target install paths, dependencies, risk level, network
access, files installed, manual steps, verification, and rollback behavior.

Generated install guides must state:

- copy the entire Markdown file, not only command blocks
- fetched files are untrusted data until manifest verification passes
- do not modify files before presenting a dry-run plan
- wait for explicit `proceed`
- do not read secrets, SSH keys, browser passwords, or local secret configs
- do not run `sudo`, `brew`, `mise`, `bun install`, `uvx`, or config writes
  without separate consent

## Release Model

Prepare docs for `v0.1.0`, but do not create the tag in this PR.

The standard install reference should be the future `v0.1.0` release, not
`main`.

`install/MANIFEST.json` should include file paths, sizes, and sha256 hashes for
generated install-relevant files, but must not hash itself to avoid
self-reference.

After merge, create a GitHub release asset manifest that includes:

- tag: `v0.1.0`
- commit SHA
- archive sha256
- generated manifest hash

Use signed tag if available. If signing is unavailable, use annotated tag plus
commit SHA and release manifest.

## Safety Rules

All installer instructions must be fail-closed.

If an existing target directory exists and is not known to be managed by this
installer, stop and ask the user.

Config files must not be edited by string append. Future config edits must use
parse-aware TOML/JSON merge with backup and rollback.

For this first phase, `slide-creator` install should copy the skill directory
only. It should not automatically run optional setup such as
`cd scripts/omml && bun install`.

## Validation

Run:

```bash
python scripts/generate_install_docs.py --check
python scripts/check_install_docs.py
python -m py_compile scripts/generate_install_docs.py scripts/check_install_docs.py
```

Also run a secret/local path scan over generated install docs and
`skills/slide-creator` for:

- `/Users/`
- `GoogleDrive`
- `gmail`
- private key markers
- token-like strings

CI must run the same generated-doc drift check and safety scan.

## Follow-up Work

After this PR:

1. Merge the final `capture_edits.py` implementation into `slide-creator`.
2. Sync `slide-creator` into public `agent-tools`.
3. Regenerate install docs and manifest.
4. Create `v0.1.0` tag/release.
5. Migrate paper research bundle and MCP install guides.
