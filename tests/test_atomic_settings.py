"""Persisted configuration safety, profile selection and CLI precedence."""
from contextlib import redirect_stderr,redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config
from tgk.widgets import TermuxBackend


class AtomicSettingsTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"settings"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        config.clear_config_cache()
        self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def test_preset_files_populated_without_overwriting_user_files(self):
        initial=config.initialize_config()
        self.assertEqual(initial["created"],[])
        self.assertGreater(initial["total"],30)
        file=self.root/"palettes"/"ocean.json"
        edited={"theme":"ocean","colors":{"background":"#112233"}}
        file.write_text(json.dumps(edited),encoding="utf-8")
        config.initialize_config()
        self.assertEqual(json.loads(file.read_text()),edited)

    def test_atomic_update_selects_default_and_inherits_option_profile(self):
        result=config.update_config("ui","option_profile","battery_saver")
        self.assertEqual(result["runtime"]["clock_callbacks_per_tick"],48)
        self.assertEqual(result["io"]["workers"],1)
        self.assertEqual(result["tools"]["canvas_fps"],20)
        result=config.update_config("layout","touch_target_dp",60)
        self.assertEqual(result["layout"]["touch_target_dp"],60)
        self.assertEqual(result["io"]["workers"],1)
        result=config.update_config("ui","theme","ocean")
        self.assertEqual(result["ui"]["theme"],"ocean")
        self.assertEqual(config.configured_theme().name,"ocean")

    def test_backend_inherits_defaults_unless_overridden(self):
        config.update_config("layout","touch_target_dp",64)
        config.update_config("runtime","clock_callbacks_per_tick",47)
        config.update_config("runtime","idle_sleep_seconds",.03)
        backend=TermuxBackend(tg=object())
        self.assertEqual(backend.layout_scale.touch_target_dp,64)
        self.assertEqual(backend.clock_callbacks_per_tick,47)
        self.assertAlmostEqual(backend.idle_sleep_seconds,.03)
        from tgk.adaptive import LayoutScale
        explicit=TermuxBackend(tg=object(),layout_scale=LayoutScale(touch_target_dp=52))
        self.assertEqual(explicit.layout_scale.touch_target_dp,52)

    def test_invalid_updates_preserve_previous_bytes(self):
        path=config.config_path()
        snapshot=path.read_bytes()
        examples=[("ui","option_profile","bogus"),
                  ("ui","theme","nonexistent"),
                  ("runtime","clock_callbacks_per_tick",0),
                  ("layout","touch_target_dp",False),
                  ("io","workers",100),
                  ("unknown","field",1),
                  ("ui","missing","x")]
        for section,key,value in examples:
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):
                config.update_config(section,key,value)
            self.assertEqual(path.read_bytes(),snapshot)
        self.assertFalse(list(self.root.glob(".tgk-config-*")))

    def test_rejects_symlink_target_without_mutating_original(self):
        original=config.config_path()
        payload=original.read_bytes()
        dest=self.root/"external.json"
        dest.write_bytes(payload)
        original.unlink()
        original.symlink_to(dest)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.update_config("ui","theme","paper")
        self.assertEqual(dest.read_bytes(),payload)

    def test_json_cli_get_set_and_error_reporting(self):
        out=StringIO()
        with redirect_stdout(out):
            rc=config.main(["set","ui","text_style",json.dumps("title_h2")])
        self.assertEqual(rc,0)
        self.assertEqual(json.loads(out.getvalue())["ui"]["text_style"],"title_h2")
        out=StringIO()
        with redirect_stdout(out):
            config.main(["get","ui","text_style"])
        self.assertEqual(json.loads(out.getvalue())["value"],"title_h2")
        out=StringIO()
        with redirect_stdout(out):
            config.main(["profiles"])
        self.assertIn("accessibility_touch",json.loads(out.getvalue())["available"])
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit) as ctx:
            config.main(["set","io","workers","1000"])
        self.assertEqual(ctx.exception.code,2)


if __name__=="__main__":
    unittest.main()
