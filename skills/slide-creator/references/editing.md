# Editing Existing Decks (python-pptx + OOXML surgery)

python-pptx (MIT) is the only mature library that *reads* pptx. Use it for
content edits; drop to raw OOXML only for what it can't reach. When the user
supplies a template, inherit its design — never rebuild from scratch.

## Content edits with python-pptx

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-pptx"]
# ///
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation("deck.pptx")
slide = prs.slides[1]                       # 0-indexed
for shape in slide.shapes:
    print(shape.shape_id, shape.name, shape.shape_type)
prs.save("deck.pptx")
```

Run one-off edit scripts with `uv run` (inline deps as above).

**Preserve formatting when replacing text.** Setting `shape.text_frame.text`
or `shape.text` nukes run-level formatting. Replace at run level instead:

```python
for para in shape.text_frame.paragraphs:
    for run in para.runs:
        if "PLACEHOLDER" in run.text:
            run.text = run.text.replace("PLACEHOLDER", "actual value")
```

Longer replacement text may overflow the box — visual QA catches this; be
ready to shrink font size or shorten the text.

**Preserve native list formatting.** Bullets and numbered lists must remain
PowerPoint-native and editable. Do not replace a list with literal "•", "-",
"1.", "1)", or circled-number prefixes, and do not create detached marker
shapes for ordinary lists. When editing an existing list, replace run text
inside each paragraph and leave the paragraph properties (`<a:pPr>`,
including `<a:buChar>` / `<a:buAutoNum>`) intact. If you must create a new
list while editing, use pptxgenjs bullet/numbering options or add the bullet
OOXML deliberately; python-pptx indentation alone is not a substitute for a
real PowerPoint list marker.

**Images into placeholders**: `placeholder.insert_picture(path)`. Free
placement: `slide.shapes.add_picture(path, Inches(x), Inches(y), width=...)`.

**Duplicating and deleting slides**: python-pptx has no API, and the
widely-circulated deepcopy idiom silently breaks slides that carry images,
video, charts, or notes (their relationships aren't copied). Use the
bundled tool instead — it wires rels, Content_Types, and presentation.xml,
and sweeps orphaned parts on delete:

```bash
uv run scripts/clone_slide.py clone deck.pptx --slide 3 --after 5
uv run scripts/clone_slide.py delete deck.pptx --slide 4
uv run scripts/clone_slide.py clean deck.pptx     # orphan sweep only
```

Slide numbers are presentation order (1-based). Clones share media parts
with the original (no file bloat); speaker notes are not carried over.

**Reordering** lives in `ppt/presentation.xml` → `<p:sldIdLst>`; python-pptx
exposes `prs.slides._sldIdLst` — reorder its children.

**Working from a supplied template**: read
[template-following.md](template-following.md) — the clone-and-edit
contract there overrides the guidance below.

## Syncing user PowerPoint edits back to source

If the deck was generated from a round-trip-ready build script, do not make
manual source edits by eye after the user adjusts the PPTX. Inspect the edited
PPTX and patch the managed JS block:

```bash
uv run scripts/sync_from_pptx.py edited.pptx \
  --source deck-build/build_deck.mjs \
  --state deck-build/.slide-creator/state.json \
  --out deck-build/.slide-creator/sync-report.json

uv run scripts/sync_from_pptx.py edited.pptx \
  --source deck-build/build_deck.mjs \
  --state deck-build/.slide-creator/state.json \
  --apply

# If the user added new manual objects after the baseline:
uv run scripts/sync_from_pptx.py edited.pptx \
  --source deck-build/build_deck.mjs \
  --state deck-build/.slide-creator/state.json \
  --apply --import-untagged --asset-dir assets/roundtrip
```

Read [roundtrip.md](roundtrip.md) first. The current safe patch surface is
stable-id text and geometry, plus explicit import of new untagged text, image,
video, and OMML equation objects with `--import-untagged`. Charts, animations,
SmartArt, and complex groups remain review-only unless the user explicitly asks
for a targeted rebuild.

## OOXML surgery (the escape hatch)

```bash
unzip -o deck.pptx -d unpacked/
# edit unpacked/ppt/slides/slide2.xml ...
cd unpacked && zip -q -r -X ../deck-edited.pptx . && cd ..
```

Iron rules:

- Zip the **contents** of the unpacked dir, not the dir itself —
  `[Content_Types].xml` must sit at archive root or PowerPoint reports the
  file unreadable.
- Every `r:embed`/`r:link`/`r:id` in a slide must have a matching entry in
  `ppt/slides/_rels/slideN.xml.rels`; every media file needs its extension
  in `[Content_Types].xml`. The triangle (slide XML ↔ rels ↔ Content_Types)
  must stay consistent — `verify_deck.py` checks it.
- Pretty-print for reading (`xmllint --format`), but edit the original
  compact file; do not re-save whole files through a formatter (whitespace
  inside `<a:t>` is significant unless `xml:space="preserve"`).
- Namespace prefixes matter. Never let a tool rewrite or strip them.
- Prefer surgical string/element edits with clearly unique anchors over
  parse-transform-serialize round trips.

When adding text with typographic quotes or non-ASCII punctuation directly
into XML, use numeric entities (`&#x201C;` etc.) to survive editor encoding
mishaps.

## Working with a supplied template

1. Render it once (LibreOffice → PDF → images) and look: identify the layout
   families, fonts, and color language.
2. Reuse its slide masters/layouts: `prs.slide_layouts` from *their* file,
   not a blank Presentation().
3. Replace placeholder content at run level (formatting survives).
4. If the template has N example items and your content has fewer, delete the
   extra shapes entirely (image + text as a unit) — clearing text but leaving
   frames is the most common template-editing defect.
5. Leftover-placeholder scan is built into `verify_deck.py`.

## Feature gaps — route around, don't fight

| Need | Route |
|---|---|
| Equations | `scripts/add_equation.py` (after content edits) |
| Video embed/autoplay | `scripts/add_video.py` |
| Transitions/animations | `scripts/animate.py` (last, after visual QA) |
| SmartArt | Not programmable with OSS. Recreate as shapes, or leave untouched. |
| Combo charts (new) | Build that slide with pptxgenjs and merge, or use a matplotlib image. |
