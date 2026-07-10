# Improving an Existing Hand-Made Deck

Use this mode when the user supplies a .pptx they built by hand in PowerPoint
and wants it improved. There is **no build script**: nothing can be
regenerated, so every change is surgery on the binary. Core principle:
**preserve the user's design and content, edit surgically, verify the diff.**

## Step 1 — Understand the deck first

Read the deck's OWN design system before touching anything:

```bash
uv run scripts/ingest_deck.py deck.pptx                    # text + layout + media + summary
uv run scripts/ingest_deck.py deck.pptx --render qa/thumbs # + approximate thumbnails
uv run scripts/verify_deck.py deck.pptx --text             # plain text read-through
```

From the report and thumbnails, note the palette, fonts, layout rhythm
(margins, title band, column grid), and the proof object anchoring each slide.
The existing deck IS the design system — exactly as in template-following. Do
not impose a new one, and do not "fix" stylistic choices the user didn't ask
about. Thumbnails are approximate (LibreOffice); trust geometry numbers from
`ingest_deck.py` over rendered pixel positions.

## Step 2 — Improve surgically

This is a targeted-edit job — read [editing.md](editing.md):

- Content/layout changes: python-pptx at run level (formatting survives),
  OOXML surgery for what it can't reach.
- Equations/videos/animations: the power tools (`add_equation.py`,
  `add_video.py`, `animate.py`).
- Swap or pull out images: `extract_media.py` to get the originals, then
  replace deliberately.
- Duplicate/delete slides: `clone_slide.py`.

**NEVER rebuild from scratch.** There is no source to rebuild from; a rebuild
means retyping the user's deck from a lossy reading of it — content and
formatting will silently drift. Change only what was asked.

## Step 3 — Guardrail: the deck is a user-owned master

- **Back it up before the first edit** with an OS-native file copy. Never edit
  the only copy. `safe_rebuild.py` is for generated decks that have a current
  source-built reference; a hand-made deck usually has no such reference.
- If the user may also edit the deck in PowerPoint between your edits, check
  the file mtime and re-ingest before each editing session — your mental
  model may be stale (same failure mode as [roundtrip.md](roundtrip.md)'s
  live-master guard).
- **After each change, diff your result against your pre-edit backup:**

  ```bash
  uv run scripts/capture_edits.py --reference backup.pptx \
      --edited deck.pptx --hide-low-confidence
  ```

  Every reported change must be one you intended. Anything else is drift —
  investigate before continuing.

## Step 4 — Verify

```bash
uv run scripts/verify_deck.py deck.pptx                          # structural gate
uv run scripts/render_slides.py deck.pptx --slides 3,7 --out qa/ # re-render touched slides
uv run scripts/check_video.py deck.pptx --thumb qa/video         # if videos involved
```

Use PowerPoint PDF QA (`powerpoint_pdf_qa.py`) before final delivery, as for
any deck a human will see.
