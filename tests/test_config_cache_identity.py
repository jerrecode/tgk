"""Persisted defaults reload after atomic replacement, even with copied mtimes."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config


class CacheIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary=TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/"tgk"
        self.environment=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        config.clear_config_cache()
        self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def test_atomic_replace_same_size_same_mtime_observes_new_theme(self):
        path=config.config_path()
        data=json.loads(path.read_text())
        data["ui"]["theme"]="forest"
        path.write_text(json.dumps(data,sort_keys=True))
        config.clear_config_cache()
        self.assertEqual(config.load_config()["ui"]["theme"],"forest")
        original=path.stat()

        data["ui"]["theme"]="sunset"
        new_payload=json.dumps(data,sort_keys=True).encode()
        self.assertEqual(len(new_payload),original.st_size)
        temporary=path.with_name("config.next")
        temporary.write_bytes(new_payload)
        os.utime(temporary,ns=(original.st_atime_ns,original.st_mtime_ns))
        os.replace(temporary,path)
        replaced=path.stat()
        self.assertEqual(original.st_size,replaced.st_size)
        self.assertEqual(original.st_mtime_ns,replaced.st_mtime_ns)
        self.assertNotEqual(original.st_ino,replaced.st_ino)

        self.assertEqual(config.load_config()["ui"]["theme"],"sunset")
        self.assertEqual(config.configured_theme().name,"sunset")

    def test_unchanged_file_uses_cached_validation(self):
        config.load_config()
        before=config._load_cached.cache_info().hits
        config.load_config()
        self.assertGreater(config._load_cached.cache_info().hits,before)


if __name__=="__main__":
    unittest.main()
