"""Persistent, versioned TGK defaults with safe create-only installation.

User files live in ${TGK_CONFIG_HOME} or ${XDG_CONFIG_HOME:-~/.config}/tgk.
Explicit instance args and CLI flags always override these defaults.
The module performs NO filesystem writes on import or runtime reads.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re


SCHEMA_VERSION=1
MAX_JSON_BYTES=512*1024
DEFAULT_CONFIG={
    "schema_version":SCHEMA_VERSION,
    "ui":{"theme":"midnight","text_style":"body","option_profile":"balanced",
          "orientation":"system","window_mode":"normal"},
    "layout":{
        "columns":12,"grid_unit_dp":4,"touch_target_dp":48,
        "small_spacing_dp":8,"medium_spacing_dp":16,"large_spacing_dp":24,
        "compact_margin_dp":16,"medium_margin_dp":24,"expanded_margin_dp":32,
        "max_content_width_dp":1200},
    "runtime":{"clock_callbacks_per_tick":128,"idle_sleep_seconds":0.01},
    "io":{"chunk_bytes":65536,"max_bytes":268435456,"timeout":30.0,
          "workers":2,"pending":4},
    "icons":{"low":32,"mid":96,"high":256,"raster":False,"max_icons":1500},
    "tools":{"max_file_items":150,"max_progress_json_bytes":1048576,
             "canvas_fps":30},
}
OPTIONS={
    "balanced":{},
    "battery_saver":{"runtime":{"clock_callbacks_per_tick":48,
                                "idle_sleep_seconds":0.025},
                     "io":{"workers":1,"pending":1},
                     "tools":{"canvas_fps":20}},
    "performance":{"runtime":{"clock_callbacks_per_tick":256,
                              "idle_sleep_seconds":0.005},
                   "io":{"workers":4,"pending":8},
                   "tools":{"canvas_fps":60}},
    "accessibility_touch":{"layout":{"touch_target_dp":64,
                                    "grid_unit_dp":8}},
    "compact":{"layout":{"compact_margin_dp":8,"medium_spacing_dp":8}},
    "large_screen":{"layout":{"expanded_margin_dp":40,
                             "max_content_width_dp":1600}},
}
_SAFE_NAME=re.compile(r"^[a-z][a-z0-9_]{0,70}$")


def config_home():
    specified=os.environ.get("TGK_CONFIG_HOME")
    if specified:return Path(specified).expanduser()
    xdg=os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg).expanduser() if xdg else Path.home()/".config")/"tgk"


def config_path():return config_home()/"config.json"


def _safe_name(value):
    if not isinstance(value,str) or not _SAFE_NAME.fullmatch(value):
        raise ValueError("preset names must use lowercase letters, numbers and underscores")
    return value


def _read_json(path):
    with Path(path).open("rb") as stream:
        raw=stream.read(MAX_JSON_BYTES+1)
    if len(raw)>MAX_JSON_BYTES:raise ValueError("TGK JSON file exceeds size limit")
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError("TGK JSON file must contain an object")
    return value


def _merge(base,override,section="config"):
    if not isinstance(override,dict):raise ValueError(section+" must be an object")
    unknown=set(override)-set(base)
    if unknown:raise ValueError("unknown "+section+" keys: "+", ".join(sorted(unknown)))
    for name,value in override.items():
        if isinstance(base[name],dict):
            _merge(base[name],value,section+"."+name)
        else:base[name]=value


def _apply_option_profile(settings):
    """Apply selected profile ONLY to fields still equal to shipped defaults.

    This preserves explicitly customized numeric values in the complete
    generated config.json while allowing a single preset selector to change
    the remaining default-valued settings. No implicit disk writes.
    """
    name=_safe_name(settings["ui"]["option_profile"])
    path=config_home()/"options"/(name+".json")
    if path.is_file():
        entry=_read_json(path)
        if set(entry)-{"name","settings"} or entry.get("name")!=name:
            raise ValueError("invalid option profile file "+str(path))
        options=entry.get("settings")
    else:
        if name not in OPTIONS:raise ValueError("unknown selected option profile: "+name)
        options=OPTIONS[name]
    if not isinstance(options,dict):raise ValueError("option profile settings must be an object")
    if "schema_version" in options:raise ValueError("profile may not override schema_version")
    if isinstance(options.get("ui"),dict) and "option_profile" in options["ui"]:
        raise ValueError("profiles may not redirect other profiles")
    changed=deepcopy(DEFAULT_CONFIG)
    _merge(changed,options,"option profile")
    def apply(current,profile,defaults):
        for key,value in profile.items():
            if isinstance(value,dict):
                apply(current[key],value,defaults[key])
            elif value!=defaults[key] and current[key]==defaults[key]:
                current[key]=value
    apply(settings,changed,DEFAULT_CONFIG)


def validate_config(value):
    """Validate strict types/ranges and return effective, merged configuration."""
    if not isinstance(value,dict):raise ValueError("TGK configuration must be an object")
    config=deepcopy(DEFAULT_CONFIG)
    _merge(config,value)
    _apply_option_profile(config)
    if type(config["schema_version"]) is not int or config["schema_version"]!=SCHEMA_VERSION:
        raise ValueError("unsupported TGK config schema_version")
    ui=config["ui"]
    for key in ("theme","text_style","option_profile"):_safe_name(ui[key])
    from .theme import PRESETS as PALETTES
    from .typography import PRESETS as TYPOGRAPHY
    if ui["theme"] not in PALETTES and not (
            config_home()/"palettes"/(ui["theme"]+".json")).is_file():
        raise ValueError("unknown default palette: "+ui["theme"])
    if ui["text_style"] not in TYPOGRAPHY and not (
            config_home()/"text_styles"/(ui["text_style"]+".json")).is_file():
        raise ValueError("unknown default typography: "+ui["text_style"])
    if ui["orientation"] not in ("system","portrait","landscape"):
        raise ValueError("ui.orientation must be system, portrait or landscape")
    if ui["window_mode"] not in ("normal","dialog","overlay"):
        raise ValueError("ui.window_mode must be normal, dialog or overlay")
    from .adaptive import LayoutScale
    from .io_pipeline import Limits
    LayoutScale(**config["layout"])
    Limits(**config["io"])
    runtime=config["runtime"]
    n=runtime["clock_callbacks_per_tick"]
    if type(n) is not int or not 1<=n<=10000:
        raise ValueError("runtime.clock_callbacks_per_tick must be 1..10000")
    idle=runtime["idle_sleep_seconds"]
    if type(idle) not in (float,int) or not math.isfinite(idle) or not 0<=idle<=.1:
        raise ValueError("runtime.idle_sleep_seconds must be finite in 0..0.1")
    icons=config["icons"]
    dimensions=tuple(icons[k] for k in ("low","mid","high"))
    if any(type(v) is not int or not 8<=v<=1024 for v in dimensions) or not (
            dimensions[0]<dimensions[1]<dimensions[2]):
        raise ValueError("icons low/mid/high must be increasing dimensions 8..1024")
    if type(icons["raster"]) is not bool:raise ValueError("icons.raster must be boolean")
    if type(icons["max_icons"]) is not int or not 1<=icons["max_icons"]<=5000:
        raise ValueError("icons.max_icons must be 1..5000")
    tools=config["tools"]
    for key,lower,upper in (("max_file_items",1,500),("max_progress_json_bytes",1024,8388608),
                            ("canvas_fps",1,60)):
        val=tools[key]
        if type(val) is not int or not lower<=val<=upper:
            raise ValueError(f"tools.{key} must be integer {lower}..{upper}")
    return config


@lru_cache(maxsize=32)
def _load_cached(path,mtime_ns,size):
    try:return validate_config(_read_json(path))
    except (json.JSONDecodeError,UnicodeDecodeError) as exc:
        raise ValueError(f"invalid TGK configuration {path}: {exc}") from exc


def load_config(path=None):
    path=Path(path) if path is not None else config_path()
    try:info=path.stat()
    except FileNotFoundError:return deepcopy(DEFAULT_CONFIG)
    if not path.is_file():raise ValueError("TGK config path is not a file")
    return deepcopy(_load_cached(str(path.resolve()),info.st_mtime_ns,info.st_size))


def update_config(section,key,value):
    """Atomically update one stored config key after full schema validation.

    Only explicitly requested edits are persisted; unrelated theme/font
    registry files are left unchanged. On any validation or I/O failure,
    the previous configuration remains intact.
    """
    _safe_name(section)
    _safe_name(key)
    if section not in DEFAULT_CONFIG or not isinstance(DEFAULT_CONFIG[section],dict):
        raise ValueError("unknown config section: "+section)
    if key not in DEFAULT_CONFIG[section]:
        raise ValueError("unknown config field: "+section+"."+key)
    root=config_home()
    target=config_path()
    if root.is_symlink() or target.is_symlink():
        raise ValueError("refuse to update symlink configuration")
    if not target.is_file():
        raise FileNotFoundError("initialize configuration first: tgk config init")
    raw=_read_json(target)
    updated=deepcopy(DEFAULT_CONFIG)
    _merge(updated,raw)
    updated[section][key]=value
    # Validation must complete BEFORE replacing the prior file.
    validate_config(updated)
    import tempfile
    encoded=(json.dumps(updated,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
    fd,temp_path=tempfile.mkstemp(prefix=".config-",suffix=".json",dir=root)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(encoded)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp_path,0o600)
        if target.is_symlink():raise ValueError("refuse symlink configuration target")
        os.replace(temp_path,target)
    finally:
        Path(temp_path).unlink(missing_ok=True)
    _load_cached.cache_clear()
    return load_config()


def clear_config_cache():
    """Force fresh reads after changes made by another process."""
    _load_cached.cache_clear()


def option_config(name):
    """Apply a named shipped option profile to defaults, without a write."""
    _safe_name(name)
    path=config_home()/"options"/(name+".json")
    if path.is_file():
        data=_read_json(path)
        if data.get("name")!=name or set(data)-{"name","settings"}:
            raise ValueError("invalid named option profile")
        override=data["settings"]
    elif name in OPTIONS:override=OPTIONS[name]
    else:raise ValueError("unknown option profile "+name)
    return validate_config(override)


def _write_new(path,value):
    data=(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    try:fd=os.open(path,flags,0o600)
    except FileExistsError:return False
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise
    return True


def initialize_config(root=None):
    """Create missing files only; never replace a user's existing edits."""
    from .theme import PRESETS,BASE_ROLES
    from .typography import PRESETS as TEXT_PRESETS
    directory=Path(root).expanduser() if root is not None else config_home()
    if directory.is_symlink():raise ValueError("refuse symlink TGK config directory")
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    created=[];preserved=[]
    for subdir in ("palettes","text_styles","options"):
        dest=directory/subdir
        if dest.is_symlink():raise ValueError("refuse symlink preset directory")
        dest.mkdir(mode=0o700,exist_ok=True)
    payloads={"config.json":deepcopy(DEFAULT_CONFIG)}
    for name,colors in PRESETS.items():
        payloads[f"palettes/{name}.json"]={"theme":name,"colors":{
            role:colors[role] for role in BASE_ROLES}}
    for name,properties in TEXT_PRESETS.items():
        payloads[f"text_styles/{name}.json"]={"style":name,
                                             "properties":dict(properties)}
    for name,settings in OPTIONS.items():
        payloads[f"options/{name}.json"]={"name":name,"settings":settings}
    for relative,data in payloads.items():
        target=directory/relative
        if _write_new(target,data):created.append(relative)
        else:preserved.append(relative)
    return {"path":str(directory),"created":created,"preserved":preserved,
            "total":len(payloads)}


def configured_theme():
    """Resolved theme after user-editable preset file; no installation required."""
    settings=load_config()
    name=settings["ui"]["theme"]
    preset=config_home()/"palettes"/(_safe_name(name)+".json")
    from .theme import load_theme,resolve_theme
    if preset.is_file():
        return load_theme(preset)
    return resolve_theme(name)


def configured_text_style():
    settings=load_config()
    name=_safe_name(settings["ui"]["text_style"])
    preset=config_home()/"text_styles"/(name+".json")
    from .typography import resolve_text_style
    if not preset.is_file():return resolve_text_style(name)
    entry=_read_json(preset)
    if set(entry)-{"style","properties"} or not isinstance(entry.get("properties"),dict):
        raise ValueError("invalid TGK text style file "+str(preset))
    return resolve_text_style(entry.get("style",name),**entry["properties"])


def configured_layout_scale():
    from .adaptive import LayoutScale
    return LayoutScale(**load_config()["layout"])


def configured_io_limits():
    from .io_pipeline import Limits
    return Limits(**load_config()["io"])


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Initialize/read persistent TGK configuration")
    parser.add_argument("action",choices=("init","show","path","validate"),nargs="?",default="show")
    args=parser.parse_args(argv)
    if args.action=="init":result=initialize_config()
    elif args.action=="path":result={"path":str(config_path())}
    elif args.action=="show":result=load_config()
    else:result={"valid":True,"config":load_config()}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
