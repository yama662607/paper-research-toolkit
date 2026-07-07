# Design Profiles — the Genre Layer

[design-principles.md](design-principles.md) holds the universal layer that
applies to every deck. This file adds what *changes* by genre. Read the
principles once, then exactly one profile below. Where a profile contradicts
the universal layer, the profile wins — the contradiction encodes a real
genre difference. This file also encodes the owner's taste; edit freely.

## Choosing a profile

Two questions determine almost everything:

1. **What does the audience do with it?** Understand & verify (academic) /
   decide & act (business) / learn & retain (lecture).
2. **How is it consumed?** Presented live (voice carries the explanation,
   slides stay sparse) vs read standalone (deck must be self-sufficient,
   text density rises). Never use one deck for both — the requirements are
   opposite (the "universal deck fallacy").

| Profile | Audience mode | Consumption |
|---|---|---|
| `progress-meeting` | discuss & advise | presented, interactive |
| `journal-club` | learn & critique | presented |
| `conference-talk` | get interested in the paper | presented, strict time |
| `consulting-deck` | decide | **read standalone** |
| `pitch` | invest | presented (+ separate reading deck) |
| `lecture` | learn & retain | presented + handout |
| (template-following) | any | **inherit their design** — see [template-following.md](template-following.md); the visual system below does NOT apply |

## Quality plan before code

Before creating slides from scratch, write this five-line plan in the build
notes or script comments:

1. **Claim spine** — one title/claim per slide; read alone, the titles tell
   the story.
2. **Proof objects** — the figure, chart, equation, table, image, or video
   that proves each claim. Text alone is not a proof object.
3. **Visual motif** — one content-derived repeated device, such as annotated
   phase-space panels, paired parameter badges, equation/result callouts, or
   consistent figure-side rails. Do not use bars, stripes, or generic icon
   rows as the motif.
4. **Palette roles** — one base, one structural color, one highlight, each
   with a meaning. If the colors could be pasted into an unrelated sales deck
   unchanged, choose again.
5. **Contact-sheet rhythm** — the sequence of layout families. Avoid three
   consecutive slides with the same silhouette unless it is a deliberate
   lecture derivation.

## The visual system (all presented profiles)

**Sandwich structure**: dark cover (and optionally the closing/discussion
slide) on `1B2A4A` deep navy; content slides on white. Frames the deck,
reads as intentional at thumbnail scale.

**Palette** (defaults — swap per deck, keep the roles). Prefer a palette
that comes from the subject matter: microscopy images, simulation colors,
material/field metaphors, or the paper's figure language. The default below
is only a safe starting point, not a brand.

| Role | Default | Used for |
|---|---|---|
| Ink | `1A1A1A` | body text on white |
| Paper | `FFFFFF` | content background |
| Deep accent | `1B2A4A` navy | dark slides, claim emphasis, fit curves |
| Highlight | `D55E00` vermilion-orange | THE number/phrase; data points |
| Muted | `666666` | kickers, captions, footers |

One color = one meaning across the whole deck. Red only for
problem/disagreement. Never introduce colors casually (≤ 3–4 total). The
highlight should be visible because it marks the claim-carrying element, not
because it is loud. The old bright amber `E8890C` can look arbitrary on covers
and small labels; use it only after checking the rendered cover/contact sheet,
not as a default.

**Cover composition**: a cover is a composed slide, not a title dropped into
empty space. Use 2–3 anchor zones: small context/date near the top or
bottom, the main title slightly above optical center, and affiliation or
one-line context near the opposite edge. If the title/subtitle is short,
increase scale or add meaningful context; do not leave a large empty middle
or push the title low because a template placeholder used to be there. On
dark covers, reserve highlight color for one short phrase or metric, never
for the whole title.

**Title band**: on content slides the title block hugs the top of the slide
(top edge ≈ 0.3–0.5"), kicker just above it, at the same height on every
slide. Never vertically center a title on a content slide — centered titles
belong only to the dark cover/closing slides. Body content starts below the
title band and uses the full remaining height. Treat one-line titles as the
default: first shorten, then reduce by 1–2 pt, then split into a short title
plus smaller support line. A two-line title is allowed only when the body
region is moved down to preserve a visible gap; figures and cards must never
intrude into the title band.

**Layout families** — vary them (two consecutive slides may share a family,
three may not): claim+figure (workhorse) / figure+side-rail / stat callout /
two-column compare / timeline-steps / discussion card (quiet tinted panel,
clear decision language). A layout family is defined by its silhouette and
reading path, not by changing colors on the same card grid.

Stat callout discipline: reserve it for THE headline number of the deck —
with its unit and one context line (「緩和時間の極小」ρ ≈ 0.54 など). An
arbitrary value blown up to 60 pt is decoration, not emphasis.

Text boxes: size them so bullets and prose wrap to at most ~2 lines; a
narrow column forcing constant line breaks reads as broken. Widen the box,
shorten the text, or change the layout family.

Cards and filled boxes: use them sparingly and make the internal padding
visibly symmetric. Text needs comparable breathing room above and below; a
card with comfortable top padding and text touching the bottom edge reads as
broken even when no text technically overflows. Equal-role cards share exact
height, width, alignment, and text inset.

Japanese line breaks: never let titles or bullets split a semantic word
(`モデル`, `シミュレーション`, a method name) across lines. Insert manual
breaks at phrase boundaries, or reduce the font size by 1-2 pt before
accepting an ugly wrap. Long claim titles may become a short title plus a
smaller support line; do not let the title consume the slide.

**Kickers**: small muted label above the claim title naming the slide's role
(`結果 2/3`, `議論`, `NEXT`), 11–12 pt.

**Still banned** (see qa-checklist.md for the full prohibition list):
decorative bars/stripes, boxes around prose, icon confetti, identical card
grids, centered body text, cream/beige "warm neutral" default backgrounds
(background is white or a deliberate palette color), and half-committed
styling — style every slide to the system or keep the whole deck plain;
one designed slide amid plain ones reads as an accident. Text-only slides
are a smell on results pages: give every content slide a visual anchor
(figure, diagram, stat, table) or move the prose to speaker notes.

## Typography — Japanese/Latin pairing

| Role | Font / weight | Size |
|---|---|---|
| 見出し | **Hiragino Kaku Gothic ProN + bold**(和文はウェイト明示が命 — デフォルトの細さが「見えにくい」の主犯) | 24–28 pt |
| 本文 | 同 ProN(W3)、18 pt 未満禁止 | 18–20 pt |
| 条件・脚注 | 同 ProN(W3)、投影で読む条件文は13–14 pt、純粋な出典だけ11–12 pt可 | 11–14 pt |
| Latin & digits | Arial / Helvetica Neue(数字を和文フォントで組まない) | matches |
| Math | Cambria Math(OMML エンジンの固定要件) | display 24–28 pt |
| Code | Menlo / Consolas | 14–16 pt |

Japanese conventions: スライド本文はゴシック(明朝は投影で線が痩せる)。
日本語+英語併記タイトルは学会デッキでは一般的 — 聞き手に合わせ判断。
PowerPoint export only proves the fonts installed on this Mac. Use
Hiragino/Arial when presenting from this machine; for Windows-bound decks use
Yu Gothic/Arial or another Office-standard pairing and add ~10% width slack.
Do not default to Aptos for shared decks: it is missing from older Office
installs and has poor fallback predictability in non-PowerPoint renderers.
全角/半角・スペースの表記揺れ(「AIモデル」「AI モデル」)は QA で潰す。

**Equations**: key results only — show the equation that carries the claim
plus its physical meaning; derivations go to the appendix. Define every
symbol at first appearance (below or beside the equation). Display size
24–28 pt (`--font-size 24`); a hero equation alone may take 32 pt, never
more.

## Academic profiles

### progress-meeting(進捗報告)

The audience is your PI and labmates; the *product of the meeting is the
discussion*, not the deck. Deliberately under-polish: a progress deck that
looks like a conference talk signals "conclusion already fixed" and
suppresses the feedback you came for. 5–10 slides.

1. **Cover** (dark): theme, date, one line of context.
2. **Recap** (kicker `前回まで`): where we left off + this week's question.
3. **Results** (1 slide per claim, kicker `結果 n/m`): claim title +
   figure/video + conditions line (N, parameters, dataset) in small muted
   type. Headline result → stat-callout family. Simulation videos:
   `--normalize --autoplay`, ≤ 2×2 grid, parameter label per cell. For
   side-by-side videos, treat each panel as a comparison card: same size,
   same baseline, label adjacent to the poster frame, and a short comparison
   axis (`低密度`, `高密度`, `control`, `perturbation`) rather than value-only
   labels. Add a one-line comparison takeaway so the audience knows what to
   watch for; two posters plus parameter values are not enough.
4. **Interpretation / problem**: concrete (「ρ>1.1 でフィットが発散」), and
   the discussion card listing **exactly what you want decided or advised**.
5. **Next steps** (timeline family): 2–4 items with expected outcomes. When
   the slide is meant to drive lab action, include the visible decision gate:
   timing, priority, owner, or the criterion for choosing between paths.
6. **Appendix**: everything else. Moving a slide here is success, not loss.

### journal-club(論文紹介)

The audience hasn't read the paper. Two hard rules from practice: walk
through **axes and legends before interpreting any figure**, and keep the
**authors' claims separate from your evaluation** — the Discussion section
of a paper is the authors' argument, and your critique slide is where your
own voice lives (accent color, discussion-card family).

1. **Bibliographic cover** (dark): title, authors, venue+year, one-line
   "why this paper". DOI/arXiv in footer.
2. **Problem & prior state** (1–2): the gap being attacked.
3. **Key idea** (1): the trick as a schematic — redraw rather than
   screenshot when feasible.
4. **Evidence** (2–4): one key figure per slide, cropped tight, axis labels
   readable (re-plot if not), citation in caption: "Fig. 2 of Tanaka et al.
   2026". Region labels and annotations belong inside or beside the figure,
   but must not obscure the data they explain. Borrowed figures always
   credited "From …" (verbatim) or "Adapted from …" (modified) — redrawing
   does NOT remove the need to credit.
5. **Critique**: what convinces, what doesn't, hidden assumptions.
6. **Relevance to us**: what the lab should take from it.

### conference-talk(学会講演)— NEW

A 10–15 min contributed talk is an **advertisement for the paper**, not the
paper: one core idea the audience should remember, ruthlessly pruned
(Peyton Jones: "the talk is the ad, the paper is the beef"). Fewer slides
than minutes — leave room for the story to breathe and for questions.

- Open with the problem and why it matters (≤ 2 slides), state the main
  result *early*, don't build a mystery.
- Prefer one strong figure per slide; cut anything the audience can't
  absorb in the room ("details in arXiv:XXXX" is a feature).
- Never assume the audience remembers slide 3 when you're on slide 9 —
  re-show, don't reference.
- Related work: organized by comparison axis relevant to YOUR claim, never
  a chronological list; author-year in small type where relevant.
- Time discipline is part of the genre: running over reads as incompetence.
- Invited talks (30–45 min) shift toward field overview: same rules, wider
  arc, explicit chapter transitions.

### Figures (all academic profiles)

- Re-plot for slides: axis/label fonts ≥ 12 pt at final size, line widths
  and markers 2–3× paper versions, `dpi=200, bbox_inches="tight"`.
- Keep visuals editable when PowerPoint can represent them faithfully: simple
  bar/line/scatter/pie/combo charts should stay native if the user may revise
  data or labels. Use a high-resolution image for scientific plots that need
  custom annotations, colormaps, or geometry PowerPoint cannot express.
- Never ship matplotlib defaults. Remove top/right spines, lighten gridlines,
  direct-label when practical, and place legends where they do not compete
  with the claim. A graph that looks like a draft plot makes the deck look
  unfinished even when the data are correct.
- Match the deck palette: fit curves in deep accent, data in highlight, no
  matplotlib default color soup; `ax.spines[["top","right"]].set_visible(False)`.
- Error bars: state the type (SD / SE / 95% CI) and n on the slide — SE
  bars alone are a known misleader (≈67% CI).
- Colormaps: viridis family for continuous data (never jet/rainbow — false
  boundaries); Okabe-Ito for categorical (color-vision-safe).
- Multi-panel: (a)(b)(c) labels top-left, one caption line, muted italic.
  Simultaneous panels when the audience must *compare*; sequential build
  when the story is *stepwise* — choose deliberately.
- Simulation snapshots/videos: scale bar, time stamp, identical colormap
  across compared panels; annotate what is assumption vs measurement.
- Cards and critique boxes: prefer quiet tinted fills, whitespace, and
  hierarchy over strong outlines. Heavy borders make critique slides look like
  forms; spacing and hierarchy should do most of the design work.

## Business profiles (compact)

### consulting-deck(意思決定用・読む資料)

Opposite consumption mode: the deck must stand alone without a presenter.
- **Action titles**: every slide title is a finding with the so-what
  ("Q3売上は前年比14%増 — APAC拡大が主要因"), ≤ ~15 words. If "and" creeps
  in, split the slide.
- **Horizontal flow**: titles alone, read in order, must carry the complete
  argument (this replaces the presenter).
- **Answer first** (pyramid principle): conclusion on slide 1 / executive
  summary (Situation → Complication → Resolution), then supporting logic,
  grouped MECE.
- Ghost-deck first: draft all titles before designing any slide; review the
  title sequence for logical gaps.
- Every number carries "Source: …; 年月". Appendix = anticipated-question
  answers, not leftovers. Text density higher than presented decks — that
  is correct here, not a violation. Dense slides still need one dominant
  takeaway, clear grouping, and a visible reading path; density organized
  into regions is a consulting slide, density scattered uniformly is a dump.

### pitch(投資家向け)

- 10/20/30 (Kawasaki): ~10 slides, 20 minutes, ≥ 30 pt fonts.
- Arc: problem → solution/why-now → market (bottom-up TAM/SAM/SOM, not
  top-down兆円×1%) → traction (growth rate over absolutes) → team/moat →
  ask. Explain the inflection point of any growth curve or cut the curve.
- Make TWO decks: the presented one (sparse) and the send-ahead/leave-behind
  reading deck (self-contained). Never one deck for both.

### dashboard-report(データ報告)

One chart, one claim: headline sentence states the conclusion, a single
visual supports it, a so-what line closes it. If the slide's claim can't be
said in one sentence, it's a dashboard, not a slide — restructure. KPIs
≤ 3–5, decimals only where precision changes the decision, status never by
red/green alone (add arrows/symbols).

## Lecture profile(講義・チュートリアル)— compact

- Progressive disclosure is *pedagogically justified here* (reveal items
  when mentioned, dim after discussion — attention follows the voice), but
  it trades away improvisation and discussion; use builds for derivations
  and layered diagrams, static slides where you want questions.
- Segment aggressively: ~1 slide/min, one concept per slide, pre-teach key
  terms before the complex diagram (pre-training principle).
- Math-heavy lecture slides may carry more elements than a talk slide, but
  the structure must be pedagogical: equation, symbol definitions, geometric
  or physical interpretation, and one checkpoint/question. Derivations should
  reveal line-by-line; do not show five unintroduced equations at once.
- Slides ≠ handout: make the deck sparse for the room and either write
  speaker notes into a separate reading document, or accept the deck is not
  self-study material. Distributing dense "slideuments" degrades both.
- Boards still beat slides for live derivations (pacing); design the deck
  to leave room for the board.
