"""Read-only integrity checks for the entire installed TGK preset tree."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config
from tgk.theme import load_theme


class PresetAuditTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"settings"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        env.start();self.addCleanup(env.stop)
        config.clear_config_cache();self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def test_all_initialized_presets_valid(self):
        audit=config.audit_presets(require_builtins=True)
        self.assertTrue(audit["valid"])
        self.assertGreater(audit["counts"]["text_styles"],35)
        self.assertGreater(audit["counts"]["palettes"],8)
        self.assertGreater(audit["counts"]["options"],3)
        self.assertFalse(any(audit["missing_builtins"].values()))
        self.assertEqual(audit["total"],sum(audit["counts"].values()))

    def test_inactive_corrupted_palette_is_caught(self):
        path=self.root/"palettes"/"ocean.json"
        path.write_text('{"theme":"ocean","colors":{"accent":"not a color"}}')
        # Current config points to midnight, so normal load still works.
        self.assertEqual(config.load_config()["ui"]["theme"],"midnight")
        with self.assertRaises(ValueError):
            config.audit_presets()

    def test_inactive_broken_font_and_option_detected(self):
        path=self.root/"text_styles"/"comment.json"
        path.write_text('{"style":"body","properties":{"size":5000}}')
        with self.assertRaisesRegex(ValueError,"text size"):
            config.audit_presets()
        config.initialize_config() # create-only must not erase broken user file
        self.assertIn("5000",path.read_text())
        path.unlink()
        config.initialize_config()
        option=self.root/"options"/"battery_saver.json"
        option.write_text('{"name":"battery_saver","settings":{"io":{"workers":999}}}')
        with self.assertRaisesRegex(ValueError,"workers"):
            config.audit_presets()

    def test_symlink_and_size_caps_without_external_reads(self):
        base=self.root/"palettes"/"forest.json"
        base.unlink()
        outside=self.root/"outside.json"
        outside.write_text("private")
        base.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.audit_presets()
        base.unlink()
        config.initialize_config()
        # Refuse oversize input without reading full JSON into RAM.
        base.write_bytes(b" "* (config.MAX_JSON_BYTES+1))
        with self.assertRaisesRegex(ValueError,"size limit"):
            config.audit_presets()
        with self.assertRaisesRegex(ValueError,"size limit"):
            load_theme(base)

    def test_file_count_bound_and_missing_builtins(self):
        with self.assertRaisesRegex(ValueError,"too many"):
            config.audit_presets(max_files=1)
        (self.root/"palettes"/"forest.json").unlink()
        result=config.audit_presets(require_builtins=False)
        self.assertIn("forest",result["missing_builtins"]["palettes"])
        with self.assertRaisesRegex(ValueError,"missing built-in"):
            config.audit_presets(require_builtins=True)

    def test_readonly_audit_does_not_change_files(self):
        before={str(p.relative_to(self.root)):p.read_bytes()
                for p in self.root.rglob("*.json")}
        config.audit_presets(require_builtins=True)
        after={str(p.relative_to(self.root)):p.read_bytes()
               for p in self.root.rglob("*.json")}
        self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
