"""Performance regression: local style mutations must not repaint the entire UI.

Before this fix a color swatch triggered Termux:GUI setters on every widget,
and a set of 11 swatches incurred O(11 * number_of_widgets) IPC messages.
"""
import unittest

from tgk.widgets import BoxLayout, Label, Button, TermuxBackend
from tgk.theme import tgui_color,resolve_theme
from tgk.demos import Laboratory


class CountingNative:
    def __init__(self):
        self.messages=[]
    def setbackgroundcolor(self,value):self.messages.append(('background',value))
    def settextcolor(self,value):self.messages.append(('foreground',value))
    def settextsize(self,value):self.messages.append(('size',value))


class StyleInvalidationTests(unittest.TestCase):
    def setUp(self):
        self.backend=TermuxBackend(tg=object(),theme='midnight')
        self.root=BoxLayout(orientation='vertical')
        self.labels=[Label(text=f'cell-{i}',height=40) for i in range(160)]
        for label in self.labels:self.root.add_widget(label)
        for node in self.root.walk():
            node._native=CountingNative()
            node._theme_hook=lambda name,node=node:self.backend.invalidate_style(node,name)
            self.backend.nodes.append(node)
        self.backend.apply_theme()
        self._reset_counts()

    def _reset_counts(self):
        for node in self.backend.nodes:node._native.messages.clear()

    def _messages(self):
        return sum(len(node._native.messages) for node in self.backend.nodes)

    def test_one_swatch_changes_only_one_view(self):
        target=self.labels[47]
        target.background_color='#345678'
        self.assertEqual(self._messages(),1)
        self.assertEqual(target._native.messages,
                         [('background',tgui_color('#345678'))])
        # Reassigning equivalent style does not issue another native command.
        target.background_color='#345678'
        self.assertEqual(self._messages(),1)

    def test_many_swatches_do_not_trigger_quadratic_ipc(self):
        for i in range(11):
            self.labels[i].background_color=f'#{i:02X}4277'
        self.assertEqual(self._messages(),11)
        self.assertEqual(sum(bool(x._native.messages) for x in self.labels),11)

    def test_inherited_palette_invalidates_only_changed_subtree(self):
        group=BoxLayout()
        for i in range(4):group.add_widget(Label(text=f'child-{i}'))
        group.parent=self.root
        self.root.children.append(group)
        for node in group.walk():
            node._native=CountingNative()
            node._theme_hook=lambda name,node=node:self.backend.invalidate_style(node,name)
            self.backend.nodes.append(node)
        self.backend.apply_theme()
        self._reset_counts()
        group.colors={'text':'#44BBDD'}
        self.assertEqual(self._messages(),4)
        self.assertEqual([len(c._native.messages) for c in group.children],
                         [1,1,1,1])
        self.assertEqual([len(c._native.messages) for c in self.labels],
                         [0]*160)

    def test_noop_global_reapply_sends_no_native_messages(self):
        self.backend.apply_theme('midnight')
        self.assertEqual(self._messages(),0)
        self.backend.apply_theme('ocean')
        changed=self._messages()
        self.assertGreater(changed,100)
        self._reset_counts()
        self.backend.apply_theme('ocean')
        self.assertEqual(self._messages(),0)

    def test_button_uses_button_text_role_not_body_text(self):
        root=BoxLayout()
        btn=Button(text="Do")
        root.add_widget(btn)
        btn._native=CountingNative()
        self.backend.nodes.append(btn)
        self.backend.apply_theme()
        expected=tgui_color(resolve_theme('ocean')['button_text']) if (
            self.backend.theme.name=='ocean') else tgui_color(resolve_theme('midnight')['button_text'])
        self.assertIn(('foreground',expected),btn._native.messages)


class StudioLiveSliderTests(unittest.TestCase):
    def test_offline_rgb_edits_apply_without_a_clock(self):
        app=Laboratory(scenario='12_studio')
        app.build()
        app.rgb_sliders[0].value=99
        self.assertEqual(app.theme['accent'][:3],'#63')
        self.assertIsNone(app._pending_rgb)

    def test_running_rgb_events_coalesce_to_one_timer(self):
        app=Laboratory(scenario='12_studio')
        app.build()
        class Running:activity=object()
        app._backend=Running()
        from tgk.widgets import Clock
        calls=[]
        original=Clock.schedule_once
        try:
            Clock.schedule_once=lambda callback,delay:(calls.append((callback,delay)) or object())
            app.rgb_sliders[0].value=77
            app.rgb_sliders[1].value=88
            app.rgb_sliders[2].value=99
            self.assertEqual(len(calls),1)
            self.assertEqual(app.theme['accent'],resolve_theme('midnight')['accent'])
            calls[0][0](0)
            self.assertEqual(app.theme['accent'],'#4D5863FF')
            self.assertIsNone(app._pending_rgb)
        finally:Clock.schedule_once=original


if __name__=="__main__":
    unittest.main()
