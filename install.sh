#!/usr/bin/env sh
# Install TGK into the selected Python environment. No root required.
set -eu
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python}"
CC="${CC:-cc}"
ENABLE_AUTO=1
INSTALL_MODE=editable

for arg in "$@"; do
  case "$arg" in
    --no-auto) ENABLE_AUTO=0 ;;
    --enable-auto) ENABLE_AUTO=1 ;;
    --copy) INSTALL_MODE=copy ;;
    --editable) INSTALL_MODE=editable ;;
    --help|-h)
      printf '%s\n' 'Usage: ./install.sh [--copy|--editable] [--enable-auto|--no-auto]' \
        '  --editable  Link Python installation to this source checkout (default).' \
        '  --copy      Install a self-contained copy, safe to remove source afterwards.' \
        '  --no-auto   Leave the Kivy compatibility startup hook disabled.'
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

command -v "$CC" >/dev/null 2>&1 || { echo 'Missing C compiler: pkg install clang' >&2; exit 1; }
command -v "$PYTHON" >/dev/null 2>&1 || { echo 'Missing Python: pkg install python' >&2; exit 1; }
"$PYTHON" -m pip --version >/dev/null || {
  echo 'Missing pip for the selected Python interpreter' >&2
  exit 1
}
"$PYTHON" -c 'import setuptools.build_meta' || {
  echo 'Missing Python build tools: python -m pip install setuptools' >&2
  exit 1
}
printf 'Compiling native TGK renderer using %s...\n' "$CC"
"$CC" -O3 -std=c11 -fPIC -shared -Wall -Wextra -Werror -o tgk/libtgk.so tgk/native/tgk_canvas.c -lm
if [ "$INSTALL_MODE" = copy ]; then
  # Non-editable install is essential if a caller cloned us into a temporary directory.
  "$PYTHON" -m pip install --no-build-isolation --no-deps --force-reinstall .
else
  "$PYTHON" -m pip install --no-build-isolation --no-deps --editable .
fi
if [ "$ENABLE_AUTO" -eq 1 ]; then "$PYTHON" -m tgk.install_hook; fi
# Populate XDG/Termux user-owned presets without overwriting edited files.
# Importing TGK never creates configuration automatically; installation does.
"$PYTHON" -m tgk.config init --json
"$PYTHON" -m tgk.config validate --json
"$PYTHON" -c 'import tgk; from tgk.canvas import _lib; _lib(); print("Installed TGK:", tgk.__version__, "from", tgk.__file__)'
printf '%s\n' 'Ready. Check the Termux:GUI service with: tgk doctor --connect (requires tgk-tools).'
