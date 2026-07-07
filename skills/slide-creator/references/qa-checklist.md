# Review Checklist & Prohibitions

Use this at two moments: **step 4 visual QA** (subagent inspection of the
PowerPoint-exported PDF) and the **final pre-delivery review**. Principles behind
every item: [design-principles.md](design-principles.md). Genre-specific
expectations: [design-profiles.md](design-profiles.md).

## Ready-made visual-QA subagent prompt

Export a PowerPoint PDF first (SKILL.md → Visual QA). Prefer
`scripts/powerpoint_pdf_qa.py --pdf-only`, which exports through Microsoft
PowerPoint for Mac and stages files inside PowerPoint's container to avoid
"Grant Access" prompts. Then pass the PDF directly to a subagent with fresh
eyes and this prompt, filling the bracketed parts:

```
Inspect this PowerPoint-exported PDF for defects a live audience would notice.
Deck profile: [progress-meeting / journal-club / conference-talk / ...].
Language: [Japanese/English]. For each slide, list problems found (or "OK").
Review source: [PowerPoint PDF / fallback renderer name].
Skip sub-pixel nitpicks a viewer wouldn't register.
Tie every finding to a slide/page number. Separate structural defects from
polish. Do not claim full accessibility compliance from rendered images alone;
report only visible risks and evidence limits.
Use Product Design audit discipline: cite visible PDF/page evidence, separate
design/UX problems from visible accessibility risks, and name what PDF/page
inspection cannot prove.

PART 1 — Mechanical defects (always fatal, report every instance):
- Text overflowing or clipped at its box/slide edge
- Overlapping elements (text through shapes, labels colliding)
- Gaps < 0.3" between separate blocks; margins < 0.4" from slide edge
- Misaligned elements that share a row/column/grid
- Low-contrast text (must be readable at a glance; body ≈4.5:1 against
  background)
- Leftover placeholder/template text; broken characters (tofu 豆腐, mojibake)
- Fake list markers: literal bullets/numbers typed into text, or detached
  number/icon shapes standing in for an ordinary editable PowerPoint list
- Equations rendered as garbage (this render is approximate — judge
  plausibility of the formula, not exact spacing)

PART 2 — Design-system compliance:
- Contact-sheet test: at thumbnail size, does the deck show a coherent
  visual system, varied slide silhouettes, and a visible argument? Flag decks
  that look like the same card/grid template repeated with new text.
- Does every content slide have a claim-style title (a sentence, not a
  topic label)? Exception: section dividers, agenda.
- Does every content slide have one dominant proof object (figure, chart,
  equation, table, image, or video poster) that supports the title? Flag text
  blocks that merely restate what the presenter should say.
- Cover composition: title block, context/date, and affiliation/supporting
  text form a deliberate vertical composition. Flag covers with a low title,
  a large empty middle, or highlight color used as decoration rather than
  meaning.
- Title position: titles sit in the TOP band of the slide (top edge around
  0.3-0.5"), at a consistent height on every content slide. A vertically
  centered or low-floating title is a defect.
- Title length: one-line title is the default. If a title wraps, check that
  the break follows meaning, the title still reads as one claim, and the body
  region was moved down. A figure, table, or card overlapping the title band
  is a structural defect.
- One message per slide? Flag slides trying to say two things.
- Text boxes sized to their content: bullets or prose wrapping to 3+ lines
  because the box is too narrow is a defect — widen the box or shorten the
  text.
- Japanese wraps: flag broken words or ugly phrase splits in titles and
  bullets (`モデ/ル`, method names split mid-word). Manual line breaks should
  follow meaning, not the textbox edge.
- Visual hierarchy: is the intended first-look element actually the most
  salient? Flag slides where everything has equal weight.
- Authoring instructions visible to the audience (`click to reveal`,
  `クリックごとに表示`, TODO-style production notes) are defects. Put reveal
  intent in notes or the build script, not on the slide.
- Stat callouts: only for THE headline number, with its unit and a context
  line. A big number that isn't the slide's main claim is decoration.
- Palette discipline: base + accent + highlight only; flag stray colors and
  accent-color overuse (accent everywhere = accent nowhere).
- Palette fit: do the colors feel chosen for this topic or evidence? Flag
  generic purple/blue "tech" styling, arbitrary amber accents, or palettes
  that would fit an unrelated deck unchanged.
- Highlight discipline: orange/amber/copper belongs to the one number,
  phrase, or data series that carries the claim. If the highlight color is
  the first thing noticed but does not encode the main point, flag it.
- Motif discipline: repeated design devices should come from the content
  (parameter badges, side rails, figure callouts, equation/result pairing).
  Flag decorative bars, stripes, or repeated icon rows used as a substitute
  for a real motif.
- Same role = same look across slides (kickers, captions, page numbers,
  footers identical in position and style — a footer that changes style
  mid-deck is a defect).
- Footnotes/condition lines: if the audience must read it to understand the
  result, it must be readable from the back of the room. Do not hide N,
  parameters, units, or error-bar definitions in hairline text.
- Layout variety: flag 3+ consecutive slides with identical composition.
- Labels adjacent to what they label; direct labels preferred over distant
  legends.
- Editability risks visible from the deck structure: ordinary lists should
  be PowerPoint lists, simple charts should remain native when later editing
  is likely, and speaker guidance should live in notes rather than visible
  text. If the PDF cannot prove editability, list it as a structural check.

PART 3 — Visible accessibility and evidence limits:
- Contrast risks visible in the render, including low-contrast captions,
  hairline labels, and text over images.
- Color-only meaning: if a result, status, or category is only encoded by
  color, flag it even if the colors look distinct on your monitor.
- Reading order: at thumbnail size, does the eye find the title, evidence,
  and takeaway in the intended order? Flag layouts where the path is unclear.
- Dense slide exception: consulting and lecture slides may contain many
  elements, but they must be grouped into a small number of clear regions
  with one dominant takeaway. Flag uniform density where every element has
  equal weight.
- Motion/media limits: static images cannot prove autoplay, timing, keyboard
  access, or screen-reader behavior. Name those as structural verification
  items, not visual claims.

PART 4 — Genre checks for [profile]:
[paste the profile's own checklist items from design-profiles.md]

Report format:
1. Blocking defects
2. Major design/UX risks
3. Visible accessibility risks and evidence limits
4. Minor polish
5. Strengths worth preserving
6. Skill-rule lessons, if any

PDF (absolute path):
<path>/deck.pdf

Expected pages:
1. slide 1 — (expected: [one-line description])
2. ...
```

After the report: fix real, user-visible defects; re-render only affected
slides; **stop after one fix cycle** unless a new user-visible defect
appeared. Check text-fit first — overflow is the most common defect and is
always visible to the audience.

## Numeric floors (cross-source consensus)

| Item | Floor / rule | Consensus sources |
|---|---|---|
| Body font | ≥ 18 pt (prefer 20–24) | Harvard Chan, ACU, WCAG-derived |
| Title font | ≥ 24 pt (prefer 26–28 here) | Harvard Chan, ACU |
| Conditions/captions | 13–14 pt if needed for interpretation; 11–12 pt only for pure source notes | projection practice |
| Contrast | ≥ 4.5:1 body, ≥ 3:1 large text | WCAG 2.x AA |
| Bullets per slide | ≤ 4 | Harvard Chan, ACU, TEDx |
| Colors | ≤ 3–4 beyond black/white | McKinsey convention, Ethos3 |
| Typefaces | ≤ 2 (+ Cambria Math for equations) | McKinsey, ACU |
| Line spacing | ≥ 1.5 Latin / ≥ 1.15 Japanese | Harvard Chan |
| Pace | ~1 slide per minute of talk | Harvard Chan, Naegle 2021 |
| Elements per slide | Presented talks: ≤ ~6 distinct objects. Consulting/lecture dense slides: many elements allowed only when grouped into clear regions with one dominant takeaway | Naegle 2021 (PLOS Comp Biol), consulting convention |

These are floors for delivered decks; a deliberate design choice may exceed
them, but must be a choice, not an accident.

## Prohibitions

**Universal** (theory-grounded — see design-principles.md for the why):
wall-of-bullets slides; slide text that scripts the narration; topic-only
titles on content slides; unreadable font sizes; low contrast; color-only
meaning; labels far from referents; underline emphasis; everything
emphasized; flat hierarchy; chartjunk (3D charts, heavy gridlines,
decorative gradients on data); undefined jargon; form contradicting meaning.

**"AI slop" tells** — these specific patterns are now widely recognized as
machine-generated filler and quietly destroy credibility. Never produce:
- Purple/indigo gradient backgrounds and cyan-on-dark "tech" styling
- Sparkle/rocket/bulb icon rows; emoji as bullet markers (🚀✨💡)
- Grids of identical feature cards, especially with a colored bar on one
  edge of each card (the single most recognizable tell)
- Accent bars/stripes under titles or along slide edges
- Numbered 1-2-3 "step cards" as default scaffolding for non-process content
- Hand-made bullets or numbering: use native PowerPoint list markers so the
  audience or editor can revise the list normally
- Uniform font size/weight/spacing everywhere (flattened hierarchy)
- Font choices that depend on unavailable fonts for body text, especially
  Aptos in decks meant for older Office installs or mixed Mac/Windows use
- Decoration semantically unrelated to the content ("resembles everything,
  argues for nothing")
The root cause is averaging + safety: defaults that fit any deck fit no
deck. Every visual element must be traceable to THIS deck's content.

**Chart, diagram & geometry precision** (structured visuals are proof
objects — treat them as geometry systems, not decoration):
- A chart must *prove the slide's claim*, not merely display related data.
  If the title says "non-monotonic" the eye must find the minimum instantly.
- Use native editable PowerPoint charts when the visual is a standard chart
  and future editing matters. Use rendered images only when PowerPoint cannot
  express the visual faithfully, and keep the source figure script beside the
  deck.
- One dominant evidence object per slide; two competing charts = two slides.
- Direct-label series on the chart when practical; legends force the eye to
  commute.
- Slide charts must not look like raw notebook output: tune line widths,
  marker size, grid, legend, and annotation placement for the final slide
  size.
- Axis labels, region labels, and annotations must remain readable at slide
  scale. A shaded region, callout, or label that covers the data it explains
  makes the evidence weaker, not clearer.
- Arrows only where direction carries meaning; a connector must visibly
  attach to the objects it relates — floating or mis-attached connectors
  actively mislead.
- Never fake geometry: a trend/connected series must be one continuous path
  or a native chart series — not disconnected segments that can drift apart
  on export.
- Equal-role elements (cards, panels, KPI items, timeline steps) must share
  exact size, alignment, and padding; and a repeated pattern must be
  complete on every item — one KPI cell missing its label reads as an error.
- Text inside filled shapes needs visible breathing room top and bottom;
  asymmetric top/bottom padding, text touching an edge, or text spilling past
  a card edge is delivery-blocking.
- If using media panels or figure placeholders, judge the content's
  occupancy and visual center, not only the frame. A tiny diagram floating
  in a large inherited box is a template-following defect.
- Video comparison slides need a visible comparison takeaway or observation.
  Side-by-side posters with only parameter labels leave the audience to infer
  the point.
- Tables must keep row/column alignment legible even at thumbnail size.
- **Brand authenticity**: never draw, trace, or approximate someone's logo,
  mascot, app icon, or product UI. Use a verified original asset or omit it
  — a lookalike mark is worse than nothing.
- A visible defect in the rendered image overrides any script/checker that
  stays silent about it.

**Academic blockers** (delivery-stopping for academic profiles):
- Pasted paper figures/tables with illegible axis labels (re-plot at slide
  scale: fonts ≥ 12 pt at final size, 2–3× line widths)
- Charts without axis labels/units, or error bars without type (SD/SE/CI)
  and n
- rainbow/jet colormaps on quantitative data (false boundaries); use
  viridis-family; categorical → Okabe-Ito palette
- Borrowed figures without "From …" / "Adapted from …" credit
- Undefined symbols in equations; derivation dumps where a key result +
  physical meaning suffices
- Conclusion withheld until the end (state the answer early; the talk is
  the argument, not a mystery)

**Business blockers** (business profiles):
- Conclusion-last structure (pyramid principle inverts it: answer first)
- Action titles that state activity ("analyzed X") instead of finding
  ("X drives 20% of cost")
- Unsourced numbers; growth curves without an explained inflection point
- Dashboard dumps: many charts, no claim (one chart, one claim)
- False precision (needless decimals); red/green as the only status signal

## Final pre-delivery tests (mechanical + human)

1. `uv run scripts/powerpoint_pdf_qa.py deck.pptx --out qa/powerpoint-pdf --pdf-only` —
   PowerPoint PDF artifact exists and was inspected.
2. `uv run scripts/verify_deck.py deck.pptx` — structural pass required.
3. **Title read-through**: read only the titles in order — they must tell
   the complete story on their own (horizontal flow).
4. **Glance test**: each slide's point graspable in ~3 seconds at thumbnail
   size.
5. **Back-of-room test**: at 50% zoom on screen, is everything readable?
   If borderline, fonts are too small for the projector.
6. **Grayscale test**: flip the rendered images to grayscale mentally (or
   with ImageMagick) — is any meaning lost? If so, color-only encoding
   slipped in.
7. **Editability test**: ordinary lists are native lists; equations are OMML
   where the skill claims native math; simple charts are native when likely to
   be edited; generated plot images keep their source script beside the deck.
8. Time sanity: slide count ≈ talk minutes (±30%).
