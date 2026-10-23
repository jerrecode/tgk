# TGK — Termux:GUI/KV native runtime

[![CI](https://github.com/jerrecode/tgk/actions/workflows/ci.yml/badge.svg)](https://github.com/jerrecode/tgk/actions/workflows/ci.yml)

**Experimental v0.4.0:** C-accelerated RGBA rasterizer, native Android controls using `termuxgui`, declarative KV subset, and an **opt-in reversible interpreter startup hook** for selected Kivy imports. This is **not** complete upstream Kivy, and Android hardware validation remains required.

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

## Native event indexing and large widget trees

Native click, touch, text and tab selection events use a dictionary indexed
by the stable scalar View ID returned from Termux:GUI. This removes the
previous O(number_of_widgets) linear search from the event hot path;
ordinary dispatch is O(1) average, while custom bindings without scalar IDs
retain a compatibility fallback. Native View objects themselves are **never**
dictionary keys (the Termux:GUI Python bindings may make them unhashable).
The index is cleared with the Activity on shutdown.

`Widget.walk()` uses iterative preorder traversal instead of recursion,
so traversing very deeply nested widget models does not fail from Python's
recursion limit. Real Android-native nesting depth and layout performance
still require separate device testing.

## Targeted theme repaint and resource-bounded data pipelines

For Android drag responsiveness, a local `Widget.background_color` or
`text_color` change now paints **only that widget**. Replacing a subtree
`colors` dictionary repaints only its descendants; `App.set_theme`
reevaluates the whole tree once. Each native View remembers its previously
sent values so identical colors, font sizes, markup and C-buffer palettes do
not trigger redundant IPC. The theme studio coalesces rapid RGB events to at
most roughly **30 palette commits per second** while its Android event loop
is running; the final drag value is applied. Previously 11 swatch updates
could send O(11 × total_widgets) native requests. Regression tests count
native setter invocations for a synthetic 160-label tree.

Run the studio with your updated TGK installation:

```sh
python -m tgk.demos --demo 12_studio --theme ocean
python examples/layout_lab.py --demo 13_workbench
```

TGK additionally exposes **opt-in, bounded standard-library I/O adapters**:

```python
from tgk.io_pipeline import Limits, BoundedPool, hash_file, copy_file, ffprobe
lim=Limits(chunk_bytes=64*1024,max_bytes=100*1024*1024,
           timeout=20,workers=2,pending=3)
digest=hash_file("video.mp4",limits=lim)
result=copy_file("video.mp4","video-copy.mp4",limits=lim)
metadata=ffprobe("video.mp4",timeout=10)  # requires installed ffprobe
with BoundedPool(lim) as workers:
    futures=[workers.submit(hash_file,p,limits=lim) for p in ["a.bin","b.bin"]]
    print([f.result().sha256 for f in futures])
```

`transfer()` copies between binary streams using fixed-size chunks, handles
short writes, respects a byte cap/deadline/cancellation and calculates SHA-256
incrementally. `copy_file()` writes a sibling temp file and commits using
atomic rename; existing destinations require explicit `overwrite=True`.
`hash_file()` does not read whole files into RAM. `download()` supports
HTTPS by default with optional hostname restrictions and no redirects; HTTP
requires deliberate `allow_http=True`. Do not treat hostnames as an SSRF
firewall: callers using untrusted URLs should enforce DNS/IP/network
allowlists separately. `ffprobe()` uses a subprocess argument list (never
`shell=True`) for local file metadata, a protocol whitelist, a deadline and
a bounded JSON result. It requires `pkg install ffmpeg` on Termux.

`BoundedPool` uses a small, configurable thread pool with a bounded
submission queue (not an unbounded task list). These primitives do **not**
implement FTP, SSH, Telnet, SOCKS, SFTP, SMTP, Gopher, UDP, live media decoding,
hardware video rendering or automatic multiprocessing. They are building
blocks to integrate such opt-in plugins safely. Android throughput and
power consumption remain unmeasured.

## Adaptive Android dp grid and expanded semantic UI styles

TGK's optional `ResponsiveGrid` implements a **12-column width-class grid**,
with breakpoints compact (<600 dp), medium (600–839 dp) and expanded (840+ dp).
Each widget can specify `span_compact`, `span_medium` and
`span_expanded` (integer 1–12). The native Android `GridLayout` retains
12 columns and positions child views using `setgridlayoutparams`, so a
Termux:GUI `config` event (rotation/window resize) reflows existing views
without reconstructing them. Native pointer targets default to at least
**48 dp**; a widget can opt out with `allow_small_touch_target=True`.

```python
from tgk import App, ResponsiveGrid, Button
grid=ResponsiveGrid()
for i in range(12):
    grid.add_widget(Button(text=str(i),span_compact=12,
                           span_medium=6,span_expanded=4))
# App(orientation_mode="system") respects system rotation;
# use "portrait" or "landscape" to lock just this Activity.
```

`ScreenMetrics.from_configuration` reads actual Termux:GUI
`Activity.getconfiguration()` keys `screenwidth`, `screenheight`,
`orientation`, `density` and `fontscale`; the dimensions are Android
**window dp**, not necessarily the physical display's maximum resolution.
Its `approx_window_px` is computed using density, and
`max_refresh_hz`, physical panel resolution, color depth and explicit
status/navigation-bar inset fields remain **None unless an authoritative
provider supplies them**. Standard Android Activities already lay out inside
the safe content area; TGK does **not** apply a guessed extra status-bar
offset (which would double-offset some devices).

The defaults use a 4 dp spacing grid, a 48 dp interactive touch minimum,
gutter/margin scale and a capped content width.
`tgk.adaptive.arrange_spans` is a pure, testable first-fit row-packing
algorithm; `LayoutScale` exposes spacing, grid columns and touch units.

### Component colors, state roles and styled tables

Each of the twelve palette presets now defines over sixty semantic roles.
New derived roles include `button_pressed`, `button_active`,
`button_inactive`, `button_border`, `input_background`,
`dropdown_background`, `list_row_alt`, `list_selected`,
`table_header`, `table_row_alt`, `table_column_alt`,
`table_first_row`, `table_first_column`, `table_divider`,
`tab_active`, `tab_inactive`, `slider_fill`, `slider_thumb`,
`progress_track`, `progress_fill`, `panel`, `menu`,
`notification`, `top_bar`, `bottom_bar`, `selection`, and
`text_selected`. These are derived by interpolating base scheme colors
and are individually overridable. Updating a base color recomputes derived
roles not explicitly replaced in that operation.

For a button use `visual_state="normal"|"pressed"|"active"|"disabled"`
(the latter are visual variants, **not** automatic input gating).
`ComponentStyle` and `TableStyle` are immutable style contracts for
padding, margins, border widths/styles, corner radii, text-fit metadata,
alternating row/column shading, first row/column emphasis and cell headers.
Android native Views do not expose all these decoration setters.
`RichTable` implements the full table styling in a local, escaped,
CSP-restricted, JavaScript-free WebView instead:

```python
from tgk import RichTable, TableStyle
table=RichTable(rows=[["Metric","Value"],["Width","393 dp"]],
                table_style=TableStyle(
                  shade_alternate_rows=True,
                  shade_alternate_columns=True,
                  first_column_right_width_dp=3,
                  header_bottom_width_dp=4,
                  bold_first_row=True))
```

Typography presets now include heading levels H1–H5, descriptions, hyperlinks,
filesystem paths, code, comments, citations/references, footnotes, metadata,
tables, input fields, selected text and notification text. They inherit
palette color roles and can still be overridden on individual widgets.

```sh
python examples/adaptive_layout.py --theme ocean --orientation system
python examples/adaptive_layout.py --theme paper --orientation landscape
```

Offline tests verify window metric parsing, missing hardware information,
all theme roles, HTML escaping and borders, and geometry changes on config
events. Screen rotation, Android font-scale accessibility, rendering, status
bar behavior and actual touch dimensions **must** still be tested on device.

## Compact mobile actions and live Activity backgrounds

Use `tgk.layout_helpers.compact_action_bar("Close",callback,margin=12)`
as the last child of a vertical root to obtain a **48 dp-tall, text-sized
button anchored to the bottom-right safe content edge** with a weighted
spacer and configurable margins. The button uses an explicit width rather
than filling an entire row or an unrestricted fraction of the screen.
`action_width(text)` bounds other demo buttons by their label length.

```python
from tgk import App,BoxLayout,ScrollView
from tgk.layout_helpers import compact_action_bar
class Example(App):
    def build(self):
        root=BoxLayout(orientation="vertical")
        content=ScrollView(weight=1)
        root.add_widget(content)
        root.add_widget(compact_action_bar("Close",self.stop))
        return root
```

TGK's Activity root now fills the Android content viewport when its dimensions
are unspecified. `App.set_theme(...)` refreshes both the native child View
palette **and the Activity window background theme**, avoiding the previous
stale startup-colored region behind translucent or margin-offset children.
Whether Android applies every Activity theme field immediately depends on the
installed Termux:GUI plugin version; hardware validation is still required.

## TGK 0.5.0: hierarchical composable SVG icon assets

The existing Unicode/semantic icon catalog remains backward compatible.
The new `tgk.icon_builder` defines reusable SVG base shapes (files,
folders, data, media, actions), recursively inherited icon recipes and
small foreground layers (text/code lines, stylus/pen, zipper, lock, audio
note, terminal marker, play button, badge, and centered label). Individual
recipes combine these primitives without duplicating hand-written SVGs.

Code and data extensions include HTML, CSS, XML, JSON, YAML, TOML, Graph,
DOT, HTMX, JavaScript, Java, Python/PYC/PYO, JSONL, MusicXML, LilyPond,
C/H, TeX, BibTeX, Markdown/MDBook, AsciiDoc, ASCII, HEX, EEPROM, BIN,
BYTE, MEM, DAT, DATA, GeoJSON, INFO, HELP, MAN, SH, BASH, BAT and more.
Every `file_ext_*` recipe has an uppercase label centered inside the
drawn file's inner bounds. Special recipes render README, LICENSE, INFO,
AGENTS, MAKE, REQ and INSTALL in addition to the icon overlay, with more
special filenames included in the public catalog.

```python
from tgk.icon_builder import render_svg,asset_key_for_path,build_assets
print(asset_key_for_path("README.md"))  # filename_readme_md
print(render_svg("file_ext_jsonl",size=64))
build_assets("/tmp",names=["file_ext_py","file_ext_json","filename_readme_md"])
# /tmp/icons/svg/*.svg, /tmp/icons/{ico,low_res,mid_res,high_res}/ empty
```

Asset generation uses a validation-first **atomic staging/rename** pipeline:
no SVG is published until all selected recipes compile successfully. It
creates exactly `icons/svg`, `icons/ico`, `icons/low_res`,
`icons/mid_res`, and `icons/high_res` plus a manifest with SHA-256
hashes, recipe ancestry and overlays. The four non-SVG directories remain
empty on a pure SVG run. Generated assets are not duplicated in Git history;
the empty output directories are tracked for discoverability.

```sh
# Standard library SVG-only export for all supported recipes.
python -m tgk.icon_builder --output /tmp --overwrite

# Generate all three PNG and JPEG resolutions plus multiresolution ICO.
# CairoSVG and Pillow are optional, user-installed renderer dependencies.
python -m pip install cairosvg pillow
python -m tgk.icon_builder --output /tmp --raster --overwrite

# Restrict a build to a small list of named assets.
python -m tgk.icon_builder --output /tmp --overwrite \
  --icon file_ext_html --icon filename_agents_md --icon folder_git
```

The raster presets default to low 32×32, mid 96×96, high 256×256 PNG/JPEG,
plus a 16/24/32/48/64-pixel multi-size ICO. Rasterization performs bounded
per-icon processing and never requires downloading icon fonts. SVG text
uses system fonts, so its pixel-level appearance depends on the selected
rendering backend; names and metadata are deterministic.

A separate `Layered TGK icon asset pack` GitHub Actions workflow runs the
whole raster conversion, verifies output counts, and uploads a downloadable
ZIP under that run's artifacts. All SVG samples are XML-validated in unit
tests. Android native image controls still need PNG/JPEG bytes rather than
SVG source: use the generated raster assets or a trusted on-device renderer.

## Persistent configuration and editable presets (TGK 0.6.0)

TGK initializes its user-owned, platform-neutral configuration during
`sh ./install.sh`. The directory is `$TGK_CONFIG_DIR` when set, otherwise
`$XDG_CONFIG_HOME/tgk`, otherwise `~/.config/tgk`. Ordinary module imports
never write configuration files. Installation creates **only missing files**;
reinstalling does not overwrite your manual edits.

```text
~/.config/tgk/
  config.json              # core system and default selections
  palettes/midnight.json   # + all built-in palette presets
  palettes/ocean.json
  typography/body.json     # + all built-in font/text presets
  typography/title_h3.json
  options/layout.json      # + backend, io, icons and other component options
  options/backend.json
  options/button.json
  options/table.json
```

`config.json` has validated sections `defaults` (theme and text_style),
`window` (Activity type and orientation),
`layout` (12 columns, dp spacing/gutters, touch target),
`backend` (bounded Clock callback budget and idle sleep),
`io` (chunk/total limits, timeout, worker counts) and `icons`
(resolution tiers and maximum pack size). All are initialized with
working factory defaults. The per-preset files are human-editable JSON.
Palette files may override individual semantic roles, while typography files
override validated font/style parameters. Edited `options/button.json`,
`options/table.json` and similar component presets are resolved on use by
`resolve_component_style(name)`; explicitly passed `ComponentStyle` values
take precedence. `config.json` is the **live source of system-level
settings** such as responsive layout, backend scheduling, bounded I/O defaults
and icon export sizes; editing one component preset does not automatically
override every widget in a running Activity.

```sh
python -m tgk.config init   # safely recreate missing catalog entries
python -m tgk.config show   # validate and print the active config
```

Defaults are applied consistently for new `App()` and bare
`TermuxBackend()` instances. **Explicit application constructor values
and explicit CLI flags always win** over saved defaults; per-object styling
overrides always win over inherited theme values. A ContextVar theme/text
selection overrides the persisted process default. Invalid config files
produce actionable errors instead of silently replacing user data.

The native event loop uses the configured callback budget, read once at
Activity startup; restart an App to apply edits to event-loop scheduling.
`Clock.tick()` remains explicitly adjustable. This facility does not give unsupported
Android APIs arbitrary hardware FPS, color-depth, or true window inset data.

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
