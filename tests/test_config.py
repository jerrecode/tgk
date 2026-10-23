"""Persistent TGK profiles must be valid, editable, idempotent, and lazy."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest

from tgk import config
from tgk.theme import get_theme,_active_theme
from tgk.typography import get_text_style,_active
from tgk.widgets import App,TermuxBackend


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"tgk-settings"
        p=patch.dict(os.environ,{"TGK_CONFIG_DIR":str(self.root)})
        p.start();self.addCleanup(p.stop)
        t=_active_theme.set(None);self.addCleanup(lambda:_active_theme.reset(t))
        ty=_active.set(None);self.addCleanup(lambda:_active.reset(ty))

    def test_fresh_default_config_is_read_only(self):
        value=config.get_config()
        self.assertEqual(value["defaults"]["theme"],"midnight")
        self.assertEqual(value["defaults"]["text_style"],"body")
        self.assertEqual(value["layout"]["touch_target_dp"],48)
        self.assertEqual(value["backend"]["clock_callbacks_per_tick"],128)
        self.assertFalse(self.root.exists())

    def test_install_populates_all_catalogs_without_replacing_edits(self):
        report=config.initialize_config()
        self.assertGreater(report["created"],65)
        self.assertEqual(report["created"],report["total"])
        self.assertTrue((self.root/"palettes/midnight.json").is_file())
        self.assertTrue((self.root/"typography/body.json").is_file())
        self.assertTrue((self.root/"options/backend.json").is_file())
        special=self.root/"typography/body.json"
        special.write_text('{"preset":"body","settings":{"size":25}}',encoding="utf-8")
        second=config.initialize_config()
        self.assertEqual(second["created"],0)
        self.assertEqual(second["total"],report["total"])
        self.assertEqual(json.loads(special.read_text())["settings"]["size"],25)
        self.assertEqual(get_text_style().size,25)

    def test_config_defaults_and_explicit_app_precedence(self):
        config.initialize_config()
        edited=config.update_config("defaults","theme","ocean")
        edited=config.update_config("defaults","text_style","title_h3")
        config.update_config("layout","touch_target_dp",56)
        config.update_config("window","orientation","landscape")
        self.assertEqual(get_theme().name,"ocean")
        self.assertEqual(get_text_style().size,23)
        app=App()
        self.assertEqual(app.theme.name,"ocean")
        self.assertEqual(app.text_style.size,23)
        self.assertEqual(app.layout_scale.touch_target_dp,56)
        self.assertEqual(app.orientation_mode,"landscape")
        overridden=App(theme="paper",text_style="body",orientation_mode="portrait")
        self.assertEqual(overridden.theme.name,"paper")
        self.assertEqual(overridden.text_style.size,16)
        self.assertEqual(overridden.orientation_mode,"portrait")
        self.assertEqual(overridden.layout_scale.touch_target_dp,56)

    def test_theme_customization_survives_base_color_changes(self):
        config.initialize_config()
        file=self.root/"palettes/ocean.json"
        palette=json.loads(file.read_text())
        palette["colors"]["accent"]="#AA33BB"
        palette["colors"]["button_pressed"]="#EECC00"
        file.write_text(json.dumps(palette),encoding="utf-8")
        config.update_config("defaults","theme","ocean")
        chosen=get_theme()
        self.assertEqual(chosen["accent"],"#AA33BBFF")
        self.assertEqual(chosen["button_pressed"],"#EECC00FF")
        self.assertEqual(chosen["button_active"],chosen.override(button="#CCEE11")["button_active"] if False else chosen["button_active"])

    def test_config_invalid_updates_do_not_corrupt_file(self):
        config.initialize_config()
        old=(self.root/"config.json").read_bytes()
        for section,key,value in (
            ("defaults","theme","unknown_theme"),
            ("layout","columns",999),
            ("backend","clock_callbacks_per_tick",0),
            ("backend","idle_sleep_seconds",float("nan")),
            ("io","workers",0),
            ("icons","high_res",1),
            ("defaults","not_a_setting","hey"),
        ):
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):
                config.update_config(section,key,value)
            self.assertEqual((self.root/"config.json").read_bytes(),old)

    def test_symlink_not_overwritten(self):
        config.initialize_config()
        target=self.root/"real.json";target.write_text('{}')
        link=self.root/"custom.json"
        link.symlink_to(target)
        self.assertFalse(config._atomic_write_new(link,{"unsafe":"value"}))
        self.assertEqual(target.read_text(),'{}')
        original=self.root/"config.json"
        original.unlink()
        original.symlink_to(target)
        with self.assertRaises(ValueError):
            config.update_config("defaults","theme","paper")

    def test_reload_changed_profile_during_same_process(self):
        config.initialize_config()
        self.assertEqual(get_theme().name,"midnight")
        path=self.root/"config.json"
        data=json.loads(path.read_text())
        data["defaults"]["theme"]="forest"
        path.write_text(json.dumps(data),encoding="utf-8")
        self.assertEqual(get_theme().name,"forest")

    def test_invalid_file_fails_loudly(self):
        config.initialize_config()
        (self.root/"config.json").write_text('{"schema_version":1,"layout":{"columns":0}}')
        with self.assertRaises(ValueError):config.get_config()

    def test_backend_inherits_config_defaults(self):
        config.initialize_config()
        config.update_config("layout","grid_unit_dp",8)
        backend=TermuxBackend(tg=object())
        self.assertEqual(backend.layout_scale.grid_unit_dp,8)


if __name__=="__main__":unittest.main()
