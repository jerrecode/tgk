"""TGK install/runtime configuration: create-only writes and explicit precedence."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config
from tgk.adaptive import LayoutScale
from tgk.widgets import App
from tgk.theme import get_theme,_active_theme
from tgk.typography import get_text_style,_active


class PersistentConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)/"settings"
        self.env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.dir)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.theme_token=_active_theme.set(None)
        self.style_token=_active.set(None)
        self.addCleanup(lambda:_active_theme.reset(self.theme_token))
        self.addCleanup(lambda:_active.reset(self.style_token))

    def write(self,relative,object):
        path=self.dir/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(object),encoding="utf-8")
        return path

    def test_installer_creates_config_and_every_preset(self):
        from tgk.theme import PRESETS as PALETTES
        from tgk.typography import PRESETS as FONTS
        result=config.initialize_config()
        self.assertTrue((self.dir/"config.json").is_file())
        self.assertEqual(len(list((self.dir/"palettes").glob("*.json"))),len(PALETTES))
        self.assertEqual(len(list((self.dir/"text_styles").glob("*.json"))),len(FONTS))
        self.assertEqual(len(list((self.dir/"options").glob("*.json"))),len(config.OPTIONS))
        self.assertEqual(result["total"],1+len(PALETTES)+len(FONTS)+len(config.OPTIONS))
        self.assertEqual(config.load_config(),config.DEFAULT_CONFIG)

    def test_reinstall_preserves_all_user_editing_and_permissions(self):
        config.initialize_config()
        original=self.dir/"palettes"/"midnight.json"
        custom=b'{ "theme":"midnight", "colors":{"accent":"#12AB34"}}\n'
        original.write_bytes(custom)
        settings=self.dir/"config.json"
        settings.write_text('{"ui":{"theme":"ocean"}}',encoding="utf-8")
        first=config.initialize_config()
        self.assertEqual(original.read_bytes(),custom)
        self.assertEqual(settings.read_text(encoding="utf-8"),'{"ui":{"theme":"ocean"}}')
        self.assertEqual(first["created"],[])
        self.assertEqual(len(first["preserved"]),first["total"])
        self.assertTrue(settings.exists())
        created=self.dir/"text_styles"/"body.json"
        self.assertTrue(created.is_file())

    def test_theme_and_typography_defaults_are_loaded_from_editable_files(self):
        config.initialize_config()
        cfg=deepcopy(config.DEFAULT_CONFIG)
        cfg["ui"].update({"theme":"ocean","text_style":"title_h2",
                          "orientation":"landscape","window_mode":"dialog"})
        cfg["layout"]["touch_target_dp"]=64
        cfg["runtime"]["clock_callbacks_per_tick"]=28
        cfg["runtime"]["idle_sleep_seconds"]=.025
        self.write("config.json",cfg)
        self.write("palettes/ocean.json",{"theme":"ocean",
                                          "colors":{"accent":"#123456"}})
        self.write("text_styles/title_h2.json",{"style":"title_h2",
                                           "properties":{"size":30,"role":"warning"}})
        app=App()
        self.assertEqual(app.theme["accent"],"#123456FF")
        self.assertEqual(app.text_style.size,30)
        self.assertEqual(app.text_style.role,"warning")
        self.assertEqual(app.orientation_mode,"landscape")
        self.assertEqual(app.window_mode,"dialog")
        self.assertEqual(app.layout_scale.touch_target_dp,64)
        self.assertEqual(app.clock_callbacks_per_tick,28)
        self.assertAlmostEqual(app.idle_sleep_seconds,.025)

    def test_explicit_args_override_persisted_settings_without_mutation(self):
        config.initialize_config()
        self.write("config.json",{"ui":{"theme":"ocean","text_style":"title_h2",
                                          "orientation":"landscape"},
                                  "layout":{"touch_target_dp":60}})
        app=App(theme="paper",text_style="caption",
                orientation_mode="portrait",layout_scale=LayoutScale(touch_target_dp=72),
                clock_callbacks_per_tick=10,idle_sleep_seconds=.005)
        self.assertEqual(app.theme.name,"paper")
        self.assertEqual(app.text_style.size,12)
        self.assertEqual(app.orientation_mode,"portrait")
        self.assertEqual(app.layout_scale.touch_target_dp,72)
        self.assertEqual(app.clock_callbacks_per_tick,10)
        self.assertEqual(config.load_config()["ui"]["theme"],"ocean")

    def test_schema_and_operational_limits_are_strict(self):
        bad=[
            {"schema_version":0},
            {"runtime":{"clock_callbacks_per_tick":0}},
            {"runtime":{"idle_sleep_seconds":float('nan')}},
            {"layout":{"touch_target_dp":0}},
            {"ui":{"theme":"../../outside"}},
            {"icons":{"raster":3}},
            {"icons":{"low":256,"mid":32}},
            {"tools":{"max_file_items":10000}},
            {"network":{"open_ports":80}},
        ]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                config.validate_config(item)

    def test_no_implicit_bootstrap_or_write_from_runtime_read(self):
        self.assertEqual(config.load_config(),config.DEFAULT_CONFIG)
        self.assertEqual(get_theme().name,"midnight")
        self.assertEqual(get_text_style().size,16)
        self.assertFalse(self.dir.exists())

    def test_read_is_bounded_and_error_does_not_overwrite_file(self):
        path=self.write("config.json",{"ui":{"theme":"ocean"}})
        path.write_bytes(b"x"*(config.MAX_JSON_BYTES+1))
        with self.assertRaisesRegex(ValueError,"size limit"):
            config.load_config()
        self.assertEqual(path.stat().st_size,config.MAX_JSON_BYTES+1)

    def test_name_profiles_and_io_limits(self):
        config.initialize_config()
        result=config.option_config("battery_saver")
        self.assertEqual(result["io"]["workers"],1)
        self.assertEqual(result["runtime"]["clock_callbacks_per_tick"],48)
        self.write("config.json",{"io":{"workers":3,"pending":5}})
        self.assertEqual(config.configured_io_limits().workers,3)
        with self.assertRaises(ValueError):config.option_config("../outside")

    def test_atomic_multifield_patch_and_profiles(self):
        config.initialize_config()
        old=(self.dir/"config.json").read_bytes()
        settings=config.patch_config({
            "ui":{"theme":"ocean","text_style":"title_h2",
                  "option_profile":"battery_saver"},
            "layout":{"touch_target_dp":60},
        })
        self.assertEqual(settings["ui"]["theme"],"ocean")
        self.assertEqual(settings["ui"]["text_style"],"title_h2")
        self.assertEqual(settings["io"]["workers"],1)
        self.assertEqual(settings["runtime"]["clock_callbacks_per_tick"],48)
        self.assertEqual(settings["layout"]["touch_target_dp"],60)
        self.assertNotEqual(old,(self.dir/"config.json").read_bytes())
        single=config.update_config("io","workers",3)
        self.assertEqual(single["io"]["workers"],3)
        self.assertEqual(single["ui"]["theme"],"ocean")
        self.assertEqual(config.load_config(),single)

    def test_atomic_updates_rollback_on_invalid_input(self):
        config.initialize_config()
        before=(self.dir/"config.json").read_bytes()
        for value in (999,-1,False,float("nan")):
            with self.subTest(value=value),self.assertRaises(ValueError):
                config.update_config("io","workers",value)
            self.assertEqual((self.dir/"config.json").read_bytes(),before)
        for change in (
            {"ui":{"option_profile":"not_a_real_profile"}},
            {"ui":{"theme":"no_such_palette"}},
            {"ui":{"text_style":"invalid_style"}},
            {"layout":{"columns":0}},
            {"unknown":{}},
        ):
            with self.subTest(change=change),self.assertRaises(ValueError):
                config.patch_config(change)
            self.assertEqual((self.dir/"config.json").read_bytes(),before)
        self.assertFalse(list(self.dir.glob(".tgk-config-*")))

    def test_symlink_target_rejected_without_touching_source(self):
        config.initialize_config()
        path=self.dir/"config.json"
        before=path.read_bytes()
        outside=self.dir.parent/"outside.json"
        outside.write_bytes(before)
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.update_config("ui","theme","ocean")
        self.assertEqual(outside.read_bytes(),before)
        self.assertEqual(path.read_bytes(),before)

    def test_preset_edits_are_preserved_when_updating_config(self):
        config.initialize_config()
        palette=self.dir/"palettes"/"midnight.json"
        custom=palette.read_text().replace("#","X",1)
        # Do not require a palette file to be valid until selected/loading it.
        palette.write_text(custom)
        config.update_config("ui","text_style","body")
        self.assertEqual(palette.read_text(),custom)
        for f in (self.dir/"text_styles").glob("*.json"):
            self.assertGreater(f.stat().st_size,0)

    def test_config_entrypoint_reports_json(self):
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(config.main(["init"]),0)
        self.assertEqual(json.loads(output.getvalue())["path"],str(self.dir))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(config.main(["validate"]),0)
        self.assertTrue(json.loads(output.getvalue())["valid"])


if __name__=="__main__":unittest.main()
