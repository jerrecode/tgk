"""Selected TGK presets and config reads must not bypass audit path safety."""
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config
from tgk.theme import get_theme,load_theme


class SafeConfigReadsTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)/"tgk"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        config.clear_config_cache()
        self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def test_selected_palette_symlink_rejected_without_external_read(self):
        target=self.home/"palettes"/"ocean.json"
        outside=Path(self.temp.name)/"private.json"
        outside.write_text('{"theme":"ocean","colors":{"accent":"#778899"}}')
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,"symlink"):
            load_theme(target)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config._read_json(target)
        config.update_config("ui","theme","paper")
        # Changing an unrelated selected theme must not read ocean's link.
        self.assertEqual(config.configured_theme().name,"paper")

    def test_config_file_symlink_rejected_even_when_valid_json(self):
        config_file=self.home/"config.json"
        outside=Path(self.temp.name)/"config-copy.json"
        outside.write_bytes(config_file.read_bytes())
        config_file.unlink()
        config_file.symlink_to(outside)
        config.clear_config_cache()
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.load_config()
        self.assertEqual(outside.read_bytes(),outside.read_bytes())

    def test_selected_option_and_font_symlinks_rejected(self):
        for folder,name,reader in [
            ("options","battery_saver",lambda:config.option_config("battery_saver")),
            ("text_styles","body",config.configured_text_style),
        ]:
            with self.subTest(folder=folder):
                target=self.home/folder/(name+".json")
                outside=Path(self.temp.name)/(folder+".json")
                outside.write_bytes(target.read_bytes())
                target.unlink();target.symlink_to(outside)
                with self.assertRaisesRegex(ValueError,"symlink"):
                    reader()
                target.unlink()
                config.initialize_config()

    def test_symlinked_preset_parent_directory_rejected(self):
        presets=self.home/"palettes"
        outside=Path(self.temp.name)/"presets-copy"
        presets.rename(outside)
        presets.symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.configured_theme()

    def test_nonregular_files_are_rejected_without_blocking(self):
        pipe=self.home/"options"/"pipe.json"
        os.mkfifo(pipe)
        with self.assertRaisesRegex(ValueError,"regular"):
            config._read_json(pipe)
        if Path("/dev/null").exists():
            with self.assertRaisesRegex(ValueError,"regular"):
                config._read_json("/dev/null")

    def test_hardlinked_preset_rejected_without_modification(self):
        origin=self.home/"palettes"/"forest.json"
        alias=self.home/"palettes"/"forest_copy.json"
        os.link(origin,alias)
        old=origin.read_bytes()
        with self.assertRaisesRegex(ValueError,"regular nonlinked"):
            config._read_json(origin)
        self.assertEqual(origin.read_bytes(),old)

    def test_normal_files_and_size_cap_still_work(self):
        self.assertEqual(config._read_json(self.home/"config.json")["schema_version"],1)
        source=self.home/"text_styles"/"body.json"
        self.assertIn("properties",config._read_json(source))
        source.write_bytes(b" "*(config.MAX_JSON_BYTES+1))
        with self.assertRaisesRegex(ValueError,"size limit"):
            config._read_json(source)
        self.assertEqual(source.stat().st_size,config.MAX_JSON_BYTES+1)


if __name__=="__main__":
    unittest.main()
