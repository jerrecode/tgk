"""Termux-only site hook. For desktop tests: TGK_ENABLE=1."""
import os
import sys

def maybe_activate():
    if os.environ.get('TGK_DISABLE')=='1':return False
    prefix=os.environ.get('PREFIX','')
    is_termux='com.termux' in prefix or 'com.termux' in sys.executable
    if not (os.environ.get('TGK_ENABLE')=='1' or is_termux):return False
    from .compat import activate
    activate()
    return True
