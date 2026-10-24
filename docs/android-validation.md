# Android/Termux validation record and manual plan

## Host evidence, 2026-10-23

The current maintenance pass runs on Linux x86_64 with Python 3.12.14.
There is no attached Android device, adb executable or Termux:GUI binding.
`tgk doctor --connect` reports `ModuleNotFoundError: No module named 'termuxgui'`.
This is an environment limitation, not successful Android validation.

The framework suite constructs every laboratory and exercises compact action
geometry, live Activity/root palette changes, override inheritance, input
event handling, adaptive reflow, inset planning, configuration migrations,
safe presets, caching and native C behavior with models/backend doubles.
These checks cannot establish physical touch, keyboard or system bar behavior.

## Host shutdown regression evidence, 2026-10-24

Linux host regressions drive real `TermuxBackend.run` startup and event
shutdown with fake Termux:GUI connections, views and buffers and the native C
Canvas. They inject slider/canvas close, buffer exit, model style reset and
connection exit failures. The checks verify that remaining cleanup runs,
Activity callbacks and gesture state clear before resource closure, exported
Canvas memory releases before buffer exit, native widget references and
indexes clear, and the original startup/event exception (or first cleanup
failure) survives while secondary cleanup errors are logged to stderr.
Activity construction failures also clear backend connection/activity state.

This is host regression coverage, not an Android service-failure, lifecycle,
or framebuffer test on hardware. Background/resume, repeated open/close,
service loss and physical input validation remain pending on a target device.

## Device setup and evidence

On the target device, install a matching Termux:GUI Android application and
Python binding. Compile native code locally; do not copy a Linux `.so`.
Record phone model, Android version, Termux/Termux:GUI application versions,
Python version, font/display scaling and keyboard application/version.

```sh
python --version
python -m pip show termuxgui tgk tgk-tools
tgk doctor --connect
tgk layout-plan --connect --json
python -m tgk.config validate
python -m tgk.config audit
python -m tgk.demos --list
python -m tgk.demos
tgk adaptive-demo --orientation system
```

The first commands record the environment, service connectivity, observed
window metrics and preset integrity. The last two open the single-Activity
gallery and responsive demonstration. Use `--help` to select individual cases.
Unknown refresh rate, physical panel resolution, color depth and insets must
remain unknown; approximate window pixels are not panel measurements.

## Manual acceptance matrix — all pending on hardware

For each row capture screenshots in portrait and landscape, with the soft
keyboard hidden and visible where input exists. Repeat at default and large
system text scale and under light/dark/high-contrast palettes. Include the
full window so system bars and clipped controls are visible.

| Area | Action | Expected result |
| --- | --- | --- |
| Compact actions | Open each demo, gallery, viewer and CLI dialog | Close/Cancel stays content-sized, at least 48dp, bottom-right with safe margins; content scrolls instead of enlarging the action |
| Keyboard | Edit text at the beginning and middle, select text, type using composition | Cursor and composition stay stable; active field/action remains reachable |
| Insets | Rotate; change gesture/three-button navigation; open keyboard | Available content remains usable; already-safe Android decor is not subtracted twice |
| Theme | Switch palette while gallery, tabs and popup content are visible | Window, root, child backgrounds and newly shown content use the active theme; explicit object overrides remain |
| Navigation | Open several demos and Close back to catalog; change tabs | One Activity, correct active page, no visual flash from inactive pages |
| Responsive grid | Rotate and resize supported windows; inspect `layout-plan` | Columns/breakpoints follow saved configuration; no overlap or lost actions |
| Accessibility | Enable TalkBack, large text, keyboard focus | Labels and actions are understandable and reachable; record platform styling limitations |
| Overlay | Test permission denied, then granted; test documented fallback | Actionable error when permission/protocol is unavailable; no silent window-mode substitution |
| Lifecycle | Background/resume; Android Back; repeated open/close | Clean cancellation, no stale callbacks, leaked Activity or native buffer access |

CLI cases include `tgk prompt`, `confirm`, `choose --multi`, `show`, `image`,
`files`, `progress`, `ui-lab`, `typography --preview` and `canvas-demo`.
Consult each command's help for required inputs and cancellation exit codes.
Use filenames with spaces/Unicode and directories large enough to paginate.

## Performance protocol — measurements pending

Record median/p95 native draw, buffer publication, refresh and event dispatch
time separately, plus peak RSS/CPU, at 256², 512² and 1080p with bounded
15/30/60 FPS where supported. Use identical scenes/configuration before and
after changes; Python-only benchmark results do not measure Android IPC,
compositor latency, GPU or battery. No device performance improvement is
claimed by this maintenance pass. Track outstanding hardware work in issue #3.
