"""Hierarchical icon recipes, XML validity, safe labels and atomic asset builds."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from tgk.icon_builder import (
    EXTENSIONS,SPECIAL_FILES,Layer,Recipe,recipe_names,recipe_for,
    render_svg,asset_key_for_path,build_assets,_resolve_layers)
from tgk.icons import ICONS,icon_for_path,svg


class VectorRecipeTests(unittest.TestCase):
    def test_every_declared_and_legacy_icon_builds_valid_svg(self):
        names=recipe_names()
        self.assertGreater(len(names),250)
        self.assertTrue(set(ICONS).issubset(set(names)))
        for name in names:
            with self.subTest(name=name):
                source=render_svg(name)
                root=ET.fromstring(source)
                self.assertEqual(root.tag,"{http://www.w3.org/2000/svg}svg")
                self.assertIn('viewBox="0 0 64 64"',source)

    def test_file_extensions_have_exact_uppercase_centered_labels(self):
        for ext in EXTENSIONS:
            with self.subTest(ext=ext):
                name="file_ext_"+ext
                source=render_svg(name)
                self.assertIn(">"+ext.upper()+"</text>",source)
                self.assertIn('text-anchor="middle"',source)
                self.assertIn('dominant-baseline="middle"',source)
                self.assertIn('x="16" y="28"',source)
        for filename,label in SPECIAL_FILES.items():
            key=asset_key_for_path(filename,is_dir=False)
            self.assertTrue(key.startswith("filename_"))
            self.assertIn(">"+label+"</text>",render_svg(key))

    def test_parent_chain_and_modifiers(self):
        self.assertEqual(recipe_for("file_document").parent,"file_text")
        base,layers=_resolve_layers("file_document")
        self.assertEqual(base,"file")
        self.assertEqual([z.value for z in layers],["text","pen"])
        self.assertIn("M37 51L49 39",render_svg("file_document"))
        self.assertIn("M18 31L25 37",render_svg("file_ext_sh"))
        self.assertIn("M32 21V48",render_svg("file_ext_zip"))

    def test_old_classification_unchanged_new_asset_path_specific(self):
        self.assertEqual(icon_for_path("README.md",is_dir=False),"markdown")
        self.assertEqual(icon_for_path("README.md",is_dir=False,detailed=True),
                         "filename_readme_md")
        self.assertEqual(icon_for_path("x.py",is_dir=False,detailed=True),
                         "file_ext_py")
        self.assertEqual(asset_key_for_path("LICENSE",is_dir=False),
                         "filename_license")
        self.assertEqual(icon_for_path("x.unknown",is_dir=False,detailed=True),"file")
        self.assertEqual(svg("file_ext_json",64).count("<svg"),1)

    def test_invalid_inputs_and_cycles(self):
        with self.assertRaises(ValueError):Layer("script","evil")
        with self.assertRaises(ValueError):Layer("modifier","javascript")
        with self.assertRaises(ValueError):Recipe("../bad",None)
        with self.assertRaises(ValueError):render_svg("file_ext_py",size=2)
        with self.assertRaises(ValueError):render_svg("file_ext_py",stroke="url(js)")
        with self.assertRaises(KeyError):render_svg("something_nonexistent")
        with patch("tgk.icon_builder.recipe_for",side_effect=lambda x:
                  Recipe(x,"cycle_b") if x=="cycle_a" else Recipe(x,"cycle_a")):
            with self.assertRaisesRegex(ValueError,"cycle"):
                _resolve_layers("cycle_a")

    def test_svg_only_export_creates_empty_raster_dirs_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            result=build_assets(directory,names=[
                "file_ext_py","file_ext_jsonl","filename_readme_md",
                "file_document","folder_git"],raster=False)
            self.assertEqual(result["count"],5)
            root=Path(directory)/"icons"
            self.assertEqual(len(list((root/"svg").glob("*.svg"))),5)
            for sub in ("ico","low_res","mid_res","high_res"):
                self.assertTrue((root/sub).is_dir())
                self.assertEqual(list((root/sub).iterdir()),[])
            manifest=json.loads((root/"manifest.json").read_text())
            self.assertEqual(len(manifest["icons"]),5)
            with self.assertRaises(FileExistsError):
                build_assets(directory,names=["file"])
            build_assets(directory,names=["file"],overwrite=True)
            self.assertEqual(len(list((root/"svg").glob("*.svg"))),1)

    def test_no_partial_publication_on_invalid_recipes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"icons"
            root.mkdir()
            marker=root/"keep.txt"
            marker.write_text("original")
            with self.assertRaises(KeyError):
                build_assets(directory,names=["file","not_registered"],
                             overwrite=True)
            self.assertEqual(marker.read_text(),"original")
            self.assertFalse(list(Path(directory).glob(".tgk-icons-stage-*")))

    def test_invalid_asset_request_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):build_assets(directory,names=[])
            with self.assertRaises(ValueError):
                build_assets(directory,names=["file","folder"],max_icons=1)
            with self.assertRaises(ValueError):
                build_assets(directory,names=["file"],low=64,mid=64)
            with self.assertRaises(ValueError):
                build_assets(directory,names=["../file"])


if __name__=="__main__":
    unittest.main()
