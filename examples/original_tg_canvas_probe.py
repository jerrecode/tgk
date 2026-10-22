#!/usr/bin/env python3

import json
import sys
import numpy as np
import termuxgui as tg


W = 512
H = 512


def normalize_pointer_samples(value):
    """
    Normalize all pointer representations we may encounter to:

        [
            [ {"id": ..., "x": ..., "y": ...}, ... ],
            [ {"id": ..., "x": ..., "y": ...}, ... ],
            ...
        ]

    The outer list represents historical/current samples.
    The inner list contains simultaneous pointers.
    """

    pointers = value.get("pointers", [])

    if pointers is None:
        return []

    # Possible representation:
    #
    #   "pointers": {"id": 0, "x": ..., "y": ...}
    #
    if isinstance(pointers, dict):
        return [[pointers]]

    if not isinstance(pointers, (list, tuple)):
        return []

    if not pointers:
        return []

    # Observed representation on the current device:
    #
    #   "pointers": [
    #       {"id": 0, "x": ..., "y": ...},
    #       {"id": 1, "x": ..., "y": ...}
    #   ]
    #
    # i.e. one current sample containing N pointers.
    if all(isinstance(p, dict) for p in pointers):
        return [list(pointers)]

    # Documented representation:
    #
    #   "pointers": [
    #       [
    #           {"id": 0, "x": ..., "y": ...},
    #           {"id": 1, "x": ..., "y": ...}
    #       ],
    #       [
    #           {"id": 0, "x": ..., "y": ...},
    #           {"id": 1, "x": ..., "y": ...}
    #       ]
    #   ]
    #
    result = []

    for sample in pointers:
        if isinstance(sample, dict):
            result.append([sample])

        elif isinstance(sample, (list, tuple)):
            valid = [
                p for p in sample
                if isinstance(p, dict)
            ]

            if valid:
                result.append(valid)

    return result


def draw_disc(img, cx, cy, radius=18):
    cx = int(round(cx))
    cy = int(round(cy))

    y0 = max(0, cy - radius)
    y1 = min(img.shape[0], cy + radius + 1)

    x0 = max(0, cx - radius)
    x1 = min(img.shape[1], cx + radius + 1)

    if x0 >= x1 or y0 >= y1:
        return

    yy, xx = np.ogrid[y0:y1, x0:x1]

    mask = (
        (xx - cx) ** 2 +
        (yy - cy) ** 2
    ) <= radius ** 2

    region = img[y0:y1, x0:x1]

    region[mask] = (
        255,
        255,
        255,
        255,
    )


def draw_pointer_color(img, pointer, action):
    x = pointer.get("x")
    y = pointer.get("y")

    if x is None or y is None:
        return

    # Larger marker for down events.
    radius = 24 if action in (
        "down",
        "pointer_down",
    ) else 14

    draw_disc(
        img,
        float(x),
        float(y),
        radius,
    )


with tg.Connection() as c:

    print(
        "Termux:GUI version:",
        c.getversion()
    )

    activity = tg.Activity(
        c,
        intercept=True,
    )

    image = tg.ImageView(activity)

    image.setdimensions(
        tg.View.MATCH_PARENT,
        tg.View.MATCH_PARENT,
    )

    image.sendtouchevent(True)

    buffer = tg.Buffer(
        c,
        W,
        H,
    )

    image.setbuffer(buffer)

    # IMPORTANT:
    #
    # Buffer.__exit__() already calls Buffer.remove().
    # Therefore there must be NO additional
    # buffer.remove() afterwards.
    with buffer as mem:

        pixels = np.ndarray(
            shape=(H, W, 4),
            dtype=np.uint8,
            buffer=mem,
        )

        try:

            # -----------------------------
            # Initial test pattern
            # -----------------------------

            xgradient = (
                np.arange(
                    W,
                    dtype=np.uint16,
                )
                * 255
                // max(1, W - 1)
            ).astype(np.uint8)

            ygradient = (
                np.arange(
                    H,
                    dtype=np.uint16,
                )
                * 255
                // max(1, H - 1)
            ).astype(np.uint8)

            pixels[:, :, 0] = xgradient[None, :]
            pixels[:, :, 1] = ygradient[:, None]
            pixels[:, :, 2] = 70
            pixels[:, :, 3] = 255

            # Corner reference blocks.
            pixels[0:80, 0:80] = (
                255, 0, 0, 255
            )

            pixels[0:80, -80:] = (
                0, 255, 0, 255
            )

            pixels[-80:, 0:80] = (
                0, 0, 255, 255
            )

            pixels[-80:, -80:] = (
                255, 255, 255, 255
            )

            buffer.blit()
            image.refresh()

            print()
            print(
                f"Framebuffer active: "
                f"{W} x {H}"
            )

            print(
                "Draw with one or more fingers."
            )

            print(
                "Android Back closes the test."
            )

            print()

            touch_count = 0
            move_count = 0

            for ev in c.events():

                # -------------------------
                # Touch
                # -------------------------

                if ev.type == tg.Event.touch:

                    touch_count += 1

                    action = ev.value.get(
                        "action"
                    )

                    samples = (
                        normalize_pointer_samples(
                            ev.value
                        )
                    )

                    # Dump the first few raw events.
                    #
                    # This is useful because we want
                    # to establish what this exact
                    # Termux:GUI version emits.
                    if touch_count <= 5:
                        print(
                            "\nRAW TOUCH EVENT:"
                        )

                        print(
                            json.dumps(
                                ev.value,
                                indent=2,
                                default=str,
                            )
                        )

                    if not samples:
                        print(
                            "TOUCH without usable "
                            "pointer data:",
                            ev.value,
                        )

                        continue

                    # The newest/current sample is
                    # the final sample.
                    current = samples[-1]

                    # Avoid flooding stdout with every
                    # single MOVE event.
                    should_print = (
                        action != "move"
                    )

                    if action == "move":
                        move_count += 1

                        if move_count % 10 == 0:
                            should_print = True

                    if should_print:

                        print(
                            "\nTOUCH",
                            f"action={action}",
                            f"index="
                            f"{ev.value.get('index')}",
                            f"time="
                            f"{ev.value.get('time')}",
                            f"samples={len(samples)}",
                            f"pointers="
                            f"{len(current)}",
                        )

                    for pointer in current:

                        pid = pointer.get(
                            "id",
                            "?"
                        )

                        x = pointer.get("x")
                        y = pointer.get("y")

                        if (
                            x is None or
                            y is None
                        ):
                            continue

                        if should_print:
                            print(
                                "  "
                                f"id={pid} "
                                f"x={float(x):.1f} "
                                f"y={float(y):.1f}"
                            )

                        draw_pointer_color(
                            pixels,
                            pointer,
                            action,
                        )

                    # Publish modified shared memory.
                    buffer.blit()

                    # Ask ImageView to redraw it.
                    image.refresh()

                # -------------------------
                # Back
                # -------------------------

                elif ev.type == tg.Event.back:

                    print(
                        "\nBack pressed."
                    )

                    activity.finish()

                # -------------------------
                # Configuration changes
                # -------------------------

                elif ev.type == tg.Event.config:

                    print(
                        "\nCONFIG:"
                    )

                    print(
                        json.dumps(
                            ev.value,
                            indent=2,
                            default=str,
                        )
                    )

                # -------------------------
                # Activity lifecycle end
                # -------------------------

                elif ev.type == tg.Event.destroy:

                    print(
                        "\nDESTROY:",
                        ev.value,
                    )

                    if ev.value.get(
                        "finishing",
                        False,
                    ):
                        break

        finally:

            # Very important:
            #
            # release NumPy's exported reference to
            # the mmap BEFORE Buffer.__exit__()
            # tries to close that mmap.
            del pixels


print()
print(
    "Termux:GUI canvas test finished cleanly."
)
