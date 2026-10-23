"""Viewport-aware sizing constraints in Android dp, not physical pixels.

The plan is pure and deterministic, avoiding GUI/native IPC during measurement.
Unreported system bar insets are not guessed: ordinary Android Activities
already provide a decor-safe content viewport through getconfiguration().
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional


def _unit(value, name, *, allow_zero=False):
    if value is None:return
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise ValueError(name+" must be finite")
    if value<0 or (not allow_zero and value==0):
        raise ValueError(name+" must be positive")


@dataclass(frozen=True)
class SizeSpec:
    """One explicit sizing strategy per dimension, with optional constraints.

    Defaults leave unspecified dimensions to native layout engines, preserving
    WRAP_CONTENT and weighted layout behavior. Fractions always refer to the
    currently available window width/height after known insets and margins.
    """
    width_dp:float|None=None
    height_dp:float|None=None
    width_fraction:float|None=None
    height_fraction:float|None=None
    min_width_dp:float|None=None
    min_height_dp:float|None=None
    max_width_dp:float|None=None
    max_height_dp:float|None=None
    max_width_fraction:float|None=None
    max_height_fraction:float|None=None
    aspect_ratio:float|None=None
    margin_horizontal_dp:float=0
    margin_vertical_dp:float=0
    fit:str="contain"

    def __post_init__(self):
        for name in ("width_dp","height_dp","min_width_dp","min_height_dp",
                     "max_width_dp","max_height_dp","aspect_ratio"):
            _unit(getattr(self,name),name)
        for name in ("width_fraction","height_fraction","max_width_fraction",
                     "max_height_fraction"):
            value=getattr(self,name)
            if value is not None:
                _unit(value,name)
                if value>1:raise ValueError(name+" must not exceed 1")
        for name in ("margin_horizontal_dp","margin_vertical_dp"):
            _unit(getattr(self,name),name,allow_zero=True)
        if self.width_dp is not None and self.width_fraction is not None:
            raise ValueError("choose width_dp or width_fraction")
        if self.height_dp is not None and self.height_fraction is not None:
            raise ValueError("choose height_dp or height_fraction")
        for low,high in (("min_width_dp","max_width_dp"),("min_height_dp","max_height_dp")):
            if getattr(self,low) is not None and getattr(self,high) is not None and getattr(self,low)>getattr(self,high):
                raise ValueError(low+" exceeds "+high)
        if self.fit not in ("contain","stretch"):
            raise ValueError("fit must be contain or stretch")


@dataclass(frozen=True)
class ResolvedSize:
    width_dp:int|None
    height_dp:int|None
    available_width_dp:float
    available_height_dp:float


def resolve_size(spec, metrics, *, touch_target_dp=48, interactive=False,
                 intrinsic_width_dp=None,intrinsic_height_dp=None):
    """Resolve a bounded size using observed Android *window* dp dimensions.

    No dimensions are forced unless a dimension, intrinsic fallback, or aspect
    ratio is supplied. Explicit touch constraints take precedence over
    min_width/min_height, but the physical content viewport always caps both.
    """
    from .adaptive import ScreenMetrics
    if not isinstance(spec,SizeSpec):raise TypeError("spec must be SizeSpec")
    if not isinstance(metrics,ScreenMetrics):raise TypeError("metrics must be ScreenMetrics")
    _unit(touch_target_dp,"touch_target_dp")
    _unit(intrinsic_width_dp,"intrinsic_width_dp")
    _unit(intrinsic_height_dp,"intrinsic_height_dp")
    width_available=max(1.0,metrics.width_dp-max(0,spec.margin_horizontal_dp))
    # Android reports content-window dp, NOT raw physical screen size.
    height_available=max(1.0,metrics.height_dp-
        (metrics.inset_top_dp or 0)-(metrics.inset_bottom_dp or 0)-
        max(0,spec.margin_vertical_dp))
    w=(spec.width_dp if spec.width_dp is not None else
       width_available*spec.width_fraction if spec.width_fraction is not None else intrinsic_width_dp)
    h=(spec.height_dp if spec.height_dp is not None else
       height_available*spec.height_fraction if spec.height_fraction is not None else intrinsic_height_dp)

    if spec.aspect_ratio is not None:
        if w is not None and h is None:h=w/spec.aspect_ratio
        elif h is not None and w is None:w=h*spec.aspect_ratio
        elif w is not None and h is not None and spec.fit=="contain":
            scale=min(w/h/spec.aspect_ratio,1.0)
            if scale<1:w=h*spec.aspect_ratio
            else:h=w/spec.aspect_ratio

    def constrain(value,available,minimum,maximum,fraction):
        if value is None:return None
        low=max(minimum or 0,touch_target_dp if interactive else 0)
        high=min(available,maximum if maximum is not None else available,
                 available*fraction if fraction is not None else available)
        # A very narrow content viewport cannot fit a 48dp physical target.
        return max(1,math.ceil(max(0,min(high,max(low,value)))))
    w=constrain(w,width_available,spec.min_width_dp,spec.max_width_dp,spec.max_width_fraction)
    h=constrain(h,height_available,spec.min_height_dp,spec.max_height_dp,spec.max_height_fraction)
    return ResolvedSize(w,h,width_available,height_available)
