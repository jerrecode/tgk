"""Validated mobile UI component sizing, borders and table appearance.

Design metadata can drive native controls where the binding exposes setters;
full border/table decoration is rendered in restricted local WebView HTML.
These tokens do not invent native border, tab tint or progress tint APIs.
"""
from __future__ import annotations
from dataclasses import dataclass,replace
from html import escape
from types import MappingProxyType
import math


@dataclass(frozen=True)
class ComponentStyle:
    padding_dp:int=12
    margin_dp:int=8
    border_width_dp:float=1.0
    corner_radius_dp:float=8.0
    min_touch_dp:int=48
    line_style:str="solid"
    wrap:bool=True
    text_fit:str="none"
    shadow_dp:float=0.0

    def __post_init__(self):
        for name in ("padding_dp","margin_dp","border_width_dp","corner_radius_dp",
                     "min_touch_dp","shadow_dp"):
            val=getattr(self,name)
            if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or val<0 or val>256:
                raise ValueError("invalid component style field: "+name)
        if self.min_touch_dp<32:raise ValueError("minimum touch size must be >=32 dp")
        if self.line_style not in ("solid","dashed","dotted","double","none"):
            raise ValueError("invalid border line style")
        if self.text_fit not in ("none","width","height","both"):
            raise ValueError("invalid text fit strategy")
        if type(self.wrap) is not bool:raise ValueError("wrap must be boolean")
    def override(self,**kwargs):return replace(self,**kwargs)


@dataclass(frozen=True)
class TableStyle:
    border_width_dp:float=1
    header_bottom_width_dp:float=2
    first_column_right_width_dp:float=2
    line_style:str="solid"
    cell_padding_dp:int=9
    shade_alternate_rows:bool=True
    shade_alternate_columns:bool=False
    shade_first_row:bool=True
    shade_first_column:bool=True
    bold_first_row:bool=True
    bold_first_column:bool=False

    def __post_init__(self):
        for name in ("border_width_dp","header_bottom_width_dp",
                     "first_column_right_width_dp","cell_padding_dp"):
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or value>32:
                raise ValueError("invalid table style: "+name)
        if self.line_style not in ("solid","dashed","dotted","double","none"):
            raise ValueError("invalid table line style")
        for name in ("shade_alternate_rows","shade_alternate_columns",
                     "shade_first_row","shade_first_column",
                     "bold_first_row","bold_first_column"):
            if type(getattr(self,name)) is not bool:raise ValueError(name+" must be boolean")
    def override(self,**kwargs):return replace(self,**kwargs)


DEFAULT_STYLES=MappingProxyType({
    "button":ComponentStyle(padding_dp=12,margin_dp=4,border_width_dp=1,corner_radius_dp=9),
    "input":ComponentStyle(padding_dp=12,margin_dp=4,border_width_dp=1,corner_radius_dp=6),
    "dropdown":ComponentStyle(padding_dp=10,margin_dp=4,border_width_dp=1),
    "list":ComponentStyle(padding_dp=8,margin_dp=0,border_width_dp=0),
    "panel":ComponentStyle(padding_dp=16,margin_dp=8,border_width_dp=1),
    "menu":ComponentStyle(padding_dp=12,margin_dp=0),
    "notification":ComponentStyle(padding_dp=12,margin_dp=8),
    "progress":ComponentStyle(padding_dp=6,margin_dp=4,border_width_dp=0,min_touch_dp=32),
    "slider":ComponentStyle(padding_dp=8,margin_dp=4,border_width_dp=0),
    "tab":ComponentStyle(padding_dp=10,margin_dp=0,border_width_dp=0),
    "textbox":ComponentStyle(padding_dp=10,margin_dp=4,wrap=True,text_fit="width"),
    "top_bar":ComponentStyle(padding_dp=8,margin_dp=0),
    "bottom_bar":ComponentStyle(padding_dp=8,margin_dp=0),
    "left_bar":ComponentStyle(padding_dp=8,margin_dp=0),
    "right_bar":ComponentStyle(padding_dp=8,margin_dp=0),
    "table":TableStyle(),
})

def resolve_component_style(name,**overrides):
    if name not in DEFAULT_STYLES:raise ValueError("unknown component style "+str(name))
    # User-owned option presets are installed separately and may be modified.
    from .config import config_directory,_cached,_check_dict
    from dataclasses import asdict
    preset=DEFAULT_STYLES[name]
    record=_cached(config_directory()/"options"/(name+".json"))
    if record is not None:
        _check_dict(record,("component","settings"),"component option")
        if record.get("component")!=name:raise ValueError("component preset identity mismatch")
        settings=record.get("settings",{})
        _check_dict(settings,asdict(preset),"component style settings")
        preset=preset.override(**settings)
    return preset.override(**overrides) if overrides else preset

def table_html(rows,theme=None,style=None,max_cells=5000,max_text_chars=300_000):
    """Escape data and render a bounded, local CSP-only HTML table."""
    from .theme import get_theme,normalize_color,blend_color
    theme=theme or get_theme()
    style=style or resolve_component_style("table")
    if not isinstance(style,TableStyle):raise TypeError("style must be TableStyle")
    if not isinstance(rows,(list,tuple)):raise TypeError("table rows must be list or tuple")
    if len(rows)>max_cells:raise ValueError("too many table rows")
    width=None
    total=0
    text_used=0
    body=[]
    for ri,row in enumerate(rows):
        if not isinstance(row,(tuple,list)):raise TypeError("table row must be list or tuple")
        if width is None:width=len(row)
        if len(row)!=width:raise ValueError("ragged table")
        total+=len(row)
        if total>max_cells:raise ValueError("maximum table cell count exceeded")
        cells=[]
        for ci,value in enumerate(row):
            if not isinstance(value,(int,float,bool,str)) and value is not None:
                raise TypeError("table cells must be scalar values")
            cell_text="" if value is None else str(value)
            text_used+=len(cell_text)
            if text_used>max_text_chars:
                raise ValueError("maximum table text size exceeded")
            role="table_background"
            if style.shade_alternate_rows and ri%2:role="table_row_alt"
            if style.shade_alternate_columns and ci%2:
                role="table_column_alt"
            if style.shade_first_column and ci==0:role="table_first_column"
            if style.shade_first_row and ri==0:role="table_first_row"
            border=f"{style.border_width_dp:g}px {style.line_style} {normalize_color(theme['table_divider'])}"
            top=f"background:{normalize_color(theme[role])};border:{border};"
            if ri==0:top+=f"border-bottom-width:{style.header_bottom_width_dp:g}px;"
            if ci==0:top+=f"border-right-width:{style.first_column_right_width_dp:g}px;"
            bold=(ri==0 and style.bold_first_row) or (ci==0 and style.bold_first_column)
            top+=f"padding:{style.cell_padding_dp:g}px;font-weight:{700 if bold else 400};"
            tag="th" if bold else "td"
            cells.append(f'<{tag} style="{top}">'+escape(cell_text)+f'</{tag}>')
        body.append("<tr>"+''.join(cells)+"</tr>")
    from .theme import normalize_color
    css="body{margin:0;background:"+normalize_color(theme["background"])+";color:"+normalize_color(theme["table_text"])+";font-family:sans-serif}table{border-collapse:collapse;width:100%;table-layout:auto}td,th{overflow-wrap:anywhere}"
    doc=('<html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
         '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">'
         '<style>'+css+'</style></head><body><table>'+''.join(body)+'</table></body></html>')
    return doc.encode("ascii","xmlcharrefreplace").decode("ascii")
