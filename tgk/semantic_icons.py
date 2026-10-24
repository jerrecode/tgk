"""Purpose-built, deterministic SVG paths for operational and UI icons.

Paths use a 24x24 local coordinate system, scaled to the 64x64 icon catalog.
Only file/directory classifications use a shared document/folder template.
No Unicode icon fonts, network assets, generic action badges or executable SVG.
"""
from __future__ import annotations

from html import escape

# Bump when generated SVG geometry materially changes. Install upgrades only
# untouched TGK-owned catalogs; user-customized catalogs remain intact.
ICON_GEOMETRY_REVISION = 3

# Individual line-art motifs. Deliberately distinct from file-extension recipes.
_PATHS = {
    "select": "M4 12L9 17L20 6 M3 3H21V21H3Z",
    "selected": "M3 4H21V20H3Z M6 12L10 16L18 8",
    "unselected": "M4 4H20V20H4Z",
    "select_all": "M6 5H20V19H6Z M2 9V2H16 M9 12L12 15L17 9",
    "select_none": "M6 5H20V19H6Z M2 9V2H16 M9 12H17",
    "invert_selection": "M4 4H12V12H4Z M12 12H20V20H12Z M15 3L19 3L19 7 M9 21H5V17",
    "copy": "M9 7V3H17L21 7V16H16 M17 3V7H21 M3 8H11L15 12V22H3Z M11 8V12H15",
    "paste": "M9 4H15V6H19V21H5V6H9Z M9 3H15V8H9Z M9 12H15 M9 16H15",
    "cut": "M9 7A3 3 0 1 1 3 7A3 3 0 0 1 9 7 M9 17A3 3 0 1 1 3 17A3 3 0 0 1 9 17 M9 9L20 21 M9 15L20 3 M16 17L20 21",
    "move": "M12 2V22 M2 12H22 M8 6L12 2L16 6 M8 18L12 22L16 18 M6 8L2 12L6 16 M18 8L22 12L18 16",
    "pack": "M4 9H20V21H4Z M4 9L8 3H16L20 9 M12 3V16 M9 13L12 16L15 13",
    "unpack": "M4 8H20V21H4Z M4 8L8 3H16L20 8 M12 16V3 M9 6L12 3L15 6",
    "copy_to": "M3 4H12V15H3Z M8 9H17V20H8Z M17 4H22 M19 2L22 4L19 6",
    "move_to": "M3 4H12V15H3Z M8 9H17V20H8Z M16 4H22 M19 1L22 4L19 7",
    "search": "M11 4A7 7 0 1 0 11 18A7 7 0 1 0 11 4 M16 16L22 22",
    "search_replace": "M10 3A7 7 0 1 0 10 17A7 7 0 1 0 10 3 M15 16L20 21 M17 5H22L20 3 M22 5L19 8",
    "check": "M4 12L9 17L20 6",
    "wrong": "M5 5L19 19 M19 5L5 19 M3 3H21V21H3Z",
    "close": "M5 5L19 19 M19 5L5 19",
    "filter_clear": "M2 3H17L12 10V17L8 20V10Z M16 15L22 21 M22 15L16 21",
    "proceed": "M3 12H21 M14 5L21 12L14 19",
    "run": "M3 4H21V20H3Z",
    "loading": "M12 2A10 10 0 0 1 22 12 M12 22A10 10 0 0 1 2 12 M17 3L21 5L21 9",
    "loading_0": "M12 2A10 10 0 0 1 22 12 M19 8L22 12L23 8",
    "loading_1": "M22 12A10 10 0 0 1 12 22 M16 19L12 22L16 23",
    "loading_2": "M12 22A10 10 0 0 1 2 12 M5 16L2 12L1 16",
    "loading_3": "M2 12A10 10 0 0 1 12 2 M8 5L12 2L8 1",
    "home": "M3 11L12 3L21 11 M6 10V21H18V10 M10 21V14H14V21",
    "delete": "M4 6H20 M9 6V4H15V6 M6 6L7 21H17L18 6 M10 10V17 M14 10V17",
    "rename": "M3 5H13V9 M8 5V19 M3 15V19H13 M16 19L21 14L19 12L14 17L13 21Z",
    "undo": "M9 4L3 10L9 16 M3 10H13A7 7 0 0 1 20 17",
    "redo": "M15 4L21 10L15 16 M21 10H11A7 7 0 0 0 4 17",
    "save": "M4 3H18L21 6V21H3V3Z M7 3V10H17V3 M7 21V14H17V21",
    "save_as": "M3 3H17L20 6V13 M6 3V9H16V3 M7 21H4V3 M13 20L20 13L23 16L16 23H13Z",
    "open": "M5 20V5H15 M9 9H21V21H9 M13 3H21V11 M21 3L11 13",
    "settings": "M12 3V6 M12 18V21 M3 12H6 M18 12H21 M5.5 5.5L8 8 M16 16L18.5 18.5 M18.5 5.5L16 8 M8 16L5.5 18.5 M17 12A5 5 0 1 1 7 12A5 5 0 0 1 17 12",
    "info": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M12 10V17 M12 7V7.5",
    "warning": "M12 2L23 21H1Z M12 9V14 M12 18V18.5",
    "error": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M12 7V14 M12 18V18.5",
    "help": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M9 9A3 3 0 1 1 14 11L12 13V15 M12 18V18.5",
    "plus": "M12 4V20 M4 12H20",
    "minus": "M4 12H20",
    "edit": "M3 21L8 20L21 7L17 3L4 16Z M14 6L18 10",
    "refresh": "M20 10A8 8 0 0 0 6 6 M4 14A8 8 0 0 0 18 18",
    "download": "M12 3V16 M7 11L12 16L17 11 M4 18V21H20V18",
    "upload": "M12 17V4 M7 9L12 4L17 9 M4 18V21H20V18",
    "share": "M7 12L17 6 M7 12L17 18 M6 9A3 3 0 1 1 6 15A3 3 0 0 1 6 9 M19 3A3 3 0 1 1 19 9A3 3 0 0 1 19 3 M19 15A3 3 0 1 1 19 21A3 3 0 0 1 19 15",
    "pin": "M9 3H18L16 9L20 13H4L8 9L6 3Z M12 13V22",
    "unpin": "M9 3H18L16 9L20 13H4L8 9L6 3Z M12 13V22 M3 3L21 21",
    "lock": "M5 10H19V21H5Z M8 10V7A4 4 0 0 1 16 7V10 M12 14V17",
    "unlock": "M5 10H19V21H5Z M8 10V7A4 4 0 0 1 16 7 M12 14V17",
    "filter": "M3 4H21L14 12V20L10 22V12Z",
    "sort": "M7 4V20 M3 8L7 4L11 8 M17 20V4 M13 16L17 20L21 16",
    "sort_ascending": "M6 19V5 M2 9L6 5L10 9 M14 8H21 M14 12H19 M14 16H17",
    "sort_descending": "M6 5V19 M2 15L6 19L10 15 M14 8H17 M14 12H19 M14 16H21",
    "expand": "M5 8L12 15L19 8",
    "chevron_left": "M15 4L7 12L15 20",
    "chevron_right": "M9 4L17 12L9 20",
    "collapse": "M5 15L12 8L19 15",
    "left": "M19 12H5 M12 5L5 12L12 19",
    "right": "M5 12H19 M12 5L19 12L12 19",
    "up": "M12 20V4 M5 11L12 4L19 11",
    "down": "M12 4V20 M5 13L12 20L19 13",
    "close_window": "M4 4H20V20H4Z M16 8L8 16 M8 8L16 16",
    "power": "M12 2V12 M6 5A9 9 0 1 0 18 5",
    "drag": "M12 2V22 M2 12H22 M8 6L12 2L16 6 M8 18L12 22L16 18 M6 8L2 12L6 16 M18 8L22 12L18 16",
    "resize": "M5 9V5H9 M15 5H19V9 M5 15V19H9 M15 19H19V15 M5 5L10 10 M19 19L14 14",
    "maximize": "M4 4H20V20H4Z M4 9H20",
    "minimize": "M4 4H20V20H4Z M9 16H15",
    "window": "M3 4H21V20H3Z M3 9H21 M6 6H6.5 M9 6H9.5",
    "popup": "M2 7H16V21H2Z M8 3H22V17H17 M6 11H12",
    "overlay": "M2 4H17V17H2Z M7 9H22V22H7Z",
    "tabs": "M2 5H8L10 8H22V20H2Z M10 5H16L18 8",
    "layers": "M12 2L22 8L12 14L2 8Z M2 12L12 18L22 12 M2 16L12 22L22 16",
    "menu": "M3 5H21 M3 12H21 M3 19H21",
    "more": "M5 12H5.5 M12 12H12.5 M19 12H19.5",
    "more_vertical": "M12 5V5.5 M12 12V12.5 M12 19V19.5",
    "grid": "M3 3H10V10H3Z M14 3H21V10H14Z M3 14H10V21H3Z M14 14H21V21H14Z",
    "columns": "M3 3H21V21H3Z M10 3V21 M17 3V21",
    "play": "M8 4L20 12L8 20Z",
    "pause": "M7 4H10V20H7Z M14 4H17V20H14Z",
    "stop": "M5 5H19V19H5Z",
    "next": "M5 4L16 12L5 20Z M19 4V20",
    "previous": "M19 4L8 12L19 20Z M5 4V20",
    "fast_forward": "M3 5L12 12L3 19Z M12 5L21 12L12 19Z",
    "fast_backward": "M21 5L12 12L21 19Z M12 5L3 12L12 19Z",
    "step_forward": "M5 5L15 12L5 19Z M19 5V19",
    "step_backward": "M19 5L9 12L19 19Z M5 5V19",
    "gallery": "M3 4H21V20H3Z M3 16L8 11L12 15L16 10L21 16 M8 8A1 1 0 1 1 6 8A1 1 0 0 1 8 8",
    "video": "M3 5H17V19H3Z M17 10L22 7V17L17 14Z M8 9L13 12L8 15Z",
    "audio": "M4 9H9L14 5V19L9 15H4Z M17 9A5 5 0 0 1 17 15",
    "playlist": "M3 5H18 M3 10H18 M3 15H12 M16 14L22 17L16 20Z",
    "catalogue": "M3 4H11L12 6L13 4H21V20H13L12 22L11 20H3Z M12 6V22 M5 9H9 M15 9H19",
    "dictionary": "M4 3H18V20H4A2 2 0 0 1 4 16Z M4 16H18 M8 7H14 M11 7V13 M8 13H14",
    "repeat": "M5 8V6A3 3 0 0 1 8 3H18L21 6 M17 6H21V2 M19 16V18A3 3 0 0 1 16 21H6L3 18 M7 18H3V22",
    "repeat_one": "M5 8V6A3 3 0 0 1 8 3H18L21 6 M17 6H21V2 M19 16V18A3 3 0 0 1 16 21H6L3 18 M7 18H3V22 M12 9V16 M10 11L12 9",
    "repeat_off": "M5 8V6A3 3 0 0 1 8 3H18L21 6 M17 6H21V2 M19 16V18A3 3 0 0 1 16 21H6L3 18 M7 18H3V22 M3 3L21 21",
    "shuffle": "M3 5H7L17 19H21 M17 15L21 19L17 23 M3 19H7L17 5H21 M17 1L21 5L17 9",
    "shuffle_off": "M3 5H7L17 19H21 M17 15L21 19L17 23 M3 19H7L17 5H21 M17 1L21 5L17 9 M3 3L21 21",
    "mute": "M3 9H8L13 5V19L8 15H3Z M17 9L22 15 M22 9L17 15",
    "headphones": "M4 13V12A8 8 0 0 1 20 12V13 M4 12H8V20H4Z M16 12H20V20H16Z",
    "microphone": "M9 4A3 3 0 0 1 15 4V13A3 3 0 0 1 9 13Z M5 12A7 7 0 0 0 19 12 M12 19V22 M8 22H16",
    "record": "M12 3A9 9 0 1 1 12 21A9 9 0 1 1 12 3 M12 7A5 5 0 1 1 12 17A5 5 0 1 1 12 7",
    "camera": "M3 7H7L9 4H15L17 7H21V20H3Z M12 9A4 4 0 1 1 12 17A4 4 0 1 1 12 9",
    "crop": "M6 2V18H22 M2 6H18V22",
    "rotate": "M21 11A9 9 0 1 0 12 21 M21 5V11H15",
    "mirror": "M12 2V22 M3 7L9 4V20L3 17Z M21 7L15 4V20L21 17Z",
    "aspect": "M2 6H22V18H2Z M7 10L11 14 M11 10L7 14",
    "picture_in_picture": "M2 4H22V20H2Z M12 11H20V18H12Z",
    "zoom_in": "M10 3A7 7 0 1 1 10 17A7 7 0 1 1 10 3 M15 15L22 22 M10 6V14 M6 10H14",
    "zoom_out": "M10 3A7 7 0 1 1 10 17A7 7 0 1 1 10 3 M15 15L22 22 M6 10H14",
    "zoom_reset": "M10 3A7 7 0 1 1 10 17A7 7 0 1 1 10 3 M15 15L22 22 M10 7V13 M7 10H13",
    "zoom_fit": "M2 9V2H9 M15 2H22V9 M2 15V22H9 M15 22H22V15 M6 6L10 10 M18 18L14 14",
    "focus": "M3 9V3H9 M15 3H21V9 M3 15V21H9 M15 21H21V15 M9 12H15 M12 9V15",
    "fullscreen": "M3 9V3H9 M15 3H21V9 M3 15V21H9 M15 21H21V15",
    "fullscreen_exit": "M9 3V9H3 M15 3V9H21 M9 21V15H3 M15 21V15H21",
    "canvas": "M3 3H21V21H3Z M7 17L11 12L14 15L18 9 M7 7H7.5",
    "ruler": "M3 7L17 3L21 17L7 21Z M8 6L10 10 M12 5L14 8 M6 10L9 12",
    "measure": "M3 12H21 M7 8L3 12L7 16 M17 8L21 12L17 16",
    "align_left": "M4 3V21 M7 6H20 M7 11H15 M7 16H18",
    "align_center": "M12 3V21 M4 6H20 M7 11H17 M5 16H19",
    "align_right": "M20 3V21 M4 6H17 M9 11H17 M6 16H17",
    "align_top": "M3 4H21 M7 7V20 M12 7V16 M17 7V18",
    "align_bottom": "M3 20H21 M7 4V17 M12 8V17 M17 6V17",
    "align_middle": "M3 12H21 M7 3V21 M12 5V19 M17 3V21",
    "justify": "M3 5H21 M3 10H21 M3 15H21 M3 20H21",
    "eye": "M2 12Q12 1 22 12Q12 23 2 12Z M12 8A4 4 0 1 1 12 16A4 4 0 1 1 12 8",
    "eye_off": "M2 12Q12 1 22 12Q12 23 2 12Z M12 8A4 4 0 1 1 12 16A4 4 0 1 1 12 8 M3 3L21 21",
    "portrait": "M7 2H17V22H7Z M10 19H14",
    "landscape": "M2 7H22V17H2Z M10 14H14",
    "rotate_left": "M3 11A9 9 0 1 1 12 21 M3 5V11H9",
    "theme": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M12 2V22 M2 12H12",
    "palette": "M12 2A10 10 0 1 0 12 22H14A2 2 0 0 0 16 18A2 2 0 0 1 18 16H20A4 4 0 0 0 22 12A10 10 0 0 0 12 2 M7 10V10.5 M11 6V6.5 M17 9V9.5",
    "color_picker": "M13 5L19 11 M9 18L19 8L16 5L6 15L5 21L11 20Z M9 16H13",
    "font": "M4 21L11 3H13L20 21 M7 14H17",
    "font_size": "M4 20L9 5H11L16 20 M6 15H14 M20 4V20 M17 7L20 4L23 7 M17 17L20 20L23 17",
    "bold": "M6 3H14A5 5 0 0 1 14 13H6Z M6 13H15A4 4 0 0 1 15 21H6Z",
    "italic": "M11 3H19 M5 21H13 M15 3L9 21",
    "underline": "M7 3V13A5 5 0 0 0 17 13V3 M5 21H19",
    "strikethrough": "M8 4H18 M12 4C4 4 5 11 13 12C22 14 20 20 6 20 M3 12H21",
    "text_wrap": "M3 5H21 M3 10H21 M3 15H18A3 3 0 1 1 18 21H13 M16 18L13 21L16 24",
    "ui_scale": "M3 10V3H10 M14 3H21V10 M3 14V21H10 M14 21H21V14 M3 3L9 9 M21 21L15 15",
    "brightness": "M12 2V5 M12 19V22 M2 12H5 M19 12H22 M5 5L7 7 M17 17L19 19 M19 5L17 7 M7 17L5 19 M12 7A5 5 0 1 1 12 17A5 5 0 1 1 12 7",
    "contrast": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M12 2V22",
    "opacity": "M12 2C8 9 4 12 4 16A8 8 0 0 0 20 16C20 12 16 9 12 2Z M12 5V23",
    "border": "M3 3H21V21H3Z M7 7H17V17H7Z",
    "tree": "M4 3H10V8H4Z M12 5H18V10H12Z M12 15H18V20H12Z M10 6H11V18H12",
    "timeline": "M4 12H20 M6 9V15 M12 9V15 M18 9V15",
    "breadcrumb": "M4 5L11 12L4 19 M13 5L20 12L13 19",
    "bookmark": "M5 3H19V22L12 17L5 22Z",
    "star": "M12 2L15 9L23 9L17 14L19 22L12 18L5 22L7 14L1 9L9 9Z",
    "notification": "M6 17H18L16 14V10A4 4 0 0 0 8 10V14Z M10 20A2 2 0 0 0 14 20",
    "calendar": "M3 5H21V21H3Z M3 10H21 M8 2V7 M16 2V7 M7 14H10 M14 14H17",
    "clock": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M12 6V12L17 15",
    "keyboard": "M2 5H22V19H2Z M5 8H6 M9 8H10 M13 8H14 M17 8H18 M5 11H6 M9 11H10 M13 11H14 M17 11H18 M7 15H17",
    "mouse": "M8 2H16V22H8Z M12 2V11",
    "touch": "M12 2V15 M9 10A3 3 0 0 1 15 10 M12 15L8 12A2 2 0 0 0 5 15L9 22H18L21 16L17 12",
    "wifi": "M2 9Q12 0 22 9 M5 13Q12 7 19 13 M9 17Q12 14 15 17 M12 21V21.5",
    "network": "M12 3V10 M12 10L4 18 M12 10L20 18 M12 3A2 2 0 1 1 12 7A2 2 0 1 1 12 3 M4 17A2 2 0 1 1 4 21A2 2 0 1 1 4 17 M20 17A2 2 0 1 1 20 21A2 2 0 1 1 20 17",
    "cloud": "M6 19H19A4 4 0 0 0 19 11A7 7 0 0 0 5 12A4 4 0 0 0 6 19",
    "offline": "M3 3L21 21 M6 10Q12 5 18 10 M9 14Q12 12 15 14 M12 19V19.5",
    "online": "M12 2A10 10 0 1 1 12 22A10 10 0 1 1 12 2 M12 8A4 4 0 1 1 12 16A4 4 0 1 1 12 8",
}
_PATHS["sync"] = _PATHS["copy"]
# Accented secondary geometry where it improves readability without changing
# the fundamental pictogram (e.g. refresh arrows and terminal prompt).
_ACCENTS = {
    "refresh": "M6 2V6H10 M18 22V18H14",
    "run": "M6 9L10 12L6 15 M12 16H18",
}
# All action/navigation/media/view names must explicitly select a pictogram.
# Aliases share geometry only for the same concrete physical action.
_ICON_MOTIF: dict[str, str] = {}

def _assign(motif: str, names: str) -> None:
    if motif not in _PATHS:
        raise RuntimeError("missing icon geometry: " + motif)
    for name in names.split():
        _ICON_MOTIF[name] = motif

_assign("select", "select")
_assign("selected", "selected")
_assign("unselected", "unselected")
_assign("select_all", "select_all")
_assign("select_none", "select_none")
_assign("invert_selection", "invert_selection")
_assign("copy", "copy")
_assign("paste", "paste")
_assign("cut", "cut")
_assign("move", "move drag grab pan")
_assign("pack", "pack")
_assign("unpack", "unpack")
_assign("copy_to", "copy_to")
_assign("move_to", "move_to")
_assign("search", "search inspect")
_assign("search_replace", "search_replace")
_assign("check", "confirm acknowledge correct success")
_assign("wrong", "wrong")
_assign("close", "cancel close")
_assign("filter_clear", "filter_clear")
_assign("proceed", "proceed continue goto")
_assign("run", "run terminal console")
_assign("loading", "loading")
_assign("loading_0", "loading_0")
_assign("loading_1", "loading_1")
_assign("loading_2", "loading_2")
_assign("loading_3", "loading_3")
_assign("home", "home")
_assign("delete", "delete")
_assign("rename", "rename")
_assign("undo", "undo history")
_assign("redo", "redo")
_assign("save", "save")
_assign("save_as", "save_as")
_assign("open", "open external_link web_link")
_assign("settings", "settings")
_assign("info", "info properties")
_assign("warning", "warning")
_assign("error", "error")
_assign("help", "help")
_assign("plus", "add new")
_assign("minus", "remove")
_assign("edit", "edit")
_assign("refresh", "refresh reload")
_assign("download", "download")
_assign("upload", "upload")
_assign("share", "share")
_assign("pin", "pin")
_assign("unpin", "unpin")
_assign("lock", "lock")
_assign("unlock", "unlock")
_assign("filter", "filter")
_assign("sort", "sort")
_assign("sort_ascending", "sort_ascending")
_assign("sort_descending", "sort_descending")
_assign("expand", "expand dropdown")
_assign("chevron_right", "dropright")
_assign("collapse", "collapse dropup")
_assign("chevron_left", "dropleft")
_assign("power", "exit")
_assign("resize", "resize")
_assign("maximize", "maximize")
_assign("minimize", "minimize")
_assign("window", "window")
_assign("popup", "popup")
_assign("overlay", "overlay")
_assign("tabs", "tab tabs")
_assign("layers", "layers")
_assign("menu", "menu")
_assign("more", "more")
_assign("more_vertical", "more_vertical")
_assign("grid", "grid")
_assign("columns", "columns")
_assign("play", "play")
_assign("pause", "pause")
_assign("stop", "stop")
_assign("next", "next last seek_end")
_assign("previous", "previous first seek_start")
_assign("fast_forward", "forward forward_two")
_assign("fast_backward", "backward back_two")
_assign("step_forward", "forward_one frame_forward")
_assign("step_backward", "back_one frame_backward")
_assign("gallery", "gallery images")
_assign("video", "videos")
_assign("audio", "audios speaker volume")
_assign("playlist", "playlist")
_assign("catalogue", "catalogue")
_assign("dictionary", "dictionary")
_assign("repeat", "repeat_all")
_assign("repeat_one", "repeat_one")
_assign("repeat_off", "repeat_off")
_assign("shuffle", "shuffle")
_assign("shuffle_off", "shuffle_off")
_assign("mute", "mute")
_assign("headphones", "headphones")
_assign("microphone", "microphone")
_assign("record", "record")
_assign("camera", "camera")
_assign("crop", "crop")
_assign("rotate", "rotate rotate_right")
_assign("mirror", "mirror")
_assign("aspect", "aspect_ratio")
_assign("picture_in_picture", "picture_in_picture")
_assign("zoom_in", "zoom_in")
_assign("zoom_out", "zoom_out")
_assign("zoom_reset", "zoom_reset")
_assign("zoom_fit", "zoom_fit")
_assign("fullscreen", "fullscreen")
_assign("fullscreen_exit", "fullscreen_exit")
_assign("focus", "focus coordinates")
_assign("canvas", "canvas")
_assign("ruler", "ruler")
_assign("measure", "measure")
_assign("align_left", "align_left")
_assign("align_center", "align_center center text_align")
_assign("align_right", "align_right")
_assign("align_top", "align_top")
_assign("align_bottom", "align_bottom")
_assign("align_middle", "align_middle")
_assign("justify", "justify")
_assign("eye", "eye visible")
_assign("eye_off", "eye_off hidden")
_assign("portrait", "portrait")
_assign("landscape", "landscape")
_assign("rotate_left", "rotate_left")
_assign("theme", "theme")
_assign("palette", "palette")
_assign("color_picker", "color_picker colorize")
_assign("font", "font")
_assign("font_size", "font_size")
_assign("bold", "bold")
_assign("italic", "italic")
_assign("underline", "underline")
_assign("strikethrough", "strikethrough")
_assign("text_wrap", "text_wrap")
_assign("ui_scale", "ui_scale gui_scale ux_scale")
_assign("brightness", "brightness")
_assign("contrast", "contrast")
_assign("opacity", "opacity")
_assign("border", "border")
_assign("left", "back left arrow_left")
_assign("chevron_left", "chevron_left")
_assign("right", "right arrow_right forward")
_assign("chevron_right", "chevron_right")
_assign("up", "up arrow_up")
_assign("collapse", "chevron_up")
_assign("down", "down arrow_down")
_assign("expand", "chevron_down")
_assign("grid", "dashboard grid_view")
_assign("menu", "list_view")
_assign("tree", "tree")
_assign("timeline", "timeline")
_assign("breadcrumb", "breadcrumb")
_assign("bookmark", "bookmark")
_assign("star", "star star_filled")
_assign("notification", "notification")
_assign("calendar", "calendar")
_assign("clock", "clock")
_assign("keyboard", "keyboard")
_assign("mouse", "mouse")
_assign("touch", "touch")
_assign("wifi", "wifi")
_assign("network", "network")
_assign("cloud", "cloud")
_assign("sync", "sync")
_assign("offline", "offline")
_assign("online", "online")
# Public read-only by convention; used by the icon builder and tests.
SEMANTIC_ICONS = frozenset(_ICON_MOTIF)


def render_semantic_svg(name: str, *, size: int = 64, stroke: str = "#D5EFFF",
                        accent: str = "#57DCED", background: str | None = None,
                        stroke_width: float = 1.7) -> str:
    """Render only an explicit vector icon; never substitute a generic badge."""
    from .theme import normalize_color
    if name not in _ICON_MOTIF:
        raise KeyError("no semantic geometry: " + str(name))
    if type(size) is not int or not 8 <= size <= 4096:
        raise ValueError("size out of range")
    if type(stroke_width) not in (int, float) or not 0 < stroke_width <= 32:
        raise ValueError("invalid stroke width")
    color = normalize_color(stroke)
    accent_color = normalize_color(accent)
    motif = _ICON_MOTIF[name]
    outline = _PATHS[motif]
    # Avoid any SVG markup outside fixed compiler-owned templates.
    result = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'width="{size}" height="{size}" role="img" '
        f'aria-label="{escape(name.replace("_", " "), quote=True)}">'
    ]
    if background is not None:
        result.append(f'<rect width="64" height="64" fill="{normalize_color(background)}"/>')
    result.append('<g transform="translate(4 4) scale(2.3333333333333335)" fill="none" '
                  f'stroke="{color}" stroke-width="{stroke_width:.12g}" '
                  'stroke-linecap="round" stroke-linejoin="round">')
    path_fill = color if name == "star_filled" else "none"
    result.append(f'<path d="{escape(outline, quote=True)}" fill="{path_fill}"/>')
    if motif in _ACCENTS:
        result.append(f'<path d="{escape(_ACCENTS[motif], quote=True)}" '
                      f'stroke="{accent_color}"/>')
    if motif == "sync":
        # Reuse the refresh pictogram at exactly one quarter size, clear of
        # both document silhouettes, rather than inventing another abbreviation.
        result.append('<g transform="translate(16.5 16.5) scale(0.25)" '
                      f'stroke="{accent_color}">')
        for data in (_PATHS["refresh"], _ACCENTS["refresh"]):
            result.append(f'<path d="{escape(data, quote=True)}"/>')
        result.append('</g>')
    result.append('</g></svg>')
    return ''.join(result)
