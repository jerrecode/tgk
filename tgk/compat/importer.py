"""Selective PEP451 import hook: transitive imports require no code rewrite.
Tiny during normal Python startup; compatibility classes load only for Kivy imports.
"""
import importlib.abc
import importlib.machinery
import sys

_PACKAGE_NAMES={'kivy','kivy.uix','kivy.core'}
_SUPPORTED={
 'kivy','kivy.app','kivy.uix','kivy.uix.widget','kivy.uix.boxlayout',
 'kivy.uix.gridlayout','kivy.uix.floatlayout','kivy.uix.scrollview',
 'kivy.uix.label','kivy.uix.button','kivy.uix.textinput',
 'kivy.uix.checkbox','kivy.uix.switch','kivy.uix.progressbar',
 'kivy.uix.image','kivy.uix.spinner','kivy.uix.togglebutton',
 'kivy.uix.slider',
 'kivy.clock','kivy.lang','kivy.factory','kivy.event','kivy.properties',
 'kivy.metrics','kivy.core','kivy.core.window',
}

class _Window:
    size=(0,0);width=0;height=0
    @staticmethod
    def bind(**kwargs):
        raise NotImplementedError('Kivy Window event bindings not supported by Termux:GUI adapter')

def _resolve(fullname):
    from .. import widgets
    if fullname in _PACKAGE_NAMES:return {'__version__':'0.2.0-tgk-subset','require':lambda *_:None} if fullname=='kivy' else {}
    if fullname=='kivy.app':return {'App':widgets.App}
    if fullname=='kivy.clock':return {'Clock':widgets.Clock}
    if fullname=='kivy.event':return {'EventDispatcher':widgets.EventDispatcher}
    if fullname=='kivy.metrics':return {'dp':float,'sp':float,'pt':float}
    if fullname=='kivy.core.window':return {'Window':_Window()}
    if fullname in ('kivy.lang','kivy.factory'):
        from ..kv import Builder,Factory
        return {'Builder':Builder} if fullname.endswith('.lang') else {'Factory':Factory}
    if fullname=='kivy.properties':
        return {name:getattr(widgets,name) for name in (
            'StringProperty','NumericProperty','BooleanProperty',
            'ObjectProperty','ListProperty','DictProperty',
            'OptionProperty','BoundedNumericProperty')}
    widget_name=fullname.rsplit('.',1)[-1]
    widget_map={
        'widget':'Widget','boxlayout':'BoxLayout','gridlayout':'GridLayout',
        'floatlayout':'FloatLayout','scrollview':'ScrollView','label':'Label',
        'button':'Button','textinput':'TextInput','checkbox':'CheckBox',
        'switch':'Switch','progressbar':'ProgressBar','image':'Image',
        'spinner':'Spinner','togglebutton':'ToggleButton',
        'slider':'Slider',
    }
    cls=widget_map.get(widget_name)
    if cls is None:raise ImportError(f'Unsupported TGK Kivy module: {fullname}')
    return {cls:getattr(widgets,cls)}

class Loader(importlib.abc.Loader):
    def create_module(self,spec):return None
    def exec_module(self,module):
        module.__dict__.update(_resolve(module.__name__))
        module.__dict__['__tgk_shim__']=True
        if module.__name__ in _PACKAGE_NAMES:module.__path__=[]
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname not in _SUPPORTED:return None
        return importlib.machinery.ModuleSpec(fullname,Loader(),is_package=fullname in _PACKAGE_NAMES)
_finder=Finder()
def activate():
    if _finder not in sys.meta_path:
        if 'kivy' in sys.modules and not getattr(sys.modules['kivy'],'__tgk_shim__',False):
            raise RuntimeError('Kivy already imported; activate TGK before importing Kivy')
        sys.meta_path.insert(0,_finder)
def deactivate():
    if _finder in sys.meta_path:sys.meta_path.remove(_finder)
