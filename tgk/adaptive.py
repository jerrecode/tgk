"""Responsive 12-column layout planning for Termux:GUI activities.

Android reports *window* dp dimensions through Activity.getconfiguration(),
not guaranteed physical panel resolution, refresh rate, color depth or
status-bar insets. Android already handles window decor in normal Activities:
never subtract a guessed status bar height from the content viewport.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

DEFAULT_BREAKPOINTS=(600,840)


def _positive(number,label):
    if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or number<=0:
        raise ValueError(label+" must be a finite positive number")
    return float(number)


@dataclass(frozen=True)
class ScreenMetrics:
    width_dp:float
    height_dp:float
    density:float=1.0
    font_scale:float=1.0
    orientation:str="portrait"
    max_refresh_hz:float|None=None
    physical_width_px:int|None=None
    physical_height_px:int|None=None
    color_depth_bits:int|None=None
    inset_top_dp:float|None=None
    inset_bottom_dp:float|None=None

    def __post_init__(self):
        for field in ("width_dp","height_dp","density","font_scale"):
            _positive(getattr(self,field),field)
        if self.orientation not in ("portrait","landscape"):
            raise ValueError("unsupported orientation")
        if self.max_refresh_hz is not None:_positive(self.max_refresh_hz,"max_refresh_hz")
        for name in ("physical_width_px","physical_height_px","color_depth_bits"):
            v=getattr(self,name)
            if v is not None and (type(v) is not int or v<=0):
                raise ValueError(name+" must be a positive integer or None")
        for name in ("inset_top_dp","inset_bottom_dp"):
            value=getattr(self,name)
            if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
                raise ValueError(name+" must be nonnegative or None")

    @classmethod
    def from_configuration(cls,config):
        """Parse actual Termux:GUI Configuration keys, or accept explicit mocks."""
        if not isinstance(config,dict):
            raise TypeError("getconfiguration() must return a dictionary")
        width=config.get("screenwidth")
        height=config.get("screenheight")
        if width is None or height is None:
            raise ValueError("configuration lacks screenwidth/screenheight")
        orientation=config.get("orientation")
        if orientation not in ("portrait","landscape"):
            orientation="landscape" if width>height else "portrait"
        return cls(width_dp=float(width),height_dp=float(height),
                   density=float(config.get("density",1)),
                   font_scale=float(config.get("fontscale",1)),
                   orientation=orientation)

    @property
    def aspect_ratio(self):return self.width_dp/self.height_dp

    @property
    def safe_content_size_dp(self):
        """Available content when actual *additional* insets are known.

        Android standard Activity windows already exclude system chrome, so
        unknown insets default to no extra subtraction (never guessed).
        """
        top=0.0 if self.inset_top_dp is None else self.inset_top_dp
        bottom=0.0 if self.inset_bottom_dp is None else self.inset_bottom_dp
        return (self.width_dp,max(1.0,self.height_dp-top-bottom))

    @property
    def is_landscape(self):return self.orientation=="landscape"

    @property
    def approx_window_px(self):
        return (round(self.width_dp*self.density),
                round(self.height_dp*self.density))

    @property
    def size_class(self):
        if self.width_dp<DEFAULT_BREAKPOINTS[0]:return "compact"
        if self.width_dp<DEFAULT_BREAKPOINTS[1]:return "medium"
        return "expanded"

    def to_dict(self):
        return {"width_dp":self.width_dp,"height_dp":self.height_dp,
                "density":self.density,"font_scale":self.font_scale,
                "orientation":self.orientation,"aspect_ratio":self.aspect_ratio,
                "size_class":self.size_class,"approx_window_px":self.approx_window_px,
                "physical_width_px":self.physical_width_px,
                "physical_height_px":self.physical_height_px,
                "max_refresh_hz":self.max_refresh_hz,
                "color_depth_bits":self.color_depth_bits,
                "inset_top_dp":self.inset_top_dp,
                "inset_bottom_dp":self.inset_bottom_dp}


@dataclass(frozen=True)
class LayoutScale:
    columns:int=12
    grid_unit_dp:int=4
    touch_target_dp:int=48
    small_spacing_dp:int=8
    medium_spacing_dp:int=16
    large_spacing_dp:int=24
    compact_margin_dp:int=16
    medium_margin_dp:int=24
    expanded_margin_dp:int=32
    max_content_width_dp:int=1200
    compact_breakpoint_dp:int=600
    expanded_breakpoint_dp:int=840
    font_touch_scale_limit_pct:int=150

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            val=getattr(self,name)
            if type(val) is not int or val<=0:raise ValueError(name+" must be positive integer")
        if self.columns>32:raise ValueError("columns must be <= 32")
        if not 240<=self.compact_breakpoint_dp<self.expanded_breakpoint_dp<=3000:
            raise ValueError("breakpoints must increase within 240..3000 dp")
        if not 100<=self.font_touch_scale_limit_pct<=250:
            raise ValueError("font touch scale limit must be 100..250 percent")

    def size_class(self,metrics):
        if metrics.width_dp<self.compact_breakpoint_dp:return "compact"
        if metrics.width_dp<self.expanded_breakpoint_dp:return "medium"
        return "expanded"

    def margin(self,metrics):
        return {"compact":self.compact_margin_dp,"medium":self.medium_margin_dp,
                "expanded":self.expanded_margin_dp}[self.size_class(metrics)]

    def available_width(self,metrics):
        return max(1.0,min(metrics.width_dp,self.max_content_width_dp)-
                   2*self.margin(metrics))

    def column_width(self,metrics,gutter_dp=None,columns=None):
        gutter=self.medium_spacing_dp if gutter_dp is None else gutter_dp
        if isinstance(gutter,bool) or not isinstance(gutter,(int,float)) or not math.isfinite(gutter) or gutter<0:
            raise ValueError("gutter must be finite nonnegative")
        n=self.columns if columns is None else columns
        if type(n) is not int or not 1<=n<=32:
            raise ValueError("invalid column count")
        usable=self.available_width(metrics)
        return max(1.0,(usable-(n-1)*gutter)/n)

    def dp(self,size):
        """Round a dimension to the 4-dp spacing grid, not physical pixels."""
        if not math.isfinite(float(size)) or size<0:raise ValueError("invalid dimension")
        return round(size/self.grid_unit_dp)*self.grid_unit_dp

    def touch_height(self,requested=None,metrics=None):
        """Keep targets accessible when Android font size is enlarged.

        Font scale is read from Android; cap the touch-area multiplier to
        avoid turning each control into a screen-height button.
        """
        multiplier=1.0 if metrics is None else min(
            max(1.0,metrics.font_scale),self.font_touch_scale_limit_pct/100)
        minimum=math.ceil(self.touch_target_dp*multiplier)
        if requested is None:return minimum
        return max(minimum,math.ceil(_positive(requested,"requested height")))


def arrange_spans(children,columns=12,metrics=None,*,span_units=None,size_class=None):
    """Pure first-fit row packing of child spans with deterministic bounds."""
    if type(columns) is not int or not 1<=columns<=32:
        raise ValueError("invalid column count")
    units=columns if span_units is None else span_units
    if type(units) is not int or not 1<=units<=32:
        raise ValueError("invalid span units")
    if metrics is None:metrics=ScreenMetrics(393,852)
    selected_class=metrics.size_class if size_class is None else size_class
    if selected_class not in ("compact","medium","expanded"):
        raise ValueError("invalid screen class")
    positions=[]
    row=0;col=0
    for widget in children:
        requested=getattr(widget,"span",None)
        if requested is None:
            choices={"compact":"span_compact","medium":"span_medium",
                     "expanded":"span_expanded"}
            requested=getattr(widget,choices[selected_class],units)
        if type(requested) is not int or not 1<=requested<=units:
            raise ValueError("invalid responsive grid span")
        # Preserve the familiar 12-unit design contract even when the native
        # grid is configured for 4, 8, 16 or 24 physical columns.
        span=max(1,min(columns,math.ceil(requested*columns/units)))
        if col+span>columns:row+=1;col=0
        positions.append((row,col,1,span))
        col+=span
        if col==columns:row+=1;col=0
    return positions


def measure_activity(activity):
    """Read Android window data when available; None if the binding lacks it."""
    method=getattr(activity,"getconfiguration",None)
    if not callable(method):return None
    return ScreenMetrics.from_configuration(method())


class ResponsiveGrid:
    """Mixin-style wrapper: create TGK ResponsiveGrid via tgk.widgets.GridLayout."""
    pass
