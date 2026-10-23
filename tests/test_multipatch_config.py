"""A single durable config transaction for UI defaults and resource controls."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config


class ConfigPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"user"
        self.env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        config.initialize_config()
        self.path=self.root/"config.json"

    def test_patch_updates_selected_profile_theme_and_layout_atomically(self):
        before=self.path.read_bytes()
        updated=config.patch_config({
            "ui":{"theme":"ocean","text_style":"title_h1",
                  "option_profile":"battery_saver"},
            "layout":{"touch_target_dp":56},
        })
        self.assertEqual(updated["ui"]["theme"],"ocean")
        self.assertEqual(updated["ui"]["text_style"],"title_h1")
        self.assertEqual(updated["io"]["workers"],1)
        self.assertEqual(updated["layout"]["touch_target_dp"],56)
        raw=json.loads(self.path.read_text())
        self.assertEqual(raw["ui"]["option_profile"],"battery_saver")
        self.assertEqual(raw["layout"]["touch_target_dp"],56)
        self.assertNotEqual(before,self.path.read_bytes())
        self.assertEqual(config.load_config(),updated)

    def test_multiple_invalid_fields_cannot_partially_apply(self):
        before=self.path.read_bytes()
        for choices in (
            {"ui":{"theme":"ocean"},"io":{"workers":999}},
            {"ui":{"option_profile":"unknown_profile"}},
            {"layout":{"touch_target_dp":0}},
            {"ui":{"theme":"../../../unsafe"}},
            {"ui":{"text_style":"no_such_style"}},
            {"not_allowed":{"oops":1}},
            {"ui":{}},
            {},
        ):
            with self.subTest(choices=choices),self.assertRaises(ValueError):
                config.patch_config(choices)
            self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.root.glob(".tgk-config-*")),[])

    def test_single_field_wrapper_persists_independent_values(self):
        config.update_config("ui","theme","paper")
        result=config.update_config("runtime","clock_callbacks_per_tick",42)
        self.assertEqual(result["ui"]["theme"],"paper")
        self.assertEqual(result["runtime"]["clock_callbacks_per_tick"],42)
        self.assertEqual(config.load_config(),result)

    def test_presets_not_overwritten_and_symlinks_refused(self):
        palette=self.root/"palettes"/"ocean.json"
        old=b"custom user palette data"
        palette.write_bytes(old)
        config.patch_config({"ui":{"text_style":"caption"}})
        self.assertEqual(palette.read_bytes(),old)
        target=self.path
        original=target.read_bytes()
        elsewhere=self.root/"elsewhere.json"
        elsewhere.write_bytes(original)
        target.unlink()
        target.symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.patch_config({"ui":{"window_mode":"dialog"}})
        self.assertEqual(elsewhere.read_bytes(),original)

    def test_raster_pack_default_can_be_explicitly_disabled(self):
        from tgk.icon_builder import build_assets
        config.patch_config({"icons":{"raster":True,"low":24,"mid":64,
                                     "high":128,"max_icons":2}})
        with patch("tgk.icon_builder._raster_backend",
                   side_effect=RuntimeError("backend selected")):
            with self.assertRaisesRegex(RuntimeError,"backend selected"):
                build_assets(self.temp.name,names=["file"])
        result=build_assets(self.temp.name,names=["file"],raster=False)
        self.assertEqual(result["svg_files"],1)
        self.assertFalse(result["raster"])
        manifest=json.loads((Path(self.temp.name)/"icons"/"manifest.json").read_text())
        self.assertEqual(manifest["sizes"],{"low":24,"mid":64,"high":128})


if __name__=="__main__":
    unittest.main()
