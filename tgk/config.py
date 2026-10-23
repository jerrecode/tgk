"""Persistent, user-owned TGK configuration and preset registries.

Importing TGK never writes to the filesystem. Installation explicitly calls
init_config(), which creates missing JSON files but never overwrites edits.
Settings are read at most once per config root/process unless clear_cache()
is called. CLI and application overrides remain higher priority.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import os
from pathlib import Path
import re

SCHEMA_VERSION=1
FILE_LIMIT=1_048_576

def config_dir():
    override=os.environ.get("TGK_CONFIG_HOME")
    if override:
        return Path(override).expanduser()
    xdg=os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg).expanduser() if xdg else Path.home()/".config")/"tgk"

def paths():
    root=config_dir()
    return {
        "root":root,"config":root/"config.json",
        "colors":root/"presets"/"colors.json",
        "typography":root/"presets"/"typography.json",
        "options":root/"presets"/"options.json",
    }

def default_config():
    from .adaptive import LayoutScale
    return {
        "schema_version":SCHEMA_VERSION,
        "defaults":{"palette":"midnight","typography":"body","options":"balanced"},
        "ui":{"orientation":"system","window_mode":"normal","layout_overrides":{}},
        "runtime":{},
        "io":{"chunk_bytes":65536,"max_bytes":268435456,"timeout":30,
              "workers":2,"pending":4},
        "render":{"target_frame_hz":30,"max_canvas_pixels":1048576},
        "icons":{"low_res":32,"mid_res":96,"high_res":256},
    }

def default_options():
    from .adaptive import LayoutScale
    base=vars(LayoutScale())
    return {
        "balanced":{"layout":dict(base),"runtime":{"clock_max_callbacks":128,"idle_sleep_ms":10}},
        "compact":{"layout":dict(base,touch_target_dp=48,medium_spacing_dp=12,
                                 compact_margin_dp=8),
                   "runtime":{"clock_max_callbacks":96,"idle_sleep_ms":10}},
        "accessible":{"layout":dict(base,touch_target_dp=56,grid_unit_dp=4,
                                    small_spacing_dp=12,medium_spacing_dp=20),
                      "runtime":{"clock_max_callbacks":96,"idle_sleep_ms":10}},
        "performance":{"layout":dict(base),"runtime":{"clock_max_callbacks":64,
                                                      "idle_sleep_ms":8}},
    }

def default_colors():
    from .theme import PRESETS,BASE_ROLES
    # Store base roles so all derived colors follow changes automatically.
    return {name:{role:colors[role] for role in BASE_ROLES}
            for name,colors in PRESETS.items()}

def default_typography():
    from .typography import PRESETS
    return {name:dict(properties) for name,properties in PRESETS.items()}

def _read_json(path):
    if not path.is_file():return None
    if path.stat().st_size>FILE_LIMIT:raise ValueError("TGK config file too large: "+str(path))
    try:parsed=json.loads(path.read_text("utf-8"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError("invalid TGK JSON: "+str(path)) from exc
    if not isinstance(parsed,dict):raise ValueError("TGK JSON must be an object: "+str(path))
    return parsed

def _write_new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise ValueError("refuse to write through symlink: "+str(path))
    encoded=(json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
    if len(encoded)>FILE_LIMIT:raise ValueError("initial TGK JSON too large")
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:return False
    try:
        with os.fdopen(fd,"wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True

def init_config():
    """Create missing config and complete default registries; preserve all edits."""
    files=paths()
    presets={
        "colors":{"schema_version":SCHEMA_VERSION,"palettes":default_colors()},
        "typography":{"schema_version":SCHEMA_VERSION,
                      "presets":default_typography()},
        "options":{"schema_version":SCHEMA_VERSION,"presets":default_options()},
    }
    created={}
    for name in ("colors","typography","options"):
        created[name]=_write_new(files[name],presets[name])
    created["config"]=_write_new(files["config"],default_config())
    clear_cache()
    return {"paths":{key:str(path) for key,path in files.items()},
            "created":created}

def _registry(name,container,fallback):
    path=paths()[name]
    data=_read_json(path)
    if data is None:return fallback
    if set(data)!={"schema_version",container} or data["schema_version"]!=SCHEMA_VERSION:
        raise ValueError("invalid TGK "+name+" registry schema")
    value=data[container]
    if not isinstance(value,dict):raise ValueError(name+" entries must be a mapping")
    if len(value)>512:raise ValueError("too many "+name+" entries")
    return value

@lru_cache(maxsize=8)
def _cache_for_root(root):
    # root participates in the cache key, so changing TGK_CONFIG_HOME is safe.
    raw=_read_json(Path(root)/"config.json")
    defaults=default_config()
    if raw is None:raw={}
    if set(raw)-set(defaults):raise ValueError("unknown TGK config sections")
    if raw.get("schema_version",SCHEMA_VERSION)!=SCHEMA_VERSION:
        raise ValueError("unsupported TGK config schema")
    for section in ("defaults","ui","runtime","io","render","icons"):
        incoming=raw.get(section,{})
        if not isinstance(incoming,dict):raise ValueError(section+" must be an object")
        if set(incoming)-set(defaults[section]):
            raise ValueError("unknown TGK config option in "+section)
        defaults[section].update(incoming)
    _validate_config(defaults)
    return defaults

def _validate_config(cfg):
    from .adaptive import LayoutScale
    from .io_pipeline import Limits
    d=cfg["defaults"]
    for key in ("palette","typography","options"):
        if not isinstance(d[key],str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}",d[key]):
            raise ValueError("invalid default "+key)
    ui=cfg["ui"]
    if ui["orientation"] not in ("system","portrait","landscape"):
        raise ValueError("invalid orientation")
    if ui["window_mode"] not in ("normal","dialog","overlay"):
        raise ValueError("invalid window mode")
    if not isinstance(ui["layout_overrides"],dict):raise ValueError("layout_overrides must be an object")
    if set(ui["layout_overrides"])-set(LayoutScale.__dataclass_fields__):
        raise ValueError("unknown layout override")
    rt=cfg["runtime"]
    if "clock_max_callbacks" in rt and (type(rt["clock_max_callbacks"]) is not int
                                       or not 1<=rt["clock_max_callbacks"]<=100000):
        raise ValueError("invalid clock_max_callbacks")
    if "idle_sleep_ms" in rt and (type(rt["idle_sleep_ms"]) is not int
                                 or not 0<=rt["idle_sleep_ms"]<=1000):
        raise ValueError("invalid idle_sleep_ms")
    Limits(**cfg["io"])
    rnd=cfg["render"]
    if type(rnd["target_frame_hz"]) is not int or not 1<=rnd["target_frame_hz"]<=240:
        raise ValueError("invalid target_frame_hz")
    if type(rnd["max_canvas_pixels"]) is not int or not 4096<=rnd["max_canvas_pixels"]<=16_777_216:
        raise ValueError("invalid max_canvas_pixels")
    icon=cfg["icons"]
    dims=[icon[k] for k in ("low_res","mid_res","high_res")]
    if any(type(x) is not int or not 8<=x<=1024 for x in dims) or dims!=sorted(set(dims)):
        raise ValueError("invalid icon size hierarchy")

def settings():
    return deepcopy(_cache_for_root(str(config_dir().resolve())))

@lru_cache(maxsize=8)
def _validated_color_registry(root):
    from .theme import normalize_color,BASE_ROLES,DERIVED_ROLES
    data=_registry("colors","palettes",default_colors())
    valid={}
    for name,colors in data.items():
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}",name):
            raise ValueError("invalid palette name")
        if not isinstance(colors,dict) or set(colors)-set(BASE_ROLES+DERIVED_ROLES):
            raise ValueError("invalid color roles for "+name)
        if set(BASE_ROLES)-set(colors):raise ValueError("missing palette base roles: "+name)
        valid[name]={k:normalize_color(v) for k,v in colors.items()}
    return valid

def color_registry():
    return _validated_color_registry(str(config_dir().resolve()))

@lru_cache(maxsize=8)
def _validated_text_registry(root):
    from .typography import TextStyle
    data=_registry("typography","presets",default_typography())
    valid={}
    for name,properties in data.items():
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}",name):
            raise ValueError("invalid typography name")
        if not isinstance(properties,dict):raise ValueError("invalid text preset")
        valid[name]=TextStyle(**properties)
    return valid

def text_registry():
    return _validated_text_registry(str(config_dir().resolve()))

@lru_cache(maxsize=8)
def _validated_option_registry(root):
    from .adaptive import LayoutScale
    data=_registry("options","presets",default_options())
    valid={}
    for name,value in data.items():
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}",name):
            raise ValueError("invalid option preset name")
        if not isinstance(value,dict) or set(value)-{"layout","runtime"}:
            raise ValueError("invalid option preset")
        layout=value.get("layout",{})
        runtime=value.get("runtime",{})
        if not isinstance(layout,dict) or not isinstance(runtime,dict):
            raise ValueError("invalid preset sections")
        if set(runtime)-{"clock_max_callbacks","idle_sleep_ms"}:
            raise ValueError("invalid preset runtime")
        LayoutScale(**layout)
        for k,v in runtime.items():
            if type(v) is not int or v<0 or (k=="clock_max_callbacks" and v==0):
                raise ValueError("invalid runtime preset")
        valid[name]=deepcopy(value)
    return valid

def option_registry():
    return _validated_option_registry(str(config_dir().resolve()))

def layout_scale():
    from .adaptive import LayoutScale
    cfg=settings()
    profile=option_registry().get(cfg["defaults"]["options"])
    if profile is None:raise ValueError("unknown option preset")
    values=dict(profile.get("layout",{}))
    values.update(cfg["ui"]["layout_overrides"])
    return LayoutScale(**values)

def runtime_settings():
    cfg=settings()
    profile=option_registry().get(cfg["defaults"]["options"])
    if profile is None:raise ValueError("unknown option preset")
    return dict(profile.get("runtime",{}),**cfg["runtime"])

def validate_installation():
    cfg=settings()
    colors=color_registry();fonts=text_registry();opts=option_registry()
    for key,mapping in (("palette",colors),("typography",fonts),("options",opts)):
        if cfg["defaults"][key] not in mapping:
            raise ValueError("configured default "+key+" does not exist")
    layout_scale()
    return {"config_dir":str(config_dir()),"default_palette":cfg["defaults"]["palette"],
            "default_typography":cfg["defaults"]["typography"],
            "default_options":cfg["defaults"]["options"],
            "palettes":len(colors),"text_presets":len(fonts),
            "option_presets":len(opts)}

def set_defaults(*,palette=None,typography=None,options=None,
                 orientation=None,window_mode=None):
    """Atomically persist default choices; preserve unrelated configuration."""
    choices={"palette":palette,"typography":typography,"options":options}
    ui={"orientation":orientation,"window_mode":window_mode}
    if all(v is None for v in (*choices.values(),*ui.values())):
        raise ValueError("no changes specified")
    raw=_read_json(paths()["config"]) or default_config()
    registries={"palette":color_registry(),"typography":text_registry(),
                "options":option_registry()}
    for field,value in choices.items():
        if value is not None:
            if value not in registries[field]:raise ValueError("unknown "+field+" preset")
            raw.setdefault("defaults",{})[field]=value
    for field,value in ui.items():
        if value is not None:raw.setdefault("ui",{})[field]=value
    cfg=default_config()
    for name in ("defaults","ui","runtime","io","render","icons"):
        cfg[name].update(raw.get(name,{}))
    _validate_config(cfg)
    result=(json.dumps(raw,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    if len(result)>FILE_LIMIT:raise ValueError("TGK config exceeds byte limit")
    path=paths()["config"]
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise ValueError("refusing config symlink")
    import tempfile
    fd,temp=tempfile.mkstemp(prefix=".tgk-config-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as handle:
            os.fchmod(handle.fileno(),0o600)
            handle.write(result);handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        try:os.unlink(temp)
        except FileNotFoundError:pass
    clear_cache()
    return validate_installation()


def clear_cache():
    _cache_for_root.cache_clear()
    _validated_color_registry.cache_clear()
    _validated_text_registry.cache_clear()
    _validated_option_registry.cache_clear()


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Manage persistent TGK presets and settings")
    parser.add_argument("action",choices=("init","validate","show","paths"),nargs="?",
                        default="show")
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args(argv)
    if args.action=="init":
        result=init_config()
        validate_installation()
    elif args.action=="validate":result=validate_installation()
    elif args.action=="paths":result={k:str(v) for k,v in paths().items()}
    else:result={"settings":settings(),"defaults":validate_installation()}
    if args.json:print(json.dumps(result,indent=2,sort_keys=True))
    else:
        for key,value in result.items():print(f"{key}: {value}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
