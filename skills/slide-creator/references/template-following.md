# Template-Following Mode

When the user supplies a template or existing deck whose look must be
preserved (lab template, conference template, corporate format), the design
system is **inherited, not designed**. This mode overrides
design-profiles.md's visual system entirely — the template IS the visual
system. Phrases that route here: 「このテンプレで」「この形式に合わせて」
「研究室のフォーマット」, or any attached pptx presented as a starting point.

## The contract: clone-and-edit, never rebuild

The single failure mode this document exists to prevent: *rebuilding
template slides from scratch to "match" their look*. A rebuild always
drifts — fonts fall back, spacing shifts, theme colors get hardcoded, and
placeholder inheritance breaks. The reliable operation is mechanical:
**duplicate the template's own slide, then edit the copy's content in
place.** Layout, masters, theme, and spacing then survive by construction
rather than by imitation.

## Workflow

1. **Inventory** — render the template
   (`soffice --headless --convert-to pdf` → `pdftoppm`) and view every
   layout. Extract text (`verify_deck.py --text`). For each template slide
   record: its role (cover / section / content-1col / content-2col /
   closing…), which text runs are placeholder vs fixed chrome (logos,
   footers, page numbers), and what must never change.

2. **Map** — for each output slide, choose which template slide it derives
   from. Every output slide must map to exactly one template slide. If no
   template slide can host some content, say so and propose the closest
   fit — do not invent a new layout in someone else's design system.

3. **Duplicate** — `uv run scripts/clone_slide.py clone deck.pptx --slide N
   [--after M]` for each mapped output slide (media references and
   package wiring are handled; notes are not carried). Work on a copy of
   the template file, never the user's original.

4. **Edit in place** — replace text at run level (`run.text`), swap images
   via the existing picture shapes where possible. Preserve everything you
   weren't asked to change: fonts, sizes, colors, positions, footers,
   decorative chrome — even elements you dislike. Template-following mode
   suspends our own taste rules; inherited "violations" (their accent bars,
   their beige) are *their* brand, keep them.

5. **Trim** — delete unused template slides
   (`clone_slide.py delete deck.pptx --slide N`; orphan sweep is automatic).

6. **Fidelity QA** — render and compare against the template renders
   side-by-side. A screenshot of the output by itself is not enough; place or
   view the reference slide and output slide together and judge the visible
   differences. The question is not "does it look good?" but **"does it look
   like the template with new content?"** Check: same fonts (no silent
   fallback), same title positions, chrome intact, no leftover placeholder
   text (`verify_deck.py` scans), text still fits (longer replacement text is
   the main overflow source — shrink text or split content, don't resize the
   template's boxes). Also check natural line breaks: Japanese titles must not
   split words mid-term, and inherited figure/media boxes must have content
   with a reasonable visual center and occupancy, not a small diagram stranded
   in empty space.

7. **Deviation log** — anything you changed beyond content (had to shrink
   a font, removed a 4th feature box because content had 3 items), list
   explicitly in your report. Silent deviations are how template decks
   lose trust.

## Rules of thumb

- Template has 4 item-boxes, content has 3 → delete the 4th box *entirely*
  (its icon, frame, and text as a unit). Empty frames are the most common
  template-editing defect.
- Adding slides mid-deck: clone the template's closest content slide, not
  the previous output slide (avoids compounding edits).
- Closing/summary slides: use a full-bleed or dark closing layout only if
  the template already has that role. Otherwise clone the closest normal
  summary/content slide; do not invent a new closing style inside someone
  else's format.
- Figures inserted into template placeholders should fill the intended area
  gracefully. Prefer enlarging/re-rendering the figure within the placeholder
  over leaving wide blank margins; keep explanatory prose in the template's
  text area, not inside the figure unless it is a short label.
- Never re-save through LibreOffice, never "clean up" their XML style, and
  keep `p:cNvPr` names when Morph transitions may be in play (Morph matches
  by name).
- Our power tools still work in this mode: equations
  (`add_equation.py` — match the template's body font size), video
  (`add_video.py`), and `verify_deck.py` at the end.
