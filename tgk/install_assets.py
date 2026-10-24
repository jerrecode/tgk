"""Install and safely refresh deterministic, TGK-managed icon catalogs.

Missing assets are created; user-owned or edited assets are NEVER overwritten.
An older generated catalog is refreshed only after manifest integrity checks
prove that all files still match the originals and no foreign files exist.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from .config import _config_write_lock, config_home, load_config
from .icon_builder import build_assets, recipe_names, CatalogChangedError
from .semantic_icons import ICON_GEOMETRY_REVISION

_ASSET_NAME = re.compile(
    r"^(svg|ico|low_res|mid_res|high_res)/[a-z][a-z0-9_]{0,80}\.(svg|ico|png|jpg)$"
)
_DIRS = frozenset(("svg", "ico", "low_res", "mid_res", "high_res"))
_ALLOWED_EXT = {"svg": frozenset(("svg",)), "ico": frozenset(("ico",)),
                "low_res": frozenset(("png", "jpg")),
                "mid_res": frozenset(("png", "jpg")),
                "high_res": frozenset(("png", "jpg"))}
_MAX_FILES = 35000
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024


def _read_regular(path, *, limit):
    """Read only regular, nonlinked files without following symbolic links."""
    flags = os.O_RDONLY
    for optional in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
        flags |= getattr(os, optional, 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("not an unlinked regular file")
        if info.st_size > limit:
            raise ValueError("generated icon file exceeds declared limit")
        return fd, info
    except BaseException:
        os.close(fd)
        raise


def _manifest_if_untouched(folder):
    """Return the manifest only for byte-for-byte pristine TGK catalogs.

    Reject malformed metadata, symlinks, hardlinks, missing/generated extra
    files, oversized manifests and unexpectedly modified asset bytes.
    Broken/missing manifests are treated as customized catalogs and preserved.
    """
    try:
        fd, info = _read_regular(folder / "manifest.json",
                                 limit=_MAX_MANIFEST_BYTES)
        try:
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(_MAX_MANIFEST_BYTES + 1)
        finally:
            fd = -1
        if len(raw) > _MAX_MANIFEST_BYTES:
            return None
        manifest = json.loads(raw)
        if (not isinstance(manifest, dict) or
                manifest.get("source") != "tgk.icon_builder" or
                manifest.get("schema_version") != 1 or
                type(manifest.get("geometry_revision", 0)) is not int or
                manifest.get("geometry_revision", 0) < 0):
            return None
        entries = manifest.get("files")
        if not isinstance(entries, dict) or not 1 <= len(entries) <= _MAX_FILES:
            return None
        expected = {"manifest.json"}
        for relative, record in entries.items():
            if (not isinstance(relative, str) or
                    not (matched := _ASSET_NAME.fullmatch(relative)) or
                    matched[2] not in _ALLOWED_EXT[matched[1]] or
                    not isinstance(record, dict)):
                return None
            size, digest = record.get("bytes"), record.get("sha256")
            if (type(size) is not int or not 0 <= size <= 16 * 1024 * 1024 or
                    not isinstance(digest, str) or
                    not re.fullmatch(r"[a-f0-9]{64}", digest)):
                return None
            expected.add(relative)
        actual = {"manifest.json"}
        with os.scandir(folder) as roots:
            for entry in roots:
                if entry.name == "manifest.json":
                    if not entry.is_file(follow_symlinks=False):
                        return None
                    continue
                if entry.name not in _DIRS or not entry.is_dir(follow_symlinks=False):
                    return None
                with os.scandir(entry.path) as assets:
                    for file in assets:
                        if not file.is_file(follow_symlinks=False):
                            return None
                        actual.add(entry.name + "/" + file.name)
                        if len(actual) > _MAX_FILES + 1:
                            return None
        if actual != expected:
            return None
        for relative, record in entries.items():
            fd, info = _read_regular(folder / relative,
                                     limit=16 * 1024 * 1024)
            with os.fdopen(fd, "rb") as stream:
                if info.st_size != record["bytes"]:
                    return None
                digest = sha256()
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
                if digest.hexdigest() != record["sha256"]:
                    return None
        return manifest
    except (OSError, ValueError, TypeError, UnicodeDecodeError,
            json.JSONDecodeError):
        return None


def initialize_icon_assets(root=None, *, settings=None, raster=None):
    """Create missing catalog, refresh pristine stale catalog, preserve edits."""
    parent = Path(root).expanduser() if root is not None else config_home()
    if parent.is_symlink():
        raise ValueError("refuse symlink TGK config directory")
    if not parent.is_dir():
        raise FileNotFoundError(
            "TGK configuration not initialized; run python -m tgk.config init")
    target = parent / "icons"
    if settings is None:
        settings = load_config()
    icon_settings = settings["icons"]
    if raster is None:
        raster = icon_settings["raster"]
    if type(raster) is not bool:
        raise ValueError("raster must be a boolean")

    with _config_write_lock(parent):
        if target.is_symlink():
            raise ValueError("refuse symlink TGK icon catalog")
        if target.exists() and not target.is_dir():
            raise ValueError("TGK icons path is not a directory")
        overwrite = False
        if target.exists():
            manifest = _manifest_if_untouched(target)
            if manifest is None:
                return {"path": str(target), "status": "preserved",
                        "created": False, "reason": "not a pristine generated catalog"}
            if manifest.get("geometry_revision", 0) >= ICON_GEOMETRY_REVISION:
                return {"path": str(target), "status": "preserved",
                        "created": False, "reason": "geometry already current"}
            # Old pristine catalogs are safe to refresh. No user edits exist.
            overwrite = True
        def unchanged(moved):
            return _manifest_if_untouched(moved) == manifest
        try:
            result = build_assets(parent, raster=raster, overwrite=overwrite,
                                  low=icon_settings["low"], mid=icon_settings["mid"],
                                  high=icon_settings["high"],
                                  max_icons=icon_settings["max_icons"],
                                  _replace_guard=unchanged if overwrite else None)
        except CatalogChangedError:
            return {"path": str(target), "status": "preserved", "created": False,
                    "reason": "catalog changed during generation; original restored"}
        receipt={"path": result["output"],
                "status": "refreshed" if overwrite else "created",
                "created": not overwrite, "count": result["count"],
                "raster": raster, "svg_files": result["svg_files"],
                "png_files": result["png_files"],
                "jpeg_files": result["jpeg_files"],
                "ico_files": result["ico_files"]}
        if "previous_output" in result:
            receipt["previous_output"]=result["previous_output"]
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=
        "Install missing icons or refresh pristine legacy TGK-generated icons")
    overrides = parser.add_mutually_exclusive_group()
    overrides.add_argument("--raster", dest="raster", action="store_true",
                           help="require CairoSVG and Pillow for raster assets")
    overrides.add_argument("--svg-only", dest="raster", action="store_false",
                           help="generate SVGs only")
    parser.set_defaults(raster=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="inspect destination without changing files")
    args = parser.parse_args(argv)
    if args.dry_run:
        data = {"path": str(config_home() / "icons"), "status": "dry_run",
                "would_generate": len(recipe_names())}
    else:
        data = initialize_icon_assets(raster=args.raster)
    print(json.dumps(data, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
