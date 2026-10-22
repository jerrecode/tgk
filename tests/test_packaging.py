"""Build real distributions: native wheels must not advertise platform 'any'."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def copy_source(self, base):
        source = base/'source'
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(
            '.git', '__pycache__', '*.so', '*.egg-info', 'build', 'dist'))
        return source

    def test_wheel_builds_native_library_and_is_platform_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = self.copy_source(base)
            env = os.environ.copy()
            env['PIP_NO_INDEX'] = '1'
            done = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
                '--no-build-isolation', '--no-cache-dir', '--wheel-dir', str(base/'wheels'),
                str(source)], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 0, done.stdout+done.stderr)
            wheel = next((base/'wheels').glob('tgk-*.whl'))
            self.assertNotEqual(wheel.stem.rsplit('-', 1)[-1], 'any')
            with zipfile.ZipFile(wheel) as archive:
                metadata = next(name for name in archive.namelist() if name.endswith('.dist-info/WHEEL'))
                self.assertIn('Root-Is-Purelib: false', archive.read(metadata).decode())
                self.assertIn('tgk/libtgk.so', archive.namelist())
                archive.extractall(base/'installed')
            verify = "from tgk.canvas import Canvas,rgba; b=bytearray(16); c=Canvas(b,2,2); c.clear(rgba(1,2,3)); c.close(); assert b==bytes((1,2,3,255))*4"
            env['PYTHONPATH'] = str(base/'installed')
            done = subprocess.run([sys.executable, '-c', verify], cwd=base,
                                  capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 0, done.stdout+done.stderr)

    def test_source_distribution_excludes_stale_native_binaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = self.copy_source(base)
            (source/'tgk/libtgk.so').write_bytes(b'wrong architecture')
            done = subprocess.run([sys.executable, '-c',
                'import setuptools.build_meta as b; b.build_sdist("dist")'], cwd=source,
                capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout+done.stderr)
            with tarfile.open(next((source/'dist').glob('*.tar.gz'))) as archive:
                names = archive.getnames()
                self.assertFalse(any(name.endswith('.so') for name in names))
                self.assertTrue(any(name.endswith('/native/tgk_canvas.c') for name in names))


if __name__ == '__main__':
    unittest.main()
