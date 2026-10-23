"""Decode real optional raster outputs; no Android rendering claim."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from tgk.icon_builder import build_assets, main


RASTER_AVAILABLE = all(importlib.util.find_spec(name) is not None
                       for name in ("cairosvg", "PIL"))


@unittest.skipUnless(RASTER_AVAILABLE, "optional CairoSVG and Pillow required")
class RasterAssetTests(unittest.TestCase):
    def test_tiny_valid_sizes_still_produce_decodable_ico(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            build_assets(directory, names=["file"], raster=True,
                         low=8, mid=9, high=10)
            with Image.open(Path(directory)/"icons/ico/file.ico") as icon:
                icon.load()
                self.assertEqual(icon.format, "ICO")
                self.assertEqual(icon.size, (10, 10))

    def test_decoded_formats_dimensions_alpha_and_integrity(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            build_assets(directory, names=["file", "file_ext_py"], raster=True,
                         low=16, mid=32, high=64)
            root = Path(directory)/"icons"
            manifest = json.loads((root/"manifest.json").read_text())
            for name in ("file", "file_ext_py"):
                for folder, size in (("low_res", 16), ("mid_res", 32),
                                     ("high_res", 64)):
                    for extension, fmt in (("png", "PNG"), ("jpg", "JPEG")):
                        with Image.open(root/folder/(name+"."+extension)) as image:
                            image.load()
                            self.assertEqual(image.format, fmt)
                            self.assertEqual(image.size, (size, size))
                            if extension == "png":
                                self.assertEqual(image.convert("RGBA").getpixel((0, 0))[3], 0)
                            else:
                                self.assertEqual(image.mode, "RGB")
                with Image.open(root/"ico"/(name+".ico")) as icon:
                    self.assertEqual(icon.ico.sizes(), {(16, 16), (24, 24),
                                                       (32, 32), (48, 48), (64, 64)})
                    for size in icon.ico.sizes():
                        icon.ico.getimage(size).load()
            files = {path.relative_to(root).as_posix(): path.read_bytes()
                     for path in root.rglob("*")
                     if path.is_file() and path.name != "manifest.json"}
            self.assertEqual(len(files), 16)
            self.assertEqual(set(manifest["files"]), set(files))
            for path, data in files.items():
                self.assertEqual(manifest["files"][path], {
                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})

    def test_identical_raster_builds_have_identical_files(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory)/name for name in ("first", "second")]
            snapshots = []
            for root in roots:
                root.mkdir()
                build_assets(root, names=["file_ext_jsonl"], raster=True,
                             low=16, mid=32, high=64)
                snapshots.append({path.relative_to(root).as_posix(): path.read_bytes()
                                  for path in root.rglob("*") if path.is_file()})
            self.assertEqual(snapshots[0], snapshots[1])


class BoundedSelectionTests(unittest.TestCase):
    def test_module_cli_honors_saved_raster_default(self):
        from tgk.config import initialize_config, patch_config, clear_config_cache
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"TGK_CONFIG_HOME": str(Path(directory)/"config")}):
                initialize_config()
                patch_config({"icons": {"raster": True}})
                with patch("tgk.icon_builder._raster_backend",
                           side_effect=RuntimeError("optional backend requested")):
                    with self.assertRaisesRegex(RuntimeError, "optional backend requested"):
                        main(["--output", directory, "--icon", "file"])
                clear_config_cache()

    def test_module_cli_can_disable_saved_raster_default(self):
        from tgk.config import initialize_config, patch_config, clear_config_cache
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"TGK_CONFIG_HOME": str(Path(directory)/"config")}):
                initialize_config()
                patch_config({"icons": {"raster": True}})
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["--output", directory, "--icon", "file",
                                           "--svg-only"]), 0)
                self.assertFalse(json.loads(output.getvalue())["raster"])
                clear_config_cache()

    def test_create_only_does_not_replace_catalog_created_during_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/"icons"
            # Rendering currently precedes the initial output existence check;
            # create the competing catalog after that check instead.
            import tempfile as tempfile_module
            original = tempfile_module.mkdtemp
            def staging(*args, **kwargs):
                if kwargs.get("prefix") == ".tgk-icons-stage-":
                    root.mkdir()
                    (root/"custom.svg").write_text("user asset")
                return original(*args, **kwargs)
            with patch("tgk.icon_builder.tempfile.mkdtemp", side_effect=staging):
                with self.assertRaises(FileExistsError):
                    build_assets(directory, names=["file"], raster=False)
            self.assertEqual((root/"custom.svg").read_text(), "user asset")
            self.assertFalse(list(Path(directory).glob(".tgk-icons-stage-*")))

    def test_lazy_recipe_selection_is_bounded_before_materializing(self):
        consumed = []
        def names():
            for _ in range(100):
                consumed.append(1)
                yield "file"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build_assets(directory, names=names(), max_icons=2, raster=False)
            self.assertLessEqual(len(consumed), 3)
            self.assertFalse((Path(directory)/"icons").exists())

    def test_mixed_invalid_names_raise_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build_assets(directory, names=["file", None], raster=False)


if __name__ == "__main__":
    unittest.main()
