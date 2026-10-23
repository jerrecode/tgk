"""Validated text presets and safe, JS-free rich-text HTML for Termux:GUI WebView.

Native TextView protocol supports only size/gravity/color; bold/italic/underline/
font family and mixed-span styling need the separate RichTextLabel WebView path.
No custom font files, arbitrary CSS, JavaScript or remote resources are loaded.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from html import escape
from types import MappingProxyType
from contextvars import ContextVar
import math
import re

FAMILIES=("sans","serif","mono")
FAMILY_CSS={"sans":"sans-serif","serif":"serif","mono":"monospace"}
PRESETS=MappingProxyType({
    "body":dict(family="sans",size=16,weight=400),
    "caption":dict(family="sans",size=12,weight=400),
    "small":dict(family="sans",size=14,weight=400),
    "subtitle":dict(family="sans",size=18,weight=600),
    "title":dict(family="sans",size=26,weight=700),
    "display":dict(family="sans",size=36,weight=700),
    "monospace":dict(family="mono",size=15,weight=400),
    "terminal":dict(family="mono",size=14,weight=500),
    "code":dict(family="mono",size=14,weight=400),
    "serif":dict(family="serif",size=18,weight=400),
    "quote":dict(family="serif",size=18,weight=400,italic=True),
    "emphasis":dict(family="sans",size=16,weight=700),
    "warning":dict(family="sans",size=16,weight=700,role="warning"),
    "danger":dict(family="sans",size=16,weight=700,role="danger"),
    "muted":dict(family="sans",size=14,weight=400,role="muted"),
    "link":dict(family="sans",size=16,weight=500,role="accent",underline=True),
    "title_h1":dict(family="sans",size=32,weight=700),
    "title_h2":dict(family="sans",size=27,weight=700),
    "title_h3":dict(family="sans",size=23,weight=600),
    "title_h4":dict(family="sans",size=20,weight=600),
    "title_h5":dict(family="sans",size=18,weight=600),
    "description":dict(family="sans",size=16,weight=400),
    "hyperlink":dict(family="sans",size=16,weight=500,role="link",underline=True),
    "filesystem_link":dict(family="mono",size=14,weight=500,role="link"),
    "comment":dict(family="mono",size=13,role="muted",italic=True),
    "reference":dict(family="serif",size=14,role="muted"),
    "footnote":dict(family="serif",size=12,role="muted"),
    "data":dict(family="mono",size=15),
    "metadata":dict(family="mono",size=12,role="muted"),
    "tabular":dict(family="mono",size=14),
    "button":dict(family="sans",size=16,weight=600,role="button_text"),
    "rich":dict(family="serif",size=17),
    "highlighted":dict(family="sans",size=16,weight=700,role="highlight"),
    "subscript":dict(family="sans",size=12),
    "superscript":dict(family="sans",size=12),
    "info":dict(family="sans",size=14,role="muted"),
    "label":dict(family="sans",size=14,weight=500),
    "selected":dict(family="sans",size=16,weight=700,role="text_selected"),
    "unselected":dict(family="sans",size=16,role="text_unselected"),
    "table_header":dict(family="sans",size=14,weight=700),
    "table_cell":dict(family="sans",size=14),
    "input":dict(family="sans",size=16),
    "menu":dict(family="sans",size=16,weight=500),
    "notification":dict(family="sans",size=14,weight=500),
})

ROLES=("text","muted","accent","success","warning","danger","button_text",
       "link","text_selected","text_unselected","highlight")
@dataclass(frozen=True)
class TextStyle:
    family:str="sans"
    size:int=16
    weight:int=400
    italic:bool=False
    underline:bool=False
    strike:bool=False
    role:str="text"
    align:str="left"
    line_height:float=1.35

    def __post_init__(self):
        if self.family not in FAMILIES:raise ValueError("unknown font family")
        if type(self.size) is not int or not 6<=self.size<=128:raise ValueError("text size must be 6..128")
        if type(self.weight) is not int or self.weight not in range(100,1000,100):
            raise ValueError("font weight must be 100..900 in steps of 100")
        if self.role not in ROLES:raise ValueError("unknown text color role")
        if self.align not in ("left","center","right","justify"):
            raise ValueError("unsupported text alignment")
        if not isinstance(self.line_height,(float,int)) or not math.isfinite(self.line_height) or not .8<=self.line_height<=3:
            raise ValueError("line height must be finite between 0.8 and 3")
        for name in ("italic","underline","strike"):
            if type(getattr(self,name)) is not bool:raise ValueError(name+" must be boolean")

    def override(self,**fields):
        return replace(self,**fields)

    def css(self,theme=None):
        from .theme import get_theme,normalize_color
        palette=theme or get_theme()
        color=normalize_color(palette[self.role])
        decorations=" ".join(k for k,on in (("underline",self.underline),("line-through",self.strike)) if on) or "none"
        return ("font-family:"+FAMILY_CSS[self.family]+";font-size:"+str(self.size)+"px;"
                "font-weight:"+str(self.weight)+";font-style:"+("italic" if self.italic else "normal")+";"
                "text-decoration:"+decorations+";line-height:"+str(self.line_height)+";"
                "text-align:"+self.align+";color:"+color+";")

def resolve_text_style(style="body",**overrides):
    if isinstance(style,TextStyle):
        base=style
    elif isinstance(style,str) and style in PRESETS:
        base=TextStyle(**PRESETS[style])
    else:raise ValueError("unknown typography preset: "+str(style))
    return base.override(**overrides) if overrides else base

_active=ContextVar("tgk_typography",default=None)
def get_text_style():
    current=_active.get()
    if current is not None:return current
    from .config import selected_text_style
    return selected_text_style()
def set_text_style(style="body",**overrides):
    value=resolve_text_style(style,**overrides);_active.set(value);return value

@dataclass(frozen=True)
class TextSpan:
    text:str
    style:TextStyle|str|None=None
    color:str|None=None
    def __post_init__(self):
        if not isinstance(self.text,str):raise ValueError("span text must be a string")
        if self.color is not None:
            from .theme import normalize_color
            normalize_color(self.color)

def rich_html(spans,*,style="body",theme=None,limit=250_000):
    """HTML-escaped spans embedded in a restricted CSP document, no JavaScript."""
    from .theme import get_theme,normalize_color
    palette=theme or get_theme()
    base=resolve_text_style(style)
    if isinstance(spans,str):spans=(TextSpan(spans),)
    if not isinstance(spans,(tuple,list)) or not all(isinstance(x,TextSpan) for x in spans):
        raise ValueError("rich text must be a string or a list of TextSpan values")
    if sum(len(x.text) for x in spans)>limit:raise ValueError("rich text exceeds safety limit")
    segments=[]
    for span in spans:
        st=resolve_text_style(span.style or base)
        color=normalize_color(span.color) if span.color else None
        css=st.css(palette)
        if color:css=re.sub(r"color:#[0-9A-F]{8};", "color:"+color+";", css)
        segments.append('<span style="'+css+'">'+escape(span.text).replace("\n","<br>")+'</span>')
    background=normalize_color(palette["background"])
    html=('<html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
          '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
          'style-src &#39;unsafe-inline&#39;; img-src data:">'
          '<style>html,body{margin:0;padding:0;background:'+background+';overflow-wrap:anywhere;}'
          'body{padding:6px;}</style></head><body>'+''.join(segments)+'</body></html>')
    # Termux:GUI's non-base64 setData expects ASCII entities for non-ASCII text.
    return html.encode("ascii","xmlcharrefreplace").decode("ascii")
