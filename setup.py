"""Build the ctypes renderer locally and mark wheels as platform-specific."""
import os
from pathlib import Path
import shlex
import subprocess

from setuptools import Distribution, setup
from setuptools.command.build_py import build_py


class NativeDistribution(Distribution):
    def has_ext_modules(self):
        # libtgk.so is native code even though ctypes loads it rather than a
        # CPython extension import. Never label this distribution "any".
        return True


class BuildNative(build_py):
    def run(self):
        super().run()
        if getattr(self, 'editable_mode', False):
            return  # install.sh/make build supplies the in-place renderer
        package = Path(self.build_lib)/'tgk'
        compiler = shlex.split(os.environ.get('CC', 'cc'))
        subprocess.run(compiler + ['-O3', '-std=c11', '-fPIC', '-shared',
            '-Wall', '-Wextra', '-Werror', '-o', str(package/'libtgk.so'),
            str(package/'native/tgk_canvas.c'), '-lm'], check=True)


setup(distclass=NativeDistribution, cmdclass={'build_py': BuildNative})
