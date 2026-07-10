# slide-creator v0.2.0 completion plan

## Goal

Publish the current local slide-creator implementation as one reproducible,
cross-agent release before the next feedback-driven development cycle begins.

## Scope

- Publish existing-deck ingestion and surgical-edit guidance.
- Publish layout/media extraction, video-completeness checks, approximate
  selective rendering, and the safe rebuild gate.
- Publish the expanded tagged and untagged round-trip workflow.
- Keep PowerPoint PDF QA explicitly macOS-only and document approximate
  LibreOffice behavior on macOS, Linux, and Windows.
- Use the current Antigravity `.agents/skills` discovery path.
- Regenerate deterministic install docs and the release manifest for v0.2.0.
- Validate on macOS, Linux, and Windows CI.

## Verification

```bash
python scripts/generate_install_docs.py --check
python scripts/check_install_docs.py
python -m py_compile scripts/*.py skills/slide-creator/scripts/*.py
python -m unittest discover -s tests -p "test_*.py"
uv run tests/runtime_smoke.py
```

Run the read-only analysis tools against a real deck containing equations,
video, and animations. Confirm self-diff produces zero changes. The historical
smoke fixture may remain intentionally invalid when it demonstrates that the
current verifier rejects an unresolved relationship.

## Release

Merge through a pull request, create the annotated `v0.2.0` tag, attach a
release manifest with commit and archive hashes, then deploy the exact released
skill tree to Claude Code, Codex, and Antigravity.
