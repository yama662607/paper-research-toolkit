# Transitions and Shape Animations

The most dangerous PPTX territory. Read the risk model first; it dictates
everything else.

## Risk model (community-verified)

- **Slide transitions (`p:transition`)**: simple, flat element. Raw XML
  injection is reliable. Safe to use freely.
- **Shape animations (`p:timing`)**: a deep SMIL-derived timing tree. Small
  mistakes make PowerPoint **silently drop the animation** or destabilize the
  file — there is no error to iterate against. This is why python-pptx has
  refused the feature since 2014 and why `scripts/animate.py` only instantiates
  *proven* XML templates (extracted from real PowerPoint files and public
  Microsoft samples) with substituted parameters, instead of composing trees
  freely.
- **LibreOffice**: transitions survive fine; shape animations can make
  Impress misbehave or crash (e.g. entrance+emphasis stacked on one trigger).
  Hence the build order: animations are injected **after** visual QA, and
  nothing renders the deck afterwards.

Keep it minimal: for academic decks, transitions + fade/appear entrances
cover 95% of real needs. Resist building animation choreography.

Do not put animation instructions on audience-facing slides. Text like
`click to reveal`, `クリックごとに表示`, or "shown after click" belongs in
speaker notes, the build script, or the task list. If it appears in the
rendered slide image, it is a QA defect even when the animation itself works.

## Transitions

```bash
uv run scripts/animate.py transition deck.pptx --slide 2 --type fade
uv run scripts/animate.py transition deck.pptx --all --type fade      # whole deck
uv run scripts/animate.py transition deck.pptx --slide 1 --type push --duration 700
uv run scripts/animate.py transition deck.pptx --slide 4 --type morph
```

Types: `fade`, `wipe`, `push` (2010 extension, p14 namespace), `morph`
(2015 extension, p159 namespace). For p14/p159 types the script writes the
required `mc:AlternateContent` with a plain `<p:fade/>` in `mc:Fallback` —
omitting the fallback makes older PowerPoint and LibreOffice show a "repair"
dialog, so never strip it.

**Morph specifics**: Morph interpolates shapes matched **by name** (not spid)
between consecutive slides — ensure the moving shape has the same
`p:cNvPr name` on both slides. A slide containing untouched empty
placeholders can prevent Morph from engaging; delete unused placeholders.

## Shape animations

Workflow — always list shapes first, then attach effects by id:

```bash
uv run scripts/animate.py shapes deck.pptx --slide 2
#   id=2  name="Title 1"
#   id=4  name="fig-panel-a"     ...

uv run scripts/animate.py effect deck.pptx --slide 2 --spid 4 --effect fade-in
uv run scripts/animate.py effect deck.pptx --slide 2 --spid 5 --effect fade-in --trigger after --delay 500
uv run scripts/animate.py effect deck.pptx --slide 2 --spid 6 --effect appear --trigger auto
```

Effects (v1, deliberately minimal): `appear` (instant visibility toggle via
`p:set`), `fade-in` (`p:animEffect filter="fade"` + opacity ramp), `wipe-in`
(`filter="wipe(fromLeft)"`). Triggers:

| `--trigger` | Meaning | XML reality |
|---|---|---|
| `click` (default) | next click starts it | new click group, `delay="indefinite"` |
| `with` | simultaneous with previous | sibling in same group, `delay="0"` |
| `after` | after previous | sibling, `delay="<ms>"` (use `--delay`) |
| `auto` | on slide entry | top-level condition `delay="0"` |

The trigger is *only* a `p:cond` delay value — the tree shape is identical.
This is why one template per effect suffices.

## How the injection works (for when you must go deeper)

Templates live in `assets/timing-templates/`. Each is a verified fragment for
one click-group; `animate.py` substitutes shape id, duration, delay, and
assigns globally-unique `p:cTn id` values, then:

- slide has **no** `<p:timing>` → builds the root scaffold
  (tmRoot → mainSeq) and inserts the group.
- slide has a timing tree **created by this tool** → appends another click
  group into the existing mainSeq.
- slide has a **foreign or `mc:AlternateContent`-wrapped** timing tree →
  **refuses**. Merging into unknown trees is exactly how files corrupt
  (cf. python-pptx #954). Options: accept the refusal (skip animation), or
  rebuild that slide's animations entirely with this tool.

Element order inside `p:sld` matters: `p:cSld`, `p:clrMapOvr`,
`p:transition`, `p:timing`. The scripts maintain this; keep it if editing
manually.

`spid` gotchas: animation targets shapes via `p:spTgt spid` = `p:cNvPr id`.
Duplicate ids (a real-world occurrence after careless shape copying) make
animations fire on the wrong shape — `verify_deck.py` checks id uniqueness.
Prefer animating a **group shape** over many individual shapes: group the
"reveal unit" in the build step, animate the group. Fewer moving parts,
fewer id problems.

## Verification

After any animation work: `uv run scripts/verify_deck.py deck.pptx` (never a
LibreOffice render). For decks that matter, flip through once in real
PowerPoint — silent drops are invisible to structural checks by definition.
