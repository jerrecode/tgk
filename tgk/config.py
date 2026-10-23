"""Persistent, validated TGK application preferences and bundled preset catalogs.

Install-time initialization is explicit and non-destructive. Ordinary imports
never write user files. The configuration is XDG-compliant on Linux/Termux.
CLI/app overrides take precedence; invalid JSON never silently overwrites data.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import json
import os
import tempfile
import math

SCHEMA_VERSION=1

_DEFAULTS={
    "schema_version":SCHEMA_VERSION,
    "defaults":{"theme":"midnight","text_style":"body"},
    "window":{"mode":"normal","orientation":"system"},
    "layout":{"columns":12,"grid_unit_dp":4,"touch_target_dp":48,
              "small_spacing_dp":8,"medium_spacing_dp":16,"large_spacing_dp":24,
              "compact_margin_dp":16,"medium_margin_dp":24,
              "expanded_margin_dp":32,"max_content_width_dp":1200},
    "backend":{"clock_callbacks_per_tick":128,"idle_sleep_seconds":0.01},
    "io":{"chunk_bytes":65536,"max_bytes":268435456,
          "timeout":30.0,"workers":2,"pending":4},
    "icons":{"low_res":32,"mid_res":96,"high_res":256,"max_icons":1500},
}

def config_directory():
    override=os.environ.get("TGK_CONFIG_DIR")
    if override:return Path(override).expanduser()
    base=os.environ.get("XDG_CONFIG_HOME")
    if base:return Path(base).expanduser()/"tgk"
    return Path.home()/".config"/"tgk"


def _check_dict(obj,keys,section):
    if not isinstance(obj,dict):raise ValueError(section+" must be a JSON object")
    unknown=set(obj)-set(keys)
    if unknown:raise ValueError(section+" contains unknown keys: "+", ".join(sorted(map(str,unknown))))


def _validate(config):
    from .adaptive import LayoutScale
    from .theme import PRESETS
    from .typography import PRESETS as FONTS
    from .io_pipeline import Limits
    _check_dict(config,_DEFAULTS,"config")
    if config.get("schema_version")!=SCHEMA_VERSION:
        raise ValueError("unsupported TGK config schema_version")
    checked={}
    for section,values in _DEFAULTS.items():
        if section=="schema_version":continue
        custom=config.get(section,{})
        _check_dict(custom,values,section)
        checked[section]={**values,**custom}
    if checked["defaults"]["theme"] not in PRESETS:
        raise ValueError("unknown default theme")
    if checked["defaults"]["text_style"] not in FONTS:
        raise ValueError("unknown default text style")
    if checked["window"]["mode"] not in ("normal","dialog","overlay"):
        raise ValueError("unknown window mode")
    if checked["window"]["orientation"] not in ("system","portrait","landscape"):
        raise ValueError("unknown orientation")
    LayoutScale(**checked["layout"])
    if checked["layout"]["columns"]!=12:
        raise ValueError("current ResponsiveGrid backend requires exactly 12 columns")
    Limits(**checked["io"])
    budget=checked["backend"]["clock_callbacks_per_tick"]
    if type(budget) is not int or not 1<=budget<=4096:
        raise ValueError("clock_callbacks_per_tick must be in 1..4096")
    idle=checked["backend"]["idle_sleep_seconds"]
    if isinstance(idle,bool) or not isinstance(idle,(float,int)) or not math.isfinite(idle) or not 0<=idle<=0.5:
        raise ValueError("idle_sleep_seconds must be in 0..0.5")
    icon=checked["icons"]
    dims=[icon[key] for key in ("low_res","mid_res","high_res")]
    if any(type(x) is not int or not 8<=x<=1024 for x in dims) or dims!=sorted(set(dims)):
        raise ValueError("icon resolution sizes must increase within 8..1024")
    if type(icon["max_icons"]) is not int or not 1<=icon["max_icons"]<=5000:
        raise ValueError("max_icons must be in 1..5000")
    return {"schema_version":SCHEMA_VERSION,**checked}


def _read_json(path,max_bytes=262144):
    path=Path(path)
    if path.stat().st_size>max_bytes:raise ValueError("config/preset file is too large")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _read_cached(path,mtime_ns,size):
    return _read_json(path)


def _cached(path):
    path=Path(path)
    if not path.exists():return None
    stat=path.stat()
    return _read_cached(str(path),stat.st_mtime_ns,stat.st_size)


def get_config():
    path=config_directory()/"config.json"
    data=_cached(path)
    if data is None:data={"schema_version":SCHEMA_VERSION}
    return _validate(data)


def _atomic_write_new(path,content):
    """Write only absent files; a symlink or existing user file is never replaced."""
    path=Path(path)
    if path.is_symlink() or path.exists():return False
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".tgk-new-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(json.dumps(content,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
            f.flush();os.fsync(f.fileno())
        # Exclusive hardlink provides create-if-absent semantics even with races.
        try:os.link(tmp,path)
        except FileExistsError:return False
        return True
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass


def initialize_config():
    """Populate editable config/palette/font/options catalogs (idempotently)."""
    from .theme import PRESETS
    from .typography import PRESETS as TEXT
    from .style_tokens import DEFAULT_STYLES
    from dataclasses import asdict
    root=config_directory()
    root.mkdir(parents=True,exist_ok=True)
    made=[]
    records={"config.json":_DEFAULTS}
    records.update({f"palettes/{name}.json":{"theme":name,"colors":dict(palette)}
                    for name,palette in PRESETS.items()})
    records.update({f"typography/{name}.json":{"preset":name,"settings":dict(style)}
                    for name,style in TEXT.items()})
    records.update({f"options/{name}.json":{"component":name,"settings":asdict(style)}
                    for name,style in DEFAULT_STYLES.items()})
    records["options/layout.json"]={"section":"layout","settings":dict(_DEFAULTS["layout"])}
    records["options/backend.json"]={"section":"backend","settings":dict(_DEFAULTS["backend"])}
    records["options/io.json"]={"section":"io","settings":dict(_DEFAULTS["io"])}
    records["options/window.json"]={"section":"window","settings":dict(_DEFAULTS["window"])}
    records["options/icons.json"]={"section":"icons","settings":dict(_DEFAULTS["icons"])}
    for rel,content in records.items():
        if _atomic_write_new(root/rel,content):made.append(rel)
    return {"directory":str(root),"created":len(made),"total":len(records),
            "existing_preserved":len(records)-len(made)}


def _load_preset(folder,name,root_keys):
    # Names are validated from built-in registries before any file read.
    data=_cached(config_directory()/folder/(name+".json"))
    if data is None:return None
    _check_dict(data,root_keys,folder+" preset")
    return data


def selected_theme():
    """Saved palette or builtin fallback, with explicit ContextVar overrides elsewhere."""
    from .theme import PRESETS,resolve_theme,ROLES
    name=get_config()["defaults"]["theme"]
    record=_load_preset("palettes",name,("theme","colors"))
    if record is None:return resolve_theme(name)
    if record.get("theme")!=name:raise ValueError("palette filename and theme disagree")
    colors=record.get("colors",{})
    _check_dict(colors,ROLES,"palette colors")
    # Preset file has a full generated palette. Supply its base + distinct
    # derived overrides so edits to derived color roles remain meaningful.
    from .theme import BASE_ROLES,DERIVED_ROLES,Theme
    if not set(BASE_ROLES)<=set(colors):raise ValueError("palette missing base color roles")
    normalized={k:colors[k] for k in BASE_ROLES}
    built=resolve_theme(name)
    override={k:colors[k] for k in DERIVED_ROLES if k in colors and
              colors[k].upper()!=built[k].upper()}
    return Theme(name,normalized).override(**override)


def selected_text_style():
    from .typography import resolve_text_style,TextStyle
    name=get_config()["defaults"]["text_style"]
    record=_load_preset("typography",name,("preset","settings"))
    if record is None:return resolve_text_style(name)
    if record.get("preset")!=name:raise ValueError("typography filename and preset disagree")
    settings=record.get("settings",{})
    if not isinstance(settings,dict):raise ValueError("typography settings must be a mapping")
    return resolve_text_style(name,**settings)


def selected_layout_scale():
    from .adaptive import LayoutScale
    return LayoutScale(**get_config()["layout"])


def update_config(section,key,value):
    """Validate and atomically persist one explicitly requested setting.

    Does not touch any palette/typography/option preset file. Existing files
    are preserved by reinitialization; this method is an explicit edit.
    """
    root=config_directory()
    path=root/"config.json"
    if path.is_symlink():raise ValueError("refusing to replace a symlink config")
    current=get_config()
    if section not in _DEFAULTS or section=="schema_version":
        raise ValueError("unknown config section")
    if key not in _DEFAULTS[section]:raise ValueError("unknown config parameter")
    candidate={**current,section:{**current[section],key:value}}
    checked=_validate(candidate)
    root.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".tgk-config-",dir=root)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(checked,stream,sort_keys=True,indent=2,ensure_ascii=False)
            stream.write("\n")
            stream.flush();os.fsync(stream.fileno())
        if path.is_symlink():raise ValueError("refusing to replace a symlink config")
        os.replace(tmp,path)
        try:os.chmod(path,0o600)
        except OSError:pass
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass
    return checked


def cli_main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(prog="python -m tgk.config")
    parser.add_argument("command",choices=("init","show"))
    args=parser.parse_args(argv)
    result=initialize_config() if args.command=="init" else get_config()
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(cli_main())
