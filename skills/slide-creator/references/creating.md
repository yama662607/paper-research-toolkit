# Creating Decks from Scratch (pptxgenjs)

Use pptxgenjs (MIT, actively maintained) via bun. Write a build script and
keep it next to the output — regeneration must always be one command.

## Before coding

Do not open with `addText` calls. First write the quality plan from
design-profiles.md as comments near the top of the build script: profile,
claim spine, proof objects, visual motif, palette roles, and slide-family
rhythm. Then define layout constants and helpers that implement that plan.

Every content slide should have a dominant proof object. If a slide has only
prose, either move the prose to speaker notes, turn it into a diagram/table,
or split it into a discussion/decision slide with an explicit ask.

## Project setup

```bash
mkdir deck-build && cd deck-build && bun add pptxgenjs
```

```javascript
// build_deck.mjs
import pptxgen from "pptxgenjs";
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";          // 13.333 x 7.5 inches — all coords in inches
// If you want the slide-creator 10 x 5.625 inch coordinate system instead:
// pres.defineLayout({ name: "SC_16X9", width: 10, height: 5.625 });
// pres.layout = "SC_16X9";

// Japanese decks: set fonts per text element (theme fonts alone don't cover
// JP/Latin pairing). Headings need bold:true — default-weight JP text looks
// faint on a projector.
const JP = "Hiragino Kaku Gothic ProN";
const slide = pres.addSlide();
slide.addText("秩序化ダイナミクスは密度に依存する", {
  x: 0.5, y: 0.35, w: 9, h: 0.7, fontSize: 26, bold: true,
  fontFace: JP, color: "1A1A1A",
});
await pres.writeFile({ fileName: "../deck.pptx" });
```

Run: `bun build_deck.mjs`. Geometry: PowerPoint widescreen is 16:9; choose
one coordinate system and keep it consistent. `LAYOUT_WIDE` is **13.333 x
7.5 in**. The custom `SC_16X9` example above is **10 x 5.625 in**.

## The gotchas that actually bite

- **Normalize and verify immediately after the first write.** pptxgenjs can
  emit stale `[Content_Types].xml` overrides and directory entries that make
  PowerPoint repair the deck even when the visible slides look fine. Before
  adding equations, videos, or animations, run:
  `uv run scripts/normalize_package.py deck.pptx && uv run scripts/verify_deck.py deck.pptx`.
  Opening and re-saving in PowerPoint can hide the original writer bug; do
  not use that as the fix.
- **Color values**: use six-character hex strings without `#`. Do not encode
  opacity in an eight-character hex string; use the library's transparency or
  opacity fields.
- **Native editable lists only**: never prefix text with "•", "-", "1.",
  "1)", or circled numbers to fake a list. Also do not draw separate number
  chips/icons when the content is semantically a bullet or numbered list.
  Use pptxgenjs paragraph options so PowerPoint owns the marker:
  `{ text: "...", options: { bullet: true, breakLine: true } }` items in an
  array. Sub-levels: `indentLevel: 1`. Numbered lists:
  `bullet: { type: "number" }`. Keep the list in one editable text box unless
  the design is a real process diagram or timeline, not a replacement for a
  list.
- **Multi-line text** requires `breakLine: true` on each item (last one may
  omit it).
- **Text box padding**: boxes have internal margin by default; set
  `margin: 0` when aligning text flush with shapes/images. For filled cards,
  do the opposite: give text an explicit inset with comparable top and bottom
  breathing room. If a card has a separate shape and text box, compute the
  text box from the card bounds instead of eyeballing it.
- **Fresh option objects**: pptxgenjs mutates some option objects internally.
  Use helper factories (`makeShadow()`, `cardFill()`) instead of reusing the
  same object across many shapes.
- **Character spacing** is `charSpacing` (`letterSpacing` is silently
  ignored).
- **Rounded rectangles**: `rectRadius` works only on
  `pres.shapes.ROUNDED_RECTANGLE`.
- **Gradients are not supported** — use solid fills or a background image.
- **Images**: path, URL, or base64 all work; `sizing: {type:"contain"|"cover"|"crop"}`
  controls fit. SVG is supported (renders in modern PowerPoint). For
  matplotlib output prefer PNG at ≥ 200 dpi with `bbox_inches="tight"`.
- **Charts**: choose by PowerPoint editability and visual fidelity, not habit.
  Use native `addChart()` for standard bar/column/line/pie/scatter/combo
  charts, especially in business decks or anything the user may revise later.
  For chart features pptxgenjs does not expose but PowerPoint supports
  (trendlines, error bars), prefer adding a native series or targeted OOXML
  post-processing over flattening to an image. Use a rendered PNG/SVG only
  for visuals PowerPoint cannot faithfully express (custom scientific plots,
  phase diagrams, network/chord/Sankey-style figures), and keep the source
  script beside the deck.
- **Speaker notes**: `slide.addNotes("...")`. Put presenter cues, reveal
  instructions, and explanatory narration here, not as visible slide text.
- **Slide numbers**: `pres.defineSlideMaster` with `slideNumber` or
  `slide.slideNumber = {x, y}`.

## Structure for reuse

Define your layout constants once, build helper functions per layout family,
and drive slides from a plain data array. That keeps next week's edit to a
data change:

```javascript
const M = 0.5;                       // margin
const W = 10 - 2 * M;                // content width
function claimFigureSlide(pres, { claim, figPath, caption }) {
  const s = pres.addSlide();
  s.addText(claim, { x: M, y: 0.3, w: W, h: 0.7, fontSize: 26, bold: true });
  s.addImage({ path: figPath, x: 1.2, y: 1.15, w: 7.6, h: 3.6, sizing: { type: "contain", w: 7.6, h: 3.6 } });
  s.addText(caption, { x: 1.2, y: 4.85, w: 7.6, h: 0.4, fontSize: 12, color: "666666", italic: true });
  return s;
}
```

Define the palette as named roles, not raw colors scattered through the file:

```javascript
const C = {
  ink: "1A1A1A",
  paper: "FFFFFF",
  deep: "1B2A4A",
  highlight: "D55E00",
  muted: "666666",
};
```

Use the role names consistently. A stray color literal in the middle of a
slide usually means the design system has drifted.

## Round-trip-ready source

When the user may refine the PPTX manually, use the managed block convention
from [roundtrip.md](roundtrip.md). The rest of the build script can stay normal
JavaScript, but the slide data that should be patched later must live in the
strict JSON-compatible block and every generated shape needs a stable
`scid:<slide>.<shape>` object name.

```javascript
const postBuildEquations = [];
const postBuildVideos = [];

for (const [slideIdx, slideSpec] of deckSpec.slides.entries()) {
  const slide = pres.addSlide();
  for (const shape of slideSpec.shapes) {
    const sourceId = shape.sourceId ?? `${slideSpec.id}.${shape.id}`;
    const box = {
      x: shape.x, y: shape.y, w: shape.w, h: shape.h,
      objectName: `scid:${sourceId}`,
    };
    if (shape.type === "image") {
      slide.addImage({
        path: shape.path,
        ...box,
        sizing: shape.sizing ?? { type: "contain", w: shape.w, h: shape.h },
      });
    } else if (shape.type === "video") {
      postBuildVideos.push({ slide: slideIdx + 1, sourceId, shape });
      // Keep BUILD structurally simple. Embed the actual local video later
      // with add_video.py so normalization/poster/relationship cleanup run.
      slide.addImage({
        path: shape.posterPath,
        ...box,
        sizing: shape.sizing ?? { type: "cover", w: shape.w, h: shape.h },
      });
    } else if (shape.type === "equation") {
      postBuildEquations.push({ slide: slideIdx + 1, shape });
    } else {
      slide.addText(shape.text, {
        ...box,
        fontSize: shape.fontSize ?? 22,
        fontFace: JP,
        color: C.ink,
      });
    }
  }
}
```

Imported PowerPoint equations are stored as OMML in the managed block. Replay
them after `pres.writeFile()` by writing `shape.omml[0]` to a temporary file
and calling:

```bash
uv run scripts/add_equation.py deck.pptx --slide N --omml-file that-file \
  --source-id "$sourceId" --x ... --y ... --w ... --h ...
```

Do not try to reverse-engineer LaTeX from user-edited equations.

Replay local embedded videos after `pres.writeFile()` with `add_video.py`:

```bash
uv run scripts/add_video.py deck.pptx video.mp4 --slide N \
  --x ... --y ... --w ... --h ... --poster poster.png --normalize
```

After the first successful build, initialize state:

```bash
uv run scripts/sync_from_pptx.py deck.pptx \
  --source deck-build/build_deck.mjs \
  --state deck-build/.slide-creator/state.json \
  --init-state
```

## Division of labor with the other tools

pptxgenjs builds structure, text, figures, and charts. It can also embed media
with `addMedia`, but the slide-creator workflow uses `add_video.py` for local
embedded videos so codec normalization, poster extraction, and relationship
cleanup happen consistently. Use pptxgenjs `addMedia` for online video links
(`type:"online"`) or a deliberate quick WIP only. For **equations, local
embedded videos, autoplay, transitions, and shape animations**, finish the
pptxgenjs build first, then apply `add_equation.py` / `add_video.py` /
`animate.py` to the written file. Follow the Build Order in SKILL.md.

Name shapes you intend to animate (`objectName` option) so they are easy to
identify with `animate.py shapes`.
