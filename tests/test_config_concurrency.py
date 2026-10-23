"""Concurrent Termux processes must not lose configuration writes.

The test runs real Python subprocesses using a shared TGK_CONFIG_HOME and
verifies that one process cannot race another between read/merge/replace.
"""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tgk import config


class ConfigLockTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"tgk"
        context=patch.dict(os.environ,{"TGK_CONFIG_HOME":str(self.root)})
        context.start()
        self.addCleanup(context.stop)
        config.clear_config_cache()
        self.addCleanup(config.clear_config_cache)
        config.initialize_config()

    def run_python(self,script,timeout=15):
        return subprocess.run([sys.executable,"-c",script],env=os.environ.copy(),
                              text=True,capture_output=True,timeout=timeout)

    def test_simultaneous_process_writes_preserve_both_keys(self):
        source="""
from tgk import config
import sys
section,key,value=sys.argv[1:]
for _ in range(5):
    config.update_config(section,key,int(value))
"""
        cmds=[
            [sys.executable,"-c",source,"io","workers","3"],
            [sys.executable,"-c",source,"layout","touch_target_dp","60"],
            [sys.executable,"-c",source,"runtime","clock_callbacks_per_tick","72"],
        ]
        processes=[subprocess.Popen(c,env=os.environ.copy(),
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for c in cmds]
        for proc in processes:
            out,err=proc.communicate(timeout=15)
            self.assertEqual(proc.returncode,0,err)
        result=config.load_config()
        self.assertEqual(result["io"]["workers"],3)
        self.assertEqual(result["layout"]["touch_target_dp"],60)
        self.assertEqual(result["runtime"]["clock_callbacks_per_tick"],72)
        self.assertEqual(set(json.loads(config.config_path().read_text())["pinned"]) &
                         {"io.workers","layout.touch_target_dp",
                          "runtime.clock_callbacks_per_tick"},
                         {"io.workers","layout.touch_target_dp",
                          "runtime.clock_callbacks_per_tick"})
        self.assertFalse(list(self.root.glob(".tgk-config-*")))

    def test_bounded_lock_timeout_preserves_existing_config(self):
        lock=self.root/".config.lock"
        fd=os.open(lock,os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            before=config.config_path().read_bytes()
            child=self.run_python("""
from tgk import config
config.patch_config({"ui":{"theme":"forest"}},lock_timeout=0.04)
""")
            self.assertNotEqual(child.returncode,0)
            self.assertIn("TimeoutError",child.stderr)
            self.assertIn("config write lock",child.stderr)
            self.assertEqual(config.config_path().read_bytes(),before)
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)
        self.assertEqual(config.update_config("ui","theme","forest")["ui"]["theme"],"forest")

    def test_lock_symlinks_and_nonfinite_timeouts_are_rejected(self):
        path=self.root/".config.lock"
        path.symlink_to(self.root/"config.json")
        with self.assertRaisesRegex(ValueError,"symlink"):
            config.update_config("ui","theme","forest")
        path.unlink()
        for invalid in (0,-1,float("inf"),float("nan"),False,61):
            with self.subTest(timeout=invalid),self.assertRaises(ValueError):
                config.patch_config({"ui":{"theme":"paper"}},lock_timeout=invalid)
        self.assertEqual(config.load_config()["ui"]["theme"],"midnight")

    def test_cross_process_lock_recovers_when_owner_exits(self):
        child=self.run_python("""
from tgk import config
print(config.update_config("layout","touch_target_dp",56)["layout"]["touch_target_dp"])
""")
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(child.stdout.strip(),"56")
        self.assertEqual(config.load_config()["layout"]["touch_target_dp"],56)
        self.assertEqual((self.root/".config.lock").stat().st_mode & 0o777,0o600)


if __name__=="__main__":
    unittest.main()
