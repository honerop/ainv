"""Offline storyboard inspection and project preset regressions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "project_inspect", Path(__file__).resolve().parents[1] / "tools" / "project_inspect.py"
)
project_inspect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project_inspect)


class StoryboardTests(unittest.TestCase):
    def test_valid_video_without_any_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "intro.png").write_bytes(b"fake")
            p = root / "project.json"
            p.write_text(json.dumps({
                "width": 640, "height": 360, "fps": 12,
                "scenes": [
                    {"duration": 2, "media": {
                        "kind": "image", "src": "intro.png", "motion": "zoom-in"}},
                    {"frames": 12, "media": {
                        "kind": "image", "provider": "commons", "search": "stone fortress",
                        "license": "public-domain", "result": 0}},
                ]}))
            report = project_inspect.analyze(p)
            self.assertTrue(report["ok"], report["problems"])
            self.assertEqual(report["frames_estimate"], 36)
            self.assertEqual(report["duration_seconds_estimate"], 3.0)
            self.assertEqual(report["scenes"][0]["media_status"], "found")
            self.assertEqual(report["scenes"][1]["media_status"], "remote-commons")
            self.assertEqual(report["scenes"][1]["start_second_estimate"], 2.0)

    def test_missing_local_asset_and_unknown_motion_are_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "broken.json"
            p.write_text(json.dumps({
                "fps": 24, "scenes": [{"duration": 2, "media": {
                    "kind": "video", "src": "lost.mp4", "motion": "zoom-in"
                }}]
            }))
            result = project_inspect.analyze(p)
            self.assertFalse(result["ok"])
            self.assertTrue(any("missing media" in e for e in result["problems"]))
            self.assertTrue(any("only for images" in e for e in result["problems"]))

    def test_all_presets_have_supported_resolution_and_scenes(self):
        for preset, expected in project_inspect.PRESETS.items():
            data = project_inspect.initial_project(preset)
            self.assertEqual((data["width"], data["height"]), expected)
            self.assertTrue(all(s.get("duration", 0) > 0 for s in data["scenes"]))
            self.assertEqual(data["fps"], 30)

    def test_frame_limit(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "huge.json"
            p.write_text(json.dumps({"fps": 30, "scenes": [{"frames": 19000}]}))
            result = project_inspect.analyze(p)
            self.assertFalse(result["ok"])
            self.assertTrue(any("18000 frame limit" in e for e in result["problems"]))

    def test_narration_duration_is_approximation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "talk.json"
            p.write_text(json.dumps({"scenes": [{"frames": 2, "narration": "hello"}]}))
            result = project_inspect.analyze(p)
            self.assertTrue(result["ok"])
            self.assertTrue(any("estimate" in w for w in result["warnings"]))

    def test_invalid_source_json_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "invalid.json"
            p.write_text("{oops")
            self.assertFalse(project_inspect.analyze(p)["ok"])

    def test_cli_creates_file_without_overwriting(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "template.json"
            self.assertEqual(project_inspect.main(["init", str(p), "--preset", "vertical"]), 0)
            self.assertEqual(json.loads(p.read_text())["height"], 1280)
            with self.assertRaises(SystemExit):
                project_inspect.main(["init", str(p)])

    def test_machine_readable_inspect_output(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "project.json"
            p.write_text(json.dumps({"scenes": [{"frames": 2}]}))
            self.assertEqual(project_inspect.main(["inspect", str(p), "--json"]), 0)


if __name__ == "__main__":
    unittest.main()
