# Round-Trip Source Workflow

Use this when the user will refine a generated PowerPoint deck by hand and
expects those edits to survive future regeneration. The goal is not to turn
PowerPoint into a perfect source format; it is to keep safe manual edits from
being overwritten.

## Contract

The build script remains the primary source. Only one region is machine-managed:
a strict JSON-compatible object block inside the JavaScript file. Everything
outside the block can stay normal JS helpers, layout functions, figure logic,
and comments.

```javascript
/* slide-creator:managed-deck:start */
export const deckSpec = {
  "version": 1,
  "slides": [
    {
      "id": "s001",
      "layout": "claim-figure",
      "shapes": [
        {
          "id": "title",
          "type": "text",
          "text": "Density selects the slowest relaxation mode",
          "x": 0.5,
          "y": 0.32,
          "w": 8.9,
          "h": 0.55
        }
      ]
    }
  ]
};
/* slide-creator:managed-deck:end */
```

The managed block must be valid JSON between the outer braces: double-quoted
keys/strings, no comments inside the object, and no trailing commas. This is
deliberate. It lets the sync tool patch the source without needing a fragile
JavaScript parser while leaving the rest of the file fully expressive.

## Stable shape IDs

Every generated object that should round-trip needs a stable source id:

```javascript
const sourceId = `${slideSpec.id}.${shapeSpec.id}`;
slide.addText(shapeSpec.text, {
  objectName: `scid:${sourceId}`,
  x: shapeSpec.x,
  y: shapeSpec.y,
  w: shapeSpec.w,
  h: shapeSpec.h,
});
```

The sync tool looks for `scid:<id>` in the PowerPoint object name or alt text.
Do not rely on PowerPoint's numeric shape id alone; PowerPoint can renumber
objects after copy/paste or grouping.

## Workflow

1. Generate the deck from the managed JS source.
2. Initialize state from the generated PPTX:
   ```bash
   uv run scripts/sync_from_pptx.py deck.pptx \
     --source deck-build/build_deck.mjs \
     --state deck-build/.slide-creator/state.json \
     --init-state
   ```
3. The user edits the deck in PowerPoint and saves it.
4. Inspect or sync the edited deck:
   ```bash
   uv run scripts/sync_from_pptx.py edited.pptx \
     --source deck-build/build_deck.mjs \
     --state deck-build/.slide-creator/state.json \
     --out deck-build/.slide-creator/sync-report.json

   uv run scripts/sync_from_pptx.py edited.pptx \
     --source deck-build/build_deck.mjs \
     --state deck-build/.slide-creator/state.json \
     --apply

   # Optional: import objects the user added manually after the baseline.
   uv run scripts/sync_from_pptx.py edited.pptx \
     --source deck-build/build_deck.mjs \
     --state deck-build/.slide-creator/state.json \
     --apply --import-untagged --asset-dir assets/roundtrip
   ```
5. Regenerate the PPTX from source and run visual QA. If manual objects were
   imported, then re-initialize state from the regenerated file. The edited
   PPTX still contains untagged manual objects, while the regenerated PPTX
   should contain generated objects with `scid:<id>`.
6. Run PowerPoint PDF QA before treating the regenerated deck as authoritative.

Always keep the edited PPTX until the regenerated PPTX has been visually
checked. Source sync is a patch proposal, not a substitute for QA.

## What sync_from_pptx.py can safely update now

- Stable-id plain text box `text`
- Stable-id shape geometry: `x`, `y`, `w`, `h`
- Stable-id equation OMML content when the source shape has an `omml` field
- Slide/shape/media/equation/chart inventory for review reports
- New untagged manual text, simple image, mp4 video, and OMML equation objects
  with `--import-untagged`, when they were added after the last initialized
  state
- State refresh after applying source changes only when no skipped or imported
  manual objects remain

## Preserve-only / warning areas

- Animations and transitions: preserve and verify structurally; do not try to
  infer user intent from timing XML yet.
- SmartArt, Morph-dependent names, complex groups, and handmade chart XML:
  preserve unless the user explicitly asks to rebuild.
- Equations edited in PowerPoint: preserve OMML. LaTeX reverse conversion is
  best-effort future work, not a safe default.
- Charts added or deeply restyled manually: inventory first. Native chart XML
  import is a separate feature; do not flatten charts to images just to make
  source sync pass.

## Manual object import

Use `--import-untagged` only after an initialized baseline exists. The tool
compares the edited PPTX to the previous state and imports only untagged shapes
that are new since that baseline. This avoids absorbing old template
placeholders, background marks, or decorative shapes.

Supported imports:

- Plain text boxes with real text
- Simple pictures without crop/flip/group features
- MP4 video media with internal PPTX assets; poster frame, autoplay, and
  timing are not inferred yet
- PowerPoint-native equations, stored as OMML

Media is copied out of the PPTX into `assets/roundtrip` by default, or the
directory passed with `--asset-dir`. Imported specs include `roundtrip` metadata
with the original PowerPoint shape id and a fingerprint so repeated runs do not
duplicate the same manual object.

The tool refuses suspiciously large packages instead of trying to parse them:
XML parts over 50 MB, imported media assets over 1 GB, compressed or
uncompressed PPTX packages over 4 GB, or packages with over 20,000 ZIP entries.
Media import is streamed to disk while hashing, so normal videos are not loaded
into memory all at once. Relationship inventory uses a full SHA-256 hash for
media up to 1 GB per target, with a 2 GB total hash budget per inspect run;
larger media keeps ZIP metadata instead of being fully read just for
inspection.

After importing any manual object, the tool does **not** update
`.slide-creator/state.json`. Regenerate from source, visually check the result,
then run `--init-state` on the regenerated PPTX. This makes the new generated
objects, with stable `scid:<id>` names, the next baseline.

The build script must render imported managed-block types. At minimum it
should handle `type: "text"`, `type: "image"`, `type: "video"`, and
`type: "equation"` specs; equation specs can be replayed with
`add_equation.py --omml-file --source-id <id>` in the post-build step.

If `--apply` sees new untagged shapes and `--import-untagged` was not used,
it does not update state. Import the supported objects or intentionally remove
or recreate the unsupported ones before advancing the baseline.

## Source patch rules

- Patch only the managed block.
- Never rewrite helper functions, figure-generation code, or custom layout
  logic outside the block.
- If a changed PPTX object lacks `scid:<id>`, report it as untagged. Import it
  only when `--import-untagged` is explicitly set and the object is one of the
  supported types.
- If a source object cannot represent the edit, report it and preserve the
  PPTX rather than forcing a lossy patch.
- If any change is skipped, the tool leaves the state file at the previous
  baseline. Resolve or explicitly preserve the skipped change before treating
  the regenerated deck as authoritative.
