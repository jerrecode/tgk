"""Reversible interpreter-local TGK/Kivy startup hook."""
from __future__ import annotations
import sysconfig
from pathlib import Path

def hook_path():
    return Path(sysconfig.get_path("purelib")) / "tgk_auto.pth"

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--remove", action="store_true")
    args = p.parse_args()
    path = hook_path()
    if args.remove:
        if path.exists():
            data = path.read_text(encoding="utf-8")
            if data != "import tgk.auto as _tgk_auto; _tgk_auto.maybe_activate()\n":
                raise RuntimeError(f"Refusing to delete an unfamiliar startup hook: {path}")
            path.unlink()
        print(f"TGK hook disabled: {path}")
        return
    path.write_text("import tgk.auto as _tgk_auto; _tgk_auto.maybe_activate()\n",encoding="utf-8")
    print(f"TGK Kivy compatibility hook enabled: {path}")
    print("Disable for one run: TGK_DISABLE=1 python script.py")
    print("Uninstall: python -m tgk.install_hook --remove")
if __name__ == "__main__": main()
