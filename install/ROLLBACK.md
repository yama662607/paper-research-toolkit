# Rollback agent-tools installs

This document defines the rollback baseline for installs generated from
`agent-tools` `v0.1.0`.

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
