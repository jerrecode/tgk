# TGK — Termux:GUI/KV native runtime

[![CI](https://github.com/jerrecode/tgk/actions/workflows/ci.yml/badge.svg)](https://github.com/jerrecode/tgk/actions/workflows/ci.yml)

**Experimental v0.2.0:** C-accelerated RGBA rasterizer, native Android controls using `termuxgui`, declarative KV subset, and an **opt-in reversible interpreter startup hook** for selected Kivy imports. This is **not** complete upstream Kivy, and Android hardware validation remains required.

## Install on Android/Termux

Install the **Termux:GUI Android plugin** separately and ensure it matches the Termux installation. Then in Termux:

```sh
pkg update
pkg install -y git python clang
python -m pip install termuxgui setuptools
# Optional but recommended: use a Python virtual environment to isolate the Kivy shim.
git clone https://github.com/jerrecode/tgk.git
cd tgk
sh ./install.sh
python examples/demo.py
```

The installer builds `tgk/libtgk.so` **on your device** for its ABI and enables a reversible Kivy import hook. By default it installs in **editable mode**: keep the cloned `tgk` directory. If you want a standalone installation and to remove the source checkout afterwards, use `sh ./install.sh --copy`. You can combine `--copy` with `--no-auto` to avoid installing the Kivy startup hook. To enable it later run `python -m tgk.install_hook`. Both modes verify that the C library loads after installation.

```sh
# Temporarily use normal Kivy instead of TGK
TGK_DISABLE=1 python another_app.py
# Remove the Python startup hook entirely
python -m tgk.install_hook --remove
# Run tests (can run on ordinary Linux without Android)
make test
```

### How the Kivy bridge behaves

It registers a standard Python `sys.meta_path` finder via an interpreter-local `.pth` file, which means transitive imports such as `app -> helper -> from kivy.uix.button import Button` resolve automatically. The hook only activates on Termux (or with `TGK_ENABLE=1`), does **not** rewrite application source, and opens an Android Activity only when `App.run()` executes. `TGK_DISABLE=1` disables it for a Python process. Because the shim overrides actual Kivy for supported modules, do not enable it in environments where you rely on real Kivy without intending to use TGK.

Supported modules/widgets include `kivy.app.App`, `kivy.lang.Builder`, `BoxLayout`, `GridLayout`, `FloatLayout`, `ScrollView`, `Label`, `Button`, `TextInput`, `Image`, `Spinner`, `ProgressBar`, `Slider`, `CheckBox`, `Switch`, `ToggleButton`, basic properties and `Clock`. KV support covers indentation-based widget trees, class rules, literal attributes, IDs, and simple callbacks. **Complex KV expressions, advanced Kivy layout, graphics instructions, OpenGL/canvas, full lifecycle and full property/event parity are not implemented.** Unknown imports fail explicitly.

### Interactive Slider in KV

The demo (`python examples/demo.py`) now has a touch-responsive horizontal **Slider** instead of presenting a noninteractive `ProgressBar` as a slider. Sliding updates the numerical level label and a separate read-only progress indicator. It supports `min`, `max`, `value`, `step` (0 for continuous), `bind(value=...)`, KV `on_value:`, and Kivy-compatible `from kivy.uix.slider import Slider`.

```kv
Slider:
    min: 0
    max: 100
    value: 65
    step: 1
    on_value: app.update_slider(self.value)
```

The custom slider uses a touch-sensitive ImageView, native shared memory, and the TGK C rasterizer because Termux:GUI does not expose an Android SeekBar. The automated touch simulation passes, but physical device behavior and screen density scaling still need testing.

Slider drags follow one pointer ID until that finger lifts or the gesture is cancelled. Lifting another finger does not interrupt the drag. Batched motion uses the latest pointer frame, and malformed coordinates cannot capture a new drag or prevent its release. As specified by the [Termux:GUI touch protocol](https://github.com/termux/termux-gui/blob/main/Protocol.md#touch-events), ImageView coordinates already refer to image/buffer pixels; TGK does not rescale them using Android view dimensions.

### Direct TGK Python API

```python
from tgk import App, BoxLayout, Label, Button

class Demo(App):
    def build(self):
        root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text='Hello, Termux:GUI'))
        button = Button(text='Close')
        button.bind(on_release=lambda *_: self.stop())
        root.add_widget(button)
        return root
Demo().run()
```

### C accelerated canvas

```python
from tgk.canvas import Canvas, rgba
pixels = bytearray(256 * 256 * 4)
canvas = Canvas(pixels, 256, 256)
canvas.gradient(rgba(15, 20, 55), rgba(65, 22, 95))
canvas.circle(128, 128, 44, rgba(255, 60, 160))
canvas.close()
```

Buffers are non-copying writable RGBA8888 views; C uses checked bounds and alpha compositing. APIs: `clear`, `rect`, `circle`, `line`, `gradient`, `map_touch`. Termux:GUI shared buffers (`tg.Buffer`) can be rendered with the same `Canvas`; call `buffer.blit()` and `image.refresh()` after modifications. Keep buffer views from outliving the memory mapping.

### Verify that installation worked

```sh
# From any directory, verifies C shared library is available
python -c "from tgk.canvas import _lib; _lib(); print('TGK renderer OK')"
# After installing tgk-tools, verifies the native Android connection
tgk doctor --connect
```

A successful Linux CI run does not verify the Android plugin connection, which needs hardware/device testing. Avoid downloading a Linux-built `.so` for Termux: `install.sh` compiles for the current device.

Non-editable Python package builds also compile the renderer from C source on the build device. Wheels are tagged for that platform/interpreter; they are never advertised as platform-independent `py3-none-any` packages. Source distributions exclude existing `.so` files so a stale host binary cannot be shipped as source. Editable installations still use the in-place renderer built by `install.sh` or `make build`.


## Semantic themes, palette inheritance and interactive laboratories

TGK now offers an **experimental centralized palette system** with twelve named presets:
`midnight` (default), `amoled`, `paper`, `ocean`, `forest`, `sunset`,
`cyberpunk`, `lavender`, `terminal`, `desert`, `high_contrast`, `ice`.
Each preset supplies all 17 semantic roles: `status_bar`, `primary`, `background`,
`surface`, `surface_alt`, `text`, `muted`, `accent`, `accent_secondary`,
`button`, `button_text`, `outline`, `track`, `thumb`, `success`,
`warning`, and `danger`. Colors are standard `#RGB`, `#RRGGBB`,
or `#RRGGBBAA`; TGK translates to the protocol's `0xAABBGGRR` byte order.

```python
from tgk import App, Label, BoxLayout, set_theme, PRESETS
set_theme("ocean", accent="#18D0F9")    # process/context default
root = BoxLayout(orientation="vertical", colors={"surface":"#183752"})
root.add_widget(Label(text="Hello", text_color="#FFDD22",
                      background_color="#232A50", halign="center"))
# App(theme="paper") overrides the default for an individual application.
# In a running application: self.set_theme("sunset", accent="#FFA966")
```

Widget `colors={role: "#HEX"}` inherits into descendants and can override any
semantic role, while `background_color="#HEX"` and `text_color="#HEX"`
override the individual view. A child `theme="paper"` starts a separate preset
subtree. Changes to those fields and `App.set_theme(...)` recolor existing
native widgets and redraw custom C sliders, without discarding the widget tree.

Native activity `settheme()` affects **only newly created Android Views**, so
TGK invokes it before building the tree and uses per-view setters for live
updates. Some Android control styling (notably native progress indicators,
switch tracks/thumbs and platform-specific focus decorations) is outside the
current protocol's per-widget color controls and may retain OS styling.

```sh
# Discover all scenarios; only --list runs without Android:
python -m tgk.demos --list
# 16 graduated cases: basic rows → grids → nesting → scroll → forms →
# linked sliders → state transitions → gravity/weights → overrides → stress →
# interactive palette editor → full workbench.
python -m tgk.demos --demo 04_nesting --theme forest
python -m tgk.demos --demo 09_anchors --theme paper
python -m tgk.demos --demo 12_studio --theme cyberpunk
python -m tgk.demos --demo 13_workbench --theme ocean --color accent=#FF55CC

python examples/layout_lab.py --list
python examples/theme_studio.py
python examples/complex_workbench.py
```

The studio supports live switching between all 12 presets, eleven 0–100% shade
swatches, arbitrary semantic-role hex input, separate R/G/B accent sliders,
interactive form/state controls and a multi-action workbench. Layout probes test
nested `BoxLayout` and `GridLayout`, `spacing`, `padding`, `weight`,
text `halign`/`valign`, grid `align_row`/`align_col`, and state changes.
These expose practical Termux:GUI limits: full Kivy positioning, anchoring,
responsive constraint layout and dynamically inserting/removing native Views
are **not** yet supported. View-gravity tests are not a substitute for true
anchor positioning tests. Inspect Android layout behavior on-device.

The tests construct all 16 scenarios without Android and check callbacks,
inherited palette semantics, invalid colors and live updates. Android device
rendering and interaction remain unverified by Linux CI.

## Advanced UI: screens, tabs, overlays, typography and icon catalog

This experimental extension adds support for multi-view **screen navigation**
and **tabbed views** without deleting/recreating child widgets on every tab switch.

```python
from tgk import (App, ScreenManager, Screen, TabbedPanel, Tab, Popup,
                 InfiniteCanvas, RichTextLabel, TextSpan, IconLabel,
                 resolve_text_style)

screens=ScreenManager()
for name in ("home","files","settings"):
    screens.add_widget(Screen(name=name,title=name.title()))
screens.switch("files")

tabs=TabbedPanel()
tabs.add_widget(Tab(name="editor",title="Editor"))
tabs.add_widget(Tab(name="preview",title="Preview"))
tabs.switch("preview")

popup=Popup(visible=False,height=240,width=320)
popup.open()       # setvisibility(VISIBLE), existing children retained
popup.dismiss()    # setvisibility(GONE), does not destroy children

canvas=InfiniteCanvas(width=512,height=384,zoom=1)
canvas.add_marker(100,-40,role="accent")
canvas.pan(32,0)
canvas.zoom_at(1.5,256,192)
```

- `ScreenManager` / `PageView`: named views sharing one native
  `FrameLayout`; selects one using native `setvisibility`.
- `TabbedPanel`: Termux:GUI's native `TabLayout` and a `FrameLayout`.
  Protocol `itemselected` messages select the matching tab content.
- `Popup`: **in-Activity** popup view intended as a child of a `FloatLayout`;
  shown/hidden without rebuilding. It is not yet a fully focus-trapping modal.
- `App(window_mode="dialog")`: Android dialog-style Activity.
  `App(window_mode="overlay")`: Android overlay Activity requiring the
  **Termux:GUI Display over other apps** system permission. These are
  *single-App* windows, not an unrestricted concurrent desktop window manager.
  Starting separate Python processes can create independent Android Activities.
- `InfiniteCanvas`: C-rendered 2D viewport with unbounded *logical* world
  coordinates, pan, two-pointer pinch zoom, finite framebuffer (max 1 MP) and
  up to 10,000 markers. Neither physical framebuffer nor marker count is
  literally infinite; the viewport does not support arbitrary zoom or 3D.

### Text presets and safe rich formatting

Fifteen typography presets: `body` (default), `caption`, `small`,
`subtitle`, `title`, `display`, `monospace`, `terminal`, `code`,
`serif`, `quote`, `emphasis`, `warning`, `danger`, `muted`,
and `link`. (This is **16** presets including body.)

```python
from tgk import App, TextStyle, TextSpan, RichTextLabel
app=App(text_style="terminal")
label=RichTextLabel(
    spans=[TextSpan("Bold",style="title"),
           TextSpan(" + italic",style="quote",color="#AE73FA")],
    style="body",height=100)
app.set_text_style("display")
# Standard Label and TextInput native setters support size and color.
# RichTextLabel implements mixed text styles using an isolated WebView.
```

Native Termux:GUI `TextView` has color, size and gravity setters but no
general font-family/weight/italic/rich-span API. TGK uses validated HTML and
CSS in a **JavaScript-disabled, navigation-disabled WebView** to provide font
families (system sans, serif, mono), bold/italic, underline, strike-through,
line height, alignment, mixed colors and safely escaped text. It deliberately
does not load custom font files, remote resources or arbitrary user CSS.
`App.set_text_style()` adjusts default native label size and color; for a
RichTextLabel, use its `style` property or run the shared theme selector.

### Semantic icons

`tgk.icons.ICONS` contains hundreds of semantic names in six groups:
`files`, `directories`, `actions`, `media`, `view`, `navigation`.
Covers detailed programming/data/media/archive/package extensions, Linux
filesystem directories, editing/actions, playback, viewport and settings.

```python
from tgk import icon_for_path, glyph, svg, IconLabel
name=icon_for_path("records.jsonl",is_dir=False)  # jsonl
print(name,glyph(name))
icon=IconLabel(icon="folder",text="Documents",font_size=18)
svg_text=svg("zoom_in",size=64,color="#18D0F9")
```

Unicode glyph labels depend on installed Android fonts and may vary by device.
TGK also includes dependency-free vector SVG stroke paths for a smaller core
icon subset; it **does not** yet bundle complete SVG paths for all named
icons or install third-party fonts. SVG strings are assets, not native
termuxgui.ImageView inputs; convert to PNG (for example with a trusted
rasterizer) before passing to a native image viewer.

### Run the composite Android lab

```sh
python examples/advanced_gui.py --theme ocean
python examples/advanced_gui.py --theme paper --mode dialog
# Requires overlay permission in Termux:GUI Android settings:
python examples/advanced_gui.py --theme cyberpunk --mode overlay
```

The lab contains five native tabs: navigation, icon gallery, rich typography,
pan/zoom C canvas, and a nested screen stack. It also includes an in-Activity
popup. This source is independently unit-tested on Linux, but Android
touch/overlay/TabLayout behavior is awaiting **real hardware validation**.

## Shell tools

GUI-first utilities such as `prompt`, `confirm`, `choose`, `show`, `files`, `image`, `progress`, `canvas-demo` and `doctor` are developed and distributed **separately** in [tgk-tools](https://github.com/jerrecode/tgk-tools). Install `tgk` first, then `tgk-tools`.

## Tests / automation

`make test` runs Android-free behavioral tests plus native pixel clipping checks. CI runs on each push and PR. Static PR review checks flag risky shell installation or credential patterns and annotate GitHub Actions output; **no unreviewed merges** are performed. Hardware-driven gesture/event tests, Android frame latency, and package/version compatibility remain outstanding.

Packaging regression tests require pip, setuptools and wheel in the test interpreter (`python -m pip install setuptools wheel`). They build real wheels and source distributions offline, check their contents/tags, and load the newly built renderer outside the source checkout.

## Repository organization

- `tgk/native/tgk_canvas.c`: bounds-checked portable C rasterizer
- `tgk/canvas.py`: `ctypes` interface to writable RGBA frames
- `tgk/widgets.py`: widget abstractions and native Android backend
- `tgk/kv.py`: KV subset compiler
- `tgk/compat/importer.py`: transitive Kivy module import hook
- `tgk/install_hook.py`: reversible `.pth` installer
- `examples/`: small KV example and original Termux:GUI probes
- `tests/`: offline regression tests

See [AGENTS.md](AGENTS.md) for engineering priorities and constraints.

MIT license. Originated from two Termux:GUI probes; development is experimental and should be evaluated on real Android devices before relying on it for production applications.
