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

    def test_option_profile_selection_and_explicit_single_field_overrides(self):
        config.initialize_config()
        initial=(self.dir/"config.json").read_bytes()
        effective=config.update_config("ui","option_profile","battery_saver")
        self.assertEqual(effective["io"]["workers"],1)
        self.assertEqual(effective["runtime"]["clock_callbacks_per_tick"],48)
        self.assertEqual(effective["tools"]["canvas_fps"],20)
        # Values specifically changed away from shipped defaults stay pinned,
        # even if a different profile would otherwise supply that field.
        effective=config.update_config("io","workers",7)
        self.assertEqual(effective["io"]["workers"],7)
        self.assertEqual(effective["runtime"]["clock_callbacks_per_tick"],48)
        effective=config.update_config("ui","option_profile","accessibility_touch")
        self.assertEqual(effective["layout"]["touch_target_dp"],64)
        self.assertEqual(effective["io"]["workers"],7)
        previous=(self.dir/"config.json").read_bytes()
        with self.assertRaises(ValueError):
            config.update_config("ui","option_profile","missing_profile")
        self.assertEqual(previous,(self.dir/"config.json").read_bytes())
        with self.assertRaises(ValueError):
            config.update_config("io","workers",999)
        self.assertEqual(previous,(self.dir/"config.json").read_bytes())
        self.assertNotEqual(initial,previous)

    def test_atomic_writer_refuses_symlink_and_preserves_source(self):
        config.initialize_config()
        target=self.dir/"config.json"
        original=target.read_bytes()
        outside=self.dir.parent/"shared_config.json"
        outside.write_bytes(original)
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.update_config("ui","theme","paper")
        self.assertEqual(outside.read_bytes(),original)

    def test_direct_backend_reads_configured_layout_and_scheduler(self):
        from tgk.widgets import TermuxBackend
        config.initialize_config()
        config.update_config("layout","touch_target_dp",60)
        config.update_config("runtime","clock_callbacks_per_tick",37)
        config.update_config("runtime","idle_sleep_seconds",.03)
        backend=TermuxBackend(tg=object())
        self.assertEqual(backend.layout_scale.touch_target_dp,60)
        self.assertEqual(backend.clock_callbacks_per_tick,37)
        self.assertAlmostEqual(backend.idle_sleep_seconds,.03)

    def test_svg_icon_export_uses_saved_default_dimensions(self):
        from tgk.icon_builder import build_assets
        config.initialize_config()
        config.update_config("icons","low",24)
        config.update_config("icons","mid",64)
        config.update_config("icons","high",128)
        config.update_config("icons","max_icons",3)
        result=build_assets(self.tmp.name,names=("file","folder"),raster=False)
        self.assertEqual(result["count"],2)
        manifest=json.loads((Path(self.tmp.name)/"icons"/"manifest.json").read_text())
        self.assertEqual(manifest["sizes"],{"low":24,"mid":64,"high":128})
        self.assertTrue((Path(self.tmp.name)/"icons"/"svg"/"file.svg").exists())
        with self.assertRaises(ValueError):
            build_assets(self.tmp.name,names=("file","folder","play","close"),
                         raster=False,overwrite=True)

    def test_config_entrypoint_reports_json(self):
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(config.main(["init"]),0)
        self.assertEqual(json.loads(output.getvalue())["path"],str(self.dir))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(config.main(["validate"]),0)
        self.assertTrue(json.loads(output.getvalue())["valid"])


if __name__=="__main__":unittest.main()
