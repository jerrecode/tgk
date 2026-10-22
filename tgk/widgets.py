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
        super().__init__(**kwargs)
        if type(self).__name__ not in (
            'Widget','BoxLayout','GridLayout','FloatLayout','ScrollView','Label',
            'Button','TextInput','CheckBox','Switch','ProgressBar','Image','Spinner',
            'ToggleButton'):
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
        if name=='font_size' and hasattr(n,'settextsize'): n.settextsize(int(value))
        if name=='active' and hasattr(n,'setchecked'): n.setchecked(bool(value))
        if name=='source' and isinstance(self,Image) and hasattr(n,'setimage'):
            n.setimage(self._read_image())
        if name=='values' and isinstance(self,Spinner) and hasattr(n,'setlist'):
            n.setlist([str(v) for v in value])
        if name=='value' and isinstance(self,ProgressBar):
            n.setprogress(max(0,min(100,round(100*value/self.max if self.max else 0))))
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
    def __init__(self, tg=None):
        if tg is None:
            try: import termuxgui as tg
            except ImportError as exc:
                raise RuntimeError('pip install termuxgui on Termux; Termux:GUI Android plugin is also required') from exc
        self.tg=tg
        self.connection=None; self.activity=None;self.nodes=[]
    def _make(self,node,parent):
        tg=self.tg;a=self.activity
        if isinstance(node,BoxLayout):
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
        if isinstance(node,Label):native.settextsize(int(node.font_size))
        if isinstance(node,ProgressBar):native.setprogress(max(0,min(100,round(100*node.value/node.max if node.max else 0))))
        if hasattr(node,'height') and node.height is not None: native.setheight(int(node.height))
        if hasattr(node,'width') and node.width is not None:native.setwidth(int(node.width))
        if isinstance(node.parent,BoxLayout):
            if node.parent.orientation=='vertical':
                if not hasattr(node,'width'):native.setwidth(tg.View.MATCH_PARENT)
                if isinstance(node,ScrollView) and not hasattr(node,'height'):
                    native.setheight(0);native.setlinearlayoutparams(1)
            elif node.parent.orientation=='horizontal' and not hasattr(node,'width'):
                native.setwidth(0);native.setlinearlayoutparams(1)
        if isinstance(node.parent,GridLayout):
            index=node.parent.children.index(node)
            native.setgridlayoutparams(index//int(node.parent.cols),index%int(node.parent.cols))
        if isinstance(node,BoxLayout) and node.padding:
            native.setmargin(int(node.padding if isinstance(node.padding,(int,float)) else node.padding[0]))
        for child in node.children:self._make(child,native)
        return native
    def render(self,root):
        return self._make(root,None)
    def event(self,e):
        if e.type=='back':self.activity.finish();return
        if e.type=='destroy':return
        if e.type not in ('click','text','itemselected'):return
        match=e.value.get('id')
        for node in self.nodes:
            # Termux:GUI Python bindings implement native view == numerical ID.
            if match!=node._native:continue
            if e.type=='itemselected' and isinstance(node,Spinner):
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
            self.activity=self.tg.Activity(c,intercept=True)
            self.render(root)
            if on_start: on_start()
            running=True
            while running:
                event=c.checkevent()
                if event is not None:
                    self.event(event)
                    if event.type=='destroy' and event.value.get('finishing',False):running=False
                Clock.tick()
                if event is None:time.sleep(0.01)
            self.nodes.clear()
            for node in root.walk():node._native=None
            self.activity=None;self.connection=None

class App(EventDispatcher):
    _running_app=None
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.root=None;self._backend=None
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
            self._backend=TermuxBackend()
            self._backend.run(self.root,self.on_start)
        finally:
            try:self.on_stop()
            finally:App._running_app=None
    def stop(self):
        if self._backend and self._backend.activity:self._backend.activity.finish()
