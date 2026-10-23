"""Semantic icon contract: UI operations cannot revert to letter badges."""
from pathlib import Path
import json
import tempfile
import unittest
from xml.etree import ElementTree as ET

from tgk.icon_builder import build_assets, recipe_for, render_svg
from tgk.icons import CATEGORIES, svg
from tgk.semantic_icons import SEMANTIC_ICONS

NS = {"s": "http://www.w3.org/2000/svg"}


class PurposeBuiltIconTests(unittest.TestCase):
    def test_every_nonfile_catalog_icon_has_explicit_semantic_geometry(self):
        categories = ("actions", "media", "view", "navigation")
        expected = {name for group in categories for name in CATEGORIES[group]}
        self.assertFalse(expected - SEMANTIC_ICONS,
                         "Unimplemented semantic vector icons: " +
                         repr(sorted(expected - SEMANTIC_ICONS)))
        self.assertTrue(expected.issubset(SEMANTIC_ICONS))

    def test_no_action_media_view_or_navigation_icon_uses_generic_badge(self):
        for name in sorted(SEMANTIC_ICONS):
            with self.subTest(name=name):
                source = render_svg(name)
                root = ET.fromstring(source)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertIsNone(root.find(".//s:text", NS))
                self.assertIsNone(root.find(".//s:rect[@x='32'][@y='42']", NS))
                self.assertIsNotNone(root.find(".//s:g/s:path", NS))
                self.assertIsNone(recipe_for(name).parent)
                self.assertIn(name.replace("_", " "), root.attrib["aria-label"])
                self.assertEqual(source, render_svg(name))

    def test_specific_pictograms_encode_the_requested_operations(self):
        for name in ("refresh", "sync", "copy", "cut", "run",
                     "play", "pause", "stop", "search", "settings"):
            self.assertIn(name, SEMANTIC_ICONS)
        samples = {name: render_svg(name) for name in
                   ("refresh", "sync", "copy", "cut", "run",
                    "play", "pause", "stop")}
        self.assertIn("A8 8", samples["refresh"])  # two curved cyclic arrows
        self.assertIn("M3 8V5", samples["sync"])     # overlapping documents
        self.assertIn("M8 7H20", samples["copy"])   # overlapping documents
        self.assertIn("A3 3", samples["cut"])       # scissor handles
        self.assertIn("M3 4H21V20H3Z", samples["run"])  # terminal window
        self.assertIn("M6 9L10 12L6 15", samples["run"])  # >_ prompt
        self.assertIn("M8 4L20 12L8 20Z", samples["play"])
        self.assertIn("M7 4H10V20H7Z", samples["pause"])
        self.assertIn("M5 5H19V19H5Z", samples["stop"])
        self.assertEqual(len({samples[n] for n in ("play", "pause", "stop")}), 3)

    def test_legacy_svg_function_uses_same_semantic_vector(self):
        for name in ("play", "pause", "stop", "refresh", "sync", "cut", "run"):
            with self.subTest(name=name):
                root = ET.fromstring(svg(name, size=32))
                self.assertEqual(root.get("viewBox"), "0 0 64 64")
                self.assertIsNone(root.find(".//s:text", NS))

    def test_file_extension_labels_still_use_document_recipes(self):
        source = render_svg("file_ext_py")
        self.assertIn(">PY</text>", source)
        self.assertIn('x="16" y="28"', source)

    def test_built_svg_assets_and_manifest_use_semantic_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = ["run", "refresh", "sync", "copy", "cut",
                        "play", "pause", "stop", "file_ext_py"]
            result = build_assets(directory, names=selected, raster=False)
            self.assertEqual(result["count"], len(selected))
            output = Path(directory) / "icons"
            manifest = json.loads((output / "manifest.json").read_text())
            for name in selected:
                source = (output / "svg" / (name + ".svg")).read_text()
                ET.fromstring(source)
                self.assertIn(name, manifest["icons"])
                if name in SEMANTIC_ICONS:
                    self.assertNotIn("<text", source)


if __name__ == "__main__":
    unittest.main()
