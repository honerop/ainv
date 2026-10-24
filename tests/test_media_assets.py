"""Offline regression tests for Wikimedia Commons image sourcing."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "media_assets", Path(__file__).resolve().parents[1] / "tools" / "media_assets.py"
)
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


def example():
    return {
        "query": {"pages": [{
            "title": "File:Old castle.png",
            "imageinfo": [{
                "url": "https://upload.wikimedia.org/real.png",
                "thumburl": "https://upload.wikimedia.org/thumb/castle.png",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Old_castle.png",
                "mime": "image/png",
                "extmetadata": {
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                    "Artist": {"value": "<a href='#'>Example Artist</a>"},
                    "AttributionRequired": {"value": "true"},
                },
            }],
        }]}
    }


class TestAssetAdapter(unittest.TestCase):
    def test_search_metadata_and_html(self):
        with patch.object(assets, "_request_json", return_value=example()):
            found = assets.search_images("castle")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["artist"], "Example Artist")
        self.assertEqual(found[0]["license"], "CC BY-SA 4.0")
        self.assertEqual(found[0]["attribution_required"], True)
        self.assertEqual(found[0]["provider"], "Wikimedia Commons")

    def test_empty_and_excessive_search_are_rejected(self):
        with self.assertRaises(assets.AssetError):
            assets.search_images(" ")
        with self.assertRaises(assets.AssetError):
            assets.search_images("x" * 241)

    def test_download_rejects_unsupported_host(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(assets.AssetError):
                assets._download_image("https://example.com/photo.jpg", Path(td) / "photo")

    def test_cache_works_offline_without_another_request(self):
        with tempfile.TemporaryDirectory() as td:
            calls = []
            def fake_download(url, dest):
                calls.append(url)
                target = dest.with_suffix(".png")
                target.write_bytes(b"\x89PNG\r\n\x1a\nmock")
                return target
            with patch.object(assets, "search_images", return_value=[{
                "title": "File:Castle.png",
                "download_url": "https://upload.wikimedia.org/thumb/castle.png",
                "license": "CC0", "source_page": "https://commons.wikimedia.org/wiki/File:Castle.png",
            }]), patch.object(assets, "_download_image", side_effect=fake_download):
                file1, meta1 = assets.fetch_image("castle", cache_dir=td)
            with patch.object(assets, "search_images", side_effect=AssertionError("network request")):
                file2, meta2 = assets.fetch_image("castle", cache_dir=td, offline=True)
            self.assertEqual(file1, file2)
            self.assertEqual(meta1, meta2)
            self.assertEqual(len(calls), 1)

    def test_offline_miss_reports_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(assets.AssetError, "not cached"):
                assets.fetch_image("not present", cache_dir=td, offline=True)

    def test_prepare_resolves_search_and_existing_relative_media(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "project.json"
            target = root / "temp" / "prepared.json"
            credits = root / "credits.json"
            source.write_text(json.dumps({
                "music": "sounds/theme.wav", "scenes": [
                    {"duration": 3, "media": {
                        "kind": "image", "search": "fortress", "provider": "commons", "fit": "cover",
                    }},
                    {"duration": 4, "media": {
                        "kind": "video", "src": "clips/video.mp4"
                    }, "audio": "sounds/voice.wav"},
                ],
            }), encoding="utf-8")
            image = root / "image.jpg"
            image.write_bytes(b"\xff\xd8\xffdummy")
            metadata = {"title": "File:Castle.jpg", "license": "CC BY 4.0", "query": "fortress"}
            with patch.object(assets, "fetch_image", return_value=(image, metadata)):
                found = assets.prepare(source, target, credits)
            transformed = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(found), 1)
            self.assertEqual(transformed["scenes"][0]["media"]["src"], str(image))
            self.assertEqual(transformed["scenes"][0]["media"]["fit"], "cover")
            self.assertNotIn("search", transformed["scenes"][0]["media"])
            self.assertEqual(transformed["scenes"][1]["media"]["src"], str(root / "clips/video.mp4"))
            self.assertEqual(transformed["scenes"][1]["audio"], str(root / "sounds/voice.wav"))
            self.assertEqual(transformed["music"], str(root / "sounds/theme.wav"))
            self.assertEqual(json.loads(credits.read_text())[0]["scene"], 1)

    def test_prepare_leaves_attribution_absent_when_no_remote_images(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = root / "p.json"
            original.write_text(json.dumps({"scenes": [{"media": {"kind": "image", "src": "img.jpg"}}]}))
            dest = root / "out" / "resolved.json"
            credits = root / "attribution.json"
            self.assertEqual(assets.prepare(original, dest, credits), [])
            self.assertFalse(credits.exists())

    def test_prepare_rejects_unknown_provider(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = root / "p.json"
            original.write_text(json.dumps({
                "scenes": [{"media": {"search": "mountain", "provider": "not-a-provider"}}]
            }))
            with self.assertRaisesRegex(assets.AssetError, "Unsupported image provider"):
                assets.prepare(original, root / "out.json")

    def test_prepare_rejects_remote_raw_url(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = root / "p.json"
            original.write_text(json.dumps({
                "scenes": [{"media": {"kind": "image", "src": "https://example.org/image.jpg"}}]
            }))
            with self.assertRaisesRegex(assets.AssetError, "Remote src URLs"):
                assets.prepare(original, root / "out.json")


if __name__ == "__main__":
    unittest.main()
