#!/usr/bin/env python3
"""AinV audio director: match scenes to speech, render video, and mux sound.

Runtime dependencies are supplied by the Nix flake, not installed with pip.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(command: list[str]) -> None:
    subprocess.run([str(item) for item in command], check=True)


def probe_duration(path: Path, ffprobe: str) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Invalid audio duration for {path}")
    return duration


def to_srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def requested_frames(scene: dict, fps: int) -> int:
    if "frames" in scene:
        frames = scene["frames"]
        if isinstance(frames, bool) or not isinstance(frames, int) or frames < 1:
            raise ValueError("scene.frames must be a positive integer")
        return frames
    duration = scene.get("duration", "auto")
    if duration == "auto":
        return fps
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ValueError("scene.duration must be a number or 'auto'")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("scene.duration must be positive")
    return max(1, round(duration * fps))


def local_file(base: Path, name: str) -> Path:
    result = (base / name).resolve()
    if not result.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {result}")
    return result


def prepare_timeline(project: dict, input_path: Path, workspace: Path,
                     voice: str | None, rate: str | None,
                     no_tts: bool, ffprobe: str, edge_tts: str):
    fps = project.get("fps", 30)
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 60:
        raise ValueError("fps must be an integer between 1 and 60")
    if not isinstance(project.get("scenes"), list) or not project["scenes"]:
        raise ValueError("scenes must be a nonempty array")
    result = copy.deepcopy(project)
    total_frames = 0
    clips = []
    captions = []
    for index, scene in enumerate(result["scenes"]):
        if not isinstance(scene, dict):
            raise ValueError(f"scene {index} must be an object")
        narration = scene.get("narration", "")
        if not isinstance(narration, str):
            raise ValueError(f"scene {index} narration must be a string")
        audio = scene.get("audio")
        if narration.strip() and audio:
            raise ValueError(f"scene {index}: use narration or audio, not both")
        clip = None
        length = 0.0
        if audio:
            clip = local_file(input_path.parent, audio)
            length = probe_duration(clip, ffprobe)
        elif narration.strip() and not no_tts:
            clip = workspace / f"voice-{index:03}.mp3"
            chosen_voice = scene.get("voice", voice or project.get("voice", "en-US-GuyNeural"))
            chosen_rate = scene.get("voice_rate", rate or project.get("voice_rate", "+0%"))
            if not isinstance(chosen_voice, str) or not isinstance(chosen_rate, str):
                raise ValueError("voice and voice_rate must be strings")
            print(f"ainv: synthesizing scene {index + 1}: {chosen_voice}", flush=True)
            run([edge_tts, "--voice", chosen_voice, f"--rate={chosen_rate}",
                 "--text", narration, "--write-media", str(clip)])
            length = probe_duration(clip, ffprobe)

        frames = requested_frames(scene, fps)
        if clip is not None:
            # Always leave a short pause after the narration, never clip a sentence.
            frames = max(frames, math.ceil((length + 0.35) * fps))
        scene.pop("duration", None)
        scene["frames"] = frames

        start = total_frames / fps
        if clip is not None:
            clips.append((clip, start))
        caption = scene.get("caption", narration)
        if not isinstance(caption, str):
            raise ValueError(f"scene {index} caption must be a string")
        if caption.strip():
            caption_end = start + (length if length > 0 else frames / fps)
            captions.append((start, min(start + frames / fps, caption_end), caption.strip()))
        total_frames += frames
    if total_frames > 18000:
        raise ValueError("video exceeds native renderer's 18000-frame limit")
    return result, clips, captions, total_frames / fps


def write_subtitles(path: Path, captions: list[tuple[float, float, str]]) -> None:
    blocks = []
    for number, (start, end, caption) in enumerate(captions, 1):
        caption = re.sub(r"\s+", " ", caption).strip()
        blocks.append(f"{number}\n{to_srt_time(start)} --> {to_srt_time(end)}\n{caption}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def mux_audio(video: Path, output: Path, clips: list[tuple[Path, float]],
              music: Path | None, subtitles: Path | None, duration: float,
              ffmpeg: str) -> None:
    # Input 0: rendered video. Input 1: silence of exactly the video's length.
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(video),
           "-f", "lavfi", "-t", f"{duration:.6f}",
           "-i", "anullsrc=r=48000:cl=stereo"]
    filters = ["[1:a]volume=0[sil]"]
    sources = ["[sil]"]
    index = 2
    for path, start in clips:
        cmd += ["-i", str(path)]
        milliseconds = round(start * 1000)
        filters.append(
            f"[{index}:a]aresample=48000,adelay={milliseconds}:all=1,"
            f"volume=1.0[voice{index}]"
        )
        sources.append(f"[voice{index}]")
        index += 1
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        filters.append(f"[{index}:a]aresample=48000,volume=0.12[music]")
        sources.append("[music]")
        index += 1
    filters.append(
        "".join(sources) + f"amix=inputs={len(sources)}:"
        "duration=first:dropout_transition=0,"
        "aresample=48000,alimiter=limit=0.95[aout]"
    )
    subtitle_index = None
    if subtitles is not None:
        subtitle_index = index
        cmd += ["-i", str(subtitles)]
    cmd += ["-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
    if subtitle_index is not None:
        cmd += ["-map", f"{subtitle_index}:s:0", "-c:s", "mov_text"]
    cmd += ["-t", f"{duration:.6f}", "-movflags", "+faststart", str(output)]
    run(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render AinV JSON to narrated MP4")
    parser.add_argument("input", nargs="?", help="JSON project (default: built-in demo)")
    parser.add_argument("output", nargs="?", help="Output MP4")
    parser.add_argument("--voice", help="Override Edge TTS voice")
    parser.add_argument("--rate", help="Edge TTS speed, e.g. -10%% (use --rate=-10%%)")
    parser.add_argument("--music", help="Add looping background audio (mixed quietly)")
    parser.add_argument("--no-tts", action="store_true",
                        help="Skip online speech synthesis; render silent or supplied audio")
    parser.add_argument("--no-subtitles", action="store_true",
                        help="Do not write or embed SRT subtitles")
    args = parser.parse_args()

    input_name = args.input or os.environ.get("AINV_DEFAULT_SPEC", "examples/math-explainer.json")
    input_path = Path(input_name).expanduser().resolve()
    output = Path(args.output or ("output.mp4" if args.input else "showcase.mp4")).expanduser().resolve()
    if not input_path.is_file():
        parser.error(f"input JSON not found: {input_path}")
    if output.suffix.lower() != ".mp4":
        parser.error("output must be a .mp4 file")
    if not output.parent.is_dir():
        parser.error(f"output directory does not exist: {output.parent}")
    project = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(project, dict):
        parser.error("project must be a JSON object")
    native = os.environ.get("AINV_NATIVE", "ainv-native")
    ffmpeg = os.environ.get("AINV_FFMPEG", "ffmpeg")
    ffprobe = os.environ.get("AINV_FFPROBE", "ffprobe")
    edge_tts = os.environ.get("AINV_EDGE_TTS", "edge-tts")
    music_name = args.music or project.get("music")
    music = local_file(input_path.parent, music_name) if music_name else None
    subtitle_output = output.with_suffix(".srt")
    try:
        with tempfile.TemporaryDirectory(prefix="ainv-") as temp:
            work = Path(temp)
            timeline, clips, captions, duration = prepare_timeline(
                project, input_path, work, args.voice, args.rate,
                args.no_tts, ffprobe, edge_tts
            )
            script = work / "timeline.json"
            script.write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
            rendered = work / "silent.mp4"
            print(f"ainv: rendering {duration:.2f}s of vector animation", flush=True)
            run([native, str(script), str(rendered)])
            sub = None
            if captions and not args.no_subtitles:
                sub = work / "captions.srt"
                write_subtitles(sub, captions)
            if clips or music is not None:
                mux_audio(rendered, output, clips, music, sub, duration, ffmpeg)
            else:
                shutil.copy2(rendered, output)
            if sub is not None:
                subtitle_output.write_text(sub.read_text(encoding="utf-8"), encoding="utf-8")
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError, OSError) as error:
        print(f"ainv: error: {error}", file=sys.stderr)
        return 1
    print(f"ainv: created {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
