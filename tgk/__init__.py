"""TGK public API; lazy imports keep the global site hook inexpensive."""
__version__ = '0.6.3'
_EXPORTS={
    'App','Widget','BoxLayout','GridLayout','ResponsiveGrid','FloatLayout','ScrollView',
    'Label','Button','TextInput','CheckBox','Switch','ProgressBar','Clock',
    'Image','Spinner','ToggleButton','Slider','EventDispatcher','StringProperty',
    'NumericProperty','BooleanProperty','ObjectProperty','ListProperty',
    'DictProperty','OptionProperty','BoundedNumericProperty',
}
def __getattr__(name):
    if name in _EXPORTS:
        from importlib import import_module
        result=getattr(import_module('.widgets',__name__),name)
        globals()[name]=result
        return result
    if name in ('Theme','PRESETS','ROLES','DEFAULT_NAME','resolve_theme',
                'get_theme','set_theme','load_theme','tgui_color',
                'rgba_channels','normalize_color','apply_activity_theme'):
        from importlib import import_module
        result=getattr(import_module('.theme',__name__),name)
        globals()[name]=result
        return result
    if name in ('Screen','ScreenManager','TabbedPanel','Tab','PageView',
                'Popup','RichTextLabel','RichTable','IconLabel','InfiniteCanvas'):
        from importlib import import_module
        result=getattr(import_module('.advanced',__name__),name)
        globals()[name]=result
        return result
    if name in ('TextStyle','TextSpan','PRESETS_TEXT','resolve_text_style',
                'get_text_style','set_text_style','rich_html'):
        from importlib import import_module
        module=import_module('.typography',__name__)
        result=module.PRESETS if name=='PRESETS_TEXT' else getattr(module,name)
        globals()[name]=result
        return result
    if name in ('Icon','ICONS','CATEGORIES','EXTENSION_ICONS','glyph',
                'icon_for_path','icon_names','svg'):
        from importlib import import_module
        result=getattr(import_module('.icons',__name__),name)
        globals()[name]=result
        return result
    if name in ('Limits','TransferResult','BoundedPool','transfer','copy_file',
                'hash_file','download','ffprobe'):
        from importlib import import_module
        result=getattr(import_module('.io_pipeline',__name__),name)
        globals()[name]=result
        return result
    if name in ('ScreenMetrics','LayoutScale','arrange_spans','measure_activity'):
        from importlib import import_module
        result=getattr(import_module('.adaptive',__name__),name)
        globals()[name]=result
        return result
    if name in ('ComponentStyle','TableStyle','DEFAULT_STYLES',
                'resolve_component_style','table_html'):
        from importlib import import_module
        result=getattr(import_module('.style_tokens',__name__),name)
        globals()[name]=result
        return result
    if name in ('Layer','Recipe','EXTENSIONS','SPECIAL_FILES','recipe_names',
                'recipe_for','render_svg','asset_key_for_path','build_assets'):
        from importlib import import_module
        result=getattr(import_module('.icon_builder',__name__),name)
        globals()[name]=result
        return result
    if name in ('DEFAULT_CONFIG','OPTIONS','config_home','config_path',
                'initialize_config','load_config','validate_config',
                'configured_theme','configured_text_style',
                'configured_layout_scale','configured_io_limits',
                'option_config','update_config','update_settings','clear_config_cache'):
        from importlib import import_module
        result=getattr(import_module('.config',__name__),name)
        globals()[name]=result
        return result
    if name=='Builder':
        from .kv import Builder
        globals()[name]=Builder
        return Builder
    raise AttributeError(name)
