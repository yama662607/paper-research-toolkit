# Capturing Manual PowerPoint Edits (untagged fallback)

When a human opens a generated deck, nudges layout in PowerPoint, and saves, you
need those tweaks folded back into the pptxgenjs build script so the next
rebuild doesn't clobber them.

Two paths (see [roundtrip.md](roundtrip.md) for the split):

- **Tagged (precise):** build script has a managed block + `scid:<id>` object
  names + `state.json`. Use `sync_from_pptx.py`. Prefer this for anything you'll
  iterate on.
- **Untagged (this doc):** plain pptxgenjs with coordinate constants, already
  hand-edited. Recover the edits by **diffing the edited deck against a
  reference regenerated from the current source**, then hand-fold the deltas
  into the coordinate constants. Tool: `scripts/capture_edits.py` (read-only;
  never writes a deck).

## Workflow

1. **Back up the edited file first**; never let a build overwrite it. All
   reference builds go to a temp path.
2. **Confirm it was saved.** PowerPoint holds edits in memory; the on-disk file
   only reflects them after Save. Check the pptx mtime is newer than your last
   build. (AppleScript `saved of presentation` is unreliable; mtime is
   dependable.)
3. **Regenerate a reference from the current source to a temp path, replaying
   the FULL post-build chain** — pptxgenjs build **plus** every
   `add_equation.py` / `add_video.py` call with identical coordinates. Skip the
   equation/video steps and those shapes read as spurious diffs.
4. Diff:
   ```bash
   uv run scripts/capture_edits.py --reference /tmp/reference.pptx \
       --edited "path/to/edited.pptx" --hide-low-confidence
   ```
5. Fold each reported delta into the build script's coordinate constants (and
   into the post-build video coords, which live in your rebuild command, not the
   .mjs).
6. **Verify:** rebuild to a temp path, re-run, repeat until the residual is ~0.
   Only then consider overwriting the live file (or leave the human's file as
   master and keep the script in sync for next time).

## How matching works

PowerPoint reorders and re-serializes shapes on save, so index-by-index
comparison prints garbage. `capture_edits.py` matches in three passes and labels
each result with `matched_by` and a `confidence`:

1. **Exact text** (`matched_by: text`, high). Whitespace is normalized, so run
   re-merging on save (extra/removed spaces) is not mistaken for a text edit.
2. **Content signature** (`matched_by: content`) — this is what distinguishes
   same-type shapes so two images are never confused by type name alone:
   - `PICTURE` / `LINKED_PICTURE`: sha1 of the embedded image pixels
     (`shape.image.sha1`, else the blip's relationship blob).
   - `MEDIA` (video/audio): sha1 of the **poster frame** plus the video/audio
     relationship targets (partname/URL). Poster pixels are stable across a
     plain save, so a resized video still matches — **high** confidence.
   - `CHART`: the chart part name. `TABLE`: a hash of the cell-text grid.
   - Unique signature on both sides → high. **Duplicate signature** (genuinely
     identical images/media) → paired by nearest position and reported
     **medium**, because identical content is inherently ambiguous.
3. **Positional proximity** (`matched_by: proximity`, medium; `ambiguous` +
   low when several candidates fall within `--pos-tol`). Recovers text edits (a
   changed string no longer matches by text) and signature-less content moves.
   A zero-width line is never paired to a solid box.

Unmatched shapes are reported as `removed_in_edited` / `added_in_edited`.

### Image replaced in place (`kind: image_replaced`)

When a proximity pair is two pictures at ~the same position whose embedded
image sha1s **differ**, the human likely swapped the figure, not moved it.
Reported as `image_replaced` with `sha1_from` / `sha1_to`, so "swapped" is
distinct from "moved". Confidence is **high** only when the picture was also
resized/moved (a clear swap); a **pure in-place** content change (no bbox
delta) is reported **medium**, because PowerPoint can re-encode/re-compress or
crop an image on save — the bytes differ but nothing was really swapped. Verify
a medium `image_replaced` (compare the two images) before repointing the build
script at a "new" file.

### Deep mode: paragraph properties (`--deep`, `kind: text_props_changed`)

Line spacing is not part of the bounding box, so the normal diff cannot see it.
With `--deep`, every matched text pair also compares per-paragraph line spacing
(`a:pPr/a:lnSpc` → `a:spcPts` val/100 as `Npt`, or `a:spcPct` val/1000 as
`N%`; `None` = inherited/default). A difference emits `text_props_changed`
with `line_spacing_from` / `line_spacing_to` arrays (one entry per paragraph)
— high confidence on an exact-text match with equal paragraph counts, medium
otherwise (a paragraph-count change may just reflect a text edit).

## Confidence tiers and the noise it filters

- **high** — exact text or unique content signature. Fold these in directly.
- **medium** — proximity match, duplicate-signature content, or a text change
  recovered by position. Verify the pairing, then fold in.
- **low** — dropped by `--hide-low-confidence`. Two sources:
  - **Re-serialization artifacts.** Native equations (`add_equation.py`,
    OMML→graphicFrame) and the dark placeholder rects behind embedded videos get
    rewritten on save and surface as `removed_in_edited` / `added_in_edited`
    `TEXT_BOX`/`AUTO_SHAPE` rows with no content signature. Not human edits.
  - **Title autofit.** PowerPoint widens an autofit title text box on save
    (e.g. `w 12.13->12.49`). A **width-only** change on a title-like box (near
    the top, wide) is tagged `suspected_noise: true` and dropped by default.
  - **Equation preview fallbacks.** When PowerPoint saves a deck containing
    native OMML equations, it adds fallback raster previews, which surface as
    phantom `added_in_edited` PICTUREs. Heuristic: an added picture whose bbox
    overlaps a shape containing `m:oMath` (expanded by 0.5 in) on the edited
    side is tagged `suspected_noise: true`, low confidence, and dropped by
    `--hide-low-confidence`. It is a geometric heuristic — a picture a human
    genuinely added *on top of* an equation would be misfiled as noise, so scan
    the low rows once before discarding.

A consistent-offset cluster (a whole diagram moved: every child shifts by the
same `dy`) is the signature of a real group-move — fold it back as one constant.

## JSON schema (`--json`)

```json
{
  "slide_count": {"reference": N, "edited": M,
                  "added_slides": [..], "deleted_slides": [..], "note": "..."},
  "changes": [
    {
      "slide": 10,
      "kind": "moved | text_changed | image_replaced | text_props_changed | added_in_edited | removed_in_edited | slide_added | slide_deleted",
      "matched_by": "text | content | proximity | ambiguous | unmatched",
      "confidence": "high | medium | low",
      "reason": "matched by content signature",
      "before_bbox": {"x":1.967,"y":1.75,"w":9.4,"h":5.248,"rot":0},
      "after_bbox":  {"x":1.439,"y":1.17,"w":10.455,"h":5.837,"rot":0},
      "text_from": "...", "text_to": "...",
      "sha1_from": "34dcd688...", "sha1_to": "88a82a74...",
      "line_spacing_from": ["18pt","18pt"], "line_spacing_to": ["14.5pt","14.5pt"],
      "deltas": [{"prop":"x","from":1.967,"to":1.439}, ...],
      "suspected_noise": false,
      "suggested_action": "Fold the bbox change into the build-script coordinate constants."
    }
  ]
}
```

All positions/sizes are in **inches**. `text_from`/`text_to` appear only on text
changes; `before_bbox`/`after_bbox`/`deltas` only where geometry applies;
`sha1_from`/`sha1_to` only on `image_replaced`; `line_spacing_from`/
`line_spacing_to` (per-paragraph, `null` = inherited) only on
`text_props_changed` (`--deep`).

## CLI

```
uv run scripts/capture_edits.py --reference REF.pptx --edited EDITED.pptx
    --threshold 0.03 | --threshold-inches 0.03   # ignore smaller moves (inches)
    --pos-tol 0.30                                # proximity window (inches)
    --slide 2,10,13                               # restrict to these slides
    --deep                                        # also diff paragraph line spacing
    --hide-low-confidence                         # human edits only
    --json                                        # machine-readable
```

Missing or non-.pptx inputs exit with code `2` and a clear message. The tool
never writes to either deck.

## Remaining limitations

- **Identical content is inherently ambiguous.** Two byte-identical images or
  two videos with the same poster share a signature; if one moves, the tool
  pairs by position and marks it **medium** — verify which one you meant.
- **Signature-less content.** A linked picture or an unusual media part with no
  extractable poster/target falls back to proximity (medium) or shows as
  add/remove; confidence is lowered accordingly.
- **Mid-deck slide insertion.** `slide_count` assumes extra/missing slides are
  trailing (positional zip of the shared prefix). If a slide was inserted in the
  middle, downstream slides shift and will over-report — reconcile structure
  first.
- **Equations still read as low-confidence removals.** OMML graphicFrames don't
  round-trip cleanly through a save; they are filtered as noise, not tracked as
  content. If a human edited an equation in PowerPoint, capture it manually.
- **No source patching.** This tool reports; it does not edit the build script.
  That hand-fold step is deliberate for untagged decks — use the tagged
  `sync_from_pptx.py` path when you want automated patching.

## Forward-looking

Regenerating a full reference just to diff is the expensive part. Two upgrades
worth building into the skill:

1. **Emit a layout snapshot at build time** — dump JSON of
   `{content-key: bbox}` next to the deck so capture diffs against the snapshot
   with no rebuild.
2. **Default new decks to scid-tagged round-trip** so `sync_from_pptx.py` maps
   edits back exactly and this heuristic stays a rescue-only path.
