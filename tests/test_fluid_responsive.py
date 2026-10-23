"""Width-aware Android layouts and bounded accessibility sizing contracts."""
import unittest
from types import SimpleNamespace

from tgk.adaptive import ScreenMetrics,LayoutScale,arrange_spans
from tgk.widgets import Button,Label,ResponsiveGrid,TermuxBackend,Slider
from tgk.config import DEFAULT_CONFIG,validate_config
from test_tgk import FakeTG


class FluidGeometryTests(unittest.TestCase):
    def test_safe_content_uses_only_authoritative_insets(self):
        size=ScreenMetrics(393,852,font_scale=1.4)
        self.assertEqual(size.safe_content_size_dp,(393,852))
        given=ScreenMetrics(393,852,inset_top_dp=28,inset_bottom_dp=24)
        self.assertEqual(given.safe_content_size_dp,(393,800))
        self.assertTrue(size.aspect_ratio<1)
        self.assertFalse(size.is_landscape)

    def test_configurable_width_classes_margin_and_gutter(self):
        scale=LayoutScale(columns=8,compact_breakpoint_dp=480,
                          expanded_breakpoint_dp=760,medium_margin_dp=20)
        self.assertEqual(scale.size_class(ScreenMetrics(470,950)),"compact")
        self.assertEqual(scale.size_class(ScreenMetrics(600,950)),"medium")
        self.assertEqual(scale.size_class(ScreenMetrics(800,400)),"expanded")
        self.assertGreater(scale.column_width(ScreenMetrics(800,400)),0)
        self.assertEqual(scale.margin(ScreenMetrics(600,900)),20)
        for fields in (dict(compact_breakpoint_dp=850,expanded_breakpoint_dp=840),
                       dict(font_touch_scale_limit_pct=99),
                       dict(columns=33)):
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                LayoutScale(**fields)

    def test_normalized_12_unit_spans_scale_to_eight_columns(self):
        controls=[Button(span_compact=12,span_medium=6,span_expanded=4) for _ in range(5)]
        pos=arrange_spans(controls,8,ScreenMetrics(900,400),span_units=12)
        self.assertEqual([(r,c,span) for r,c,_,span in pos],
                         [(0,0,3),(0,3,3),(1,0,3),(1,3,3),(2,0,3)])
        pos=arrange_spans(controls,8,ScreenMetrics(600,900),
                          span_units=12,size_class="medium")
        self.assertEqual(pos[:3],[(0,0,1,4),(0,4,1,4),(1,0,1,4)])
        with self.assertRaises(ValueError):
            arrange_spans([Button(span_compact=13)],8,ScreenMetrics(390,850),
                          span_units=12)

    def test_android_font_scale_expands_targets_with_a_cap(self):
        scale=LayoutScale(touch_target_dp=48,font_touch_scale_limit_pct=150)
        self.assertEqual(scale.touch_height(metrics=ScreenMetrics(390,850,font_scale=1.0)),48)
        self.assertEqual(scale.touch_height(metrics=ScreenMetrics(390,850,font_scale=1.25)),60)
        self.assertEqual(scale.touch_height(metrics=ScreenMetrics(390,850,font_scale=3.0)),72)
        self.assertEqual(scale.touch_height(60,ScreenMetrics(390,850,font_scale=1.5)),72)

    def test_new_layout_parameters_can_be_persisted(self):
        changed=validate_config({"layout":{"columns":8,
            "compact_breakpoint_dp":480,"expanded_breakpoint_dp":760,
            "font_touch_scale_limit_pct":175}})
        scale=LayoutScale(**changed["layout"])
        self.assertEqual(scale.columns,8)
        self.assertEqual(scale.compact_breakpoint_dp,480)


class NativeReflowTests(unittest.TestCase):
    def setUp(self):
        FakeTG.views=[];FakeTG.events=[];FakeTG.count=0

    def _backend(self,scale):
        backend=TermuxBackend(tg=FakeTG,layout_scale=scale)
        class Activity(FakeTG.Activity):
            state={"screenwidth":395,"screenheight":850,
                   "fontscale":1.0,"density":2.5,"orientation":"portrait"}
            def getconfiguration(self):return dict(self.state)
        backend.activity=Activity(None)
        backend.refresh_screen_metrics()
        return backend

    def test_native_grid_uses_configured_columns_and_nonrecreated_children(self):
        backend=self._backend(LayoutScale(columns=8,compact_breakpoint_dp=480,
                                          expanded_breakpoint_dp=760))
        grid=ResponsiveGrid()
        for index in range(4):
            grid.add_widget(Button(text=str(index),span_compact=12,
                          span_medium=6,span_expanded=4))
        backend._make(grid,None)
        self.assertEqual(grid._native.args[2],8)  # GridLayout(activity,rows,cols,parent)
        views=[child._native for child in grid.children]
        self.assertEqual(grid.children[-1]._native.setgridlayoutparams_value[:4],
                         (3,0,1,8))
        backend.activity.state={"screenwidth":950,"screenheight":430,
                  "fontscale":1.5,"density":2.5,"orientation":"landscape"}
        backend.refresh_screen_metrics()
        self.assertEqual(grid.children[1]._native.setgridlayoutparams_value[:4],
                         (0,3,1,3))
        self.assertEqual([x._native for x in grid.children],views)
        self.assertEqual(grid.children[0]._native.setheight_value,(72,))

    def test_explicit_columns_override_global_grid_setting(self):
        backend=self._backend(LayoutScale(columns=6))
        grid=ResponsiveGrid(cols=4)
        grid.add_widget(Button(text="card",span_compact=12))
        backend._make(grid,None)
        self.assertEqual(grid._native.args[2],4)
        self.assertEqual(grid.children[0]._native.setgridlayoutparams_value[:4],
                         (0,0,1,4))

    def test_touch_height_only_emitted_if_scale_changes(self):
        backend=self._backend(LayoutScale())
        button=Button(text="action")
        backend._make(button,None)
        self.assertEqual(button._native.setheight_value,(48,))
        old=button._native.setheight_value
        backend.refresh_screen_metrics()
        self.assertEqual(button._native.setheight_value,old)
        backend.activity.state={"screenwidth":395,"screenheight":850,
                     "fontscale":1.25,"density":2.5,"orientation":"portrait"}
        backend.refresh_screen_metrics()
        self.assertEqual(button._native.setheight_value,(60,))


if __name__=="__main__":unittest.main()
