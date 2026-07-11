# slide-creator v0.3.0 content-quality gates

## Goal

Turn the July 2026 real-deck feedback into enforceable content-quality gates
without weakening the v0.2.0 PowerPoint safety and round-trip guarantees.

## Scope

- require a compact content plan with claims, audience questions, evidence,
  slide-to-slide bridges, and presenter-understanding status
- distinguish measured, literature, derived, fitted, calibrated, assumed, and
  illustrative numbers
- require figure accountability and scientific-model formulation for progress
  meetings and technical research talks
- make 16 pt audience-readable text mechanically checkable through
  `verify_deck.py --min-font-size 16`
- preserve the existing fail-closed rebuild workflow unchanged

## Validation

- compile all bundled Python scripts
- run unit tests and cross-platform runtime smoke tests
- validate the skill directory
- regenerate deterministic install docs and manifest for v0.3.0
- run generated-doc, manifest, secret, and local-path checks
- obtain an independent review of crash/corruption risk and SKILL.md
  discoverability

## Release boundary

This change prepares v0.3.0 metadata and install artifacts. Do not create the
tag or GitHub release until review is complete and the branch is merged.
