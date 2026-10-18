# AinV

**AinV creates narrated, vector-based mathematical animations from JSON on NixOS.**
The default example explains curves, transformations, and tangents using animated
coordinate systems. Its aim is the *explanatory* approach of 3Blue1Brown, not a
claim to reproduce Grant Sanderson's production quality automatically.

## One-command start

With Nix flakes enabled, from any directory:

```sh
nix run github:honerop/ainv
```

This builds the renderer using Nix, synthesizes the demo narration using
Edge TTS, renders 1280 × 720 H.264 video, and creates **`showcase.mp4`** and
**`showcase.srt`** in your current directory. There is no global install.
**Edge TTS requires internet access at render time** and depends on
Microsoft's service being available. All software dependencies come from Nix.

To use your own project:

```sh
nix run github:honerop/ainv -- ./lesson.json ./lesson.mp4
```

Render without contacting Edge TTS:

```sh
nix run github:honerop/ainv -- ./lesson.json ./lesson.mp4 --no-tts
```

Use a different online narrator or speech speed:

```sh
nix run github:honerop/ainv -- ./lesson.json ./lesson.mp4 \
  --voice en-US-JennyNeural --rate=-10%
```

Use `--music path/to/music.wav` for looping background music. Paths for
`audio` and `music` in JSON resolve **relative to the JSON file**; the
`--music` command-line path also resolves relative to the JSON file.
Choose `--no-subtitles` to suppress both the SRT file and the embedded
MP4 subtitle stream. `nix run github:honerop/ainv -- --help` shows the CLI.

## Architecture

```text
JSON / Ain-generated JSON
           |
           v
Python scene director (stdlib only)
     |                      |
     |               Edge TTS per scene
     |                      |
     |               ffprobe durations
     v                      |
timeline with exact integer frame counts
     |
     v
Rust renderer: SVG -> resvg -> OpenH264 -> MP4
     |
     v
FFmpeg: align voice, mix optional music, embed subtitles -> narrated MP4
```

The existing Ain-based SVG director (`preview.ain`) remains available.
The native renderer is a Rust codec backend, not an Ain-only encoder.
Python is used for orchestration, not animation rendering. FFmpeg is used
for audio/video muxing and subtitles, not for the original SVG rasterization.

## A narrated math video

Write `lesson.json`:

```json
{
  "width": 1280,
  "height": 720,
  "fps": 30,
  "voice": "en-US-AndrewNeural",
  "voice_rate": "-5%",
  "scenes": [
    {
      "duration": "auto",
      "narration": "The graph of x squared curves upward.",
      "background": "ink",
      "elements": [
        {
          "kind": "text", "x": 110, "y": 125,
          "value": "y = x²", "font_size": 70, "fill": "white",
          "from": {"opacity": 0}, "start": 0, "end": 0.2
        },
        {
          "kind": "axes",
          "x": 170, "y": 190, "width": 940, "height": 400,
          "x_min": -3, "x_max": 3, "y_min": -1, "y_max": 9,
          "stroke": "slate"
        },
        {
          "kind": "plot", "function": "quadratic",
          "x": 170, "y": 190, "width": 940, "height": 400,
          "x_min": -3, "x_max": 3, "y_min": -1, "y_max": 9,
          "stroke": "cyan", "stroke_width": 7,
          "start": 0.2, "end": 0.85, "ease": "smooth"
        }
      ]
    }
  ]
}
```

```sh
nix run github:honerop/ainv -- lesson.json lesson.mp4
```

Narration can instead be `"audio": "recording.wav"`, using your own
recording without network access. Do not use `audio` and `narration` on
the same scene. `caption` overrides subtitle text, and `voice` or
`voice_rate` can be set per scene.

### How timing works

Each scene has either `duration` (seconds), `frames`, or
`duration: "auto"`. Speech is generated **before** rendering. The director
measures each clip and makes the scene long enough for the full audio and
a 350 ms tail. A longer explicit scene duration is preserved. Scene starts
are aligned to actual video frames, so audio, transitions, and subtitles share
one timeline.

Each element can use `start` and `end` in **0..1**, the fraction of its
scene over which it animates. Animated numeric fields can use `from` /
`to`, with `ease: "smooth"`. A `plot` draws its curve as time advances;
set `"draw": false` to show the full curve immediately.

### Available vector elements

| Kind | Main fields |
| --- | --- |
| `text` | `x`, `y`, `value`, `font_size`, `weight`, `fill` |
| `rect` | `x`, `y`, `width`, `height`, `radius`, `fill` |
| `circle` | `cx`, `cy`, `r`, `fill` |
| `line`, `arrow` | `x1`, `y1`, `x2`, `y2`, `stroke` |
| `polyline` | `points`, `stroke`, `stroke_width` |
| `axes` | position, dimensions, `x_min`, `x_max`, `y_min`, `y_max` |
| `plot` | same coordinate bounds, `function`, `a`, `b`, `c`, `draw` |

Built-in plot functions: `sin`, `cos`, `quadratic` / `parabola`,
`linear`, `cubic`, `exp`, `gaussian`.

The color palette uses names such as `ink`, `panel`, `slate`,
`white`, `muted`, `cyan`, `ice`, `blue`, `orange`, and `green`.

AinV currently supports Unicode math labels, but **not full LaTeX,
symbol-by-symbol equation morphing, 3D camera moves, or automatic
storyboarding**. Matching an actual 3Blue1Brown episode takes thoughtful
mathematical visuals, deliberate pacing, and narration. Those are not features
a dependency installer can supply.

## Development and tests

```sh
# From a clone of honerop/ainv:
nix develop           # if a dev shell is available in your checkout
python3 -m unittest discover -s tests -p test_pipeline.py -v
cargo test --manifest-path native/Cargo.toml
cargo run --release --manifest-path native/Cargo.toml -- \
  examples/mp4-smoke.json smoke.mp4
```

To render the default example using the Nix entry point:

```sh
nix run . -- ./examples/math-explainer.json ./math.mp4
```

GitHub Actions tests the Python timeline and muxer and the Rust renderer.
Legacy Ain-only experiments remain in `render.ain`, `preview.ain`, and
`tests/`.
