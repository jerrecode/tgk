"""Regression contracts for configurable fluid grids and accessible touch targets.

The Android View may already have MATCH_PARENT, an explicit size spec or a
weighted LinearLayout height. Screen font-scale changes must never destroy
those layout contracts.
"""
import unittest
from types import SimpleNamespace

from tgk.adaptive import LayoutScale, ScreenMetrics, arrange_spans
from tgk.widgets import TermuxBackend, BoxLayout, Button, ResponsiveGrid
from tgk.config import DEFAULT_CONFIG, validate_config


class Native:
    def __init__(self):
        self.heights=[]
        self.positions=[]
    def setheight(self,value):self.heights.append(value)
    def setgridlayoutparams(self,*args):self.positions.append(args)


class FluidScalingTests(unittest.TestCase):
    def setUp(self):
        self.scale=LayoutScale(columns=8,compact_breakpoint_dp=480,
                               expanded_breakpoint_dp=760,
                               font_touch_scale_limit_pct=150)
        self.backend=TermuxBackend(tg=object(),layout_scale=self.scale)
        self.backend.screen_metrics=ScreenMetrics(470,900,font_scale=1.25)

    def test_custom_breakpoints_and_span_normalization(self):
        self.assertEqual(self.scale.size_class(ScreenMetrics(470,900)),'compact')
        self.assertEqual(self.scale.size_class(ScreenMetrics(600,900)),'medium')
        self.assertEqual(self.scale.size_class(ScreenMetrics(800,500)),'expanded')
        items=[Button(span_compact=12,span_medium=6,span_expanded=4)
               for _ in range(4)]
        self.assertEqual([p[3] for p in arrange_spans(
            items,columns=8,span_units=12,metrics=ScreenMetrics(600,900),
            size_class=self.scale.size_class(ScreenMetrics(600,900)))],[4]*4)
        with self.assertRaises(ValueError):
            LayoutScale(compact_breakpoint_dp=950,expanded_breakpoint_dp=840)

    def test_font_scale_is_bounded_and_increases_touch_height(self):
        self.assertEqual(self.scale.touch_height(metrics=self.backend.screen_metrics),60)
        self.assertEqual(self.scale.touch_height(metrics=ScreenMetrics(
            393,850,font_scale=5.0)),72)
        self.assertEqual(self.scale.touch_height(90,metrics=self.backend.screen_metrics),90)

    def test_root_and_weighted_children_preserve_layout_managed_height(self):
        root=Button(text='root')
        root._native=Native()
        self.backend._set_touch_height(root)
        self.assertEqual(root._native.heights,[])
        parent=BoxLayout(orientation='vertical')
        weighted=Button(text='fill',weight=1)
        parent.add_widget(weighted)
        weighted._native=Native()
        self.backend._set_touch_height(weighted)
        self.assertEqual(weighted._native.heights,[])
        self.backend.screen_metrics=ScreenMetrics(400,850,font_scale=1.8)
        self.backend._set_touch_height(root)
        self.backend._set_touch_height(weighted)
        self.assertEqual(root._native.heights,[])
        self.assertEqual(weighted._native.heights,[])

    def test_explicit_height_and_unweighted_child_reflow_without_duplicate_ipc(self):
        parent=BoxLayout(orientation='vertical')
        implicit=Button(text='normal')
        explicit=Button(text='fixed',height=80)
        parent.add_widget(implicit)
        parent.add_widget(explicit)
        for child in parent.children:child._native=Native()
        self.backend._set_touch_height(implicit)
        self.backend._set_touch_height(explicit)
        self.assertEqual(implicit._native.heights,[60])
        self.assertEqual(explicit._native.heights,[80])
        self.backend._set_touch_height(implicit)
        self.backend._set_touch_height(explicit)
        self.assertEqual(implicit._native.heights,[60])
        self.assertEqual(explicit._native.heights,[80])
        self.backend.screen_metrics=ScreenMetrics(400,850,font_scale=2)
        self.backend._set_touch_height(implicit)
        self.backend._set_touch_height(explicit)
        self.assertEqual(implicit._native.heights,[60,72])
        self.assertEqual(explicit._native.heights,[80])

    def test_in_place_grid_reflow_uses_configured_size_class(self):
        grid=ResponsiveGrid(cols=8,span_units=12)
        for _ in range(4):
            child=Button(span_compact=12,span_medium=6,span_expanded=4)
            grid.add_widget(child)
            child._native=Native()
        self.backend._reflow_grid(grid)
        self.assertEqual([c._native.positions[-1][1] for c in grid.children],
                         [0,0,0,0])
        self.backend.screen_metrics=ScreenMetrics(600,900)
        self.backend._reflow_grid(grid)
        self.assertEqual([c._native.positions[-1][1] for c in grid.children],
                         [0,4,0,4])
        calls=sum(len(c._native.positions) for c in grid.children)
        self.backend._reflow_grid(grid)
        self.assertEqual(sum(len(c._native.positions) for c in grid.children),calls)

    def test_legacy_config_still_valid_and_new_fields_persistable(self):
        cfg=validate_config({'layout':{'columns':8,
                            'compact_breakpoint_dp':480,
                            'expanded_breakpoint_dp':760,
                            'font_touch_scale_limit_pct':175}})
        self.assertEqual(cfg['layout']['columns'],8)
        self.assertEqual(cfg['layout']['font_touch_scale_limit_pct'],175)
        self.assertEqual(validate_config({'layout':{'columns':12}})['layout']
                         ['compact_breakpoint_dp'],600)
        with self.assertRaises(ValueError):
            validate_config({'layout':{'expanded_breakpoint_dp':200}})


if __name__=='__main__':
    unittest.main()
