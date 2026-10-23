"""Installer populates icon catalog without clobbering user-defined assets."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest

from tgk.config import DEFAULT_CONFIG
from tgk.icon_builder import recipe_names
from tgk.install_assets import initialize_icon_assets,main


class InstallAssetTests(unittest.TestCase):
    def setUp(self):
        self.temporary=TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.settings=json.loads(json.dumps(DEFAULT_CONFIG))
        self.settings["icons"]["raster"]=False

    def test_svg_catalog_and_empty_raster_output(self):
        result=initialize_icon_assets(self.root,settings=self.settings)
        self.assertEqual(result["status"],"created")
        self.assertGreater(result["count"],250)
        self.assertEqual(result["count"],len(recipe_names()))
        self.assertEqual(result["png_files"],0)
        folder=self.root/"icons"
        manifest=json.loads((folder/"manifest.json").read_text())
        self.assertEqual(len(manifest["icons"]),result["count"])
        self.assertEqual(len(list((folder/"svg").glob("*.svg"))),result["count"])
        for name in ("ico","low_res","mid_res","high_res"):
            self.assertEqual(list((folder/name).iterdir()),[])

    def test_preserve_existing_user_assets_byte_for_byte(self):
        folder=self.root/"icons"
        folder.mkdir()
        marker=folder/"user_icon.svg"
        marker.write_bytes(b'<svg id="custom"/>')
        result=initialize_icon_assets(self.root,settings=self.settings)
        self.assertEqual(result["status"],"preserved")
        self.assertFalse(result["created"])
        self.assertEqual(marker.read_bytes(),b'<svg id="custom"/>')
        self.assertEqual(sorted(x.name for x in folder.iterdir()),["user_icon.svg"])

    def test_symlinks_or_nondirectory_output_refused(self):
        dest=self.root/"icons"
        outside=self.root/"outside"
        outside.mkdir()
        dest.symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,"symlink"):
            initialize_icon_assets(self.root,settings=self.settings)
        dest.unlink()
        dest.write_text("user data")
        with self.assertRaisesRegex(ValueError,"not a directory"):
            initialize_icon_assets(self.root,settings=self.settings)

    def test_failed_raster_backend_does_not_publish_partial_icons(self):
        with patch("tgk.icon_builder._raster_backend",
                   side_effect=RuntimeError("missing optional raster deps")):
            with self.assertRaisesRegex(RuntimeError,"optional"):
                initialize_icon_assets(self.root,settings=self.settings,raster=True)
        self.assertFalse((self.root/"icons").exists())
        self.assertFalse(list(self.root.glob(".tgk-icons-stage-*")))

    def test_install_script_initializes_profiles_before_assets(self):
        script=(Path(__file__).resolve().parents[1]/"install.sh").read_text()
        sequence=['"$PYTHON" -m tgk.config init',
                  '"$PYTHON" -m tgk.config validate',
                  '"$PYTHON" -m tgk.config audit',
                  '"$PYTHON" -m tgk.install_assets']
        positions=[script.index(x) for x in sequence]
        self.assertEqual(positions,sorted(positions))
        self.assertIn("icon catalog atomically",script)

    def test_dry_run_has_no_side_effects(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with patch("tgk.install_assets.config_home",return_value=self.root):
            output=StringIO()
            with redirect_stdout(output):
                code=main(["--dry-run"])
        result=json.loads(output.getvalue())
        self.assertEqual(code,0)
        self.assertEqual(result["status"],"dry_run")
        self.assertFalse((self.root/"icons").exists())


if __name__=="__main__":
    unittest.main()
