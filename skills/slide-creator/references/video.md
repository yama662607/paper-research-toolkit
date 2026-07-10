# Embedding Video in PPTX

`scripts/add_video.py` handles the whole chain: codec normalization, poster
frame, embedding, and (optionally) autoplay. This document explains what it
does and why, so you can debug or go manual when needed.

## Codec rules (the #1 cause of "video won't play")

The only combination that plays reliably on both Windows and Mac PowerPoint:

**H.264 video + AAC audio, MP4 container, yuv420p pixel format, constant
frame rate, faststart.**

Common killers: HEVC/H.265 or VP9 inside an .mp4 (extension lies), variable
frame rate from phone/screen recordings (audio desync, stalls), WMV on Mac
(never supported). `--normalize` runs:

```bash
ffmpeg -i input -c:v libx264 -profile:v high -preset slow -crf 18 \
  -pix_fmt yuv420p -r 30 -fps_mode cfr \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart output.mp4
```

Always normalize simulation renders and screen recordings. Skip only when
ffprobe already shows h264/aac/yuv420p and constant frame rate.

## What a video actually is in the XML

A video is a `p:pic` (picture shape) carrying up to three relationships:

| Reference | Points to | Role |
|---|---|---|
| `p:nvPr > a:videoFile r:link="rId1"` | the video file | legacy (2007) reference |
| `p:nvPr > p:extLst > p14:media r:embed="rId2"` | the *same* video file | modern (2010) reference; trim/fade metadata lives here |
| `p:blipFill > a:blip r:embed="rId3"` | a still image | poster frame (what you see before playback) |

Both video relationships must exist and point at the same media part — this
double-wiring is the compatibility convention. Playback control lives in a
separate tree: `p:timing > ... > p:video > p:cMediaNode`, tied to the shape
by `p:spTgt spid` = the shape's `p:cNvPr id`.

python-pptx's `add_movie()` builds the core picture/media/timing structure,
but it is still labeled EXPERIMENTAL and can emit XML that PowerPoint tolerates
in some decks and rejects or fails to export in others. The script fills the
known gaps:

- `mime_type` defaults to `video/unknown` → we always pass `video/mp4`.
- No poster extraction → we grab the first frame with ffmpeg unless
  `--poster` is given.
- It can emit an empty media action hyperlink
  (`<a:hlinkClick r:id="" action="ppaction://media"/>`) → we remove it so
  every relationship reference in the slide resolves.
- No autoplay option → see below.

## Autoplay

`add_movie()` always generates click-to-play (`<p:cond delay="indefinite"/>`
in the media timing node). `--autoplay` rewrites only the condition inside the
newly inserted video's `p:cMediaNode`, matched by the video's shape id, to
`<p:cond evt="onBegin" delay="0"/>` after insertion. It must not rewrite
other click-triggered animations on the slide. Because media timing is one of
the least portable PowerPoint XML areas, run the PowerPoint PDF/open smoke
path after embedding and fall back to click-to-play or manual insertion if
PowerPoint rejects the deck.

## The corruption guard (python-pptx issue #954)

If a slide's existing `<p:timing>` is wrapped in `mc:AlternateContent`
(PowerPoint does this when non-standard animation features are used),
`add_movie()` fails to see it and adds a *second* `<p:timing>` → corrupt
file. The script checks for this and refuses; if refused, embed the video on
a fresh slide or strip the exotic animation first.

## Embed vs link, and YouTube

- **Embed** (default): self-contained, portable; adds the full file size.
  A 2-min HD video ≈ +50 MB. Right choice for delivered decks.
- **Link**: rels entry gets `TargetMode="External"` and a path/URL; tiny file
  but breaks when the video moves. Only for work-in-progress decks.
- **YouTube/online**: same `p:pic` + `a:videoFile` structure, but the
  relationship target is `https://www.youtube.com/embed/<ID>?feature=oembed`
  with `TargetMode="External"`. Playback effectively requires Office 365.
  pptxgenjs supports this natively (`addMedia({type:'online', link})`);
  python-pptx does not.

## QA implications

- LibreOffice **cannot play** embedded video and, worse, **re-saving in
  LibreOffice destroys embedded video** (multiple confirmed bugs). PDF
  rendering is safe and shows the poster frame (LibreOffice ≥ 5.4).
- Therefore video health is verified structurally, not visually:
  `verify_deck.py` checks that every video relationship resolves to a real
  media part, rejects empty relationship references, and runs ffprobe on each
  embedded video.
- Structural success does not prove PowerPoint can export the deck to PDF or
  play the video. For delivered decks, also run the PowerPoint QA path and
  open the deck in PowerPoint if video playback matters. If PDF export fails
  only after adding embedded video, keep the poster in the deck and provide
  the clip as a separate file or insert the video manually in PowerPoint.
- Visual QA still matters for the poster frame. A video panel should read as
  video, not as a random still image: use a clear representative frame, keep
  labels adjacent, and add a small play glyph or "video" label only when the
  poster would otherwise be ambiguous.
- PowerPoint-for-web upload limit: 300 MB editable / videos ≤ 256 MB. Keep
  simulation clips short and 720p–1080p; crf 18–23.

### Verify the video plays to completion

`verify_deck.py` runs ffprobe for codec health only — it cannot detect a
TRUNCATED video (a render that died before the animation/graph finished
still probes as valid h264/aac). Use `scripts/check_video.py` instead:

```bash
uv run scripts/check_video.py deck.pptx --thumb qa/video   # all embedded videos
uv run scripts/check_video.py deck.pptx --slide 10          # one slide's video
```

It prints duration/frames/codec/size per embedded video and, with `--thumb`,
extracts each video's LAST frame as a PNG — confirm that frame shows the
finished state (curve complete, animation at its end), not a mid-run state.
Recommendation: make the video's poster frame its LAST frame (pass
`--poster` to `add_video.py` with a last-frame grab), so the static poster
shows the finished result rather than the empty starting state.

## Usage

```bash
# The standard call: normalize, auto-poster, embed, autoplay
uv run scripts/add_video.py deck.pptx --slide 3 sim.mp4 \
  --x 1 --y 1 --w 5 --h 3.75 --normalize --autoplay

# Parameter-sweep grid: loop with computed positions (16:9 slide = 10 x 5.625 in)
for i, path in enumerate(videos):  # 2x2 grid example, in your build script
    x = 0.4 + (i % 2) * 4.9; y = 1.2 + (i // 2) * 2.3
```

Coordinates in inches. Match `--w/--h` to the video's aspect ratio (the
script warns on mismatch > 2%).

For side-by-side comparison videos, lay them out as matched panels: identical
size, shared top/bottom baseline, thin neutral frame when the poster is
high-saturation, a nearby parameter label, and one short comparison cue
(`low density` / `high density`, `before` / `after`, etc.). A value label
alone is often not enough for the audience to know what to compare.
