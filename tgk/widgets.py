"""Small declarative widget tree, events, and native Termux:GUI backend.

Supported Kivy subset: App, Widget, BoxLayout, GridLayout, FloatLayout,
ScrollView, Label, Button, TextInput, CheckBox, Switch, ProgressBar,
Clock, event/property binding. Not a drop-in replacement for Kivy graphics.
"""
from __future__ import annotations
import copy
import heapq
import itertools
import logging
import math
import time
from collections import defaultdict

log = logging.getLogger('tgk')

class Property:
    def __init__(self, default=None, **kwargs): self.default = default
    def __set_name__(self, owner, name): self.name = name
    def __get__(self, obj, cls=None):
        if obj is None: return self
        return obj.__dict__.setdefault(self.name, copy.deepcopy(self.default))
class StringProperty(Property): pass
class NumericProperty(Property): pass
class BooleanProperty(Property): pass
class ObjectProperty(Property): pass
class ListProperty(Property): pass
class DictProperty(Property): pass
class OptionProperty(Property): pass
class BoundedNumericProperty(Property): pass

class EventDispatcher:
    def __init__(self, **kwargs):
        object.__setattr__(self, '_bindings', defaultdict(list))
        for k, v in kwargs.items(): setattr(self,k,v)
    def __setattr__(self, name, value):
        if name.startswith('_') or '_bindings' not in self.__dict__:
            object.__setattr__(self,name,value); return
        previous = self.__dict__.get(name, getattr(type(self), name, None))
        # Resolve descriptor defaults without inadvertently overwriting fields.
        if isinstance(previous, Property): previous = previous.default
        object.__setattr__(self,name,value)
        if previous != value:
            for callback in tuple(self._bindings.get(name, [])):
                callback(self,value)
            # Kivy's on_value: property callbacks are distinct from bind(value=...).
            for callback in tuple(self._bindings.get('on_'+name, [])):
                callback(self,value)
            handler = getattr(self, 'on_'+name, None)
            if callable(handler): handler(self,value)
            self._update_native(name,value)
    def _update_native(self,name,value): pass
    def bind(self, **kwargs):
        for name, callback in kwargs.items():
            if not callable(callback): raise TypeError(f'{name} callback must be callable')
            self._bindings[name].append(callback)
        return self
    def unbind(self, **kwargs):
        for name, callback in kwargs.items():
            if callback in self._bindings[name]: self._bindings[name].remove(callback)
    def dispatch(self, name, *args):
        if hasattr(self, name):
            handler = getattr(self,name)
            if callable(handler): handler(*args)
        for callback in tuple(self._bindings.get(name,[])):
            callback(self,*args)

class AttrDict(dict):
    def __getattr__(self,key):
        try:return self[key]
        except KeyError as exc:raise AttributeError(key) from exc

class Widget(EventDispatcher):
    def __init__(self, **kwargs):
        object.__setattr__(self,'children',[])
        object.__setattr__(self,'parent',None)
        object.__setattr__(self,'ids',AttrDict())
        object.__setattr__(self,'_native',None)
        object.__setattr__(self,'_theme_hook',None)
        object.__setattr__(self,'_effective_theme',None)
        object.__setattr__(self,'_applied_native_style',{})
        super().__init__(**kwargs)
        if type(self).__name__ not in (
            'Widget','BoxLayout','GridLayout','FloatLayout','ScrollView','Label',
            'Button','TextInput','CheckBox','Switch','ProgressBar','Image','Spinner',
            'ToggleButton','Slider'):
            from .kv import Builder
            Builder.apply(self)
    def add_widget(self,widget,*args,**kwargs):
        if not isinstance(widget,Widget): raise TypeError('expected Widget')
        if widget is self or any(w is self for w in widget.walk()):
            raise ValueError('widget cycle')
        if widget.parent is not None: raise ValueError('widget already parented')
        if self._native is not None:
            raise NotImplementedError('dynamic widget insertion requires rebuilding the view')
        widget.parent=self
        self.children.append(widget)
    def remove_widget(self,widget):
        if self._native is not None:
            raise NotImplementedError('dynamic widget removal requires rebuilding the view')
        self.children.remove(widget);widget.parent=None
    def walk(self):
        yield self
        for w in self.children: yield from w.walk()
    def _update_native(self,name,value):
        n=self._native
        if n is None: return
        if name=='text' and hasattr(n,'settext'): n.settext(str(value))
        if name=='font_size' and hasattr(n,'settextsize'):
            n.settextsize(int(value))
            self._applied_native_style['font_size']=int(value)
        if name=='active' and hasattr(n,'setchecked'): n.setchecked(bool(value))
        if name=='source' and isinstance(self,Image) and hasattr(n,'setimage'):
            n.setimage(self._read_image())
        if name=='values' and isinstance(self,Spinner) and hasattr(n,'setlist'):
            n.setlist([str(v) for v in value])
        if name=='value' and isinstance(self,ProgressBar):
            n.setprogress(max(0,min(100,round(100*value/self.max if self.max else 0))))
        if isinstance(self,Slider) and name in ('value','min','max','step'):
            if self._slider_draw is not None:
                self._slider_draw()
        if name in ('theme','colors','background_color','text_color',
                    'text_style','text_size','font_weight','font_family','italic',
                    'underline','strike','text_align','line_height','font_color_role'):
            if self._theme_hook is not None:self._theme_hook(name)
        if name=='visible' and n is not None and hasattr(n,'setvisibility'):
            n.setvisibility(2 if value else 0)
        if name=='current' and getattr(self,'_sync_views',None):
            self._sync_views()
    def _read_image(self):
        from pathlib import Path
        path=Path(getattr(self,'source',''))
        if path.suffix.lower() not in ('.png','.jpg','.jpeg'):
            raise ValueError('Image source must be PNG/JPEG')
        if path.stat().st_size>24_000_000:raise ValueError('Image exceeds 24MB safety limit')
        return path.read_bytes()
    def on_press(self,*args): pass
    def on_release(self,*args): pass
    def on_text_validate(self,*args): pass

class BoxLayout(Widget):
    def __init__(self,orientation='horizontal',spacing=0,padding=0,**kwargs):
        if orientation not in ('horizontal','vertical'): raise ValueError('bad orientation')
        super().__init__(orientation=orientation,spacing=spacing,padding=padding,**kwargs)
class GridLayout(Widget):
    def __init__(self,cols=1,rows=0,**kwargs):
        if not cols and not rows: raise ValueError('cols or rows required')
        super().__init__(cols=cols,rows=rows,**kwargs)
class FloatLayout(Widget): pass # native FrameLayout, limited Kivy positioning
class ScrollView(Widget): pass
class Label(Widget):
    def __init__(self,text='',font_size=16,**kwargs):super().__init__(text=text,font_size=font_size,**kwargs)
class Button(Label): pass
class TextInput(Widget):
    def __init__(self,text='',multiline=False,password=False,**kwargs):
        super().__init__(text=text,multiline=multiline,password=password,**kwargs)
class CheckBox(Widget):
    def __init__(self,active=False,text='',**kwargs):super().__init__(active=active,text=text,**kwargs)
class Switch(CheckBox):pass
class Image(Widget):
    def __init__(self,source='',**kwargs):super().__init__(source=source,**kwargs)
class Spinner(Label):
    def __init__(self,text='',values=(),**kwargs):
        super().__init__(text=text,values=list(values),**kwargs)
class ToggleButton(Button):
    def __init__(self,text='',state='normal',**kwargs):
        super().__init__(text=text,state=state,**kwargs)
class ProgressBar(Widget):
    def __init__(self,value=0,max=100,**kwargs):super().__init__(value=value,max=max,**kwargs)

class Slider(Widget):
    """Interactive horizontal slider (C raster + Termux:GUI ImageView touch).

    Values are independent of framebuffer resolution; step=0 is continuous.
    A native Android SeekBar isn't exposed by the current Termux:GUI protocol.
    """
    def __init__(self,min=0,max=100,value=0,step=0,**kwargs):
        if not all(math.isfinite(float(n)) for n in (min,max,value,step)):
            raise ValueError('Slider values must be finite')
        if float(max)<=float(min) or float(step)<0:
            raise ValueError('Slider requires max > min and step >= 0')
        object.__setattr__(self,'_slider_draw',None)
        object.__setattr__(self,'_drag_pointer',None)
        super().__init__(min=float(min),max=float(max),step=float(step),value=float(value),**kwargs)
        self.value=self._normalized(self.value)

    def _normalized(self,value):
        low,high=float(self.min),float(self.max)
        incoming=float(value)
        if not all(math.isfinite(n) for n in (low,high,incoming,float(self.step))):
            raise ValueError('Slider values must be finite')
        if high<=low:
            raise ValueError('Slider requires max > min')
        result=max(low,min(high,incoming))
        if self.step:
            result=low+round((result-low)/float(self.step))*float(self.step)
        return max(low,min(high,result))

    def __setattr__(self,name,value):
        if name in ('min','max','step') and '_bindings' in self.__dict__:
            value=float(value)
            if not math.isfinite(value) or (name=='step' and value<0):
                raise ValueError('Slider bounds and step must be finite; step >= 0')
            other={'min':'max','max':'min'}.get(name)
            if other in self.__dict__:
                if (name=='min' and value>=float(self.max)) or (name=='max' and value<=float(self.min)):
                    raise ValueError('Slider requires max > min')
        if name=='value' and '_bindings' in self.__dict__:
            value=self._normalized(value)
        super().__setattr__(name,value)


class _Clock:
    def __init__(self):self._jobs=[];self._ids=itertools.count();self._cancel=set()
    def schedule_once(self,callback,timeout=0):
        handle=next(self._ids)
        heapq.heappush(self._jobs,(time.monotonic()+max(0,timeout),handle,callback,0))
        return _ClockHandle(self,handle)
    def schedule_interval(self,callback,interval):
        if interval<=0:raise ValueError('interval must be positive')
        handle=next(self._ids)
        heapq.heappush(self._jobs,(time.monotonic()+interval,handle,callback,interval))
        return _ClockHandle(self,handle)
    def tick(self):
        now=time.monotonic()
        while self._jobs and self._jobs[0][0]<=now:
            due,handle,callback,interval=heapq.heappop(self._jobs)
            if handle in self._cancel:
                self._cancel.discard(handle);continue
            result=callback(max(0,now-due))
            if interval and result is not False and handle not in self._cancel:
                heapq.heappush(self._jobs,(time.monotonic()+interval,handle,callback,interval))
            self._cancel.discard(handle)
    def reset(self):self._jobs.clear();self._cancel.clear()
class _ClockHandle:
    def __init__(self,clock,handle):self.clock=clock;self.handle=handle
    def cancel(self):self.clock._cancel.add(self.handle)
Clock=_Clock()

class TermuxBackend:
    def __init__(self, tg=None, theme=None, text_style=None, window_mode='normal'):
        if tg is None:
            try: import termuxgui as tg
            except ImportError as exc:
                raise RuntimeError('pip install termuxgui on Termux; Termux:GUI Android plugin is also required') from exc
        self.tg=tg
        self.connection=None; self.activity=None;self.nodes=[]
        # Termux:GUI native View instances may be unhashable. Numeric View IDs
        # are hashable, stable during an Activity and permit O(1) event lookup.
        self._native_index={}
        self._tab_index={}
        self._slider_resources=[]
        self._canvas_resources=[]
        self._stop_requested=False
        if window_mode not in ('normal','dialog','overlay'):
            raise ValueError("window_mode must be normal, dialog or overlay")
        self.window_mode=window_mode
        from .theme import resolve_theme, get_theme
        from .typography import resolve_text_style,get_text_style
        self.theme=resolve_theme(theme or get_theme())
        self.text_style=resolve_text_style(text_style or get_text_style())

    def _node_theme(self,node):
        from .theme import resolve_theme
        result=self.theme
        ancestry=[]
        current=node
        while current is not None:
            ancestry.append(current)
            current=current.parent
        for item in reversed(ancestry):
            local=getattr(item,'theme',None)
            if local:result=resolve_theme(local)
            colors=getattr(item,'colors',None)
            if colors:result=result.override(**colors)
        return result

    def _cached_set(self,node,key,method,value):
        """Send only real native style changes; avoid redundant JSON/IPC."""
        cache=node._applied_native_style
        if cache.get(key)==value:return False
        setter=getattr(node._native,method,None)
        if not callable(setter):return False
        setter(value)
        cache[key]=value
        return True

    def invalidate_style(self,node,property_name):
        """Local style change: one view. Inherited palette change: subtree."""
        if property_name in ('colors','theme'):
            for child in node.walk():
                if child._native is not None:self._paint_node(child)
        elif node._native is not None:
            self._paint_node(node)

    def _paint_node(self,node):
        from .theme import tgui_color
        selected=self._node_theme(node)
        node._effective_theme=selected
        native=node._native
        if native is None:return
        background=getattr(node,'background_color',None)
        if background is None:
            if node.parent is None:background=selected['background']
            elif isinstance(node,(BoxLayout,GridLayout,FloatLayout,ScrollView)):background=selected['surface']
            elif isinstance(node,(Button,TextInput)):background=selected['button' if isinstance(node,Button) else 'surface_alt']
        if background is not None:
            self._cached_set(node,'background','setbackgroundcolor',tgui_color(background))
        from .advanced import InfiniteCanvas,RichTextLabel
        if isinstance(node,(Label,TextInput)):
            self._paint_text(node,selected)
        elif isinstance(node,(CheckBox,Switch,ToggleButton,Spinner)):
            foreground=getattr(node,'text_color',selected['text'])
            self._cached_set(node,'foreground','settextcolor',tgui_color(foreground))
        if isinstance(node,RichTextLabel):
            node._inherited_text_style=self.text_style
            self._cached_set(node,'markup','setdata',node.html())
        if isinstance(node,Slider) and node._slider_draw is not None:
            signature=tuple(selected[role] for role in
                            ('background','track','accent','thumb','primary'))
            if node._applied_native_style.get('slider_palette')!=signature:
                node._slider_draw()
                node._applied_native_style['slider_palette']=signature
        if isinstance(node,InfiniteCanvas) and node._draw_viewport is not None:
            signature=tuple(selected[role] for role in ('background','outline','accent'))
            if node._applied_native_style.get('canvas_palette')!=signature:
                node._draw_viewport()
                node._applied_native_style['canvas_palette']=signature

    def _paint_text(self,node,selected):
        from .typography import resolve_text_style
        from .theme import tgui_color
        style=resolve_text_style(getattr(node,'text_style',None) or self.text_style)
        options={}
        for field,override in (('family','font_family'),('size','text_size'),
                               ('weight','font_weight'),('italic','italic'),
                               ('underline','underline'),('strike','strike'),
                               ('align','text_align'),('line_height','line_height'),
                               ('role','font_color_role')):
            if hasattr(node,override):
                options[field]=getattr(node,override)
        if options:style=style.override(**options)
        native=node._native
        if native is not None:
            setsize=getattr(native,'settextsize',None)
            if callable(setsize):
                # Label.font_size predates presets; text_size/text_style is explicit.
                legacy=getattr(node,'font_size',None)
                size=legacy if legacy not in (None,16) and 'size' not in options and not hasattr(node,'text_style') else style.size
                self._cached_set(node,'font_size','settextsize',int(size))
            default_role='button_text' if isinstance(node,Button) and not hasattr(node,'font_color_role') else style.role
            color=getattr(node,'text_color',selected[default_role])
            self._cached_set(node,'foreground','settextcolor',tgui_color(color))
        return style

    def apply_text_style(self,style=None):
        from .typography import resolve_text_style
        if style is not None:self.text_style=resolve_text_style(style)
        for node in tuple(self.nodes):self._paint_node(node)

    def apply_theme(self,theme=None):
        """Recolor existing Views and redraw sliders, preserving local overrides."""
        from .theme import resolve_theme
        if theme is not None:self.theme=resolve_theme(theme)
        for node in tuple(self.nodes):self._paint_node(node)

    def _make(self,node,parent):
        from .advanced import ScreenManager,TabbedPanel,Popup,RichTextLabel,InfiniteCanvas
        tg=self.tg;a=self.activity
        tab_content=None
        if isinstance(node,TabbedPanel):
            native=tg.LinearLayout(a,parent,vertical=True)
            node._tab_bar=tg.TabLayout(a,native)
            tab_id=getattr(node._tab_bar,'id',None)
            if type(tab_id) in (int,str):self._tab_index[tab_id]=node
            node._tab_bar.setlist([c.title for c in node.children])
            tab_content=tg.FrameLayout(a,native)
            tab_content.setheight(0)
            tab_content.setlinearlayoutparams(1)
        elif isinstance(node,ScreenManager):
            native=tg.FrameLayout(a,parent)
        elif isinstance(node,RichTextLabel):
            native=tg.WebView(a,parent)
            native.setheight(int(getattr(node,'height',120)))
            node._inherited_text_style=self.text_style
            native.setdata(node.html())
        elif isinstance(node,InfiniteCanvas):
            native=tg.ImageView(a,parent)
            native.sendtouchevent(True)
            native.setdimensions(node.width,node.height)
            buffer=tg.Buffer(self.connection,node.width,node.height)
            native.setbuffer(buffer)
            memory=buffer.__enter__()
            try:
                from .canvas import Canvas
                canvas=Canvas(memory,node.width,node.height)
            except BaseException:
                buffer.__exit__(None,None,None)
                raise
            self._canvas_resources.append((node,buffer,canvas))
            node._draw_viewport=lambda: self._draw_canvas(node,buffer,canvas)
        elif isinstance(node,BoxLayout):
            native=tg.LinearLayout(a,parent,vertical=node.orientation=='vertical')
        elif isinstance(node,GridLayout):
            cols=int(node.cols or max(1,(len(node.children)+int(node.rows)-1)//int(node.rows)))
            rows=int(node.rows or (len(node.children)+cols-1)//cols)
            native=tg.GridLayout(a,max(1,rows),max(1,cols),parent)
        elif isinstance(node,ScrollView):
            if len(node.children)>1:raise ValueError('ScrollView accepts exactly one child')
            native=tg.NestedScrollView(a,parent)
        elif isinstance(node,FloatLayout) or type(node) is Widget:
            native=tg.FrameLayout(a,parent)
        elif isinstance(node,TextInput):
            input_type = 'textPassword' if node.password else ('textMultiLine' if node.multiline else 'text')
            native=tg.EditText(a,str(node.text),parent,singleline=not node.multiline,inputtype=input_type)
            native.sendtextevent(True)
        elif isinstance(node,Spinner):
            native=tg.Spinner(a,parent)
            native.setlist([str(v) for v in node.values])
        elif isinstance(node,ToggleButton):
            native=tg.ToggleButton(a,parent,checked=node.state=='down')
            native.sendclickevent(True)
        elif isinstance(node,Slider):
            native=tg.ImageView(a,parent)
            native.sendtouchevent(True)
            native.setheight(72)
            native.setwidth(tg.View.MATCH_PARENT)
            buffer=tg.Buffer(self.connection,512,72)
            native.setbuffer(buffer)
            memory=buffer.__enter__()
            try:
                from .canvas import Canvas
                canvas=Canvas(memory,512,72)
            except BaseException:
                buffer.__exit__(None,None,None)
                raise
            self._slider_resources.append((node,buffer,canvas))
            node._slider_draw=lambda: self._draw_slider(node,buffer,canvas)
        elif isinstance(node,Image):
            native=tg.ImageView(a,parent)
            if node.source:native.setimage(node._read_image())
        elif isinstance(node,Button):
            native=tg.Button(a,str(node.text),parent);native.sendclickevent(True)
        elif isinstance(node,Switch):
            native=tg.Switch(a,str(node.text),parent,checked=bool(node.active));native.sendclickevent(True)
        elif isinstance(node,CheckBox):
            native=tg.Checkbox(a,str(node.text),parent,checked=bool(node.active));native.sendclickevent(True)
        elif isinstance(node,Label):native=tg.TextView(a,str(node.text),parent)
        elif isinstance(node,ProgressBar):native=tg.ProgressBar(a,parent)
        else:raise NotImplementedError(f'{type(node).__name__} has no native renderer')
        node._native=native;self.nodes.append(node)
        native_id=getattr(native,'id',None)
        if type(native_id) in (int,str):self._native_index[native_id]=node
        node._theme_hook=lambda changed,node=node: self.invalidate_style(node,changed)
        if isinstance(node,ScreenManager):
            node._sync_views=node._sync
        if isinstance(node,Slider):node._effective_theme=self._node_theme(node)
        # _paint_node performs the initial style and slider draw exactly once.
        if isinstance(node,(Label,TextInput)):
            horizontal={'left':0,'start':0,'center':1,'right':2,'end':2}
            vertical={'top':0,'center':1,'bottom':2}
            ha=getattr(node,'halign','left')
            va=getattr(node,'valign','center')
            if ha not in horizontal or va not in vertical:
                raise ValueError('halign must be left/center/right; valign top/center/bottom')
            gravity=getattr(native,'setgravity',None)
            if callable(gravity):gravity(horizontal[ha],vertical[va])
        if isinstance(node,ProgressBar):native.setprogress(max(0,min(100,round(100*node.value/node.max if node.max else 0))))
        if hasattr(node,'height') and node.height is not None: native.setheight(int(node.height))
        if hasattr(node,'width') and node.width is not None:native.setwidth(int(node.width))
        if isinstance(node.parent,BoxLayout):
            weight=getattr(node,'weight',None)
            if weight is not None and (isinstance(weight,bool) or not isinstance(weight,int) or weight<0):
                raise ValueError('weight must be a nonnegative integer')
            if node.parent.orientation=='vertical':
                if not hasattr(node,'width'):native.setwidth(tg.View.MATCH_PARENT)
                if weight is not None and not hasattr(node,'height'):
                    native.setheight(0);native.setlinearlayoutparams(weight)
                elif isinstance(node,ScrollView) and not hasattr(node,'height'):
                    native.setheight(0);native.setlinearlayoutparams(1)
            else:
                if weight is not None and not hasattr(node,'width'):
                    native.setwidth(0);native.setlinearlayoutparams(weight)
                elif not hasattr(node,'width'):
                    native.setwidth(0);native.setlinearlayoutparams(1)
            position=node.parent.children.index(node)
            spacing=getattr(node.parent,'spacing',0)
            if spacing and position:
                native.setmargin(int(spacing),'top' if node.parent.orientation=='vertical' else 'left')
        if isinstance(node.parent,GridLayout):
            index=node.parent.children.index(node)
            rows=int(getattr(node,'row_span',1));cols=int(getattr(node,'col_span',1))
            ar=getattr(node,'align_row','center');ac=getattr(node,'align_col','center')
            allowed={'top','bottom','left','right','center','baseline','fill'}
            if rows<1 or cols<1 or ar not in allowed or ac not in allowed:
                raise ValueError('invalid grid spans or cell alignment')
            native.setgridlayoutparams(index//int(node.parent.cols),index%int(node.parent.cols),
                                       rows,cols,ar,ac)
        if isinstance(node,BoxLayout) and node.padding:
            native.setmargin(int(node.padding if isinstance(node.padding,(int,float)) else node.padding[0]))
        if isinstance(node,Popup):
            native.setvisibility(2 if node.visible else 0)
        self._paint_node(node)
        for child in node.children:self._make(child,tab_content if tab_content is not None else native)
        if isinstance(node,ScreenManager):
            node._sync()
            if isinstance(node,TabbedPanel) and node._tab_bar is not None and node.children:
                node._tab_bar.selecttab([x.name for x in node.children].index(node.current))
        return native
    @staticmethod
    def _draw_canvas(node,buffer,canvas):
        node.render_to(canvas)
        buffer.blit()
        if node._native is not None:node._native.refresh()

    @staticmethod
    def _draw_slider(node,buffer,canvas):
        from .canvas import rgba
        from .theme import rgba_channels, get_theme
        palette=node._effective_theme or get_theme()
        def color(role):return rgba(*rgba_channels(palette[role]))
        left,right=22,canvas.width-23
        canvas.clear(color('background'))
        canvas.rect(left,32,right-left+1,8,color('track'))
        fraction=(node.value-node.min)/(node.max-node.min)
        x=left+round((right-left)*fraction)
        canvas.rect(left,32,max(1,x-left+1),8,color('accent'))
        canvas.circle(x,36,15,color('thumb'))
        canvas.circle(x,36,9,color('primary'))
        buffer.blit()
        if node._native is not None:
            node._native.refresh()

    def _slider_touch(self,node,event):
        if event.type!='touch':return
        action=str(event.value.get('action','')).lower()
        if action=='cancel':
            node._drag_pointer=None
            return
        if action not in ('down','pointer_down','move','up','pointer_up'):
            return
        # ACTION_DOWN starts a new gesture, even if the previous stream lost
        # its terminal event. ACTION_UP ends the gesture even with bad data.
        owner=node._drag_pointer
        if action in ('down','up'):
            node._drag_pointer=None
        points=event.value.get('pointers',[])
        if isinstance(points,dict):points=[points]
        if isinstance(points,(list,tuple)) and points and isinstance(points[-1],(list,tuple)):
            points=points[-1]
        if not isinstance(points,(list,tuple)) or not points:
            return
        if action in ('down','pointer_down'):
            if node._drag_pointer is not None:return
            index=event.value.get('index',0) if action=='pointer_down' else 0
            if type(index) is not int or not 0<=index<len(points):return
            chosen=points[index]
        elif action=='pointer_up':
            # The action index identifies the lifted pointer; releasing a
            # different finger must neither move nor release the drag owner.
            index=event.value.get('index')
            if type(index) is not int or not 0<=index<len(points):return
            chosen=points[index]
            if not isinstance(chosen,dict) or owner is None or chosen.get('id',0)!=owner:return
            node._drag_pointer=None
        else:
            if owner is None:return
            chosen=next((p for p in points if isinstance(p,dict) and
                         p.get('id',0)==owner),None)
        if not isinstance(chosen,dict):return
        # ImageView touch coordinates are already expressed in its image/buffer
        # pixel space by Termux:GUI. Scaling them with getdimensions() again
        # moves the thumb away from the finger on high-density screens.
        try:
            x=float(chosen['x'])
        except (ValueError,TypeError,KeyError,OverflowError):
            return
        if not math.isfinite(x):
            return
        if action in ('down','pointer_down'):
            node._drag_pointer=chosen.get('id',0)
        # Keep the track endpoints identical to those used by _draw_slider.
        left,right=22,512-23
        fraction=max(0.0,min(1.0,(x-left)/(right-left)))
        node.value=node.min+(node.max-node.min)*fraction

    def render(self,root):
        return self._make(root,None)
    def stop(self):
        """Stop the event loop even for overlays without destroy lifecycle events."""
        self._stop_requested=True
        if self.activity is not None:self.activity.finish()

    def event(self,e):
        from .advanced import TabbedPanel,InfiniteCanvas
        if e.type=='back':self.stop();return
        if e.type=='destroy':return
        if e.type not in ('click','text','itemselected','touch'):return
        match=e.value.get('id')
        # The Android protocol sends a numeric ID. Keep the legacy equality
        # fallback for custom/mock bindings that do not expose a scalar ID.
        indexed=type(match) in (int,str)
        if e.type=='itemselected':
            parent=self._tab_index.get(match) if indexed else None
            if parent is None:
                parent=next((item for item in self.nodes if
                             isinstance(item,TabbedPanel) and match==item._tab_bar),None)
            if parent is not None:
                value=e.value.get('selected')
                try:index=int(value)
                except (TypeError,ValueError,OverflowError):return
                if not 0<=index<len(parent.children):return
                parent._tab_syncing=True
                try:parent.switch(parent.children[index].name)
                finally:parent._tab_syncing=False
                return
        node=self._native_index.get(match) if indexed else None
        if node is None:
            node=next((item for item in self.nodes if match==item._native),None)
        if node is not None:
            if e.type=='touch' and isinstance(node,Slider):
                self._slider_touch(node,e)
            elif e.type=='touch' and isinstance(node,InfiniteCanvas):
                node._touch(e)
            elif e.type=='itemselected' and isinstance(node,Spinner):
                node.text=str(e.value.get('selected',''))
            elif e.type=='click':
                if isinstance(node,ToggleButton) and 'set' in e.value:
                    node.state='down' if e.value['set'] else 'normal'
                if isinstance(node,(Switch,CheckBox)) and 'set' in e.value:
                    node.active=bool(e.value['set'])
                node.dispatch('on_press')
                node.dispatch('on_release')
            elif e.type=='text' and isinstance(node,TextInput):
                val=e.value.get('text')
                if val is None:
                    val=node._native.gettext()
                node.text=str(val)
            break
    def run(self,root,on_start=None):
        with self.tg.Connection() as c:
            self.connection=c
            options={'intercept':True}
            if self.window_mode=='dialog':options['dialog']=True
            if self.window_mode=='overlay':options['overlay']=True
            self.activity=self.tg.Activity(c,**options)
            try:
                from .theme import apply_activity_theme
                apply_activity_theme(self.activity,self.theme)
                self.render(root)
                if on_start: on_start()
                running=True
                while running and not self._stop_requested:
                    event=c.checkevent()
                    if event is not None:
                        self.event(event)
                        if event.type=='destroy' and event.value.get('finishing',False):
                            running=False
                    Clock.tick()
                    if event is None and not self._stop_requested:
                        time.sleep(0.01)
            finally:
                # Relinquish C's exported mmap reference before closing the buffer.
                for slider,buffer,canvas in reversed(self._slider_resources):
                    slider._slider_draw=None
                    slider._drag_pointer=None
                    canvas.close()
                    buffer.__exit__(None,None,None)
                self._slider_resources.clear()
                self._native_index.clear()
                self._tab_index.clear()
                for viewport,buffer,canvas in reversed(self._canvas_resources):
                    viewport._draw_viewport=None
                    canvas.close()
                    buffer.__exit__(None,None,None)
                self._canvas_resources.clear()
                self.nodes.clear()
                for node in root.walk():
                    node._native=None
                    node._theme_hook=None
                    node._effective_theme=None
                    node._applied_native_style.clear()
                    if hasattr(node,'_sync_views'):node._sync_views=None
                    if hasattr(node,'_tab_bar'):node._tab_bar=None
                    if hasattr(node,'_inherited_text_style'):node._inherited_text_style=None
                self.activity=None
                self.connection=None

class App(EventDispatcher):
    _running_app=None
    def __init__(self,**kwargs):
        from .theme import resolve_theme,get_theme
        from .typography import resolve_text_style,get_text_style
        selected=kwargs.pop('theme',None)
        typography=kwargs.pop('text_style',None)
        self.window_mode=kwargs.pop('window_mode','normal')
        super().__init__(**kwargs);self.root=None;self._backend=None
        self.theme=resolve_theme(selected or get_theme())
        self.text_style=resolve_text_style(typography or get_text_style())

    def set_theme(self,theme=None,**colors):
        """Switch a running application's palette without rebuilding its tree."""
        from .theme import resolve_theme
        self.theme=resolve_theme(theme or self.theme,colors)
        if self._backend is not None:self._backend.apply_theme(self.theme)
        return self.theme
    def set_text_style(self,style='body',**overrides):
        from .typography import resolve_text_style
        self.text_style=resolve_text_style(style,**overrides)
        if self._backend:self._backend.apply_text_style(self.text_style)
        return self.text_style
    @classmethod
    def get_running_app(cls):return App._running_app
    def build(self):return None
    def on_start(self):pass
    def on_stop(self):pass
    def run(self):
        if App._running_app is not None:raise RuntimeError('an App is already running')
        App._running_app=self
        try:
            self.root=self.build()
            if self.root is None:
                from .kv import Builder
                self.root=Builder.load_file(type(self).__name__.removesuffix('App').lower()+'.kv')
            if not isinstance(self.root,Widget):raise TypeError('App.build must return a Widget')
            self._backend=TermuxBackend(theme=self.theme,text_style=self.text_style,
                                        window_mode=self.window_mode)
            self._backend.run(self.root,self.on_start)
        finally:
            try:self.on_stop()
            finally:App._running_app=None
    def stop(self):
        if self._backend:self._backend.stop()
