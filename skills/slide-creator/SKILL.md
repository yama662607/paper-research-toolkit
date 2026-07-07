---
name: slide-creator
description: "Create and edit PowerPoint (.pptx) decks, with first-class support for native math equations (LaTeX → OMML), embedded videos, and animations/transitions — capabilities most pptx tooling lacks. Use whenever a .pptx file or slide deck is involved in any way: creating academic decks (progress meetings, journal clubs, conference talks), editing or reviewing existing decks, adding equations to slides, embedding simulation/experiment videos, adding slide transitions or shape animations, or extracting content from presentations. Trigger on mentions of 'slides', 'deck', 'presentation', 'PowerPoint', 'pptx', 'スライド', 'プレゼン', '発表資料', '進捗報告' — regardless of what the user plans to do with the content afterward."
license: MIT
---

# slide-creator

A general-purpose PPTX toolkit for scientific/academic slide work. Two engines,
four power tools, one build order.

## First Classify the Task

Pick the smallest mode that solves the request, then read only the matching
references:

- **Read/analyze**: inspect text/XML/images; do not load design rules unless
  the user asks for design critique.
- **Targeted edit**: preserve the existing deck's design; change only the
  requested slide/object, then verify.
- **Template-following**: clone-and-edit the supplied deck; the template is
  the design system.
- **New deck**: choose one genre profile and design the deck deliberately.
- **Round-trip collaboration**: when the user will manually adjust a generated
  deck in PowerPoint and wants future regeneration to preserve those edits,
  use a managed JS source block and read
  [references/roundtrip.md](references/roundtrip.md).

For new decks, redesigns, and broad "make this presentation" requests, lock a
lightweight brief before building: audience goal, live vs standalone
consumption, visual source/template or desired look, required media/motion
level, and the deck's proof objects (figures, charts, equations, images,
videos). Ask only for missing information. For targeted edits, do not run a
brief gate; preserve the supplied deck and make the requested change.

Before writing slide code for a new deck, write a compact quality plan:
profile, title/claim spine, visual motif, palette roles, slide-family rhythm,
and which proof object anchors each slide. If this plan would fit any deck
after replacing the topic words, it is too generic — revise it before coding.

## Quick Reference

| Task | Approach |
|------|----------|
| Read / analyze a deck | `uv run scripts/verify_deck.py deck.pptx --text` or unzip + inspect XML |
| Create a new deck | pptxgenjs — read [references/creating.md](references/creating.md) |
| Edit an existing deck | python-pptx + OOXML — read [references/editing.md](references/editing.md) |
| Follow a supplied template strictly | clone-and-edit — read [references/template-following.md](references/template-following.md) |
| Sync PowerPoint hand edits back to source | `scripts/sync_from_pptx.py` — read [references/roundtrip.md](references/roundtrip.md) |
| Normalize writer package metadata | `scripts/normalize_package.py` after BUILD, before verification |
| Duplicate / delete slides safely | `scripts/clone_slide.py` (rels/media/orphans handled) |
| Add native math equations | `scripts/add_equation.py` — read [references/equations.md](references/equations.md) |
| Embed a video | `scripts/add_video.py` — read [references/video.md](references/video.md) |
| Transitions / shape animations | `scripts/animate.py` — read [references/animations.md](references/animations.md) |
| Design foundations (any deck) | read [references/design-principles.md](references/design-principles.md) |
| Genre rules (academic/business/lecture) | read [references/design-profiles.md](references/design-profiles.md) |
| Review / QA checklists & prohibitions | read [references/qa-checklist.md](references/qa-checklist.md) |
| High-fidelity visual QA artifact | `uv run scripts/powerpoint_pdf_qa.py deck.pptx --out qa/powerpoint-pdf --pdf-only` |
| Final validation | `uv run scripts/verify_deck.py deck.pptx` |

All Python scripts are self-contained (`uv run` resolves their dependencies
inline). One-time setup for the equation converter: `cd scripts/omml && bun install`.

Lists are always native PowerPoint lists. Never fake bullets or numbering
with typed markers ("•", "1.", circled numbers) or detached marker shapes;
use editable paragraph bullet/numbering properties instead.

## The Build Order (non-negotiable)

PPTX features differ wildly in how fragile they are and how well QA tooling
tolerates them. Work in this order — it exists because the fragile things
must come after the things QA needs to see, and because non-PowerPoint render
engines can distort or corrupt some features:

```
1. BUILD      deck structure + text + figures   (pptxgenjs or python-pptx)
2. PACKAGE    normalize + structural gate        (normalize_package.py, then verify_deck.py)
3. EQUATIONS  inject LaTeX-derived native math   (scripts/add_equation.py)
4. VIDEO      normalize + embed videos           (scripts/add_video.py)
5. VISUAL QA  PowerPoint PDF → inspect/review     (read-only! see below)
6. ANIMATE    transitions + shape animations     (scripts/animate.py)
7. VERIFY     structural checks, no rendering    (scripts/verify_deck.py)
```

Rules that follow from hard-won community evidence:

- **Never let LibreOffice re-save a deck.** It has multiple known bugs that
  silently destroy embedded video and can corrupt animations. LibreOffice is
  only an approximate fallback renderer when PowerPoint is unavailable.
- **Animations go in last.** LibreOffice can crash on some shape-animation
  combinations, and visual QA cannot see animations anyway. After step 5, the
  only permitted check is step 7 (structural, no rendering).
- **Equations and video go in before visual QA** so the rendered images show
  them (equations render approximately; video shows its poster frame).
- **Normalize and verify immediately after BUILD.** Do not let equation or
  video post-processing hide a broken first writer. Run
  `normalize_package.py` to remove safe writer debris such as directory
  entries and stale `[Content_Types].xml` overrides, then run
  `verify_deck.py`. Fix anything still reported before adding equations,
  videos, or animations.

## Reading Decks

```bash
uv run scripts/verify_deck.py deck.pptx --text     # per-slide text dump
unzip -o deck.pptx -d unpacked/                     # raw XML access
unzip -p deck.pptx ppt/slides/slide1.xml | xmllint --format - | head -100
```

For a visual overview, render to images (see Visual QA below) and view them.

## Creating a New Deck

Write a build script with **pptxgenjs** (run with `bun`). Read
[references/creating.md](references/creating.md) before writing the first
line — it covers layout geometry, text/bullet gotchas, charts, images, and
the post-build rezip step.

**Keep the build script next to the output** (e.g. `deck-build/build_deck.mjs`
beside `progress-2026-07.pptx`). Decks are code: next week's meeting starts by
editing this week's script, and any fix is a re-run instead of surgery on a
binary file.

Do not start from a blank theme plus bullets. Convert the quality plan into a
contact-sheet plan first: cover, evidence slide families, dense/quiet rhythm,
and the visual anchor for every content slide. Then implement.

If the user may edit the deck in PowerPoint and continue iterating with the
agent, make the build script round-trip ready from the beginning: put slide
data in a managed JS block, set `objectName: "scid:<slide>.<shape>"` on
generated shapes, initialize `.slide-creator/state.json`, and use
`sync_from_pptx.py --apply` after manual edits. If the user adds new text,
image, video, or equation objects by hand after the baseline, import them
explicitly with `--import-untagged`, regenerate from source, then initialize
state again from the regenerated deck.

## Editing an Existing Deck

Use **python-pptx** for content changes and OOXML surgery for what it can't
reach. Read [references/editing.md](references/editing.md). Never rebuild a
deck from scratch when the user supplied a template — inherit its design
system.

## Equations, Video, Animations — the Power Tools

These three areas are where mainstream libraries fail silently. The bundled
scripts encapsulate community-verified XML so you don't hand-roll it:

```bash
# LaTeX → native, double-click-editable PowerPoint equation
# (display equations read right at 24-28pt; oversized equations look like posters)
uv run scripts/add_equation.py deck.pptx --slide 2 \
  --latex '\tau \sim \rho^{-1/2} e^{E_a / T_{\mathrm{eff}}}' \
  --x 1 --y 2.5 --w 6 --h 1 --font-size 24

# Normalize codec (H.264/AAC/CFR) and embed with poster + autoplay
uv run scripts/add_video.py deck.pptx --slide 3 sim_rho08.mp4 \
  --x 1 --y 1 --w 5 --h 3.75 --normalize --autoplay

# Slide transition, and a fade-in on one shape
uv run scripts/animate.py transition deck.pptx --slide 1 --type fade
uv run scripts/animate.py shapes deck.pptx --slide 2          # list shape ids
uv run scripts/animate.py effect deck.pptx --slide 2 --spid 4 \
  --effect fade-in --trigger click
```

Each script has `--help`, and `--emit-xml` where applicable (prints the XML it
would inject, so you can adapt it manually when the tool's assumptions don't
fit). If a tool refuses an operation (e.g. a slide already has a complex
timing tree), read its message — the refusal encodes a known corruption risk;
work around it as the message suggests rather than forcing raw XML in.

## Visual QA (step 5 — required for any deck a human will see)

Export a read-only PDF through Microsoft PowerPoint for Mac, then inspect
with fresh eyes. This is the default because PowerPoint PDF export preserves
PowerPoint layout far more closely than LibreOffice/ONLYOFFICE/PPTX browser
renderers. When handing off to an agent that can read PDFs directly, pass the
PDF itself; do not make separate slide images the review contract.

```bash
uv run scripts/powerpoint_pdf_qa.py deck.pptx --out qa/powerpoint-pdf --pdf-only
open qa/powerpoint-pdf/deck.pdf
```

The script stages the PPTX under PowerPoint's macOS container
(`~/Library/Containers/com.microsoft.Powerpoint/Data/Documents/slide-creator-export/`)
before export, copies the PDF back to `--out`, then removes staged files on
success. This avoids asking PowerPoint to read/write arbitrary project paths
and should prevent Office's "Grant Access" dialog in normal use. The script
refuses to run when PowerPoint already has an open presentation, and fails if
PowerPoint appears to open the deck under a repaired or otherwise unexpected
presentation name. If PowerPoint shows a repair dialog during QA, click
Cancel and treat the deck as failed; Repair can hide the original bug. Close
presentations first so the script cannot export the wrong active document.
Concurrent QA runs are serialized with a lock because PowerPoint automation
is single-app state. Use `--keep-staging` only when debugging a failed export.
If you need a local human thumbnail/contact-sheet check, omit `--pdf-only`;
the script will rasterize the PowerPoint PDF with PDFium as an implementation
detail.

Then have a **subagent** (not yourself — you will see what you expect, not
what is there) inspect the exported PDF using the **ready-made QA prompt in
[references/qa-checklist.md](references/qa-checklist.md)** and a Product
Design-style audit discipline: every finding is tied to screenshot evidence,
design/UX risks are separated from visible accessibility risks, and screenshot
limits are named instead of guessed through. Every finding must cite a slide
number/page from the PDF; screenshots or rendered pages are evidence, not
decoration. Fix real, user-visible
defects, re-render only affected slides, and **stop after one fix cycle**
unless a new user-visible defect appeared.

Before delivery, also run the final tests at the end of qa-checklist.md
(title read-through, glance test, grayscale test, time sanity).

Fallback: if PowerPoint for Mac is unavailable, render a PDF with LibreOffice
or ONLYOFFICE and rasterize with PDFium, but label the result approximate and
do not treat it as final visual truth. If those approximate renderers disagree
or show formula/media drift, escalate to PowerPoint PDF export before judging
slide quality.

Font caveat: even with PowerPoint export, text can drift on another machine if
the presentation uses fonts not installed there. Hiragino/Arial are safe on
this Mac; equations use Cambria Math. For Windows-bound decks add ~10% width
slack.

## Final Verification (step 7)

```bash
uv run scripts/verify_deck.py deck.pptx
```

Checks ZIP/package structure, relationship integrity (every referenced media
file exists), re-opens via python-pptx, scans for placeholder debris, and
runs ffprobe on embedded media. It also rejects list-marker-looking text that
was typed by hand instead of made as native PowerPoint bullets/numbering.
Package checks include duplicate ZIP entries, stale `[Content_Types].xml`
overrides, and empty or unresolved `r:id`/`r:embed`/`r:link` references. This
is the only check allowed after animations are injected. Fix anything it
reports before delivering.

## Design (not optional)

Two layers, read **before building** any deck a human will see:

1. [references/design-principles.md](references/design-principles.md) —
   universal, theory-grounded rules (cognitive load, hierarchy, contrast,
   assertion-evidence). Apply always.
2. [references/design-profiles.md](references/design-profiles.md) — pick the
   ONE genre profile that matches the task (progress-meeting, journal-club,
   conference-talk, consulting-deck, pitch, lecture) and commit to the
   visual system (dark-cover sandwich, role-based palette, stat callouts,
   kickers, varied layouts, explicit Japanese font weights).

A structurally perfect deck with plain black-on-white bullets is a *failed*
deck here: the audience reads design as care. Equally failed is generic
"AI-slop" styling — [references/qa-checklist.md](references/qa-checklist.md)
lists the tells; every visual element must be traceable to this deck's
content.

The design standard is the contact-sheet test: at thumbnail size the deck
should show a coherent system, varied slide rhythms, and a visible argument.
At readable size each slide should have one claim, one dominant proof object,
and no filler.

## Dependencies

- `uv` (Python scripts resolve their own deps via inline metadata)
- `bun` + one-time `cd scripts/omml && bun install` (equation conversion)
- `pptxgenjs` for new decks: `bun add pptxgenjs` in your build directory
- Microsoft PowerPoint for Mac — high-fidelity visual QA PDF export
- PDFium via `pypdfium2` (optional local PDF raster/contact-sheet path)
- LibreOffice/ONLYOFFICE — approximate fallback visual QA only
- `ffmpeg`/`ffprobe` — video normalization and verification
