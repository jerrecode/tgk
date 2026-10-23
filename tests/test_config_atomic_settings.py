"""Persistent config: explicit overrides, profile fallback and atomic rollback."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from tgk import config


class AtomicConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"tgk"
        self.env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        config.clear_config_cache()
        self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def raw(self):
        return json.loads((self.root/"config.json").read_text("utf-8"))

    def test_default_install_has_all_editable_preset_families(self):
        from tgk.theme import PRESETS as palettes
        from tgk.typography import PRESETS as fonts
        self.assertEqual(len(list((self.root/"palettes").glob("*.json"))),len(palettes))
        self.assertEqual(len(list((self.root/"text_styles").glob("*.json"))),len(fonts))
        self.assertEqual(len(list((self.root/"options").glob("*.json"))),len(config.OPTIONS))
        self.assertEqual(config.load_config()["pinned"],[])

    def test_explicitly_pinned_factory_value_beats_battery_saver(self):
        effective=config.update_config("ui","option_profile","battery_saver")
        self.assertEqual(effective["io"]["workers"],1)
        self.assertEqual(effective["runtime"]["clock_callbacks_per_tick"],48)
        effective=config.update_config("io","workers",2)
        self.assertEqual(effective["io"]["workers"],2)
        self.assertIn("io.workers",self.raw()["pinned"])
        self.assertEqual(config.load_config()["io"]["workers"],2)
        effective=config.update_config("io","workers",None,reset=True)
        self.assertEqual(effective["io"]["workers"],1)
        self.assertNotIn("io.workers",self.raw()["pinned"])

    def test_switching_option_profile_keeps_explicit_pin(self):
        config.update_config("io","workers",7)
        config.update_config("ui","option_profile","battery_saver")
        self.assertEqual(config.load_config()["io"]["workers"],7)
        config.update_config("ui","option_profile","performance")
        self.assertEqual(config.load_config()["io"]["workers"],7)
        config.update_config("io","workers",None,reset=True)
        self.assertEqual(config.load_config()["io"]["workers"],4)

    def test_persisted_palette_and_typography_survive_reinstall(self):
        palettes=self.root/"palettes"/"ocean.json"
        colors=json.loads(palettes.read_text("utf-8"))
        colors["colors"]["accent"]="#C018F9"
        palettes.write_text(json.dumps(colors),encoding="utf-8")
        config.update_config("ui","theme","ocean")
        config.update_config("ui","text_style","title_h2")
        config.initialize_config()
        self.assertEqual(json.loads(palettes.read_text("utf-8"))["colors"]["accent"],"#C018F9")
        self.assertEqual(config.load_config()["ui"]["theme"],"ocean")
        self.assertEqual(config.load_config()["ui"]["text_style"],"title_h2")

    def test_invalid_update_keeps_previous_bytes(self):
        target=self.root/"config.json"
        original=target.read_bytes()
        for section,key,value in (
            ("layout","touch_target_dp",0),
            ("io","workers",999),
            ("ui","orientation","sideways"),
            ("unknown","key",12),
            ("runtime","clock_callbacks_per_tick",False),
        ):
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):
                config.update_config(section,key,value)
            self.assertEqual(target.read_bytes(),original)

    def test_malformed_json_and_symlink_are_never_replaced(self):
        target=self.root/"config.json"
        target.write_text("{ broken ",encoding="utf-8")
        with self.assertRaises(ValueError):config.update_config("ui","theme","ocean")
        self.assertEqual(target.read_text("utf-8"),"{ broken ")
        target.unlink()
        other=self.root/"real.json";other.write_text('{"ui":{"theme":"paper"}}')
        target.symlink_to(other)
        with self.assertRaises(ValueError):config.update_config("ui","theme","ocean")
        self.assertEqual(json.loads(other.read_text())["ui"]["theme"],"paper")

    def test_cli_set_reset_and_json_values(self):
        with redirect_stdout(StringIO()) as printed:
            self.assertEqual(config.main(["set","layout","touch_target_dp","64"]),0)
        self.assertEqual(json.loads(printed.getvalue())["layout"]["touch_target_dp"],64)
        with redirect_stdout(StringIO()) as printed:
            self.assertEqual(config.main(["set","ui","theme",'"paper"']),0)
        self.assertEqual(json.loads(printed.getvalue())["ui"]["theme"],"paper")
        with redirect_stdout(StringIO()) as printed:
            self.assertEqual(config.main(["reset","layout","touch_target_dp"]),0)
        self.assertEqual(json.loads(printed.getvalue())["layout"]["touch_target_dp"],48)

    def test_multi_setting_update_is_one_validated_transaction(self):
        result=config.update_settings({
            "ui":{"theme":"forest","option_profile":"performance"},
            "layout":{"touch_target_dp":64},
            "io":{"workers":2},
        })
        self.assertEqual(result["ui"]["theme"],"forest")
        self.assertEqual(result["io"]["workers"],2)
        self.assertEqual(result["layout"]["touch_target_dp"],64)
        pins=set(self.raw()["pinned"])
        self.assertTrue({"ui.theme","ui.option_profile",
                         "layout.touch_target_dp","io.workers"}<=pins)
        before=(self.root/"config.json").read_bytes()
        with self.assertRaises(ValueError):
            config.update_settings({"io":{"workers":3},"layout":{"columns":0}})
        self.assertEqual((self.root/"config.json").read_bytes(),before)
        config.update_settings({},reset=(("layout","touch_target_dp"),))
        self.assertEqual(config.load_config()["layout"]["touch_target_dp"],48)

    def test_invalid_option_profile_rejected_before_replacement(self):
        before=(self.root/"config.json").read_bytes()
        with self.assertRaises(ValueError):
            config.update_settings({"ui":{"option_profile":"nonexistent"}})
        self.assertEqual((self.root/"config.json").read_bytes(),before)

    def test_cache_clear_reloads_external_change(self):
        config.load_config()
        disk=self.raw()
        disk["ui"]["theme"]="ocean"
        (self.root/"config.json").write_text(json.dumps(disk))
        config.clear_config_cache()
        self.assertEqual(config.load_config()["ui"]["theme"],"ocean")


if __name__=="__main__":unittest.main()
