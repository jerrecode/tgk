"""Persistent, versioned TGK defaults with safe create-only installation.

User files live in ${TGK_CONFIG_HOME} or ${XDG_CONFIG_HOME:-~/.config}/tgk.
Explicit instance args and CLI flags always override these defaults.
The module performs NO filesystem writes on import or runtime reads.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import time


SCHEMA_VERSION=1
MAX_JSON_BYTES=512*1024
DEFAULT_CONFIG={
    "schema_version":SCHEMA_VERSION,
    "pinned":[],
    "ui":{"theme":"midnight","text_style":"body","orientation":"system",
          "window_mode":"normal","option_profile":"balanced"},
    "layout":{
        "columns":12,"grid_unit_dp":4,"touch_target_dp":48,
        "small_spacing_dp":8,"medium_spacing_dp":16,"large_spacing_dp":24,
        "compact_margin_dp":16,"medium_margin_dp":24,"expanded_margin_dp":32,
        "max_content_width_dp":1200,
        "compact_breakpoint_dp":600,"expanded_breakpoint_dp":840,
        "font_touch_scale_limit_pct":150},
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
    """Read bounded JSON from one regular, nonlinked file descriptor.

    Prevent selected custom presets or config files bypassing audit safety by
    following symlinks, FIFOs or a filename replaced between check and open.
    Opening O_NONBLOCK avoids hanging on a FIFO before fstat rejects it.
    """
    import errno
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("TGK JSON symlink path is not allowed: "+str(path))
    flags=os.O_RDONLY
    if hasattr(os,"O_CLOEXEC"):flags|=os.O_CLOEXEC
    if hasattr(os,"O_NONBLOCK"):flags|=os.O_NONBLOCK
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    try:fd=os.open(path,flags)
    except OSError as exc:
        if exc.errno==errno.ELOOP:
            raise ValueError("TGK JSON symlink path is not allowed: "+str(path)) from exc
        raise
    with os.fdopen(fd,"rb") as stream:
        details=os.fstat(stream.fileno())
        if not stat.S_ISREG(details.st_mode) or details.st_nlink!=1:
            raise ValueError("TGK JSON must be a regular nonlinked file: "+str(path))
        if details.st_size>MAX_JSON_BYTES:
            raise ValueError("TGK JSON file exceeds size limit")
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


def validate_config(value):
    """Validate strict types/ranges and return a fresh merged configuration."""
    if not isinstance(value,dict):raise ValueError("TGK configuration must be an object")
    config=deepcopy(DEFAULT_CONFIG)
    _merge(config,value)
    if type(config["schema_version"]) is not int or config["schema_version"]!=SCHEMA_VERSION:
        raise ValueError("unsupported TGK config schema_version")
    pinned=config["pinned"]
    valid={section+"."+name for section,fields in DEFAULT_CONFIG.items()
           if isinstance(fields,dict) for name in fields}
    if type(pinned) is not list or len(pinned)>128 or any(
            type(name) is not str or name not in valid for name in pinned):
        raise ValueError("pinned must be a list of known section.field keys")
    if len(pinned)!=len(set(pinned)):
        raise ValueError("duplicate pinned fields")
    ui=config["ui"]
    for key in ("theme","text_style","option_profile"):_safe_name(ui[key])
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
def _load_cached(path,mtime_ns,size,ctime_ns,inode,device):
    try:return validate_config(_read_json(path))
    except (json.JSONDecodeError,UnicodeDecodeError) as exc:
        raise ValueError(f"invalid TGK configuration {path}: {exc}") from exc


def load_config(path=None):
    path=Path(path) if path is not None else config_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("TGK config symlink path is not allowed: "+str(path))
    try:info=path.stat()
    except FileNotFoundError:return deepcopy(DEFAULT_CONFIG)
    if not path.is_file():raise ValueError("TGK config path is not a file")
    # Never resolve() a path before a no-follow read: that would turn a
    # symlink into its legitimate target and defeat the safety check.
    specified=deepcopy(_load_cached(str(path.absolute()),info.st_mtime_ns,info.st_size,
                                     info.st_ctime_ns,info.st_ino,info.st_dev))
    return _effective_config(specified)


def _effective_config(specified):
    """Resolve profile inheritance and pinned values without filesystem writes.

    Used by reads and BEFORE publication so cross-field constraints validate
    the same effective settings that a subsequent process will actually use.
    """
    name=specified["ui"]["option_profile"]
    # User-selectable option profiles are applied before explicit overrides.
    # Old installers wrote ALL built-in keys, so treat unchanged built-in
    # values as inherited to keep 0.6 configuration files compatible.
    profile=option_config(name)
    pins=set(specified["pinned"])
    for section in ("layout","runtime","io","tools"):
        for key,value in specified[section].items():
            if value!=DEFAULT_CONFIG[section][key] or section+"."+key in pins:
                profile[section][key]=value
    profile["ui"].update(specified["ui"])
    profile["icons"].update(specified["icons"])
    profile["pinned"]=specified["pinned"]
    return validate_config(profile)


def clear_config_cache():
    """Refresh cached configuration after external edits or a local update."""
    _load_cached.cache_clear()


@contextmanager
def _config_write_lock(directory, timeout=5.0):
    """Serialize read/merge/replace across independent Termux/Python processes.

    Lock a stable sibling inode, NEVER config.json: atomic os.replace changes
    config.json's inode. flock is released by the kernel when a process exits.
    """
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=60:
        raise ValueError("config lock timeout must be finite in (0,60] seconds")
    target=Path(directory)/".config.lock"
    if target.is_symlink():raise ValueError("refuse symlink TGK configuration lock")
    flags=os.O_CREAT|os.O_RDWR
    if hasattr(os,"O_CLOEXEC"):flags|=os.O_CLOEXEC
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(target,flags,0o600)
    try:
        metadata=os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink!=1:
            raise ValueError("TGK config lock must be a regular non-linked file")
        os.fchmod(fd,0o600)
        deadline=time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:
                    raise TimeoutError("timed out acquiring TGK config write lock")
                time.sleep(min(0.025,max(0.001,deadline-time.monotonic())))
        try:yield
        finally:fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)


def patch_config(changes, *, reset=(), lock_timeout=5.0):
    """Atomically replace multiple validated config fields in one transaction.

    The existing file is never replaced if validation or serialization fails.
    No preset file is overwritten. A stable private sibling lock serializes
    independent writers across the complete read-merge-rename transaction.
    The acquisition deadline is bounded to avoid indefinite blocking.
    """
    if not isinstance(changes,dict):
        raise ValueError("configuration patch must be an object")
    try:reset_fields=list(reset)
    except TypeError as exc:raise ValueError("reset must be iterable") from exc
    if not changes and not reset_fields:
        raise ValueError("configuration patch must contain edits or resets")
    for section,fields in changes.items():
        _safe_name(section)
        if section not in DEFAULT_CONFIG or not isinstance(DEFAULT_CONFIG[section],dict):
            raise ValueError("unknown TGK config section: "+section)
        if not isinstance(fields,dict) or not fields:
            raise ValueError("configuration section must contain updated fields")
        for key in fields:
            _safe_name(key)
            if key not in DEFAULT_CONFIG[section]:
                raise ValueError("unknown TGK config field: "+section+"."+key)
    reset_names=set()
    changed={section+"."+key for section,fields in changes.items()
             for key in fields}
    for pair in reset_fields:
        if not isinstance(pair,(list,tuple)) or len(pair)!=2:
            raise ValueError("reset items must be SECTION,KEY pairs")
        section,key=pair
        if section not in DEFAULT_CONFIG or not isinstance(DEFAULT_CONFIG[section],dict) or key not in DEFAULT_CONFIG[section]:
            raise ValueError("unknown reset field")
        full_name=section+"."+key
        if full_name in reset_names or full_name in changed:
            raise ValueError("duplicate or conflicting set/reset field")
        reset_names.add(full_name)
    directory=config_home()
    path=config_path()
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("refuse symlink TGK configuration target")
    if not path.is_file():
        raise FileNotFoundError("run python -m tgk.config init before editing")
    with _config_write_lock(directory,timeout=lock_timeout):
        # Preserve unknown data rejection and the current persisted fields.
        stored=_read_json(path)
        merged=deepcopy(DEFAULT_CONFIG)
        _merge(merged,stored)
        _merge(merged,changes)
        for section,key in reset_fields:
            merged[section][key]=deepcopy(DEFAULT_CONFIG[section][key])
        pinned=set(merged["pinned"])
        pinned.update(changed)
        pinned.difference_update(reset_names)
        merged["pinned"]=sorted(pinned)
        validate_config(merged)
        # Validate selected preset before writing; a syntactically valid name
        # without an installed profile must not poison the active config file.
        _effective_config(merged)
        from .theme import PRESETS as THEMES,load_theme
        theme_name=merged["ui"]["theme"]
        theme_file=config_home()/"palettes"/(theme_name+".json")
        if theme_file.is_file():load_theme(theme_file)
        elif theme_name not in THEMES:raise ValueError("unknown theme preset "+theme_name)
        from .typography import PRESETS as TEXT_PRESETS
        text_name=merged["ui"]["text_style"]
        text_file=config_home()/"text_styles"/(text_name+".json")
        if text_file.is_file():
            _text_style_from_file(text_file,text_name)
        elif text_name not in TEXT_PRESETS:raise ValueError("unknown text style "+text_name)
        payload=(json.dumps(merged,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
        if len(payload)>MAX_JSON_BYTES:raise ValueError("config would exceed size limit")
        import tempfile
        fd,temporary=tempfile.mkstemp(prefix=".tgk-config-",suffix=".tmp",dir=directory)
        try:
            with os.fdopen(fd,"wb") as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(temporary,0o600)
            if path.is_symlink():
                raise ValueError("refuse symlink TGK configuration target")
            os.replace(temporary,path)
            # Best-effort directory sync for durability after a crash.
            try:
                directory_fd=os.open(directory,os.O_RDONLY)
                try:os.fsync(directory_fd)
                finally:os.close(directory_fd)
            except OSError:pass
        finally:
            Path(temporary).unlink(missing_ok=True)
        clear_config_cache()
        return load_config()


def update_config(section,key,value=None,*,reset=False):
    """Set or reset one field without affecting unrelated saved values."""
    _safe_name(section)
    _safe_name(key)
    if reset:return patch_config({},reset=((section,key),))
    return patch_config({section:{key:value}})


def update_settings(changes,*,reset=()):
    """Validated all-or-nothing multi-setting update; alias for patch_config."""
    return patch_config(changes,reset=reset)


def option_config(name):
    """Apply a named shipped option profile to defaults, without a write."""
    _safe_name(name)
    path=config_home()/"options"/(name+".json")
    if path.is_file():
        data=_read_json(path)
        if (data.get("name")!=name or set(data)-{"name","settings"}
                or not isinstance(data.get("settings"),dict)):
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
    except FileExistsError:
        # Create-only installation must not silently trust an existing
        # symlink, directory or FIFO as a user preset.
        if path.is_symlink() or not path.is_file():
            raise ValueError("TGK preset exists but is not a regular file: "+str(path))
        return False
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
    return _text_style_from_file(preset,name)


def _text_style_from_file(path,name):
    """One validation contract for transactions, runtime reads and audits."""
    from .typography import resolve_text_style
    entry=_read_json(path)
    if set(entry)-{"style","properties"} or not isinstance(entry.get("properties"),dict):
        raise ValueError("invalid TGK text style file "+str(path))
    try:return resolve_text_style(entry.get("style",name),**entry["properties"])
    except TypeError as exc:
        raise ValueError("invalid TGK text style properties in "+str(path)) from exc


def configured_layout_scale():
    from .adaptive import LayoutScale
    return LayoutScale(**load_config()["layout"])


def configured_io_limits():
    from .io_pipeline import Limits
    return Limits(**load_config()["io"])


def audit_presets(root=None,*,max_files=2000,require_builtins=False):
    """Read-only, size-bounded audit of *all* saved palette/style/option files.

    Unlike load_config(), this detects inactive corrupt presets before a user
    selects them. The scanner never follows symlinks or rewrites user content.
    """
    if type(max_files) is not int or not 1<=max_files<=5000:
        raise ValueError("max_files must be an integer in 1..5000")
    if type(require_builtins) is not bool:
        raise ValueError("require_builtins must be boolean")
    from .theme import PRESETS as COLOR_PRESETS,load_theme
    from .typography import PRESETS as TEXT_PRESETS,resolve_text_style
    base=Path(root).expanduser() if root is not None else config_home()
    if base.is_symlink():raise ValueError("symlink preset root is not allowed: "+str(base))
    catalogs={
        "palettes":set(COLOR_PRESETS),
        "text_styles":set(TEXT_PRESETS),
        "options":set(OPTIONS),
    }
    counts={}
    missing={}
    inspected=0
    for folder,expected in catalogs.items():
        directory=base/folder
        if directory.is_symlink():raise ValueError("symlink preset directory: "+str(directory))
        if directory.exists() and not directory.is_dir():
            raise ValueError("preset directory is not a directory: "+str(directory))
        if not directory.exists():
            files=[]
        else:
            files=[]
            for filename in directory.iterdir():
                if filename.suffix!=".json":continue
                if inspected+len(files)>=max_files:
                    raise ValueError("too many preset files to audit")
                files.append(filename)
            files.sort()
        inspected+=len(files)
        if inspected>max_files:raise ValueError("too many preset files to audit")
        found=set()
        for filename in files:
            if filename.is_symlink() or not filename.is_file():
                raise ValueError("nonregular or symlink preset file: "+str(filename))
            name=_safe_name(filename.stem)
            found.add(name)
            if folder=="palettes":
                load_theme(filename) # validated and <=MAX_JSON_BYTES
            elif folder=="text_styles":
                _text_style_from_file(filename,name)
            else:
                entry=_read_json(filename)
                if (entry.get("name")!=name or set(entry)-{"name","settings"}
                        or not isinstance(entry.get("settings"),dict)):
                    raise ValueError("invalid option preset: "+str(filename))
                validate_config(entry["settings"])
        counts[folder]=len(found)
        missing[folder]=sorted(expected-found)
    if require_builtins and any(missing.values()):
        raise ValueError("missing built-in TGK presets: "+json.dumps(missing,sort_keys=True))
    return {"valid":True,"root":str(base),"counts":counts,
            "total":inspected,"missing_builtins":missing}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Initialize/read persistent TGK configuration")
    parser.add_argument("action",choices=("init","show","path","validate","audit",
                                          "get","set","reset","profiles"),nargs="?",default="show")
    parser.add_argument("section",nargs="?")
    parser.add_argument("key",nargs="?")
    parser.add_argument("value",nargs="?")
    args=parser.parse_args(argv)
    if args.action=="init":
        if args.section is not None:parser.error("init takes no field arguments")
        result=initialize_config()
    elif args.action=="path":
        result={"path":str(config_path())}
    elif args.action=="show":
        result=load_config()
    elif args.action=="audit":
        result=audit_presets(require_builtins=True)
    elif args.action=="profiles":
        result={"available":sorted(set(OPTIONS)|{
            p.stem for p in (config_home()/"options").glob("*.json")
            if p.is_file() and _SAFE_NAME.fullmatch(p.stem)})}
    elif args.action in ("get","set","reset"):
        if args.section is None or args.key is None:
            parser.error(args.action+" requires SECTION KEY")
        if args.section not in DEFAULT_CONFIG or not isinstance(DEFAULT_CONFIG[args.section],dict):
            parser.error("unknown config section: "+str(args.section))
        if args.key not in DEFAULT_CONFIG[args.section]:
            parser.error("unknown config key: "+str(args.section)+"."+str(args.key))
        if args.action=="get":
            if args.value is not None:parser.error("get accepts SECTION KEY only")
            result={"section":args.section,"key":args.key,
                    "value":load_config()[args.section][args.key]}
        elif args.action=="reset":
            if args.value is not None:parser.error("reset accepts SECTION KEY only")
            try:result=update_config(args.section,args.key,reset=True)
            except (ValueError,FileNotFoundError) as exc:parser.error(str(exc))
        else:
            if args.value is None:parser.error("set requires SECTION KEY JSON_VALUE")
            try:value=json.loads(args.value)
            except json.JSONDecodeError as exc:
                parser.error("value must be JSON (quote JSON strings): "+str(exc))
            try:result=update_config(args.section,args.key,value)
            except (ValueError,FileNotFoundError) as exc:parser.error(str(exc))
    else:
        result={"valid":True,"config":load_config()}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
