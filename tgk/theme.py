"""Central semantic color themes shared by TGK widgets and TGK Tools.

Public inputs use #RRGGBB or #RRGGBBAA. Termux:GUI uses 0xAABBGGRR.
The active default is process/context local, never written to Android settings.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from collections.abc import Mapping
import json
import re

BASE_ROLES = (
    "status_bar", "primary", "background", "surface", "surface_alt",
    "text", "muted", "accent", "accent_secondary", "button", "button_text",
    "outline", "track", "thumb", "success", "warning", "danger",
)
DERIVED_ROLES = (
    "button_active","button_pressed","button_inactive","button_border",
    "list_background","list_row_alt","list_selected","list_unselected",
    "table_background","table_header","table_row_alt","table_column_alt",
    "table_first_row","table_first_column","table_text","table_divider",
    "input_background","input_outline","input_focused","input_text",
    "tab_active","tab_inactive","tab_text",
    "progress_track","progress_fill","progress_text",
    "slider_track","slider_fill","slider_thumb",
    "dropdown_background","dropdown_border",
    "top_bar","bottom_bar","left_bar","right_bar",
    "panel","menu","notification","overlay",
    "divider","link","text_selected","text_unselected",
    "selection","highlight","shadow","border","scrollbar","tooltip",
    "modal","control_disabled",
)
ROLES=BASE_ROLES+DERIVED_ROLES
DEFAULT_NAME = "midnight"

def blend_color(first,second,amount):
    """Deterministic sRGB channel interpolation, conserving alpha."""
    if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not 0<=amount<=1:
        raise ValueError("blend amount must be within [0,1]")
    def channels(value):
        raw=value.lstrip("#")
        if len(raw)==6:raw+="FF"
        if len(raw)!=8:raise ValueError("blend requires #RRGGBB or #RRGGBBAA")
        return tuple(int(raw[i:i+2],16) for i in (0,2,4,6))
    aa,bb=channels(first),channels(second)
    return "#"+''.join(f"{round(x*(1-amount)+y*amount):02X}" for x,y in zip(aa,bb))

def _derived(colors):
    b,s,a,txt=colors["button"],colors["surface"],colors["accent"],colors["text"]
    bg=colors["background"]
    return dict(
        button_active=blend_color(b,"#FFFFFF",.18),
        button_pressed=blend_color(b,"#000000",.26),
        button_inactive=blend_color(b,bg,.52),
        button_border=colors["outline"],
        list_background=s,list_row_alt=blend_color(s,bg,.16),
        list_selected=blend_color(s,a,.27),list_unselected=s,
        table_background=s,table_header=blend_color(s,a,.23),
        table_row_alt=blend_color(s,bg,.14),
        table_column_alt=blend_color(s,bg,.12),
        table_first_row=blend_color(s,a,.23),
        table_first_column=blend_color(s,a,.13),
        table_text=txt,table_divider=colors["outline"],
        input_background=colors["surface_alt"],
        input_outline=colors["outline"],input_focused=a,input_text=txt,
        tab_active=blend_color(s,a,.27),tab_inactive=blend_color(s,bg,.20),
        tab_text=txt,
        progress_track=colors["track"],progress_fill=a,progress_text=txt,
        slider_track=colors["track"],slider_fill=a,slider_thumb=colors["thumb"],
        dropdown_background=s,dropdown_border=colors["outline"],
        top_bar=bg,bottom_bar=bg,left_bar=s,right_bar=s,
        panel=s,menu=s,notification=blend_color(s,a,.12),
        overlay=blend_color(bg,"#000000",.40),
        divider=colors["outline"],link=a,
        text_selected=colors["button_text"],text_unselected=colors["muted"],
        selection=blend_color(s,a,.35),highlight=blend_color(bg,a,.18),
        shadow=blend_color(bg,"#000000",.50),
        border=colors["outline"],scrollbar=colors["muted"],
        tooltip=colors["surface_alt"],modal=s,
        control_disabled=blend_color(txt,bg,.50),
    )

def _palette(background, surface, text, accent, **overrides):
    values = dict(status_bar=background, primary=accent, background=background,
                  surface=surface, surface_alt=surface, text=text, muted=text,
                  accent=accent, accent_secondary=accent, button=surface,
                  button_text=text, outline=accent, track=surface,
                  thumb=text, success="#39C99B", warning="#F4BD56", danger="#F17183")
    values.update(overrides)
    values.update({k:v for k,v in _derived(values).items() if k not in overrides})
    return values

_PRESET_INPUT = {
    "midnight": _palette("#10162B","#242D49","#F3F6FF","#55DCE8",muted="#A5B4D0",accent_secondary="#AF8CFF",track="#505E7D"),
    "amoled": _palette("#000000","#151515","#FFFFFF","#51F0B3",muted="#BDBDBD",track="#484848"),
    "paper": _palette("#F7F4EF","#FFFFFF","#20293A","#3157AC",muted="#5B6476",track="#D8DEE6",outline="#A8B5D0"),
    "ocean": _palette("#05243C","#103957","#EDF9FF","#27C5D8",muted="#A9D1DF",track="#286483"),
    "forest": _palette("#112D25","#25483D","#F2FFEF","#A0E16E",muted="#C1D6BD",track="#496F5A"),
    "sunset": _palette("#392239","#57364B","#FFF6ED","#FF9473",muted="#E6C5BF",track="#92687A"),
    "cyberpunk": _palette("#210B38","#3B1559","#FFFFFF","#FF36D4",accent_secondary="#26E6F2",muted="#D1B1DD",track="#713E83"),
    "lavender": _palette("#F4F0FF","#FFFFFF","#362B55","#8E63D9",muted="#6B6284",track="#C9B6EE"),
    "terminal": _palette("#08120B","#142519","#B9FFAE","#5CFF6F",muted="#77B78B",track="#31593B"),
    "desert": _palette("#31251C","#51402D","#FFF1D3","#F3BB63",muted="#D7C2A3",track="#837052"),
    "high_contrast": _palette("#000000","#000000","#FFFFFF","#FFFF00",
                              muted="#FFFFFF",button="#171717",button_text="#FFFFFF",
                              outline="#FFFFFF",track="#858585",thumb="#FFFFFF",
                              success="#00FF00",danger="#FF5555",warning="#FFFF00"),
    "ice": _palette("#DDEFFF","#F8FDFF","#172A40","#157DAE",muted="#49697B",track="#ACD3E5"),
}
PRESETS = MappingProxyType({k:MappingProxyType(dict(v)) for k,v in _PRESET_INPUT.items()})

def normalize_color(value):
    """Accept #RGB, #RRGGBB or #RRGGBBAA and return uppercase #RRGGBBAA."""
    if isinstance(value,int) and not isinstance(value,bool) and 0<=value<=0xFFFFFFFF:
        return f"#{value:08X}"
    if not isinstance(value,str):
        raise ValueError("color must be a #RGB/#RRGGBB/#RRGGBBAA string")
    if re.fullmatch(r"#[0-9a-fA-F]{3}",value):
        value="#"+''.join(c*2 for c in value[1:])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?",value):
        raise ValueError(f"invalid color {value!r}; expected #RGB, #RRGGBB or #RRGGBBAA")
    return value.upper() if len(value)==9 else value.upper()+"FF"

def tgui_color(value):
    """Convert standard hex RGBA to Termux:GUI's 0xAABBGGRR integer."""
    text=normalize_color(value)[1:]
    return int(text[6:8]+text[4:6]+text[2:4]+text[:2],16)

def rgba_channels(value):
    raw=normalize_color(value)[1:]
    return tuple(int(raw[i:i+2],16) for i in (0,2,4,6))

def _validate_overrides(overrides):
    if not isinstance(overrides,Mapping):
        raise ValueError("color overrides must be a mapping")
    invalid=set(overrides)-set(ROLES)
    if invalid:
        raise ValueError("unknown color roles: "+", ".join(sorted(map(str,invalid))))
    return {role:normalize_color(value) for role,value in overrides.items()}

@dataclass(frozen=True)
class Theme:
    name: str
    colors: Mapping
    pinned_roles: frozenset[str]|None=None

    def __post_init__(self):
        if not isinstance(self.name,str) or not self.name:
            raise ValueError("theme name must be a nonempty string")
        supplied=_validate_overrides(self.colors)
        missing=set(BASE_ROLES)-set(supplied)
        if missing:raise ValueError("missing base color roles: "+", ".join(sorted(missing)))
        if self.pinned_roles is None:
            pinned=frozenset(set(supplied)&set(DERIVED_ROLES))
        else:
            pinned=frozenset(self.pinned_roles)
        if pinned-set(DERIVED_ROLES):
            raise ValueError("pinned roles must name derived color roles")
        supplied.update({k:v for k,v in _derived(supplied).items() if k not in supplied})
        object.__setattr__(self,"colors",MappingProxyType(supplied))
        object.__setattr__(self,"pinned_roles",pinned)

    def __getitem__(self,role):
        return self.colors[role]

    def override(self,**colors):
        overrides=_validate_overrides(colors)
        result=dict(self.colors)
        result.update(overrides)
        pinned=self.pinned_roles | frozenset(set(overrides)&set(DERIVED_ROLES))
        if set(overrides)&set(BASE_ROLES):
            derived=_derived(result)
            result.update({k:v for k,v in derived.items() if k not in pinned})
        return Theme(self.name,result,pinned_roles=pinned)

    def to_dict(self):
        return {"name":self.name,"colors":dict(self.colors)}

def resolve_theme(theme=None, overrides=None):
    if isinstance(theme,Theme):base=theme
    else:
        if theme is None:theme=DEFAULT_NAME
        if theme not in PRESETS:
            raise ValueError(f"unknown theme {theme!r}; use one of: {', '.join(PRESETS)}")
        base=Theme(theme,{k:PRESETS[theme][k] for k in BASE_ROLES},
                   pinned_roles=frozenset())
    return base.override(**overrides) if overrides else base

def load_theme(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict):raise ValueError("theme JSON must be an object")
    if set(data)-{"theme","colors","name"}:raise ValueError("unsupported theme file keys")
    base=data.get("theme",data.get("name",DEFAULT_NAME))
    return resolve_theme(base,data.get("colors",{}))

_active_theme=ContextVar("tgk_theme",default=None)

def get_theme():
    selected=_active_theme.get()
    if selected is not None:return selected
    from .config import configured_theme
    return configured_theme()

def set_theme(theme=None,**overrides):
    """Set the active theme for future TGK applications in this context."""
    selected=resolve_theme(theme or get_theme(),overrides)
    _active_theme.set(selected)
    return selected

def apply_activity_theme(activity,theme):
    """Activity colors affect *new* Android views; run before widget creation."""
    t=resolve_theme(theme)
    setter=getattr(activity,"settheme",None)
    if callable(setter):
        setter(*(tgui_color(t[k]) for k in
                 ("status_bar","primary","background","text","accent")))
    return t
