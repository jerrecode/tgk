"""Semantic theme validation, inheritance and native color propagation."""
import unittest

from tgk.theme import (
    DEFAULT_NAME, PRESETS, ROLES, Theme, get_theme, set_theme,
    resolve_theme, normalize_color, rgba_channels, tgui_color,
    apply_activity_theme,
)
from tgk.widgets import (
    App, BoxLayout, Button, Label, Slider, TextInput, TermuxBackend,
)


class NativeView:
    def __init__(self):
        self.backgrounds = []
        self.foregrounds = []
    def setbackgroundcolor(self, value):
        self.backgrounds.append(value)
    def settextcolor(self, value):
        self.foregrounds.append(value)


class ThemeTests(unittest.TestCase):
    def test_all_preset_roles_are_complete(self):
        self.assertGreaterEqual(len(PRESETS), 10)
        for name in PRESETS:
            with self.subTest(name=name):
                theme=resolve_theme(name)
                self.assertEqual(set(theme.colors),set(ROLES))
                self.assertTrue(all(len(normalize_color(c))==9 for c in theme.colors.values()))

    def test_normalization_and_byte_order(self):
        self.assertEqual(normalize_color('#1aF'),'#11AAFFFF')
        self.assertEqual(normalize_color('#102030'),'#102030FF')
        self.assertEqual(rgba_channels('#10203040'),(16,32,48,64))
        self.assertEqual(tgui_color('#11223344'),0x44332211)

    def test_rejects_bad_color_and_unknown_roles(self):
        for bad in ('#rrggbb','#12345','transparent','123456',''):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_color(bad)
        with self.assertRaisesRegex(ValueError,'unknown theme'):
            resolve_theme('does-not-exist')
        with self.assertRaisesRegex(ValueError,'unknown color roles'):
            resolve_theme('midnight',{'unsupported':'#FFFFFF'})

    def test_theme_copies_overrides_without_mutating_preset(self):
        base=resolve_theme(DEFAULT_NAME)
        changed=base.override(accent='#102030')
        self.assertEqual(changed['accent'],'#102030FF')
        self.assertNotEqual(changed['accent'],base['accent'])
        self.assertEqual(changed.to_dict()['name'],DEFAULT_NAME)
        with self.assertRaises(TypeError):changed.colors['accent']='#FFFFFF'

    def test_global_selector_and_app_override(self):
        before=get_theme()
        try:
            set_theme('ocean',accent='#FEA512')
            self.assertEqual(get_theme()['accent'],'#FEA512FF')
            app=App(theme='paper')
            self.assertEqual(app.theme.name,'paper')
            self.assertEqual(app.set_theme('forest').name,'forest')
        finally:
            set_theme(before)

    def test_activity_theme_is_applied_before_children(self):
        class Activity:
            args = None
            def settheme(self,*values):
                self.args=values
        activity=Activity()
        theme=apply_activity_theme(activity,'ocean')
        self.assertEqual(len(activity.args),5)
        self.assertEqual(activity.args[4],tgui_color(theme['accent']))

    def test_inherited_and_local_widget_overrides(self):
        backend=TermuxBackend(tg=object(),theme='midnight')
        root=BoxLayout(orientation='vertical',colors={'text':'#FAFAFA'})
        inner=BoxLayout(orientation='horizontal',colors={'surface':'#212121'})
        button=Button(text='Test',text_color='#123456',background_color='#ABCDEF')
        inner.add_widget(button);root.add_widget(inner)
        self.assertEqual(backend._node_theme(inner)['surface'],'#212121FF')
        self.assertEqual(backend._node_theme(button)['text'],'#FAFAFAFF')
        button._native=NativeView()
        backend.nodes.append(button)
        backend.apply_theme()
        self.assertEqual(button._native.backgrounds[-1],tgui_color('#ABCDEF'))
        self.assertEqual(button._native.foregrounds[-1],tgui_color('#123456'))
        button.background_color='#001122'
        self.assertEqual(button._native.backgrounds[-1],tgui_color('#ABCDEF'))
        button._theme_hook=lambda changed:backend.invalidate_style(button,changed)
        button.background_color='#445566'
        self.assertEqual(button._native.backgrounds[-1],tgui_color('#445566'))

    def test_live_theme_changes_keep_local_override(self):
        backend=TermuxBackend(tg=object(),theme='paper')
        root=BoxLayout()
        a=Label(text='Inherited')
        b=Label(text='Pinned',colors={'text':'#FF00AA'})
        root.add_widget(a);root.add_widget(b)
        for node in (a,b):
            node._native=NativeView()
            backend.nodes.append(node)
        backend.apply_theme()
        before_a=a._native.foregrounds[-1]
        backend.apply_theme('terminal')
        self.assertNotEqual(a._native.foregrounds[-1],before_a)
        self.assertEqual(b._native.foregrounds[-1],tgui_color('#FF00AA'))


if __name__=='__main__':
    unittest.main()
