# ainv

JSON-driven video generation written entirely in [Ain](https://github.com/honerop/ain).

`ainv` parses animated scenes, renders frames on the CPU, and writes an actual
**YUV4MPEG2 (Y4M)** video file using existing Ain builtins. It does not run
Python, FFmpeg, MoviePy, Manim, a browser, or an external encoder. It does not
require changes to the Ain compiler or its standard library.

## Quick start

Install or build the Ain compiler (`ainc`), then run this command from the
`ainv` repository root:

```sh
AIN_VIDEO_SPEC=examples/explainer.json \
AIN_VIDEO_OUTPUT=explainer.y4m \
ainc run render.ain
```

If you keep both repositories next to each other, you can use the Ain compiler
directly without installing `ainc`:

```sh
git clone https://github.com/honerop/ain.git ../ain
AIN_VIDEO_SPEC=examples/explainer.json \
AIN_VIDEO_OUTPUT=explainer.y4m \
cargo run --manifest-path ../ain/Cargo.toml -- run render.ain
```

The `ainc` and Cargo commands **compile and run the Ain application**, rather
than acting as the video renderer. All of the rendering and file output happens
in `render.ain`.

## Complete NixOS workflow

No global installs, and the video renderer does not require Python, FFmpeg,
librsvg or any non-Ain application code. The compiler itself is built with Rust.

If your terminal does not already have flakes enabled, use
`nix --extra-experimental-features 'nix-command flakes' shell ...` in place of
`nix shell ...`.

Open a temporary development shell, clone the compiler and video app, build
the compiler, and run the demo:

```sh
nix shell nixpkgs#git nixpkgs#cargo nixpkgs#rustc

mkdir -p ~/dev
cd ~/dev
git clone https://github.com/honerop/ain.git
git clone https://github.com/honerop/ainv.git

cargo build --release --manifest-path ain/Cargo.toml

cd ainv
../ain/target/release/ainc --version
../ain/target/release/ainc check render.ain

AIN_VIDEO_SPEC=examples/explainer.json \
AIN_VIDEO_OUTPUT=explainer.y4m \
../ain/target/release/ainc run render.ain

../ain/target/release/ainc run tests/smoke.ain
ls -lh explainer.y4m
```

This makes `~/dev/ainv/explainer.y4m`. Generating the uncompressed video
may take some time because the initial implementation constructs pixel strings
one sample at a time.

For optional playback only (not rendering or encoding), install/run a player,
for example `nix shell nixpkgs#mpv -c mpv explainer.y4m`.
A player may use decoder libraries internally; ainv does not call them.

For subsequent runs:

```sh
cd ~/dev/ainv
git pull --ff-only
cd ../ain
git pull --ff-only
cargo build --release
cd ../ainv
AIN_VIDEO_SPEC=examples/explainer.json \
AIN_VIDEO_OUTPUT=explainer.y4m \
../ain/target/release/ainc run render.ain
```

## JSON input

```json
{
  "width": 96,
  "height": 64,
  "fps": 8,
  "scenes": [
    {
      "frames": 8,
      "background": "black",
      "elements": [
        {
          "kind": "rect",
          "x": 9, "y": 42,
          "width": 76, "height": 3,
          "fill": "cyan",
          "from": {"width": 0},
          "ease": "smooth"
        },
        {
          "kind": "text",
          "x": 8, "y": 7,
          "value": "AIN VIDEO",
          "scale": 2, "fill": "white"
        }
      ]
    }
  ]
}
```

Scenes run in order. Supply a duration in seconds or a frame count for each
scene. Object coordinates may animate through `from` and `to` keyframes,
using `linear` or `smooth` easing.

Supported objects are `rect`, `circle`, and `text`. Text uses a small
built-in 3×5 bitmap font (uppercase letters, digits, and limited punctuation).

## Output format and limitations

Ain currently writes UTF-8 text rather than arbitrary binary bytes.
The renderer exploits the ASCII-compatible part of the YUV420 pixel range to
produce a valid raw **.y4m** video without adding a file-writing builtin.

This is a proof of concept, **not a compressed MP4 encoder**. The format is
uncompressed, and pixel values are intentionally restricted. Colors are
represented primarily by luminance, with fixed chroma values.

- Maximum 320×180, up to 24 FPS and 240 total frames; requested values beyond
  those bounds are clamped or truncated.
- Scenes with rectangles, circles, and bitmap text, with geometry animation.
- No sound, imported images/video, line/path objects, LaTeX, or antialiasing.
- Output is built in memory, so rendering longer clips can be slow.
- Use trusted JSON only; full schema validation and error handling remain work
  for a later version.

## Tests

Run the example first, then verify its Y4M structure **using Ain**:

```sh
AIN_VIDEO_SPEC=examples/explainer.json \
AIN_VIDEO_OUTPUT=explainer.y4m \
ainc run render.ain

ainc run tests/smoke.ain
```

The repository has a GitHub Actions workflow to run the same checks against
the current Ain compiler.

## Repository boundaries

The video app lives in **honerop/ainv**, not in **honerop/ain**.
The latter is a programming-language project and remains a separate dependency
for compiling Ain source. The generator has no Python, Rust, or other language
source files of its own.
