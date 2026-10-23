"""Persistent typography and safe create-only preset installation."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk.config import initialize_config,update_config,load_config,clear_config_cache
from tgk.typography import get_text_style,set_text_style,_active
from tgk.widgets import App


class DefaultPrecedenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)/"settings"
        env=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.folder)})
        env.start();self.addCleanup(env.stop)
        saved=_active.set(None)
        self.addCleanup(lambda:_active.reset(saved))
        clear_config_cache();self.addCleanup(clear_config_cache)
        initialize_config()

    def test_no_arg_set_text_style_keeps_saved_custom_preset(self):
        update_config("ui","text_style","terminal")
        self.assertEqual(get_text_style().family,"mono")
        self.assertEqual(get_text_style().size,14)
        current=set_text_style()
        self.assertEqual(current.family,"mono")
        self.assertEqual(current.size,14)
        self.assertEqual(set_text_style(size=19).size,19)
        self.assertEqual(set_text_style().size,19)

    def test_app_no_arg_setter_never_discards_instance_style(self):
        update_config("ui","text_style","caption")
        app=App()
        self.assertEqual(app.text_style.size,12)
        self.assertEqual(app.set_text_style(size=20).size,20)
        self.assertEqual(app.set_text_style().size,20)
        explicit=App(text_style="terminal")
        self.assertEqual(explicit.set_text_style().family,"mono")

    def test_install_preserves_user_palette_and_text_changes(self):
        custom=self.folder/"palettes"/"ocean.json"
        settings=json.loads(custom.read_text())
        settings["colors"]["accent"]="#ABCDEF"
        custom.write_text(json.dumps(settings))
        textfile=self.folder/"text_styles"/"body.json"
        old=textfile.read_bytes()
        second=initialize_config()
        self.assertFalse(second["created"])
        self.assertEqual(custom.read_text().find("#ABCDEF")>=0,True)
        self.assertEqual(textfile.read_bytes(),old)

    def test_existing_preset_symlink_refused(self):
        target=self.folder/"palettes"/"ocean.json"
        target.unlink()
        secret=self.folder/"outside.json"
        secret.write_text('{"example":true}')
        target.symlink_to(secret)
        with self.assertRaisesRegex(ValueError,"not a regular file"):
            initialize_config()
        self.assertEqual(secret.read_text(),'{"example":true}')

    def test_omitted_explicit_args_inherit_saved_defaults(self):
        update_config("ui","theme","forest")
        update_config("ui","text_style","code")
        app=App()
        self.assertEqual(app.theme.name,"forest")
        self.assertEqual(app.text_style.family,"mono")
        self.assertEqual(app.text_style.size,14)
        self.assertEqual(App(theme="paper",text_style="title").theme.name,"paper")
        self.assertEqual(App(theme="paper",text_style="title").text_style.size,26)


if __name__=="__main__":
    unittest.main()
