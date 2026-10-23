"""Persistent TGK settings: bootstrapping, migrations, layering and validation."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tgk import config
from tgk.adaptive import LayoutScale
from tgk.theme import get_theme,resolve_theme,_active_theme
from tgk.typography import get_text_style,resolve_text_style,_active
from tgk.io_pipeline import Limits
from tgk.widgets import App,TermuxBackend
from tgk.icon_builder import build_assets


class PersistentConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"tgk"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        tok_theme=_active_theme.set(None)
        tok_text=_active.set(None)
        self.addCleanup(lambda:_active_theme.reset(tok_theme))
        self.addCleanup(lambda:_active.reset(tok_text))
        config.clear_cache()
        self.addCleanup(config.clear_cache)

    def _edit(self,path,callback):
        content=json.loads(path.read_text("utf-8"))
        callback(content)
        path.write_text(json.dumps(content),encoding="utf-8")
        config.clear_cache()

    def test_bootstrap_creates_four_files_and_preserves_changes(self):
        first=config.init_config()
        self.assertTrue(all(first["created"].values()))
        self.assertEqual(len(config.color_registry()),12)
        self.assertGreaterEqual(len(config.text_registry()),40)
        self.assertGreaterEqual(len(config.option_registry()),4)
        files=config.paths()
        for key in ("config","colors","typography","options"):
            self.assertTrue(files[key].is_file())
        self._edit(files["config"],lambda data:data["defaults"].update(palette="paper"))
        second=config.init_config()
        self.assertFalse(any(second["created"].values()))
        self.assertEqual(config.settings()["defaults"]["palette"],"paper")
        self.assertEqual(config.validate_installation()["default_palette"],"paper")

    def test_import_without_install_uses_built_in_defaults_and_creates_nothing(self):
        self.assertEqual(get_theme().name,"midnight")
        self.assertEqual(get_text_style(),resolve_text_style("body"))
        self.assertEqual(config.layout_scale(),LayoutScale())
        self.assertFalse(self.path.exists())

    def test_custom_default_palette_typography_options_and_explicit_app_override(self):
        config.init_config()
        files=config.paths()
        self._edit(files["colors"],lambda data:data["palettes"].update(
            custom={"status_bar":"#111111","primary":"#222222",
                    **{k:v for k,v in config.default_colors()["ocean"].items()
                       if k not in ("status_bar","primary")},
                    "accent":"#ABCDEF"}))
        self._edit(files["typography"],lambda data:data["presets"].update(
            customtext={"family":"mono","size":21,"weight":700,"role":"text"}))
        self._edit(files["config"],lambda data:data["defaults"].update(
            palette="custom",typography="customtext",options="accessible"))
        self.assertEqual(get_theme().name,"custom")
        self.assertEqual(get_theme()["accent"],"#ABCDEFFF")
        self.assertEqual(get_text_style().size,21)
        app=App()
        self.assertEqual(app.theme.name,"custom")
        self.assertEqual(app.text_style.size,21)
        self.assertEqual(app.layout_scale.touch_target_dp,56)
        explicit=App(theme="paper",text_style="caption",
                     layout_scale=LayoutScale(touch_target_dp=52),
                     orientation_mode="landscape")
        self.assertEqual(explicit.theme.name,"paper")
        self.assertEqual(explicit.text_style.size,12)
        self.assertEqual(explicit.layout_scale.touch_target_dp,52)
        self.assertEqual(explicit.orientation_mode,"landscape")

    def test_runtime_and_io_limits_follow_config_with_independent_overrides(self):
        config.init_config()
        self._edit(config.paths()["config"],lambda data:(
            data["runtime"].update(clock_max_callbacks=42,idle_sleep_ms=3),
            data["io"].update(chunk_bytes=2048,workers=1,pending=2),
            data["ui"].update(window_mode="dialog",orientation="portrait",
                              layout_overrides={"touch_target_dp":60})))
        runtime=config.runtime_settings()
        self.assertEqual(runtime["clock_max_callbacks"],42)
        self.assertEqual(runtime["idle_sleep_ms"],3)
        backend=TermuxBackend(tg=object())
        self.assertEqual(backend._runtime_config["clock_max_callbacks"],42)
        self.assertEqual(backend.layout_scale.touch_target_dp,60)
        self.assertEqual(Limits.from_config().chunk_bytes,2048)
        self.assertEqual(Limits().chunk_bytes,65536)
        app=App()
        self.assertEqual(app.window_mode,"dialog")
        self.assertEqual(app.orientation_mode,"portrait")
        self.assertEqual(app.layout_scale.touch_target_dp,60)

    def test_configured_icon_export_sizes_and_empty_raster_dirs(self):
        config.init_config()
        self._edit(config.paths()["config"],lambda data:data["icons"].update(
            low_res=24,mid_res=64,high_res=128))
        # Neither CairoSVG nor Pillow is required for SVG-only mode.
        with tempfile.TemporaryDirectory() as output:
            result=build_assets(output,names=["file_ext_json","filename_readme_md"],
                                raster=False)
            self.assertEqual(result["count"],2)
            manifest=json.loads((Path(output)/"icons"/"manifest.json").read_text())
            self.assertEqual(manifest["sizes"],{"low":24,"mid":64,"high":128})
            self.assertTrue((Path(output)/"icons"/"svg"/"file_ext_json.svg").exists())
            for name in ("low_res","mid_res","high_res","ico"):
                self.assertEqual(list((Path(output)/"icons"/name).iterdir()),[])

    def test_atomic_default_choices_preserve_preset_files_and_other_sections(self):
        config.init_config()
        files=config.paths()
        initial_colors=files["colors"].read_bytes()
        initial_typo=files["typography"].read_bytes()
        config.set_defaults(palette="ocean",typography="terminal",
                            options="accessible",orientation="landscape")
        cfg=config.settings()
        self.assertEqual(cfg["defaults"]["palette"],"ocean")
        self.assertEqual(cfg["defaults"]["typography"],"terminal")
        self.assertEqual(cfg["defaults"]["options"],"accessible")
        self.assertEqual(cfg["ui"]["orientation"],"landscape")
        self.assertEqual(config.layout_scale().touch_target_dp,56)
        self.assertEqual(get_theme().name,"ocean")
        self.assertEqual(get_text_style().family,"mono")
        self.assertEqual(files["colors"].read_bytes(),initial_colors)
        self.assertEqual(files["typography"].read_bytes(),initial_typo)
        with self.assertRaises(ValueError):config.set_defaults(palette="invalid")
        self.assertEqual(config.settings()["defaults"]["palette"],"ocean")
        with self.assertRaises(ValueError):config.set_defaults()

    def test_option_preset_runtime_is_not_overwritten_by_builtin_config(self):
        config.init_config()
        config.set_defaults(options="performance")
        self.assertEqual(config.runtime_settings()["clock_max_callbacks"],64)
        self.assertEqual(config.runtime_settings()["idle_sleep_ms"],8)
        self._edit(config.paths()["config"],lambda d:d["runtime"].update(
            clock_max_callbacks=35))
        self.assertEqual(config.runtime_settings()["clock_max_callbacks"],35)
        self.assertEqual(config.runtime_settings()["idle_sleep_ms"],8)

    def test_invalid_config_rejected_not_silently_ignored(self):
        config.init_config()
        invalid=[
            lambda d:d["runtime"].update(clock_max_callbacks=0),
            lambda d:d["io"].update(workers=100000),
            lambda d:d["ui"].update(orientation="diagonal"),
            lambda d:d["defaults"].update(palette="does_not_exist"),
            lambda d:d["render"].update(max_canvas_pixels=0),
        ]
        for mutation in invalid:
            with self.subTest(mutation=mutation):
                original=config.default_config()
                mutation(original)
                config.paths()["config"].write_text(json.dumps(original),encoding="utf-8")
                config.clear_cache()
                with self.assertRaises(ValueError):config.validate_installation()

    def test_invalid_preset_json_and_unknown_role_rejected(self):
        config.init_config()
        files=config.paths()
        files["colors"].write_text('{"schema_version":1,"palettes":{"x":{"unknown":"#fff"}}}',encoding="utf-8")
        config.clear_cache()
        with self.assertRaises(ValueError):config.color_registry()
        files["colors"].write_text("{ not valid",encoding="utf-8")
        config.clear_cache()
        with self.assertRaises(ValueError):config.color_registry()

    def test_json_size_and_symlink_safety(self):
        config.init_config()
        config.paths()["options"].write_bytes(b" "*(config.FILE_LIMIT+1))
        config.clear_cache()
        with self.assertRaises(ValueError):config.option_registry()
        with tempfile.TemporaryDirectory() as outside:
            target=Path(outside)/"danger"
            target.write_text("do not edit")
            config.paths()["options"].unlink()
            config.paths()["options"].symlink_to(target)
            with self.assertRaises(ValueError):config.init_config()
            self.assertEqual(target.read_text(),"do not edit")

    def test_cli_validation_is_read_only(self):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(config.main(["show","--json"]),0)
        self.assertIn('"default_palette": "midnight"',stream.getvalue())
        self.assertFalse(self.path.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(config.main(["init","--json"]),0)
            self.assertEqual(config.main(["validate","--json"]),0)
        self.assertTrue(self.path.exists())


if __name__=="__main__":
    unittest.main()
