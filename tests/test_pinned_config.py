"""Pinned defaults and atomic multi-field transactions remain backward compatible."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
from contextlib import redirect_stdout
from unittest.mock import patch
import unittest
from tgk import config


class PinnedConfigTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)/"tgk"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        config.clear_config_cache()
        self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def raw(self):return json.loads((self.home/"config.json").read_text("utf-8"))

    def test_pin_factory_value_while_profile_would_change_it(self):
        selected=config.update_config("ui","option_profile","battery_saver")
        self.assertEqual(selected["io"]["workers"],1)
        selected=config.update_config("io","workers",2)
        self.assertEqual(selected["io"]["workers"],2)
        self.assertIn("io.workers",self.raw()["pinned"])
        selected=config.update_config("ui","option_profile","performance")
        self.assertEqual(selected["io"]["workers"],2)
        selected=config.update_config("io","workers",reset=True)
        self.assertEqual(selected["io"]["workers"],4)
        self.assertNotIn("io.workers",self.raw()["pinned"])

    def test_batch_is_one_transaction_and_rolls_back_on_error(self):
        result=config.update_settings({
            "ui":{"theme":"forest","option_profile":"performance"},
            "io":{"workers":2},
            "layout":{"touch_target_dp":64}
        })
        self.assertEqual(result["ui"]["theme"],"forest")
        self.assertEqual(result["io"]["workers"],2)
        self.assertEqual(result["layout"]["touch_target_dp"],64)
        self.assertIn("io.workers",self.raw()["pinned"])
        before=(self.home/"config.json").read_bytes()
        invalid=[
            {"io":{"workers":999}},
            {"ui":{"option_profile":"not_installed"}},
            {"layout":{"columns":0}},
            {"unknown":{"field":12}}
        ]
        for changes in invalid:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                config.update_settings(changes)
            self.assertEqual((self.home/"config.json").read_bytes(),before)

    def test_reset_multiple_pins_and_reject_conflicting_change(self):
        config.update_settings({"layout":{"touch_target_dp":48},
                                "runtime":{"clock_callbacks_per_tick":128}})
        self.assertIn("layout.touch_target_dp",self.raw()["pinned"])
        config.update_settings({},reset=(("layout","touch_target_dp"),
                                        ("runtime","clock_callbacks_per_tick")))
        self.assertNotIn("layout.touch_target_dp",self.raw()["pinned"])
        self.assertNotIn("runtime.clock_callbacks_per_tick",self.raw()["pinned"])
        before=(self.home/"config.json").read_bytes()
        with self.assertRaises(ValueError):
            config.update_settings({"io":{"workers":1}},reset=(("io","workers"),))
        self.assertEqual(before,(self.home/"config.json").read_bytes())

    def test_legacy_config_preserves_nondefault_user_overrides(self):
        path=self.home/"config.json"
        legacy=self.raw()
        legacy.pop("pinned")
        legacy["ui"]["option_profile"]="battery_saver"
        legacy["io"]["workers"]=3
        path.write_text(json.dumps(legacy),encoding="utf-8")
        config.clear_config_cache()
        self.assertEqual(config.load_config()["io"]["workers"],3)
        self.assertEqual(config.load_config()["pinned"],[])
        config.update_config("io","workers",2)
        self.assertEqual(config.load_config()["io"]["workers"],2)
        self.assertIn("io.workers",self.raw()["pinned"])

    def test_cli_set_reset_and_json_quoted_strings(self):
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(config.main(["set","ui","theme",json.dumps("paper")]),0)
        self.assertEqual(json.loads(out.getvalue())["ui"]["theme"],"paper")
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(config.main(["set","io","workers","2"]),0)
        self.assertEqual(json.loads(out.getvalue())["io"]["workers"],2)
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(config.main(["reset","io","workers"]),0)
        self.assertEqual(json.loads(out.getvalue())["io"]["workers"],2)
        self.assertNotIn("io.workers",self.raw()["pinned"])

    def test_reinstall_preserves_custom_presets_and_pin_metadata(self):
        config.update_config("io","workers",2)
        original=(self.home/"config.json").read_bytes()
        style=self.home/"text_styles"/"body.json"
        edited=style.read_bytes()
        config.initialize_config()
        self.assertEqual((self.home/"config.json").read_bytes(),original)
        self.assertEqual(style.read_bytes(),edited)


if __name__=="__main__":unittest.main()
