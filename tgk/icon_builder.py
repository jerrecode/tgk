"""Declarative, composable icon recipes and atomic SVG/raster asset generation.

A base icon can inherit another recipe, then draw reusable overlay layers.
Everything is parameterized 64x64 SVG commands; no bundled font binaries,
external images, network access, shell interpolation, or arbitrary XML inputs.

The low/mid/high PNG+JPEG and ICO export is optional. It requires CairoSVG
and Pillow; SVG generation uses only Python's standard library.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
from itertools import islice
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from xml.etree import ElementTree as ET


EXTENSIONS=(
    "txt","document","html","css","xml","json","yaml","toml","graph",
    "dot","htmx","js","java","py","pyc","pyo","jsonl","musicxml","ly",
    "c","h","tex","bib","md","mdbook","asciidoc","ascii","hex",
    "eeprom","bin","byte","mem","dat","data","geojson","info","help",
    "man","sh","bash","bat","ps1","kv","ts","tsx","jsx","sql","csv",
    "tsv","ini","cfg","conf","log","rst","pdf","svg","png","jpg",
    "mp3","wav","mp4","mkv","zip","tar","gz","deb","apk","so","h5",
    "zarr","nc","sqlite","db","gitignore","ipynb","lock"
)
SPECIAL_FILES={
    "README.md":"README","LICENSE":"LICENSE","INFO.md":"INFO",
    "AGENTS.md":"AGENTS","Makefile":"MAKE","requirements.txt":"REQ",
    "INSTALL.md":"INSTALL","Dockerfile":"DOCKER","pyproject.toml":"PROJECT",
    "package.json":"PACKAGE","CMakeLists.txt":"CMAKE",
}
_BASE_PATHS={
    "file":"M13 5H40L52 17V59H13Z M40 5V17H52",
    "folder":"M5 16H24L31 23H59V55H5Z",
    "document":"M13 5H40L52 17V59H13Z M40 5V17H52",
    "archive":"M13 5H40L52 17V59H13Z M40 5V17H52",
    "database":"M10 14C10 5 54 5 54 14V48C54 59 10 59 10 48Z M10 14C10 24 54 24 54 14 M10 30C10 40 54 40 54 30",
    "action":"M32 4L58 20V44L32 60L6 44V20Z",
    "image":"M11 8H53V56H11Z M14 47L24 34L34 43L42 31L51 45 M42 20A4 4 0 1 1 34 20A4 4 0 0 1 42 20",
    "video":"M8 14H46V52H8Z M46 26L59 18V48L46 40Z",
    "audio":"M22 17V46 M22 19L45 12V42 M22 46A7 4 0 1 1 8 46A7 4 0 0 1 22 46 M45 42A7 4 0 1 1 31 42A7 4 0 0 1 45 42",
    "play":"M18 9L51 32L18 55Z",
    "close":"M13 13L51 51 M51 13L13 51",
    "search":"M43 26A16 16 0 1 1 11 26A16 16 0 0 1 43 26 M42 42L56 56",
    "gear":"M32 8V16 M32 48V56 M8 32H16 M48 32H56 M15 15L21 21 M43 43L49 49 M49 15L43 21 M21 43L15 49 M44 32A12 12 0 1 1 20 32A12 12 0 0 1 44 32",
    "link":"M23 40L40 23 M28 17H41A13 13 0 0 1 41 43H37 M36 47H23A13 13 0 0 1 23 21H27",
}
_MOD_PATHS={
    "text":"M20 26H44 M20 32H44 M20 38H39 M20 44H43",
    "pen":"M37 51L49 39L56 46L44 58L35 60Z M47 41L52 36L59 43L54 48",
    "code":"M25 28L18 35L25 42 M39 28L46 35L39 42 M35 25L29 45",
    "zip":"M32 21V48 M29 26H35 M29 33H35 M29 40H35 M27 47H37V53H27Z",
    "lock":"M41 48V42A6 6 0 0 1 53 42V48 M39 48H55V59H39Z",
    "play":"M40 39L54 48L40 57Z",
    "arrow":"M37 44L52 29 M42 29H52V39",
    "check":"M37 48L43 55L57 38",
    "circle":"M46 46A8 8 0 1 1 30 46A8 8 0 0 1 46 46",
    "info":"M48 41V56 M48 36V37",
    "danger":"M47 36V49 M47 53V54",
    "music":"M41 36V53 M41 38L54 34V50 M41 53A5 3 0 1 1 31 53A5 3 0 0 1 41 53",
    "picture":"M34 41H57V58H34Z M36 55L43 45L49 52L53 48L56 54",
    "terminal":"M18 31L25 37L18 43 M28 43H39",
    "book":"M17 22H31L33 25L47 22V51L33 55L17 51Z M33 25V55",
}
_NAME=re.compile(r"^[a-z][a-z0-9_]{0,80}$")


@dataclass(frozen=True)
class Layer:
    kind:str
    value:str=""
    color:str|None=None
    def __post_init__(self):
        if self.kind not in ("path","modifier","label","badge"):
            raise ValueError("unsupported overlay kind")
        if not isinstance(self.value,str) or len(self.value)>120:
            raise ValueError("invalid overlay value")
        if self.kind=="modifier" and self.value not in _MOD_PATHS:
            raise ValueError("unknown modifier")


@dataclass(frozen=True)
class Recipe:
    name:str
    parent:str|None
    layers:tuple[Layer,...]=()
    def __post_init__(self):
        if not _NAME.fullmatch(self.name):raise ValueError("invalid recipe name")
        if self.parent is not None and not _NAME.fullmatch(self.parent):
            raise ValueError("invalid parent name")
        if len(self.layers)>16:raise ValueError("too many overlays")
        if not all(isinstance(z,Layer) for z in self.layers):
            raise TypeError("layers must contain Layer")


_RECIPES={
    key:Recipe(key,None) for key in _BASE_PATHS
}
_RECIPES.update({
    "file_text":Recipe("file_text","file",(Layer("modifier","text"),)),
    "file_code":Recipe("file_code","file",(Layer("modifier","code"),)),
    "file_document":Recipe("file_document","file_text",(Layer("modifier","pen"),)),
    "file_archive":Recipe("file_archive","file",(Layer("modifier","zip"),)),
    "file_lock":Recipe("file_lock","file",(Layer("modifier","lock"),)),
    "file_executable":Recipe("file_executable","file",(Layer("modifier","play"),)),
    "file_image":Recipe("file_image","file",(Layer("modifier","picture"),)),
    "file_audio":Recipe("file_audio","file",(Layer("modifier","music"),)),
    "file_shell":Recipe("file_shell","file_code",(Layer("modifier","terminal"),)),
    "folder_link":Recipe("folder_link","folder",(Layer("modifier","arrow"),)),
    "folder_lock":Recipe("folder_lock","folder",(Layer("modifier","lock"),)),
    "action_ok":Recipe("action_ok","action",(Layer("modifier","check"),)),
    "action_link":Recipe("action_link","action",(Layer("modifier","arrow"),)),
})

_FILE_CODES={"txt","md","rst","asciidoc","ascii","info","help","man"}
_CODE_CODES={"html","css","xml","json","yaml","toml","graph","dot","htmx",
    "js","java","py","pyc","pyo","jsonl","musicxml","ly","c","h","tex",
    "bib","mdbook","hex","eeprom","bin","byte","mem","dat","data",
    "geojson","sh","bash","bat","ps1","kv","ts","tsx","jsx","sql","ini",
    "cfg","conf","ipynb"}
_MEDIA_IMAGES={"svg","png","jpg"}
_MEDIA_VIDEO={"mp4","mkv"}
_MEDIA_AUDIO={"mp3","wav"}
_ARCHIVES={"zip","tar","gz","deb","apk"}
def _base_for_extension(ext):
    if ext in _ARCHIVES:return "file_archive"
    if ext in _MEDIA_IMAGES:return "file_image"
    if ext in _MEDIA_VIDEO:return "video"
    if ext in _MEDIA_AUDIO:return "file_audio"
    if ext in ("sqlite","db","h5","zarr","nc"):return "database"
    if ext in ("sh","bash","bat","ps1"):return "file_shell"
    if ext in _CODE_CODES:return "file_code"
    if ext in _FILE_CODES:return "file_text"
    return "file"


for _ext in EXTENSIONS:
    _key="file_ext_"+_ext
    _RECIPES[_key]=Recipe(_key,_base_for_extension(_ext),
                          (Layer("label",_ext.upper()),))
for _filename,_label in SPECIAL_FILES.items():
    _key="filename_"+_filename.lower().replace(".","_")
    _base="file_document" if _filename.lower().endswith(".md") else "file_code"
    _RECIPES[_key]=Recipe(_key,_base,(Layer("label",_label),))

def recipe_names(*,include_existing=True):
    """Stable set of programmable icons; no aliases are expanded recursively."""
    from .icons import ICONS
    keys=set(_RECIPES)
    from .semantic_icons import SEMANTIC_ICONS
    keys.update(SEMANTIC_ICONS)
    if include_existing:keys.update(ICONS)
    return tuple(sorted(keys))


def recipe_for(name):
    if not isinstance(name,str) or not _NAME.fullmatch(name):
        raise ValueError("invalid icon name")
    from .semantic_icons import SEMANTIC_ICONS
    if name in SEMANTIC_ICONS:
        return Recipe(name, None)  # independently drawn, no inherited action badge
    if name in _RECIPES:return _RECIPES[name]
    from .icons import CATEGORIES
    for group,names in CATEGORIES.items():
        if name not in names:continue
        if group=="directories":
            if name=="folder_open":return Recipe(name,"folder",(Layer("modifier","arrow"),))
            suffix=name.removeprefix("folder_").upper()
            return Recipe(name,"folder",(Layer("badge",suffix[:8]),))
        if group=="files":
            if name in ("file","file_text","document","database","image","video","audio","code"):
                parent={"document":"file_document","image":"file_image",
                        "code":"file_code"}.get(name,"file")
                return Recipe(name,parent)
            if name in ("zip","tar","archive","gzip","rar"):
                return Recipe(name,"file_archive")
            if name in ("shell","executable"):return Recipe(name,"file_shell")
            ext_alias={"python":"py","javascript":"js","header":"h","markdown":"md",
                       "makefile":"make","binary":"bin","hdf5":"h5",
                       "netcdf":"nc","sqlite":"sqlite"}
            extension=ext_alias.get(name,name)
            if extension in EXTENSIONS:return Recipe(name,"file_ext_"+extension)
            return Recipe(name,"file",(Layer("badge",name[:3].upper()),))
        if name in _BASE_PATHS:return _RECIPES[name]
        if group=="media" and name in ("play","pause","stop"):
            return Recipe(name,"action",(Layer("badge",name[:3].upper()),))
        return Recipe(name,"action",(Layer("badge",name[:3].upper()),))
    raise KeyError("unknown icon: "+name)


def _resolve_layers(name,stack=()):
    if name in stack:raise ValueError("icon inheritance cycle")
    if len(stack)>32:raise ValueError("icon recipe depth exceeded")
    recipe=recipe_for(name)
    if recipe.parent is None:
        if name not in _BASE_PATHS:raise ValueError("unknown base: "+name)
        return name,recipe.layers
    base,layers=_resolve_layers(recipe.parent,stack+(name,))
    return base,layers+recipe.layers


def _path(d,stroke):
    return f'<path d="{escape(d,quote=True)}" fill="none" stroke="{stroke}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'


def _text(value,*,x=32,y=37,max_width=29,max_height=12,color="#0C2236FF"):
    """Bound label inside a document's fold-safe inner content rectangle."""
    value=value.upper()
    if not re.fullmatch(r"[A-Z0-9_+<>-]{1,20}",value):
        raise ValueError("icon label must be uppercase ASCII")
    font=min(10.0,max(3.2,max_width/max(1,len(value)*.64)))
    return (f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="sans-serif" font-weight="700" font-size="{font:.2f}" '
            f'fill="{color}" stroke="none">{escape(value)}</text>')


def render_svg(name,*,size=64,stroke="#D5EFFF",fill="#152A48",
               accent="#57DCED",background=None):
    """Compile layered base/modifier recipes into a safe self-contained SVG."""
    from .theme import normalize_color
    if type(size) is not int or not 8<=size<=4096:raise ValueError("size out of range")
    stroke=normalize_color(stroke)
    fill=normalize_color(fill)
    accent=normalize_color(accent)
    from .semantic_icons import SEMANTIC_ICONS, render_semantic_svg
    if name in SEMANTIC_ICONS:
        return render_semantic_svg(name,size=size,stroke=stroke,
                                   accent=accent,background=background)
    base,layers=_resolve_layers(name)
    pieces=[
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'width="{size}" height="{size}" role="img" aria-label="{escape(name.replace("_"," "),quote=True)}">',
    ]
    if background is not None:
        color=normalize_color(background)
        pieces.append(f'<rect width="64" height="64" fill="{color}"/>')
    pieces.append(f'<path d="{escape(_BASE_PATHS[base],quote=True)}" stroke="{stroke}" '
                  f'stroke-width="2.6" stroke-linejoin="round" fill="{fill}"/>')
    for layer in layers:
        color=normalize_color(layer.color) if layer.color is not None else accent
        if layer.kind=="modifier":
            pieces.append(_path(_MOD_PATHS[layer.value],color))
        elif layer.kind=="path":
            # Paths from user recipes must be explicit SVG path commands,
            # without XML markup, URL references or attribute injection.
            if not re.fullmatch(r"[0-9eE.,+\-\sMLCQAZHVSTmlcqazhvst]+",layer.value):
                raise ValueError("invalid SVG path command")
            pieces.append(_path(layer.value,color))
        elif layer.kind=="label":
            # A contrasting rounded background keeps codes legible on a
            # filled file; fit text within x=17..47 with a 3dp interior margin.
            pieces.append('<rect x="16" y="28" width="32" height="17" rx="3" '
                          f'fill="{accent}" stroke="none"/>')
            pieces.append(_text(layer.value,x=32,y=37,max_width=27,color="#07182CFF"))
        elif layer.kind=="badge":
            pieces.append(f'<rect x="32" y="42" width="28" height="18" rx="5" fill="{accent}" '
                          f'stroke="{stroke}" stroke-width="1.8"/>')
            pieces.append(_text(layer.value,x=46,y=51,max_width=25,
                                color="#07182CFF"))
    pieces.append("</svg>")
    result="".join(pieces)
    ET.fromstring(result)
    return result


def asset_key_for_path(path,is_dir=None):
    """Prefer filename/extension-specific recipes while keeping icon_for_path stable."""
    path=Path(path)
    name=path.name
    if is_dir is None:is_dir=path.is_dir()
    if is_dir:
        from .icons import icon_for_path
        return icon_for_path(path,is_dir=True)
    special="filename_"+name.lower().replace(".","_")
    if special in _RECIPES:return special
    if name.lower().endswith((".tar.gz",".tar.xz",".tar.bz2",".tar.zst")):
        return "file_ext_tar"
    ext=path.suffix.lower().lstrip(".")
    if ext in EXTENSIONS:return "file_ext_"+ext
    return "file_code" if ext in ("pl","rb","php","swift") else "file"


def _raster_backend():
    try:
        import cairosvg
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Raster export requires cairosvg and Pillow: "
                           "python -m pip install cairosvg pillow") from exc
    return cairosvg,Image


class CatalogChangedError(RuntimeError):
    """An automatic replacement was cancelled to preserve concurrent edits."""


def build_assets(output_root,*,names=None,raster=None,overwrite=False,
                 low=None,mid=None,high=None,max_icons=None,_replace_guard=None):
    """Build EVERYTHING in staging first; atomically publish only on success.

    output_root/icons/{svg,ico,low_res,mid_res,high_res}. The raster folders
    exist but remain empty for a deterministic SVG-only run.
    An internal automatic-upgrade guard validates the moved old directory;
    guarded successful replacements retain it for already-open editor handles.
    """
    from .config import load_config
    if _replace_guard is not None and not callable(_replace_guard):
        raise TypeError("replacement guard must be callable")
    configured=load_config()["icons"]
    raster=configured["raster"] if raster is None else raster
    if type(raster) is not bool:raise ValueError("raster must be boolean")
    low=configured["low"] if low is None else low
    mid=configured["mid"] if mid is None else mid
    high=configured["high"] if high is None else high
    max_icons=configured["max_icons"] if max_icons is None else max_icons
    if type(max_icons) is not int or not 1<=max_icons<=5000:        raise ValueError("max_icons must be in 1..5000")
    sizes=(low,mid,high)
    if any(type(z) is not int or not 8<=z<=1024 for z in sizes):
        raise ValueError("invalid icon sizes")
    if sizes!=tuple(sorted(set(sizes))):raise ValueError("sizes must increase")
    # Bound consumption before sorting/deduplication: even an infinite stream
    # of repeated valid names must not hang or grow memory without a limit.
    requested=tuple(islice(names if names is not None else recipe_names(),max_icons+1))
    if not requested or len(requested)>max_icons:
        raise ValueError("empty or oversized icon selection")
    if any(not isinstance(n,str) or not _NAME.fullmatch(n) for n in requested):
        raise ValueError("invalid icon name")
    selection=tuple(sorted(set(requested)))
    # Validate every requested recipe and all combinations before publication.
    vector_sources={name:render_svg(name) for name in selection}
    root=Path(output_root).expanduser()
    if not root.is_dir():raise FileNotFoundError(root)
    target=root/"icons"
    if target.is_symlink():raise ValueError("refuse to overwrite symlink output")
    if target.exists() and not target.is_dir():raise ValueError("icon output must be a directory")
    if target.exists() and not overwrite:raise FileExistsError(target)
    cairo,Image=_raster_backend() if raster else (None,None)
    stage=Path(tempfile.mkdtemp(prefix=".tgk-icons-stage-",dir=root))
    backup=None
    try:
        for dirname in ("svg","ico","low_res","mid_res","high_res"):
            (stage/dirname).mkdir()
        from .semantic_icons import ICON_GEOMETRY_REVISION
        manifest={"schema_version":1,"source":"tgk.icon_builder",
                  "geometry_revision":ICON_GEOMETRY_REVISION,
                  "icons":{},"files":{},"raster":raster,
                  "sizes":{"low":low,"mid":mid,"high":high}}
        for name,vector in vector_sources.items():
            svg_data=vector.encode("utf-8")
            (stage/"svg"/(name+".svg")).write_bytes(svg_data)
            manifest["icons"][name]={"svg_sha256":sha256(svg_data).hexdigest(),
                                     "inherits":recipe_for(name).parent,
                                     "overlays":[z.kind+":"+z.value
                                                 for z in recipe_for(name).layers]}
            if not raster:continue
            from io import BytesIO
            # Keep at most one raster surface live between resolutions.
            icon=None
            for category,pixels in (("low_res",low),("mid_res",mid),("high_res",high)):
                png=cairo.svg2png(bytestring=svg_data,output_width=pixels,
                                   output_height=pixels)
                (stage/category/(name+".png")).write_bytes(png)
                with Image.open(BytesIO(png)) as image:
                    with image.convert("RGBA") as rgba:
                        with Image.new("RGB",rgba.size,(248,250,254)) as rgb:
                            with rgba.getchannel("A") as alpha:
                                rgb.paste(rgba,mask=alpha)
                            rgb.save(stage/category/(name+".jpg"),"JPEG",quality=90,
                                     optimize=True,subsampling=0)
                        if category=="high_res":icon=rgba.copy()
            # Pillow drops requested ICO frames larger than the source.
            # For valid high<16 settings the old fixed list emitted a corrupt
            # six-byte header with zero frames. Always include a fitting frame.
            edge=min(high,256)
            ico_sizes=[(z,z) for z in (16,24,32,48,64) if z<=edge]
            if not ico_sizes:ico_sizes=[(edge,edge)]
            with icon:
                icon.save(stage/"ico"/(name+".ico"),format="ICO",sizes=ico_sizes)
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                data=path.read_bytes()
                manifest["files"][path.relative_to(stage).as_posix()]={
                    "sha256":sha256(data).hexdigest(),"bytes":len(data)}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2,
                                                sort_keys=True)+"\n",encoding="utf-8")
        # Recheck after potentially long raster generation. A competing
        # create-only installer must not silently replace a published catalog.
        if target.is_symlink():raise ValueError("refuse to overwrite symlink output")
        if target.exists():
            if not overwrite:raise FileExistsError(target)
            if not target.is_dir():raise ValueError("icon output must be a directory")
            backup=Path(tempfile.mkdtemp(prefix=".tgk-icons-backup-",dir=root))
            backup.rmdir()
            os.replace(target,backup)
        try:
            if _replace_guard is not None:
                if backup is None or not _replace_guard(backup):
                    raise CatalogChangedError("icon catalog changed during generation")
            os.replace(stage,target)
        except BaseException:
            if backup is not None:
                try:os.replace(backup,target)
                except OSError as exc:
                    raise RuntimeError("Could not restore original icons; retained at "+str(backup)) from exc
            raise
        stage=None
        if backup is not None and _replace_guard is None:shutil.rmtree(backup)
        result={"output":str(target),"count":len(selection),"raster":raster,
                "svg_files":len(selection),"png_files":len(selection)*3 if raster else 0,
                "jpeg_files":len(selection)*3 if raster else 0,
                "ico_files":len(selection) if raster else 0}
        if backup is not None and _replace_guard is not None:
            result["previous_output"]=str(backup)
        return result
    finally:
        if stage is not None and stage.exists():shutil.rmtree(stage)


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Build layered SVG/PNG/JPG/ICO icons atomically")
    parser.add_argument("--output",default=".",help="parent directory for icons/")
    parser.add_argument("--icon",action="append",dest="names",help="select specific recipe names")
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--raster",dest="raster",action="store_true",help="also export PNG/JPG/ICO (CairoSVG+Pillow)")
    mode.add_argument("--svg-only",dest="raster",action="store_false",help="override saved raster setting with SVG-only output")
    parser.set_defaults(raster=None)
    parser.add_argument("--overwrite",action="store_true",help="replace existing icons/ atomically")
    parser.add_argument("--low",type=int,default=None)
    parser.add_argument("--mid",type=int,default=None)
    parser.add_argument("--high",type=int,default=None)
    parser.add_argument("--max-icons",type=int,default=None)
    args=parser.parse_args(argv)
    result=build_assets(args.output,names=args.names,raster=args.raster,
                        overwrite=args.overwrite,low=args.low,mid=args.mid,
                        high=args.high,max_icons=args.max_icons)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
