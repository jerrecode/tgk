#!/usr/bin/env python3

import sys
import termuxgui as tg

with tg.Connection() as c:
    print("Connected to Termux:GUI")

    a = tg.Activity(c)

    text = tg.TextView(a, "Hello from Python + Termux:GUI")

    for ev in c.events():
        print(
            "EVENT:",
            ev.type,
            getattr(ev, "value", None),
            file=sys.stderr,
            flush=True,
        )

        if ev.type == tg.Event.destroy:
            if ev.value.get("finishing", False):
                break
