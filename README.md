# AinV

**AinV is a general-purpose, JSON-driven video generator written in Babel.** Build
narrated explainers, motion graphics, image slideshows, social clips, tutorials,
montages, and diagrams from the same timeline. Mathematical plotting is only
one available drawing element. AinV is not a mathematics-only tool.

Nix supplies the Babel compiler, media decoders/encoders, and narration engines.
All video application logic stays in `director.babel`.

## Start

```sh
# Builds the Babel video engine and renders a general motion-graphics showcase
nix run github:honerop/ainv

# Use your own JSON project
nix run github:honerop/ainv -- ./project.json ./movie.mp4

# Render without neural or offline narration
AINV_SKIP_TTS=1 nix run github:honerop/ainv -- ./project.json ./movie.mp4
```

Output is H.264 MP4 plus a separate SRT subtitle file. Narration uses Edge TTS
when available and falls back to bundled offline espeak-ng if Edge fails.
Only the Edge provider needs an internet connection.

## Video project format

```json
{
  "width": 1280,
  "height": 720,
  "fps": 30,
  "music": "assets/music.wav",
  "music_volume": 18,
  "scenes": [
    {
      "duration": 5,
      "media": {
        "kind": "video",
        "src": "assets/footage.mp4",
        "fit": "cover"
      },
      "audio": "assets/footage.mp4",
      "elements": [
        {
          "kind": "text", "x": 90, "y": 160, "font_size": 64,
          "fill": "white", "value": "The story starts here",
          "from": {"opacity": 0}, "start_percent": 10,
          "end_percent": 45
        }
      ]
    },
    {
      "duration": 5,
      "media": {
        "kind": "image",
        "src": "assets/photograph.png",
        "fit": "contain"
      },
      "narration": "This scene shows an image while the narrator speaks.",
      "elements": [
        {
          "kind": "rect", "x": 40, "y": 580,
          "width": 900, "height": 110,
          "fill": "panel"
        },
        {
          "kind": "text", "x": 70, "y": 648,
          "value": "Add captions, shapes and graphics",
          "font_size": 34, "fill": "white"
        }
      ]
    }
  ]
}
```

The `media` field is optional. Set it to a video clip (`kind: "video"`)
or still photograph (`kind: "image"`). Both can be resized with `fit:
"cover"` (crop to the canvas) or `fit: "contain"` (letterbox/pillarbox).
Clips loop when the scene is longer than the video. Media files are resolved
relative to the project JSON; absolute paths are also accepted.

**Sound:** `narration` creates speech for the scene. `audio` instead uses
a local audio file (or a video file containing an audio stream). The scene's
duration is extended if needed to avoid truncating audio. `music` specifies
an optional global background track, looped and mixed at `music_volume`
percent (default 15). `caption` overrides the subtitle text. Use
`AINV_SKIP_TTS=1` to disable generated narration while keeping scene audio.
The engine emits a separate `.srt` file; it does not burn captions into frames.

**Graphics:** supported `elements` are `text`, `rect`, `circle`,
`line`, `arrow`, `polyline`, `axes`, and `plot`. Elements render over
the scene's background or footage. A project can use motion graphics without
any imported media. The math elements are optional, not the central schema.
Numeric properties can animate with `from`/`to` and
`start_percent`/`end_percent`.

## How it works

```text
JSON video project
        |
        v
Babel: project timeline, asset paths, graphics, scene durations, speech scheduling
        |                    |                       |
        |                    |                       +--> Edge TTS / espeak-ng
        |                    +--> SVG overlays --> librsvg rasterization
        +--> image/video backgrounds --> FFmpeg decode/scale/loop
                                       |
                                FFmpeg video composition
                                       |
                             Babel: voice / audio / music mixing
                                       |
                                   MP4 + SRT
```

The application is written in Babel. External tools (FFmpeg, librsvg,
Edge TTS and espeak-ng) are dependency executables, not application code.
The Babel compiler itself is implemented using Rust.

## Development

The Nix lock is pinned to Babel v0.3.1, rather than the old Ain compiler.
Run `nix flake update babel` when intentionally updating the compiler.


```sh
git clone https://github.com/honerop/ainv
cd ainv
nix develop
babelc check director.babel
nix flake check -L
```

`examples/general-showcase.json` is an asset-free general explainer.
`examples/math-explainer.json` remains as a mathematical animation example.
`examples/general-media-smoke.json` exercises actual photo, video and
audio/media mixing using assets created by GitHub Actions.

## Current boundaries

This is a basic general renderer, not a full nonlinear video editor. There
are no arbitrary multiple video layers per scene, crossfades between scenes,
timeline keyframes in seconds, image masks, video speed ramps, complete
typography controls, streaming frame output, or a visual editing UI.
Scene cuts are immediate. Media is currently a single scene-sized background,
with animated vector/text elements over it. Subtitle timing is per scene, not
per spoken word. Graph plotting currently uses integer arithmetic.

Next architectural steps: **typed tracks** (multiple video/image/audio layers,
z-order and in/out), **time-based keyframes**, **transitions/effects**,
**preview without full export**, and **frame streaming** to reduce
intermediate SVG/PNG files. Those will matter for broad video creation more
than adding more mathematical functions.
