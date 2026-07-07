# Install Troubleshooting

## The Release Tag Does Not Exist

Stop. The install guide is written for a fixed release. Ask the user whether to
wait for the release or explicitly opt into an unfixed development install.

## Permission Denied

Report the path and command that failed. Do not retry with `sudo` automatically.
Ask the user for the smallest permission change that would allow the install.

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
