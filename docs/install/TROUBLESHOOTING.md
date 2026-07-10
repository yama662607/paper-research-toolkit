# Install Troubleshooting

## The Release Tag Does Not Exist

Stop. The install guide is written for a fixed release. Ask the user whether to
wait for the release or explicitly opt into an unfixed development install.

## Permission Denied

Report the path and command that failed. Do not retry with `sudo` automatically.
Ask the user for the smallest permission change that would allow the install.

## Windows Path Not Found

Confirm whether the target agent is a native Windows app or is running inside
WSL. Native Windows paths should be under `%USERPROFILE%` or
`$env:USERPROFILE`; WSL paths should be under the Linux home directory. Do not
create both unless the user asks for both target environments.

## PowerShell Execution Policy

Installing `slide-creator` does not require changing the PowerShell execution
policy. If a later optional command appears to need an execution policy change,
stop and ask the user for separate consent with the exact command and rollback
step.

## WSL And Windows Target Confusion

If an agent runs in WSL, it usually discovers skills from the WSL filesystem. If
an agent runs as a native Windows app, it usually discovers skills from the
Windows profile directory. Ask the user which app actually loads the skill
before writing through `/mnt/c/` or copying into both locations.

## Path Separator Or Case Issues

Use OS-native path handling. Avoid mixing `/` and `\` in generated commands.
Treat case sensitivity as platform-dependent, especially when a Windows path is
accessed from WSL.

## Target Directory Already Exists

If the directory was not created by this installer, stop and ask. The user may
want to back up, compare, or remove it manually.

## Manifest Check Failed

Stop. Do not install partially verified files. Report the failing path, expected
hash, actual hash, and release reference.

## Optional Runtime Tool Is Missing

The `slide-creator` skill can be installed without optional runtime setup.
Report the missing tool and explain which later operation needs it. Ask before
running package managers.

On macOS, package managers may include Homebrew or mise. On Linux, they may
include apt, dnf, pacman, zypper, or mise. On Windows, they may include winget,
choco, scoop, or runtime installers. Do not run any of them without separate
consent.

Microsoft PowerPoint PDF automation is macOS-only. On Linux or Windows, use
LibreOffice only as an explicitly approximate render path, or ask the user to
perform the final fidelity check in desktop PowerPoint. Do not present an
approximate render as PowerPoint truth.
