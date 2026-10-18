# AinV

**Ain-authored mathematical videos for NixOS.** Ain now owns the timeline,
math curves, vector drawing, frame files, narration scheduling, subtitle text,
and process orchestration. The previously added Python director and Rust MP4
renderer are not part of the default pipeline.

## One command

```sh
nix run github:honerop/ainv
```

This compiles `director.ain` with `honerop/ain` and produces
`showcase.mp4` and `showcase.srt` in the current directory. The included
showcase has four narrated math scenes at 1280×720, 30 FPS.

```sh
nix run github:honerop/ainv -- ./lesson.json ./lesson.mp4
```

Nix supplies the Ain compiler, a temporary work area, Edge TTS, librsvg,
FFmpeg, and DejaVu fonts. No global Python/Rust installation is needed to
run an already built package.

**Boundary:** the application source and scene renderer are in Ain.
Edge TTS is a third-party speech synthesizer (network required), librsvg
rasterizes Ain-generated SVG, and FFmpeg encodes video/audio. Writing a modern
H.264 encoder or a neural speech synthesis model from scratch in Ain is neither
necessary nor practical. These executables are codecs/services, not hidden
application logic.

## Project format

```json
{
  "width": 1280,
  "height": 720,
  "fps": 30,
  "scenes": [
    {
      "duration": 5,
      "narration": "A parabola comes from the simple rule y equals x squared.",
      "voice": "en-US-AndrewNeural",
      "voice_rate": "-5%",
      "background": "ink",
      "elements": [
        {
          "kind": "text", "x": 96, "y": 170,
          "value": "y = x²", "font_size": 60, "fill": "white"
        },
        {
          "kind": "axes", "x": 150, "y": 240,
          "width": 980, "height": 360,
          "x_min": -4, "x_max": 4, "y_min": -1, "y_max": 9
        },
        {
          "kind": "plot", "function": "quadratic",
          "x": 150, "y": 240, "width": 980, "height": 360,
          "x_min": -4, "x_max": 4, "y_min": -1, "y_max": 9,
          "stroke": "cyan", "stroke_width": 6,
          "start_percent": 20, "end_percent": 90
        }
      ]
    }
  ]
}
```

A `duration` is measured in seconds; `frames` can also be given.
The Ain director synthesizes narration per scene and measures it using ffprobe.
It extends a scene when the voice needs more time. It writes subtitles to an
SRT file and mixes narration into the final MP4.

Shapes: `text`, `rect`, `circle`, `line`, `arrow`,
`polyline`, `axes`, `plot`.
Plot functions currently include `quadratic`, `linear`, `cubic`,
`sin`, and `cos`. Curves use integer fixed-point sampling in Ain.
The `from`/ `to` properties can animate numeric positions and dimensions;
use integer `start_percent`/`end_percent` for staggered timing.
SVG text supports ordinary Unicode mathematical labels. No full LaTeX
typesetting or symbolic transformation engine is implemented.

## Building and validating

```sh
git clone https://github.com/honerop/ainv
cd ainv
nix flake check -L
nix run . -- examples/ain-smoke.json smoke.mp4
```

The offline smoke example needs no Edge TTS connection and exports a short
real H.264 file. In the checkout, `nix develop` provides the compiler
and multimedia tools. To compile the director as Ain:

```sh
ainc check director.ain
ainc build director.ain -o ainv
```

The older `preview.ain` and `render.ain` Ain-only experiments remain
available separately. Earlier `native/` and `pipeline.py` implementation
files are historical and no longer on the default execution path.

### Limitations

High production quality also requires good scene composition, accurate
mathematics, pacing, and original explanations. AinV offers a deterministic
vector animation framework; it does not automatically create a complete
3Blue1Brown-quality lesson from a plain English prompt. Rendering every
vector frame is relatively CPU-intensive, and Edge TTS availability is
external to Nix.
