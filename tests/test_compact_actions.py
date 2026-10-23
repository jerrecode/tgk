"""Mobile close-button sizing, anchoring and live window backdrop regression."""
import unittest
from tgk.widgets import BoxLayout,Button,Widget,Label,TermuxBackend
from tgk.layout_helpers import action_width,compact_action_bar
from tgk.demos import Laboratory,SCENARIOS
from tgk.adaptive_demo import AdaptiveLab
from tgk.theme import tgui_color,resolve_theme
from test_tgk import FakeTG


class CompactFooterTests(unittest.TestCase):
    def test_footer_button_stays_small_and_bottom_right(self):
        bar=compact_action_bar("Close",margin=12)
        self.assertIsInstance(bar,BoxLayout)
        self.assertEqual(bar.orientation,"horizontal")
        self.assertEqual(bar.height,72)
        self.assertEqual(bar.padding,12)
        self.assertEqual(len(bar.children),2)
        spacer,button=bar.children
        self.assertIs(type(spacer),Widget)
        self.assertEqual(spacer.weight,1)
        self.assertIsInstance(button,Button)
        self.assertEqual(button.height,48)
        self.assertLessEqual(button.width,112)
        self.assertGreaterEqual(button.width,48)
        self.assertEqual(button.text,"Close")
        self.assertIs(button.parent,bar)

    def test_footer_callback(self):
        calls=[]
        bar=compact_action_bar("Close",lambda:calls.append("done"))
        bar.children[-1].dispatch("on_release")
        self.assertEqual(calls,["done"])

    def test_other_actions_are_text_bounded(self):
        self.assertLessEqual(action_width("Close"),112)
        self.assertLessEqual(action_width("A complicated operation"),224)
        self.assertGreaterEqual(action_width("OK"),64)
        with self.assertRaises(ValueError):action_width("")

    def test_every_lab_has_compact_close_with_bounded_other_buttons(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                app=Laboratory(scenario=scenario)
                root=app.build()
                close=[n for n in root.walk() if isinstance(n,Button) and n.text=="Close"]
                self.assertEqual(len(close),1)
                button=close[0]
                self.assertLessEqual(button.width,112)
                self.assertEqual(button.parent.orientation,"horizontal")
                self.assertIs(root.children[-1],button.parent)
                for item in root.walk():
                    if isinstance(item,Button):
                        self.assertTrue(hasattr(item,"width"),
                                        f"Unbounded button: {scenario}, {item.text}")
                        self.assertLessEqual(item.width,300)

    def test_adaptive_demo_compact_footer(self):
        app=AdaptiveLab()
        root=app.build()
        footer=root.children[-1]
        self.assertEqual(footer.children[-1].text,"Close")
        self.assertLessEqual(footer.children[-1].width,112)

    def test_native_footer_spacer_has_weighted_width(self):
        FakeTG.views=[];FakeTG.count=0
        b=TermuxBackend(tg=FakeTG)
        b.activity=FakeTG.Activity(None)
        root=BoxLayout(orientation="vertical")
        root.add_widget(Label(text="some content",height=40))
        bar=compact_action_bar("Close")
        root.add_widget(bar)
        b.render(root)
        spacer=bar.children[0]
        self.assertEqual(spacer._native.setwidth_value,(0,))
        self.assertEqual(spacer._native.setlinearlayoutparams_value,(1,))
        self.assertEqual(bar.children[-1]._native.setwidth_value,
                         (bar.children[-1].width,))
        self.assertEqual(root._native.setheight_value,(FakeTG.View.MATCH_PARENT,))


class WindowBackdropTests(unittest.TestCase):
    def test_changing_theme_updates_activity_and_repaints_root(self):
        class ActivityWithTheme:
            def __init__(self):self.calls=[]
            def settheme(self,*args):self.calls.append(args)
        class MockNative:
            def __init__(self):self.background=[]
            def setbackgroundcolor(self,value):self.background.append(value)
        backend=TermuxBackend(tg=FakeTG,theme="ocean")
        act=ActivityWithTheme()
        backend.activity=act
        root=BoxLayout()
        root._native=MockNative()
        backend.nodes=[root]
        backend.apply_theme("forest")
        expected=resolve_theme("forest")
        self.assertEqual(len(act.calls),1)
        self.assertEqual(root._native.background[-1],tgui_color(expected["background"]))
        backend.apply_theme("paper")
        self.assertEqual(len(act.calls),2)
        self.assertEqual(root._native.background[-1],
                         tgui_color(resolve_theme("paper")["background"]))


if __name__=="__main__":unittest.main()
