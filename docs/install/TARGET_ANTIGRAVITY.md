# Target: Antigravity

Use this target only when the user explicitly chooses Antigravity.

Default skill paths:

| OS | Default path |
|---|---|
| macOS | `~/.agents/skills/slide-creator` |
| Linux | `~/.agents/skills/slide-creator` |
| Windows | `%USERPROFILE%\.agents\skills\slide-creator` |

Installation is a directory copy. If the directory already exists and was not
created by this installer, stop and ask the user before replacing it.

The current Antigravity CLI convention uses `.agents/skills`. If an older or
custom installation reports a different discovery path, stop and ask before
copying into both locations.

If Antigravity runs inside WSL, use the Linux path inside WSL. If Antigravity
runs as a native Windows app, use the Windows path. Do not bridge between the
two without explicit user confirmation.
