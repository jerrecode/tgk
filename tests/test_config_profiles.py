"""Integrated option-profile ordering, I/O and icon-export defaults."""
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tgk import config
from tgk.io_pipeline import Limits,transfer,BoundedPool
from tgk.icon_builder import build_assets
from tgk.widgets import App


class ConfigProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"settings"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        config.initialize_config()
        config._load_cached.cache_clear()
        self.addCleanup(config._load_cached.cache_clear)

    def update_config(self,fn):
        path=self.root/"config.json"
        value=json.loads(path.read_text("utf-8"))
        fn(value)
        path.write_text(json.dumps(value),encoding="utf-8")
        config._load_cached.cache_clear()

    def test_option_preset_modifies_runtime_and_touch_sizes(self):
        self.update_config(lambda d:d["ui"].update(option_profile="accessibility_touch"))
        settings=config.load_config()
        self.assertEqual(settings["layout"]["touch_target_dp"],64)
        self.assertEqual(settings["layout"]["grid_unit_dp"],8)
        self.assertEqual(App().layout_scale.touch_target_dp,64)
        self.update_config(lambda d:d["ui"].update(option_profile="battery_saver"))
        settings=config.load_config()
        self.assertEqual(settings["runtime"]["clock_callbacks_per_tick"],48)
        self.assertEqual(settings["io"]["workers"],1)

    def test_explicit_overrides_win_without_losing_other_profile_changes(self):
        def customize(d):
            d["ui"]["option_profile"]="battery_saver"
            d["io"]["pending"]=3
            d["runtime"]["clock_callbacks_per_tick"]=82
        self.update_config(customize)
        settings=config.load_config()
        self.assertEqual(settings["io"]["workers"],1)
        self.assertEqual(settings["io"]["pending"],3)
        self.assertEqual(settings["runtime"]["clock_callbacks_per_tick"],82)
        self.assertAlmostEqual(settings["runtime"]["idle_sleep_seconds"],.025)

    def test_custom_installed_option_file_is_selected(self):
        named=self.root/"options"/"custom_profile.json"
        named.write_text(json.dumps({"name":"custom_profile","settings":{
            "layout":{"touch_target_dp":68},"io":{"workers":1}}}),encoding="utf-8")
        self.update_config(lambda d:d["ui"].update(option_profile="custom_profile"))
        settings=config.load_config()
        self.assertEqual(settings["layout"]["touch_target_dp"],68)
        self.assertEqual(settings["io"]["workers"],1)

    def test_invalid_option_preset_fails_early(self):
        self.update_config(lambda d:d["ui"].update(option_profile="missing"))
        with self.assertRaisesRegex(ValueError,"unknown option profile"):
            config.load_config()

    def test_chunk_transfer_and_pool_inherit_io_config(self):
        self.update_config(lambda d:d["io"].update(max_bytes=4,chunk_bytes=1024,
                                                   workers=1,pending=0))
        dest=BytesIO()
        with self.assertRaisesRegex(ValueError,"maximum transfer"):
            transfer(BytesIO(b"abcdef"),dest)
        result=transfer(BytesIO(b"abcdef"),BytesIO(),
                        limits=Limits(max_bytes=100,chunk_bytes=1024))
        self.assertEqual(result.bytes_copied,6)
        with BoundedPool() as pool:
            self.assertEqual(pool.limits.workers,1)
            self.assertEqual(pool.limits.pending,0)

    def test_asset_export_inherits_icon_dimensions_and_limits(self):
        self.update_config(lambda d:d["icons"].update(low=24,mid=64,high=128,
                                                       max_icons=1))
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            result=build_assets(output,names=["file_ext_json"],raster=False)
            self.assertEqual(result["count"],1)
            doc=json.loads((output/"icons"/"manifest.json").read_text())
            self.assertEqual(doc["sizes"],{"low":24,"mid":64,"high":128})
            with self.assertRaisesRegex(ValueError,"oversized"):
                build_assets(output,names=["file_ext_json","file_ext_xml"],
                             raster=False,overwrite=True)
            # An explicit maximum takes precedence over the configured cap.
            result=build_assets(output,names=["file_ext_json","file_ext_xml"],
                                raster=False,max_icons=2,overwrite=True)
            self.assertEqual(result["count"],2)


if __name__=="__main__":
    unittest.main()
