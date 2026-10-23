"""Recovered branch guarantees: invalid effective settings never publish."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tgk import config


class RecoveredTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        override=patch.dict(os.environ, {"TGK_CONFIG_HOME":str(self.root)})
        override.start();self.addCleanup(override.stop)
        config.clear_config_cache();self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def test_invalid_custom_typography_preserves_previous_configuration(self):
        previous=config.config_path().read_bytes()
        for document in (
            {"style":"body","properties":{"unknown_size":-5}},
            {"style":"body","properties":{"size":-5}},
            {"style":"body","properties":{"size":"large"}},
            {"style":"missing_base","properties":{}},
        ):
            with self.subTest(document=document):
                (self.root/"text_styles/custom.json").write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    config.patch_config({"ui":{"text_style":"custom"}})
                self.assertEqual(config.config_path().read_bytes(),previous)
                self.assertEqual(config.configured_text_style().size,16)

    def test_profile_and_pinned_values_validate_together_before_write(self):
        (self.root/"options/custom.json").write_text(json.dumps({
            "name":"custom","settings":{"layout":{
                "compact_breakpoint_dp":700,"expanded_breakpoint_dp":900}}}))
        previous=config.config_path().read_bytes()
        with self.assertRaises(ValueError):
            config.patch_config({"ui":{"option_profile":"custom"},
                                 "layout":{"expanded_breakpoint_dp":650}})
        self.assertEqual(config.config_path().read_bytes(),previous)
        self.assertEqual(config.load_config()["layout"]["compact_breakpoint_dp"],600)

    def test_valid_recovered_custom_settings_are_usable_after_restart(self):
        (self.root/"text_styles/custom.json").write_text(json.dumps({
            "style":"body","properties":{"size":21}}))
        config.patch_config({"ui":{"text_style":"custom","option_profile":"performance"},
                             "io":{"workers":2}})
        config.clear_config_cache()
        self.assertEqual(config.configured_text_style().size,21)
        self.assertEqual(config.load_config()["io"]["workers"],2)

    def test_malformed_active_style_uses_the_same_validation_contract(self):
        (self.root/"text_styles/body.json").write_text(json.dumps({
            "style":"body","properties":{"unknown_size":42}}))
        with self.assertRaises(ValueError):
            config.configured_text_style()
        with self.assertRaises(ValueError):
            config.audit_presets()

    def test_audit_stops_before_materializing_excessive_preset_names(self):
        observed=[]
        def paths():
            for name in ("a.json","b.json","c.json"):
                observed.append(name)
                if len(observed)>2:raise AssertionError("audit consumed past its cap")
                yield self.root/"palettes"/name
        with patch.object(Path,"iterdir",return_value=paths()):
            with self.assertRaisesRegex(ValueError,"too many"):
                config.audit_presets(max_files=1)
        self.assertEqual(observed,["a.json","b.json"])

    def test_malformed_palette_and_option_files_raise_validation_errors(self):
        from tgk.theme import load_theme
        palette=self.root/"palettes/custom.json"
        for document in ({"theme":[]},{"theme":42},{"colors":[]},
                         {"colors":None},{"colors":0}):
            with self.subTest(document=document):
                palette.write_text(json.dumps(document))
                with self.assertRaises(ValueError):load_theme(palette)
        palette.unlink()
        (self.root/"options/custom.json").write_text('{"name":"custom"}')
        with self.assertRaises(ValueError):config.option_config("custom")
        with self.assertRaises(ValueError):config.audit_presets()


if __name__=="__main__":unittest.main()
