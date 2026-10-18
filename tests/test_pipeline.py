"""Unit and integration tests for the Nix-independent AinV audio director."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "fps": 10,
            "scenes": [
                {"duration": 1, "narration": "The parabola is useful.", "elements": []},
                {"frames": 12, "elements": []},
            ],
        }

    def test_speech_expands_short_scenes_and_positions_next_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            def fake_run(command):
                Path(command[-1]).write_bytes(b"test mp3")
            with mock.patch.object(pipeline, "run", side_effect=fake_run), \
                 mock.patch.object(pipeline, "probe_duration", return_value=2.4):
                result, clips, captions, duration = pipeline.prepare_timeline(
                    self.project, Path(temporary) / "project.json",
                    Path(temporary), None, None, False, "ffprobe", "edge-tts",
                )
            self.assertEqual(result["scenes"][0]["frames"], 28)
            self.assertEqual(result["scenes"][1]["frames"], 12)
            self.assertAlmostEqual(duration, 4.0)
            self.assertEqual(len(clips), 1)
            self.assertAlmostEqual(clips[0][1], 0.0)
            self.assertAlmostEqual(captions[0][1], 2.4)
            # Do not mutate the project loaded from disk.
            self.assertEqual(self.project["scenes"][0]["duration"], 1)

    def test_no_tts_is_network_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(pipeline, "run", side_effect=AssertionError("network used")):
                result, clips, captions, duration = pipeline.prepare_timeline(
                    self.project, Path(temporary) / "project.json",
                    Path(temporary), None, None, True, "ffprobe", "edge-tts",
                )
            self.assertEqual(result["scenes"][0]["frames"], 10)
            self.assertEqual(clips, [])
            self.assertEqual(len(captions), 1)
            self.assertAlmostEqual(duration, 2.2)

    def test_reject_invalid_frame_count(self):
        self.project["scenes"][0]["frames"] = -4
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                pipeline.prepare_timeline(
                    self.project, Path(temporary) / "spec.json",
                    Path(temporary), None, None, True, "ffprobe", "edge-tts",
                )

    def test_subtitle_timing(self):
        self.assertEqual(pipeline.to_srt_time(61.234), "00:01:01,234")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "speech.srt"
            pipeline.write_subtitles(path, [(0.0, 1.25, "First   scene"), (2.0, 2.5, "Second")])
            self.assertIn("00:00:00,000 --> 00:00:01,250", path.read_text())
            self.assertIn("First scene", path.read_text())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg and FFprobe required")
class MuxTests(unittest.TestCase):
    def test_mux_preserves_video_adds_voice_and_embeds_captions(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            base = directory / "video.mp4"
            voice = directory / "voice.wav"
            sub = directory / "subtitle.srt"
            output = directory / "result.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=size=160x96:rate=10:duration=2",
                "-c:v", "mpeg4", str(base)
            ], check=True)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.8",
                str(voice)
            ], check=True)
            pipeline.write_subtitles(sub, [(0.5, 1.3, "A plotted curve")])
            pipeline.mux_audio(base, output, [(voice, 0.5)], None, sub, 2.0, "ffmpeg")
            tracks = json.loads(subprocess.run([
                "ffprobe", "-v", "error", "-show_streams",
                "-of", "json", str(output)
            ], capture_output=True, text=True, check=True).stdout)["streams"]
            self.assertEqual(
                sorted(s["codec_type"] for s in tracks),
                ["audio", "subtitle", "video"]
            )
            self.assertTrue(output.stat().st_size > 1000)


if __name__ == "__main__":
    unittest.main()
