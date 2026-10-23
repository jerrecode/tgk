"""Create-only, config-aware TGK icon asset initialization.

The existing source recipes generate all SVGs into a temporary sibling
directory and publish by atomic rename. Installed catalogs are never
overwritten by setup; intentional regeneration uses tgk.icon_builder's
explicit --overwrite command instead.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import config_home, load_config
from .icon_builder import build_assets,recipe_names


def initialize_icon_assets(root=None,*,settings=None,raster=None):
    """Populate <config-home>/icons safely if it does not already exist.

    Respect persisted sizes/resource caps and optional raster mode. A previous
    catalog is preserved unchanged, even if a newer TGK offers more recipes.
    """
    parent=Path(root).expanduser() if root is not None else config_home()
    if parent.is_symlink():raise ValueError("refuse symlink TGK config directory")
    if not parent.is_dir():raise FileNotFoundError(
        "TGK configuration not initialized; run python -m tgk.config init")
    target=parent/"icons"
    if target.is_symlink():raise ValueError("refuse symlink TGK icon catalog")
    if target.exists():
        if not target.is_dir():raise ValueError("TGK icons path is not a directory")
        return {"path":str(target),"status":"preserved","created":False}
    if settings is None:settings=load_config()
    icon_settings=settings["icons"]
    if raster is None:raster=icon_settings["raster"]
    if type(raster) is not bool:raise ValueError("raster must be a boolean")
    result=build_assets(parent,raster=raster,
                        low=icon_settings["low"],mid=icon_settings["mid"],
                        high=icon_settings["high"],
                        max_icons=icon_settings["max_icons"])
    return {"path":result["output"],"status":"created","created":True,
            "count":result["count"],"raster":raster,
            "svg_files":result["svg_files"],
            "png_files":result["png_files"],
            "jpeg_files":result["jpeg_files"],
            "ico_files":result["ico_files"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=
        "Create missing TGK SVG/PNG/JPEG/ICO icon assets without replacing user files")
    overrides=parser.add_mutually_exclusive_group()
    overrides.add_argument("--raster",dest="raster",action="store_true",
                           help="require CairoSVG + Pillow for PNG/JPEG/ICO outputs")
    overrides.add_argument("--svg-only",dest="raster",action="store_false",
                           help="generate SVG; create empty raster directories")
    parser.set_defaults(raster=None)
    parser.add_argument("--dry-run",action="store_true",help=
        "report output location and number of recipes without writing anything")
    args=parser.parse_args(argv)
    if args.dry_run:
        data={"path":str(config_home()/"icons"),"status":"dry_run",
              "would_generate":len(recipe_names())}
    else:
        data=initialize_icon_assets(raster=args.raster)
    print(json.dumps(data,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
