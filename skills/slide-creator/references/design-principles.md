# Universal Design Principles

Genre-independent principles, grounded in perception research and cognitive
science. These apply to *every* deck; genre-specific rules live in
[design-profiles.md](design-profiles.md) and build on top of this layer.
When a profile and this file conflict, the profile wins (it encodes a
deliberate genre exception).

Everything below collapses into three meta-principles. When improvising in a
situation the rules don't cover, decide by these:

1. **Minimize extraneous cognitive load** — the audience's working memory is
   the scarcest resource in the room. Every element that isn't the message
   (decoration, redundant text, misaligned boxes) taxes it. (Sweller's
   Cognitive Load Theory; Mayer's coherence/redundancy principles)
2. **One slide = one message, stated explicitly** — don't make the audience
   infer the point. (Mayer segmenting; Duarte's Big Idea; assertion-evidence
   research)
3. **Respect the physics of perception** — content that can't be read,
   distinguished, or grouped from the back row does not exist. (typography,
   WCAG contrast, Gestalt grouping)

## Perception layer

**Typography**
- Size hierarchy ("jump ratio"): headings 1.3–2.0× body size. Same role =
  same size/weight on every slide. A flat hierarchy forces the audience to
  guess importance.
- Body text ≥ 18 pt, prefer 20–24 pt for projection; titles 28–44 pt.
  "It fits if I shrink it" is designing for the file, not the room.
- Line height 1.4–1.6 (Japanese text: 1.15–1.3 works because of taller
  glyphs, but never single-spaced walls).
- Sans-serif for projection (thin serifs break up on projectors).
- **Never underline for emphasis** — underlines sever descenders (g, p, y)
  and measurably hurt recognition (Kosslyn). Emphasize with weight, size, or
  the accent color — pick ONE mechanism and use it consistently.

**Layout (Gestalt principles do the work for you)**
- Proximity = grouping: related items closer together than unrelated ones.
  If group spacing equals item spacing, the structure is invisible.
- Similarity = category: same role → same color/shape/size. Varying icon
  styles or card shapes for same-role items breaks the category signal.
- Align everything to a grid. Slightly-off alignment reads as carelessness
  and taxes visual search even when nobody consciously notices.
- Whitespace is a design element (it separates groups and lets the eye
  rest), not empty space to fill.

**Color**
- 60-30-10: ~60% neutral base, ~30% supporting, ~10% accent. The accent
  only marks what genuinely must be seen — used everywhere, it means
  nothing.
- Assign each color one meaning and never break it across the deck.
- WCAG contrast as the floor, not the ceiling: body text ≥ 4.5:1 against
  its background, large/bold text ≥ 3:1. Projectors and lit rooms are worse
  than your monitor — when unsure, darken the text.
- Never encode meaning in color alone (color-vision diversity + B/W
  printouts): pair color with shape, label, or position.

## Cognition layer (Mayer / Sweller / Kosslyn)

- **Coherence**: cut anything not serving the message — decorative images,
  filler icons, chartjunk (3D bars, heavy gridlines, gradient fills on
  data). Tufte: maximize the share of ink that carries data.
- **Redundancy**: do NOT write what you will say. Slide text that duplicates
  narration makes comprehension *worse*, not just uglier — both channels
  process the same content twice. Slides carry the evidence and the claim;
  the voice carries the explanation.
- **Spatial contiguity**: labels belong ON or NEXT TO the thing they label.
  Direct-label chart series instead of a distant legend when practical;
  put the caption under its figure, not in a corner.
- **Signaling**: headings, arrows, and accent color that mark structure
  genuinely improve learning — signaling is the *good* kind of addition.
- **Load balancing**: the more intrinsically complex the content (dense
  math, multi-variable results), the *simpler* the presentation form must
  be. Complexity in content and complexity in form don't add — they
  multiply.
- **Compatibility (Kosslyn)**: form must match meaning — growth points up,
  bad numbers are the warning color, time flows left→right. A mismatch
  (improvement shown by a downward arrow) creates active misreading.
- **Audience knowledge**: undefined jargon and unexplained symbols spike
  intrinsic load. Define at first use or don't use.

## Message layer

- **Assertion-evidence**: title = a complete-sentence claim; body = visual
  evidence for that claim (figure, data, schematic), not bullet paraphrase.
  Experimentally supported: better comprehension, fewer misconceptions,
  better delayed recall vs topic-title + bullets (Garner & Alley 2013,
  n=110). Caveat from follow-up work: the advantage shows on *complex
  conceptual* material; for simple factual lists a topic title is fine —
  don't contort trivial slides into fake claims.
- **Glance test (Duarte)**: a viewer should grasp a slide's structure in
  ~3 seconds. If not, there is too much on it — split it (segmenting) or
  cut it (coherence).
- Every slide should answer "so what?" — if you can't say why the audience
  needs this slide, it's an appendix slide or no slide.

## Universal prohibitions (all genres)

| Prohibition | Why (principle violated) |
|---|---|
| Reading slide text verbatim to the audience | Redundancy — dual-channel waste, measurably worse comprehension |
| Multiple claims/topics on one slide | Segmenting/CLT — exceeds working memory, ambiguous priority |
| Topic-only titles ("Results", "考察") on content slides | Assertion-evidence — audience must infer the point |
| Decoration unrelated to the message (clip-art, effects, chartjunk) | Coherence / data-ink |
| Text too small to read from the back (< 18 pt body) | Perception physics |
| Low-contrast text (< 4.5:1) or pastel-on-pastel | WCAG floor; projectors amplify the problem |
| Meaning carried by color alone | Color-vision diversity, B/W printing |
| Labels/legends far from what they describe | Spatial contiguity |
| Equal spacing between related and unrelated items | Gestalt proximity — false grouping |
| Misaligned, off-grid elements | Processing fluency; reads as carelessness |
| Underline emphasis | Kosslyn — descender damage |
| Emphasizing everything (all-bold, many colors) | Salience is relative; universal emphasis = no emphasis |
| Flat visual hierarchy (all elements same weight) | No entry point for the eye |
| Undefined jargon/symbols for this audience | Intrinsic-load spike |
| Form contradicting meaning (up = worse, red = good) | Compatibility — invites misreading |

Key sources: Mayer *Multimedia Learning* (12 principles); Sweller CLT;
Kosslyn *Clear and to the Point*; Tufte *Visual Display* / *Cognitive Style
of PowerPoint*; Duarte *slide:ology*; Garner & Alley 2013 (Int'l J. Eng.
Ed. 29(6)); WCAG 2.x SC 1.4.3/1.4.11. Full research notes with URLs:
`~/Code/Projects/slide-creator-workspace/research/design/`.
