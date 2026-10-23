"""Android 16 regressions: keyboard composition, FrameLayout sizing, overlay errors."""
import unittest
from types import SimpleNamespace
from tgk.widgets import App,TextInput,Label,Button,TermuxBackend,FloatLayout
from tgk.advanced import ScreenManager,Screen,TabbedPanel,Tab
from test_tgk import FakeTG


class InputFrameTests(unittest.TestCase):
    def setUp(self):
        FakeTG.views=[];FakeTG.count=0;FakeTG.events=[]

    def test_android_text_event_does_not_echo_settext(self):
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        field=TextInput(text='a',multiline=True)
        backend.render(field)
        seen=[]
        field.bind(text=lambda _,value:seen.append(value))
        backend.event(FakeTG.Event('text',{'id':field._native.id,'text':'abc'}))
        self.assertEqual(field.text,'abc')
        self.assertEqual(seen,['abc'])
        self.assertFalse(hasattr(field._native,'settext_value'))
        self.assertNotIn('_native_text_event',field.__dict__)
        field.text='programmatic edit'
        self.assertEqual(field._native.settext_value,('programmatic edit',))

    def test_callback_transform_may_update_native_text(self):
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        field=TextInput(text='a')
        backend.render(field)
        def clean(_source,value):
            if value!=value.upper():field.text=value.upper()
        field.bind(text=clean)
        backend.event(FakeTG.Event('text',{'id':field._native.id,'text':'abcd'}))
        self.assertEqual(field.text,'ABCD')
        self.assertEqual(field._native.settext_value,('ABCD',))

    def test_tab_and_screen_children_fill_frame_viewport(self):
        for manager in (ScreenManager(),TabbedPanel()):
            backend=TermuxBackend(tg=FakeTG)
            backend.activity=FakeTG.Activity(None)
            page_type=Tab if isinstance(manager,TabbedPanel) else Screen
            p=page_type(name='one')
            p.add_widget(Label(text='one'))
            manager.add_widget(p)
            backend.render(manager)
            self.assertEqual(p._native.setwidth_value,('MATCH_PARENT',))
            self.assertEqual(p._native.setheight_value,('MATCH_PARENT',))
            self.assertEqual(manager._native.setwidth_value,('MATCH_PARENT',))

    def test_float_layout_children_default_to_full_viewport(self):
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        root=FloatLayout()
        child=Screen(name='page')
        root.add_widget(child)
        backend.render(root)
        self.assertEqual(child._native.setwidth_value,('MATCH_PARENT',))
        self.assertEqual(child._native.setheight_value,('MATCH_PARENT',))

    def test_explicit_popup_size_not_overridden_by_frame_fill(self):
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        root=FloatLayout()
        from tgk.advanced import Popup
        popup=Popup(width=300,height=210,visible=False)
        root.add_widget(popup)
        backend.render(root)
        self.assertEqual(popup._native.setwidth_value,(300,))
        self.assertEqual(popup._native.setheight_value,(210,))

    def test_overlay_protocol_error_has_guidance_without_opt_in(self):
        class RejectOverlay(FakeTG.Activity):
            def __init__(self,c,intercept=False,overlay=False):
                if overlay:raise TypeError('cannot unpack non-iterable int object')
                super().__init__(c,intercept=intercept)
        class FakeOverlay(FakeTG):Activity=RejectOverlay
        backend=TermuxBackend(tg=FakeOverlay,window_mode='overlay')
        FakeTG.events=[FakeTG.Event('destroy',{'finishing':True})]
        with self.assertRaisesRegex(RuntimeError,'Display over other apps'):
            backend.run(Label(text='x'))

    def test_overlay_explicit_fallback_reopens_normal_activity(self):
        class RejectOverlay(FakeTG.Activity):
            attempts=[]
            def __init__(self,c,intercept=False,overlay=False):
                type(self).attempts.append(overlay)
                if overlay:raise TypeError('cannot unpack non-iterable int object')
                super().__init__(c,intercept=intercept)
        class FakeOverlay(FakeTG):Activity=RejectOverlay
        backend=TermuxBackend(tg=FakeOverlay,window_mode='overlay')
        backend.overlay_fallback=True
        FakeTG.events=[FakeTG.Event('destroy',{'finishing':True})]
        backend.run(Label(text='fallback'))
        self.assertEqual(RejectOverlay.attempts,[True,False])
        self.assertIsNone(backend.activity)


if __name__=='__main__':unittest.main()
