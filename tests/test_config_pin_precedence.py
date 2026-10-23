"""Explicit config pins survive profile changes; old JSON remains valid."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tgk import config

class PinnedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"tgk"
        self.env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        self.env.start();self.addCleanup(self.env.stop)
        config.clear_config_cache();self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def test_factory_default_pinned_overrides_profile(self):
        config.update_config("ui","option_profile","battery_saver")
        self.assertEqual(config.load_config()["io"]["workers"],1)
        config.update_config("io","workers",2)
        self.assertEqual(config.load_config()["io"]["workers"],2)
        self.assertIn("io.workers",config.load_config()["pinned"])
        config.update_config("io","workers",None,reset=True)
        self.assertEqual(config.load_config()["io"]["workers"],1)
        self.assertNotIn("io.workers",config.load_config()["pinned"])

    def test_profile_switch_does_not_erase_pin(self):
        config.patch_config({"io":{"workers":7},"ui":{"option_profile":"battery_saver"}})
        self.assertEqual(config.load_config()["io"]["workers"],7)
        config.update_config("ui","option_profile","performance")
        self.assertEqual(config.load_config()["io"]["workers"],7)
        config.patch_config({},reset=(("io","workers"),))
        self.assertEqual(config.load_config()["io"]["workers"],4)

    def test_batch_atomic_failure_and_bad_pin_metadata(self):
        file=self.root/"config.json"
        before=file.read_bytes()
        with self.assertRaises(ValueError):
            config.patch_config({"io":{"workers":7},"layout":{"columns":0}})
        self.assertEqual(file.read_bytes(),before)
        with self.assertRaises(ValueError):
            config.validate_config({"pinned":["__hidden.value"]})
        with self.assertRaises(ValueError):
            config.validate_config({"pinned":["io.workers","io.workers"]})

    def test_legacy_full_file_without_pin_field(self):
        file=self.root/"config.json"
        previous=json.loads(file.read_text())
        previous.pop("pinned",None)
        previous["io"]["workers"]=3
        previous["ui"]["option_profile"]="battery_saver"
        file.write_text(json.dumps(previous))
        config.clear_config_cache()
        self.assertEqual(config.load_config()["io"]["workers"],3)
        self.assertEqual(config.load_config()["pinned"],[])

    def test_cli_reset_after_explicit_value(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            self.assertEqual(config.main(["set","ui","option_profile",'"battery_saver"']),0)
            self.assertEqual(config.main(["set","io","workers","2"]),0)
            self.assertEqual(config.main(["reset","io","workers"]),0)
        self.assertEqual(config.load_config()["io"]["workers"],1)

if __name__=="__main__":unittest.main()
