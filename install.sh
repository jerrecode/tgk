#!/usr/bin/env sh
# Install TGK into the selected Python environment. No root, no destructive upgrades.
set -eu
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python}"
CC="${CC:-cc}"
ENABLE_AUTO=1
case "${1:-}" in
  --no-auto) ENABLE_AUTO=0 ;;
  --enable-auto|'') ;;
  --help|-h) printf '%s\n' 'Usage: ./install.sh [--enable-auto|--no-auto]' ; exit 0 ;;
  *) printf 'Unknown option: %s\n' "$1" >&2 ; exit 2 ;;
esac
command -v "$CC" >/dev/null || { echo 'Missing C compiler: install clang (pkg install clang)' >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo 'Missing Python: pkg install python' >&2; exit 1; }
printf 'Building native TGK renderer for this device...\n'
"$CC" -O3 -std=c11 -fPIC -shared -Wall -Wextra -Werror -o tgk/libtgk.so tgk/native/tgk_canvas.c -lm
"$PYTHON" -m pip install --no-build-isolation --no-deps --editable .
if [ "$ENABLE_AUTO" -eq 1 ]; then "$PYTHON" -m tgk.install_hook; fi
"$PYTHON" -c 'import tgk; print("Installed TGK:", tgk.__version__)'
printf '%s\n' 'Ready. Try: python examples/demo.py (with the compatibility hook enabled)'
