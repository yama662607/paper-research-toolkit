# Native Math Equations in PPTX

Native equations (editable via PowerPoint's equation editor) are OMML —
Office Math Markup Language, namespace prefix `m:`. Neither python-pptx nor
pptxgenjs supports them; `scripts/add_equation.py` implements the only known
working approach: raw XML injection.

## How it works (the pipeline)

```
LaTeX ──latex2mathml (Python)──▶ MathML ──mathml2omml (JS, bun)──▶ OMML
     ──wrap in a14:m──▶ append to a paragraph element in the slide
```

- `latex2mathml` (MIT, Python): LaTeX → Presentation MathML.
- `mathml2omml` (LGPLv3, pure-JS, no XSLT): MathML → OMML. Called via
  `scripts/omml/convert.mjs` (stdin MathML → stdout OMML). We use this
  instead of Microsoft's MML2OMML.XSL because the XSL ships only inside an
  Office installation and cannot be redistributed.

## The critical PPTX-specific wrapper

Unlike Word (whose `w:p` accepts `m:oMath` directly), DrawingML paragraphs
(`a:p`) do **not** accept OMML as a child. It must be wrapped in the Office
2010 extension element `a14:m`:

```xml
<a:p>
  <a14:m xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">
    <m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:oMath> ... converted OMML content ... </m:oMath>
    </m:oMathPara>
  </a14:m>
</a:p>
```

- **Display equation** (own line): wrap in `m:oMathPara` as above.
- **Inline equation** (mid-sentence): omit `m:oMathPara`, put `m:oMath`
  directly under `a14:m`.
- PowerPoint itself saves equations wrapped in `mc:AlternateContent` with an
  `mc:Fallback` raster image for old readers. **Omit that when generating** —
  PowerPoint accepts the bare `a14:m` form on load (verified by multiple
  implementers), and python-pptx has a known bug enumerating shapes inside
  `mc:AlternateContent`, so adding the wrapper would break later edits.

Reference for the full structure: Microsoft [MS-ODRAWXML] "Math" section.

## Font

Office's math engine is designed around **Cambria Math** (the only font with
a complete OpenType MATH table it handles reliably). Do not restyle equation
runs with other fonts. Mixing Japanese text *inside* an equation is untested
territory — put Japanese in a normal text run next to the equation instead.

## Usage

```bash
uv run scripts/add_equation.py deck.pptx --slide 2 \
  --latex '\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}' \
  --x 1 --y 2 --w 6 --h 1.2 --font-size 24

# Inspect without touching the file:
uv run scripts/add_equation.py deck.pptx --slide 2 --latex 'E = mc^2' --emit-xml

# Replay OMML captured from a user-edited PowerPoint equation:
uv run scripts/add_equation.py deck.pptx --slide 2 --omml-file imported.omml \
  --source-id s002.eq1 --x 1 --y 2 --w 6 --h 1.2 --font-size 24
```

Coordinates are in inches. The script creates a new textbox and injects the
equation as its content.

**Sizing**: `--font-size` scales the whole equation. Display equations sit
right at **24-28 pt** next to 18-20 pt body text; a hero equation alone on a
slide can take 32 pt. Larger than that overwhelms the slide — if the default
render looks too big, re-run with a smaller `--font-size` (delete the old
textbox first, or start from the pre-injection deck). To place an equation inside an *existing* textbox,
use `--emit-xml` and append the printed `a14:m` element to the target
paragraph yourself (python-pptx: `paragraph._p.append(fragment)`).

## Verification

After injection, always:

1. `uv run scripts/verify_deck.py deck.pptx` — confirms the file still opens.
2. Visual QA render — the equation should appear (LibreOffice renders OMML
   approximately; check that it looks like the intended formula, not exact
   spacing).
3. For decks that matter, open once in real PowerPoint: the equation must be
   double-click-editable. A "gibberish equation" outcome has been reported in
   the wild for some LaTeX inputs — if that happens, simplify the LaTeX
   (split multi-line constructs, avoid exotic macros) and re-inject.

## Known limits

- LaTeX coverage is bounded by latex2mathml: standard math (fractions, roots,
  sub/superscripts, sums/integrals with limits, Greek, matrices, `\mathrm`,
  accents) works; TikZ/chemfig/custom macros do not.
- One equation per `add_equation.py` call. Loop for many.
- Equations are invisible to text extraction (`--text` dumps show them as
  empty) — this is normal; they live outside `a:t` runs.
