"""Accessible responsive sizing without overriding native layout ownership."""
import unittest
from types import SimpleNamespace

from tgk.adaptive import LayoutScale,ScreenMetrics,arrange_spans
from tgk.config import DEFAULT_CONFIG,validate_config
from tgk.widgets import BoxLayout,Button,ResponsiveGrid,TermuxBackend
from test_tgk import FakeTG


class AdaptiveContractTests(unittest.TestCase):
    def test_breakpoints_are_configurable_and_preserve_logical_spans(self):
        m=ScreenMetrics(640,800)
        default=LayoutScale()
        tuned=LayoutScale(compact_breakpoint_dp=700,
                          expanded_breakpoint_dp=980,columns=6)
        self.assertEqual(default.size_class(m),'medium')
        self.assertEqual(tuned.size_class(m),'compact')
        cards=[Button(span_compact=12,span_medium=6,span_expanded=4) for _ in range(3)]
        normal=arrange_spans(cards,columns=6,span_units=12,metrics=m)
        compact=arrange_spans(cards,columns=6,span_units=12,metrics=m,
                              size_class=tuned.size_class(m))
        self.assertEqual([x[3] for x in normal],[3,3,3])
        self.assertEqual([x[3] for x in compact],[6,6,6])
        with self.assertRaises(ValueError):
            LayoutScale(compact_breakpoint_dp=900,expanded_breakpoint_dp=600)
        with self.assertRaises(ValueError):
            LayoutScale(font_touch_scale_limit_pct=999)

    def test_accessibility_touch_bounds_not_screen_sized(self):
        settings=LayoutScale(touch_target_dp=48,font_touch_scale_limit_pct=150)
        self.assertEqual(settings.touch_height(metrics=ScreenMetrics(393,852,font_scale=1.0)),48)
        self.assertEqual(settings.touch_height(metrics=ScreenMetrics(393,852,font_scale=1.25)),60)
        self.assertEqual(settings.touch_height(metrics=ScreenMetrics(393,852,font_scale=5.0)),72)
        self.assertEqual(settings.touch_height(requested=88,
                         metrics=ScreenMetrics(393,852,font_scale=1.5)),88)

    def test_new_saved_settings_default_and_validate(self):
        current=validate_config({})
        for key in ('compact_breakpoint_dp','expanded_breakpoint_dp',
                    'font_touch_scale_limit_pct'):
            self.assertIn(key,current['layout'])
            self.assertIn(key,DEFAULT_CONFIG['layout'])
        with self.assertRaises(ValueError):
            validate_config({'layout':{'compact_breakpoint_dp':920,
                                       'expanded_breakpoint_dp':700}})

    def test_root_and_weighted_heights_stay_layout_managed_after_config(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale())
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=ScreenMetrics(393,852,font_scale=1.0)
        root=Button(text='Root',height=None)
        # Unspecified height means no 'height' attribute in this framework:
        del root.height
        backend.render(root)
        self.assertEqual(root._native.setheight_value,('MATCH_PARENT',))
        backend.screen_metrics=ScreenMetrics(393,852,font_scale=1.5)
        backend._refresh_touch_height(root)
        self.assertEqual(root._native.setheight_value,('MATCH_PARENT',))

        parent=BoxLayout(orientation='vertical')
        weighted=Button(text='Weighted',weight=1)
        parent.add_widget(weighted)
        other=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale())
        other.activity=FakeTG.Activity(None)
        other.screen_metrics=ScreenMetrics(393,852)
        other.render(parent)
        self.assertEqual(weighted._native.setheight_value,(0,))
        other.screen_metrics=ScreenMetrics(393,852,font_scale=1.5)
        other._refresh_touch_height(weighted)
        self.assertEqual(weighted._native.setheight_value,(0,))

    def test_explicit_button_heights_scale_and_cache(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale())
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=ScreenMetrics(393,852,font_scale=1)
        group=BoxLayout(orientation='vertical')
        btn=Button(text='Small',height=32)
        group.add_widget(btn)
        backend.render(group)
        self.assertEqual(btn._native.setheight_value,(48,))
        backend.screen_metrics=ScreenMetrics(393,852,font_scale=1.5)
        backend._refresh_touch_height(btn)
        self.assertEqual(btn._native.setheight_value,(72,))
        cache=dict(btn._applied_native_style)
        backend._refresh_touch_height(btn)
        self.assertEqual(btn._applied_native_style,cache)

    def test_live_grid_reflow_uses_current_scale_not_global_default(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale(
            compact_breakpoint_dp=700,expanded_breakpoint_dp=980))
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=ScreenMetrics(640,830)
        grid=ResponsiveGrid(cols=12)
        for _ in range(2):
            grid.add_widget(Button(span_compact=12,span_medium=6))
        backend.render(grid)
        self.assertEqual(grid.children[1]._native.setgridlayoutparams_value[:2],(1,0))


if __name__ == '__main__':
    unittest.main()
