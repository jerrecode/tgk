"""Semantic UI icon catalog, filename classification and self-contained SVG fallback.

Glyphs use Unicode and depend on installed Android fallback fonts. Vector icons
are provided for core navigation/actions using hand-written SVG geometry;
the remainder intentionally fall back to text glyphs with accessibility names.
No emoji/font binary files or remote resources are installed.
"""
from __future__ import annotations
from dataclasses import dataclass
from html import escape
from pathlib import Path
import re

_GROUPS={
 "files": {
  "file":"📄","file_text":"📃","document":"🗎","image":"▧","video":"▣","audio":"♫",
  "code":"⌘","json":"{}","jsonl":"≡","xml":"⌁","toml":"⚙","yaml":"☷",
  "binary":"▦","hex":"⬡","csv":"▤","tsv":"▥","table":"▦","list":"☷",
  "markdown":"ᴹ↓","pdf":"▣","python":"🐍","pyc":"⚙","kv":"◇","html":"⌘",
  "css":"✦","javascript":"JS","typescript":"TS","c":"C","header":"H",
  "cpp":"C++","java":"☕","rust":"⚙","go":"Go","asm":"⌘","makefile":"⚒",
  "sql":"▤","sqlite":"▤","mysql":"▤","postgres":"▤","mongodb":"▤","nosql":"▤",
  "hdf5":"▥","netcdf":"▥","zarr":"▥","database":"▤","dot":"•",
  "config":"⚙","shell":"$_","executable":"▶","iso":"◉","package":"▣",
  "deb":"▣","rpm":"▣","apk":"▣","archive":"▣","zip":"▣","rar":"▣",
  "tar":"▣","gzip":"▣","bzip":"▣","xz":"▣","zstd":"▣","seven_zip":"▣",
  "link":"↗","symlink":"↪","hardlink":"⇄","shortcut":"↗","lock":"▣",
  "log":"≡","ini":"⚙","properties":"⚙","csv_list":"☷",
 },
 "directories": {
  "folder":"📁","folder_open":"📂","folder_home":"⌂","folder_root":"/",
  "folder_bin":"⚙","folder_sbin":"⚙","folder_tmp":"⌛","folder_temp":"⌛",
  "folder_cache":"◌","folder_usr":"♙","folder_lib":"▣","folder_lib64":"▣",
  "folder_etc":"⚙","folder_var":"⋯","folder_opt":"◇","folder_dev":"⚙",
  "folder_proc":"◉","folder_sys":"⚙","folder_run":"▶","folder_boot":"↥",
  "folder_media":"▣","folder_mnt":"⇥","folder_data":"▥","folder_android":"▣",
  "folder_download":"⇩","folder_documents":"▤","folder_pictures":"▧",
  "folder_movies":"▣","folder_music":"♫","folder_desktop":"▣",
  "folder_git":"⑂","folder_python":"🐍","folder_node_modules":"◇",
  "folder_project":"⬡","folder_trash":"♻",
 },
 "actions": {
  "select":"☑","select_all":"☷","select_none":"□","invert_selection":"⇅",
  "selected":"☑","unselected":"□","copy":"⧉","paste":"▤","cut":"✂",
  "pack":"⇥","unpack":"⇤","copy_to":"⇥","move_to":"↪","move":"✥",
  "search":"⌕","search_replace":"⇆","confirm":"✓","acknowledge":"✓",
  "correct":"✓","wrong":"✗","cancel":"×","proceed":"→","continue":"→",
  "run":"▶","loading":"◌","loading_0":"◴","loading_1":"◷",
  "loading_2":"◶","loading_3":"◵","home":"⌂","delete":"⌫",
  "rename":"✎","undo":"↶","redo":"↷","save":"▣","save_as":"▣",
  "open":"↗","goto":"➜","external_link":"↗","web_link":"↗",
  "settings":"⚙","inspect":"⌕","properties":"☷","info":"ⓘ",
  "warning":"⚠","error":"!","success":"✓","help":"?",
  "add":"+","remove":"−","new":"+","edit":"✎","refresh":"⟳",
  "reload":"⟳","download":"⇩","upload":"⇧","share":"↗",
  "pin":"⌖","unpin":"⌖","lock":"▣","unlock":"▢","filter":"▽",
  "filter_clear":"×","sort":"⇅","sort_ascending":"↑","sort_descending":"↓",
  "expand":"⌄","collapse":"⌃","dropdown":"⌄","dropup":"⌃",
  "dropleft":"‹","dropright":"›","close":"×","exit":"⏻",
  "drag":"✥","grab":"✥","resize":"⤡","maximize":"□",
  "minimize":"_","window":"▣","popup":"▧","overlay":"▤",
  "tab":"▣","tabs":"▤","layers":"▱","menu":"☰",
  "more":"⋯","more_vertical":"⋮","grid":"▦","columns":"▥",
 },
 "media": {
  "play":"▶","pause":"Ⅱ","stop":"■","next":"⏭","previous":"⏮",
  "forward":"⏩","backward":"⏪","first":"⏮","last":"⏭",
  "forward_one":"→","forward_two":"≫","back_one":"←","back_two":"≪",
  "frame_forward":"▹|","frame_backward":"|◃","seek_start":"|◀",
  "seek_end":"▶|","gallery":"▧","catalogue":"☷","dictionary":"▤",
  "images":"▧","videos":"▣","audios":"♫","playlist":"☷",
  "repeat_one":"↻1","repeat_all":"↻","repeat_off":"×↻",
  "shuffle":"⇄","shuffle_off":"→","volume":"♫","mute":"×♫",
  "speaker":"◖","headphones":"♫","microphone":"♩","record":"●",
  "camera":"▣","crop":"□","rotate":"↻","mirror":"⇋",
  "aspect_ratio":"▭","picture_in_picture":"▣",
 },
 "view": {
  "zoom_in":"⊕","zoom_out":"⊖","zoom_reset":"⊙","zoom_fit":"⤢",
  "fullscreen":"⛶","fullscreen_exit":"▢","focus":"⌖",
  "pan":"✥","canvas":"▧","coordinates":"⌖","ruler":"┠",
  "measure":"↔","align_left":"≡","align_center":"≡",
  "align_right":"≡","align_top":"┬","align_bottom":"┴",
  "align_middle":"┼","justify":"☷","center":"⊙",
  "visible":"◉","hidden":"◌","eye":"◉","eye_off":"◌",
  "portrait":"▯","landscape":"▭","rotate_left":"↺",
  "rotate_right":"↻","theme":"◒","palette":"◉",
  "color_picker":"◉","colorize":"◉","font":"Aa","font_size":"A↕",
  "bold":"𝐁","italic":"𝑰","underline":"U̲","strikethrough":"S̶",
  "text_wrap":"↵","text_align":"≡","ui_scale":"⤡",
  "gui_scale":"⤡","ux_scale":"⤡","brightness":"☼",
  "contrast":"◐","opacity":"◌","border":"□",
 },
 "navigation": {
  "back":"←","forward":"→","up":"↑","down":"↓","left":"←","right":"→",
  "chevron_left":"‹","chevron_right":"›","chevron_up":"⌃","chevron_down":"⌄",
  "arrow_left":"←","arrow_right":"→","arrow_up":"↑","arrow_down":"↓",
  "dashboard":"▦","list_view":"☷","grid_view":"▦",
  "tree":"⑂","timeline":"─","breadcrumb":"›","history":"↶",
  "bookmark":"▣","star":"☆","star_filled":"★",
  "notification":"♧","calendar":"▦","clock":"◷",
  "terminal":"$_","console":"$_","keyboard":"⌨","mouse":"↖",
  "touch":"◉","wifi":"◉","network":"⋈","cloud":"☁",
  "sync":"⟳","offline":"◌","online":"●",
 }
}
ICONS={key:glyph for group in _GROUPS.values() for key,glyph in group.items()}
CATEGORIES={name:tuple(group) for name,group in _GROUPS.items()}
EXTENSION_ICONS={
 "txt":"file_text","md":"markdown","rst":"document","pdf":"pdf",
 "png":"image","jpg":"image","jpeg":"image","gif":"image","webp":"image","svg":"image",
 "avif":"image","bmp":"image","tif":"image","tiff":"image",
 "mp4":"video","mkv":"video","mov":"video","webm":"video","avi":"video",
 "mp3":"audio","flac":"audio","wav":"audio","ogg":"audio","m4a":"audio",
 "opus":"audio","mid":"audio","midi":"audio",
 "py":"python","pyc":"pyc","kv":"kv","sh":"shell","bash":"shell","zsh":"shell",
 "html":"html","htm":"html","css":"css","js":"javascript","mjs":"javascript",
 "ts":"typescript","tsx":"typescript","jsx":"javascript",
 "c":"c","h":"header","cc":"cpp","cpp":"cpp","hpp":"header",
 "rs":"rust","go":"go","java":"java","s":"asm","asm":"asm",
 "json":"json","jsonl":"jsonl","ndjson":"jsonl","xml":"xml","toml":"toml",
 "yaml":"yaml","yml":"yaml","csv":"csv","tsv":"tsv","sql":"sql",
 "db":"database","sqlite":"sqlite","sqlite3":"sqlite","h5":"hdf5",
 "hdf5":"hdf5","nc":"netcdf","zarr":"zarr",
 "zip":"zip","rar":"rar","tar":"tar","gz":"gzip","tgz":"tar",
 "bz2":"bzip","xz":"xz","zst":"zstd","7z":"seven_zip",
 "deb":"deb","rpm":"rpm","apk":"apk","iso":"iso",
 "exe":"executable","bin":"binary","so":"binary","a":"binary",
 "ini":"ini","conf":"config","cfg":"config","properties":"properties",
 "log":"log","patch":"code","diff":"code","lst":"list",
}
SPECIAL_FILENAMES={
 "makefile":"makefile","gnumakefile":"makefile","dockerfile":"config",
 "requirements.txt":"config","pyproject.toml":"toml","package.json":"json",
 ".gitignore":"config",".env":"config",".bashrc":"shell",".zshrc":"shell",
 "cmakelists.txt":"config",
}
SPECIAL_DIRS={
 "/":"folder_root","~":"folder_home","bin":"folder_bin","sbin":"folder_sbin",
 "tmp":"folder_tmp","temp":"folder_temp","cache":"folder_cache",
 "__pycache__":"folder_cache","home":"folder_home","usr":"folder_usr",
 "lib":"folder_lib","lib64":"folder_lib64","etc":"folder_etc","var":"folder_var",
 "opt":"folder_opt","dev":"folder_dev","proc":"folder_proc","sys":"folder_sys",
 "run":"folder_run","boot":"folder_boot","media":"folder_media","mnt":"folder_mnt",
 "data":"folder_data","android":"folder_android","downloads":"folder_download",
 "documents":"folder_documents","pictures":"folder_pictures","movies":"folder_movies",
 "music":"folder_music","desktop":"folder_desktop",".git":"folder_git",
 "node_modules":"folder_node_modules","projects":"folder_project",
 "trash":"folder_trash",
}
def glyph(name,default="file"):
    if name not in ICONS:
        if default not in ICONS:raise KeyError(name)
        return ICONS[default]
    return ICONS[name]

def icon_for_path(path,is_dir=None,*,detailed=False):
    if detailed:
        from .icon_builder import asset_key_for_path
        return asset_key_for_path(path,is_dir=is_dir)
    p=Path(path)
    if is_dir is None:is_dir=p.is_dir()
    name=p.name.casefold()
    if is_dir:
        if p.as_posix()=="/":return "folder_root"
        return SPECIAL_DIRS.get(name,"folder")
    if name in SPECIAL_FILENAMES:return SPECIAL_FILENAMES[name]
    if name.endswith((".tar.gz",".tar.bz2",".tar.xz",".tar.zst")):return "tar"
    if name.startswith(".") and not p.suffix:return "config"
    return EXTENSION_ICONS.get(p.suffix.lower().lstrip("."),"file")

def icon_names(category=None):
    if category is None:return tuple(sorted(ICONS))
    if category not in CATEGORIES:raise KeyError(category)
    return CATEGORIES[category]

# Self-contained path data for small vector previews, no external icon package.
_VECTORS={
 "file":"M6 2H15L21 8V22H6Z M15 2V8H21",
 "folder":"M2 6H9L12 9H22V21H2Z",
 "close":"M5 5L19 19 M19 5L5 19",
 "menu":"M3 5H21 M3 12H21 M3 19H21",
 "search":"M19 19L15 15 M17 10A7 7 0 1 1 3 10A7 7 0 0 1 17 10",
 "home":"M3 11L12 3L21 11 M6 10V21H18V10 M10 21V14H14V21",
 "settings":"M12 2V5 M12 19V22 M2 12H5 M19 12H22 M5 5L7 7 M17 17L19 19 M19 5L17 7 M7 17L5 19 M17 12A5 5 0 1 1 7 12A5 5 0 0 1 17 12",
 "play":"M6 3L21 12L6 21Z",
 "pause":"M7 4V20 M17 4V20",
 "stop":"M5 5H19V19H5Z",
 "add":"M12 3V21 M3 12H21",
 "remove":"M3 12H21",
 "back":"M20 12H4 M11 5L4 12L11 19",
 "forward":"M4 12H20 M13 5L20 12L13 19",
 "undo":"M10 6L4 12L10 18 M4 12H14A6 6 0 0 1 20 18",
 "redo":"M14 6L20 12L14 18 M20 12H10A6 6 0 0 0 4 18",
 "copy":"M8 7H21V22H8Z M3 2H16V7",
 "check":"M3 12L9 18L21 5",
 "delete":"M5 6H19 M9 6V4H15V6 M7 6L8 21H16L17 6",
 "zoom_in":"M19 19L15 15 M17 10A7 7 0 1 1 3 10A7 7 0 0 1 17 10 M10 6V14 M6 10H14",
 "zoom_out":"M19 19L15 15 M17 10A7 7 0 1 1 3 10A7 7 0 0 1 17 10 M6 10H14",
}
def svg(name,size=24,color="#FFFFFF",stroke=2):
    from .theme import normalize_color
    if type(size) is not int or not 8<=size<=1024:raise ValueError("invalid icon size")
    if type(stroke) not in (int,float) or not .5<=stroke<=8:raise ValueError("invalid stroke")
    fill=normalize_color(color)
    from .semantic_icons import SEMANTIC_ICONS, render_semantic_svg
    if name in SEMANTIC_ICONS:
        # Public stroke units belong to the original 24-unit SVG viewport.
        # Semantic geometry occupies 56/64 units, so compensate for its scale.
        return render_semantic_svg(name,size=size,stroke=fill,accent=fill,
                                   stroke_width=stroke*8/7)
    key={"folder_open":"folder","file_text":"file","image":"file","video":"file",
         "audio":"file","previous":"back","next":"forward","cancel":"close",
         "confirm":"check","zoom_reset":"search"}.get(name,name)
    if key not in _VECTORS:
        from .icon_builder import render_svg
        try:
            return render_svg(name,size=size,stroke=fill)
        except (KeyError,ValueError) as exc:
            raise KeyError("vector not available: "+name) from exc
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'width="{size}" height="{size}" fill="none" stroke="{fill}" '
            f'stroke-width="{stroke:g}" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="{_VECTORS[key]}"/></svg>')

@dataclass(frozen=True)
class Icon:
    name:str
    size:int=20
    color:str|None=None
    def __post_init__(self):
        if self.name not in ICONS:raise ValueError("unknown icon: "+self.name)
        if type(self.size) is not int or not 8<=self.size<=128:
            raise ValueError("icon size must be 8..128")
        if self.color is not None:
            from .theme import normalize_color
            normalize_color(self.color)
    @property
    def text(self):return glyph(self.name)
