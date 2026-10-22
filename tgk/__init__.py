"""TGK public API; lazy imports keep the global site hook inexpensive."""
__version__ = '0.2.0'
_EXPORTS={
    'App','Widget','BoxLayout','GridLayout','FloatLayout','ScrollView',
    'Label','Button','TextInput','CheckBox','Switch','ProgressBar','Clock',
    'Image','Spinner','ToggleButton','EventDispatcher','StringProperty',
    'NumericProperty','BooleanProperty','ObjectProperty','ListProperty',
    'DictProperty','OptionProperty','BoundedNumericProperty',
}
def __getattr__(name):
    if name in _EXPORTS:
        from importlib import import_module
        result=getattr(import_module('.widgets',__name__),name)
        globals()[name]=result
        return result
    if name=='Builder':
        from .kv import Builder
        globals()[name]=Builder
        return Builder
    raise AttributeError(name)
