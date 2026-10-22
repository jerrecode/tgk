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
./install.sh
python examples/demo.py
```

The installer builds `tgk/libtgk.so` **on your device** for its ABI, installs TGK in editable mode, and enables a reversible Kivy import hook. To avoid enabling the hook globally, run `./install.sh --no-auto`; to enable it later run `python -m tgk.install_hook`.

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

Supported modules/widgets include `kivy.app.App`, `kivy.lang.Builder`, `BoxLayout`, `GridLayout`, `FloatLayout`, `ScrollView`, `Label`, `Button`, `TextInput`, `Image`, `Spinner`, `ProgressBar`, `CheckBox`, `Switch`, `ToggleButton`, basic properties and `Clock`. KV support covers indentation-based widget trees, class rules, literal attributes, IDs, and simple callbacks. **Complex KV expressions, advanced Kivy layout, graphics instructions, OpenGL/canvas, full lifecycle and full property/event parity are not implemented.** Unknown imports fail explicitly.

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

## Shell tools

GUI-first utilities such as `prompt`, `confirm`, `choose`, `show`, `files`, `image`, `progress`, `canvas-demo` and `doctor` are developed and distributed **separately** in [tgk-tools](https://github.com/jerrecode/tgk-tools). Install `tgk` first, then `tgk-tools`.

## Tests / automation

`make test` runs Android-free behavioral tests plus native pixel clipping checks. CI runs on each push and PR. Static PR review checks flag risky shell installation or credential patterns and annotate GitHub Actions output; **no unreviewed merges** are performed. Hardware-driven gesture/event tests, Android frame latency, and package/version compatibility remain outstanding.

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
