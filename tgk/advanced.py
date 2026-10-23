"""Supported multi-view, popup and unbounded-coordinate canvas widget models.

Screen/Tab pages are all constructed at startup and switched with Android View
visibility. Popup is a view overlay *inside* an Activity. Window is a separate
Activity mode, not a floating desktop window manager. InfiniteCanvas uses a
finite RGBA framebuffer showing a movable viewport over infinite coordinates.
"""
from __future__ import annotations
import math

from .widgets import Widget, BoxLayout, Label
from .typography import TextSpan, rich_html, resolve_text_style
from .icons import Icon, glyph


class Screen(BoxLayout):
    def __init__(self,name="",title=None,**kwargs):
        if not isinstance(name,str) or not name:raise ValueError("Screen requires a unique name")
        super().__init__(orientation=kwargs.pop("orientation","vertical"),
                         name=name,title=title or name,**kwargs)

class ScreenManager(Widget):
    def __init__(self,current=None,**kwargs):
        object.__setattr__(self,"_sync_views",None)
        super().__init__(current=current,**kwargs)

    def add_widget(self,widget,*args,**kwargs):
        if not isinstance(widget,Screen):raise TypeError("ScreenManager children must be Screen widgets")
        if any(child.name==widget.name for child in self.children):
            raise ValueError("duplicate screen: "+widget.name)
        super().add_widget(widget,*args,**kwargs)

    def switch(self,name):
        if not isinstance(name,str) or name not in (c.name for c in self.children):
            raise ValueError("unknown screen: "+str(name))
        self.current=name
        # Keep model visibility synchronized even before Android rendering.
        self._sync()
        self.dispatch("on_switch",name)
        return name

    @property
    def active_screen(self):
        return next((s for s in self.children if s.name==self.current),None)

    def next(self):
        names=[x.name for x in self.children]
        if not names:raise ValueError("no screens")
        index=names.index(self.current) if self.current in names else -1
        return self.switch(names[(index+1)%len(names)])

    def previous(self):
        names=[x.name for x in self.children]
        if not names:raise ValueError("no screens")
        index=names.index(self.current) if self.current in names else 0
        return self.switch(names[(index-1)%len(names)])

    def _sync(self):
        current=self.current or (self.children[0].name if self.children else None)
        if current is None:return
        if not any(c.name==current for c in self.children):
            raise ValueError("invalid current screen: "+str(current))
        if self.current is None:self.current=current
        for child in self.children:
            native=child._native
            if native is not None:
                native.setvisibility(2 if child.name==current else 0)

class TabbedPanel(ScreenManager):
    """TabLayout event-driven screen switch; content views share a FrameLayout."""
    def __init__(self,**kwargs):
        object.__setattr__(self,"_tab_bar",None)
        object.__setattr__(self,"_tab_syncing",False)
        super().__init__(**kwargs)
    def add_widget(self,widget,*args,**kwargs):
        if not isinstance(widget,Tab):raise TypeError("TabbedPanel children must be Tab")
        super().add_widget(widget,*args,**kwargs)
    def switch(self,name):
        value=super().switch(name)
        if self._tab_bar is not None and not self._tab_syncing:
            self._tab_bar.selecttab([c.name for c in self.children].index(value))
        return value

class Tab(Screen):pass
class PageView(ScreenManager):pass

class Popup(BoxLayout):
    """In-Activity view overlay; static children remain allocated while hidden."""
    def __init__(self,visible=False,**kwargs):
        super().__init__(orientation=kwargs.pop("orientation","vertical"),
                         visible=bool(visible),**kwargs)
    def open(self):
        self.visible=True  # Widget._update_native handles native visibility
        self.dispatch("on_open")
    def dismiss(self):
        self.visible=False  # Widget._update_native handles native visibility
        self.dispatch("on_dismiss")

class RichTextLabel(Widget):
    """Rich text in a local JS-disabled WebView, not a native TextView."""
    def __init__(self,text="",spans=None,style=None,**kwargs):
        object.__setattr__(self,"_inherited_text_style",None)
        super().__init__(text=text,spans=spans,style=style,**kwargs)
    def html(self):
        content=self.spans if self.spans is not None else self.text
        style=self.style if self.style is not None else (self._inherited_text_style or "body")
        return rich_html(content,style=style,theme=self._effective_theme)
    def _update_native(self,name,value):
        super()._update_native(name,value)
        if name in ("text","spans","style") and self._native is not None:
            self._native.setdata(self.html())

class IconLabel(Label):
    def __init__(self,icon="file",text="",**kwargs):
        spec=Icon(icon,size=int(kwargs.get("font_size",20)),
                  color=kwargs.get("text_color"))
        self.icon_name=spec.name
        super().__init__(text=(spec.text+"  "+text if text else spec.text),**kwargs)
    def set_icon(self,name,text=""):
        icon=Icon(name)
        self.icon_name=icon.name
        self.text=icon.text+("  "+text if text else "")

class InfiniteCanvas(Widget):
    """Pan/zoom infinite world coordinates inside a bounded 2D C framebuffer.

    Logical extent is unbounded; screen width/height stay finite to cap memory.
    Touch input is in Termux:GUI's framebuffer pixel coordinate system.
    """
    def __init__(self,width=512,height=384,zoom=1.0,
                 center_x=0.0,center_y=0.0,grid_step=64,**kwargs):
        if type(width) is not int or type(height) is not int or not 32<=width<=2048 or not 32<=height<=2048:
            raise ValueError("canvas dimensions must be 32..2048 pixels")
        if width*height>1_048_576:raise ValueError("canvas framebuffer must not exceed one megapixel")
        if not math.isfinite(zoom) or not .03125<=zoom<=128:
            raise ValueError("zoom must be in [0.03125,128]")
        if not math.isfinite(center_x) or not math.isfinite(center_y):
            raise ValueError("canvas center must be finite")
        if not math.isfinite(grid_step) or not 1e-6<=grid_step<=1e6:
            raise ValueError("grid_step must be finite within [1e-6,1e6]")
        object.__setattr__(self,"_draw_viewport",None)
        object.__setattr__(self,"_defer_draw",False)
        object.__setattr__(self,"_touch_points",{})
        object.__setattr__(self,"_last_pinch_distance",None)
        object.__setattr__(self,"markers",[])
        super().__init__(width=width,height=height,zoom=float(zoom),
                         center_x=float(center_x),center_y=float(center_y),
                         grid_step=float(grid_step),**kwargs)

    def _update_native(self,name,value):
        super()._update_native(name,value)
        if name in ("zoom","center_x","center_y","grid_step"):
            if self._draw_viewport and not self._defer_draw:self._draw_viewport()

    def world_to_screen(self,x,y):
        return (self.width/2+(float(x)-self.center_x)*self.zoom,
                self.height/2+(float(y)-self.center_y)*self.zoom)

    def screen_to_world(self,x,y):
        return (self.center_x+(float(x)-self.width/2)/self.zoom,
                self.center_y+(float(y)-self.height/2)/self.zoom)

    def pan(self,dx,dy):
        if not all(math.isfinite(float(v)) for v in (dx,dy)):
            raise ValueError("pan must be finite")
        self._defer_draw=True
        try:
            self.center_x-=dx/self.zoom
            self.center_y-=dy/self.zoom
        finally:self._defer_draw=False
        if self._draw_viewport:self._draw_viewport()
        self.dispatch("on_transform",self.center_x,self.center_y,self.zoom)

    def zoom_at(self,factor,x=None,y=None):
        factor=float(factor)
        if not math.isfinite(factor) or factor<=0:raise ValueError("zoom factor must be positive")
        if x is None:x=self.width/2
        if y is None:y=self.height/2
        anchor=self.screen_to_world(x,y)
        self._defer_draw=True
        try:
            self.zoom=min(128,max(.03125,self.zoom*factor))
            self.center_x=anchor[0]-(float(x)-self.width/2)/self.zoom
            self.center_y=anchor[1]-(float(y)-self.height/2)/self.zoom
        finally:self._defer_draw=False
        if self._draw_viewport:self._draw_viewport()
        self.dispatch("on_transform",self.center_x,self.center_y,self.zoom)

    def add_marker(self,x,y,role="accent",radius=8):
        if not math.isfinite(float(x)) or not math.isfinite(float(y)):
            raise ValueError("marker must have finite position")
        from .theme import ROLES
        if role not in ROLES or type(radius) is not int or not 1<=radius<=256:
            raise ValueError("invalid marker role/radius")
        if len(self.markers)>=10_000:raise ValueError("marker limit exceeded")
        self.markers.append((float(x),float(y),role,int(radius)))
        if self._draw_viewport:self._draw_viewport()

    def _touch(self,e):
        action=str(e.value.get("action","")).lower()
        if action=="cancel":
            self._touch_points.clear();self._last_pinch_distance=None;return
        if action not in ("down","pointer_down","move","pointer_up","up"):return
        raw=e.value.get("pointers",[])
        if isinstance(raw,dict):raw=[raw]
        if raw and isinstance(raw[-1],(list,tuple)):raw=raw[-1]
        if not isinstance(raw,(tuple,list)):return
        points={}
        for index,p in enumerate(raw):
            if not isinstance(p,dict):continue
            try:
                x=float(p["x"]);y=float(p["y"]);pointer=p.get("id",index)
            except (ValueError,TypeError,OverflowError,KeyError):continue
            if type(pointer) not in (int,str):continue
            if math.isfinite(x) and math.isfinite(y):
                points[pointer]=(x,y)
        if action in ("up","pointer_up"):
            if action=="up":
                self._touch_points.clear()
                self._last_pinch_distance=None
                return
            idx=e.value.get("index")
            if type(idx) is int and 0<=idx<len(raw) and isinstance(raw[idx],dict):
                points.pop(raw[idx].get("id",idx),None)
        if action=="move" and self._touch_points:
            matching=sorted(set(points)&set(self._touch_points),key=str)
            if matching:
                old=self._touch_points[matching[0]];new=points[matching[0]]
                self.pan(new[0]-old[0],new[1]-old[1])
        if len(points)>=2:
            ids=sorted(points,key=str)[:2]
            dist=math.dist(points[ids[0]],points[ids[1]])
            if self._last_pinch_distance and dist>1 and self._last_pinch_distance>1:
                midpoint=((points[ids[0]][0]+points[ids[1]][0])/2,
                          (points[ids[0]][1]+points[ids[1]][1])/2)
                self.zoom_at(dist/self._last_pinch_distance,*midpoint)
            self._last_pinch_distance=dist
        else:self._last_pinch_distance=None
        self._touch_points=points

    def render_to(self,canvas,theme=None):
        from .theme import get_theme,rgba_channels
        from .canvas import rgba
        palette=theme or self._effective_theme or get_theme()
        def color(role,alpha=None):
            parts=rgba_channels(palette[role])
            return rgba(*(parts if alpha is None else parts[:3]+(alpha,)))
        canvas.clear(color("background"))
        # Exponentially coarsen grid while zoomed out to bound work per frame.
        step=self.grid_step*self.zoom
        while step<24:step*=2
        while step>200:step/=2
        # Alignment is stable in screen space as the world center pans.
        x0=(self.width/2-self.center_x*self.zoom)%step
        y0=(self.height/2-self.center_y*self.zoom)%step
        for i in range(int(self.width/step)+2):
            x=int(round(x0+i*step))
            canvas.line(x,0,x,self.height-1,color("outline",60))
        for j in range(int(self.height/step)+2):
            y=int(round(y0+j*step))
            canvas.line(0,y,self.width-1,y,color("outline",60))
        ox,oy=self.world_to_screen(0,0)
        if 0<=ox<self.width:canvas.line(round(ox),0,round(ox),self.height-1,color("accent",130))
        if 0<=oy<self.height:canvas.line(0,round(oy),self.width-1,round(oy),color("accent",130))
        for wx,wy,role,radius in self.markers:
            sx,sy=self.world_to_screen(wx,wy)
            if -radius<=sx<=self.width+radius and -radius<=sy<=self.height+radius:
                canvas.circle(round(sx),round(sy),radius,color(role))
