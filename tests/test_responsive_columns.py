"""Configurable native columns without breaking legacy 12-unit span designs."""
import unittest
from types import SimpleNamespace

from tgk.adaptive import LayoutScale,ScreenMetrics,arrange_spans
from tgk.widgets import ResponsiveGrid,TermuxBackend,Button,BoxLayout
from test_tgk import FakeTG


class ResponsiveColumnTests(unittest.TestCase):
    def setUp(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        self.phone=ScreenMetrics(393,852,density=2.75,font_scale=1.2)
        self.tablet=ScreenMetrics(700,900)
        self.landscape=ScreenMetrics(950,425,orientation="landscape")

    def test_logical_span_units_scale_without_zero_width_cells(self):
        items=[Button(span_compact=12,span_medium=6,span_expanded=4) for _ in range(6)]
        six=arrange_spans(items,columns=6,span_units=12,metrics=self.landscape)
        self.assertEqual(six[:3],[(0,0,1,2),(0,2,1,2),(0,4,1,2)])
        six_compact=arrange_spans(items,columns=6,span_units=12,metrics=self.phone)
        self.assertEqual([x[0] for x in six_compact],list(range(6)))
        eight=arrange_spans(items,columns=8,span_units=12,metrics=self.tablet)
        self.assertEqual(eight[:2],[(0,0,1,4),(0,4,1,4)])
        one=arrange_spans([Button(span=1)]*3,columns=6,span_units=12)
        self.assertEqual([x[3] for x in one],[1,1,1])

    def test_reject_invalid_grid_definitions_and_unit_overflows(self):
        for kw in (dict(cols=0),dict(cols=33),dict(cols=True),
                   dict(span_units=0),dict(span_units=33)):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                ResponsiveGrid(**kw)
        with self.assertRaises(ValueError):
            arrange_spans([Button(span=13)],columns=6,span_units=12)
        with self.assertRaises(ValueError):
            arrange_spans([Button(span=1)],columns=6,span_units=True)
        with self.assertRaises(ValueError):
            arrange_spans([Button(span=1)],columns=33)

    def test_backend_respects_app_layout_scale_without_recreating_children(self):
        grid=ResponsiveGrid()
        for _ in range(6):
            grid.add_widget(Button(span_compact=12,span_medium=6,
                                   span_expanded=4,width=20,height=20))
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale(columns=6))
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=self.landscape
        backend.render(grid)
        self.assertEqual(grid.cols,6)
        # Actual native GridLayout constructor sees six columns.
        self.assertEqual(grid._native.args[2],6)
        self.assertEqual(grid.children[0]._native.setgridlayoutparams_value,
                         (0,0,1,2,'fill','fill'))
        self.assertEqual(grid.children[2]._native.setgridlayoutparams_value,
                         (0,4,1,2,'fill','fill'))
        self.assertEqual(grid.children[0]._native.setwidth_value,(48,))
        self.assertEqual(grid.children[0]._native.setheight_value,(48,))
        native_ids=tuple(id(child._native) for child in grid.children)
        backend.screen_metrics=self.phone
        backend._reflow_grid(grid)
        self.assertEqual(tuple(id(child._native) for child in grid.children),native_ids)
        self.assertEqual(grid.children[-1]._native.setgridlayoutparams_value,
                         (5,0,1,6,'fill','fill'))

    def test_explicit_columns_override_config_and_opt_out_small_touch_targets(self):
        grid=ResponsiveGrid(cols=8)
        button=Button(text="Small",width=20,height=20,
                      allow_small_touch_target=True,span_compact=12)
        grid.add_widget(button)
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale(columns=6))
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=self.phone
        backend.render(grid)
        self.assertEqual(grid.cols,8)
        self.assertEqual(grid._native.args[2],8)
        self.assertEqual(button._native.setwidth_value,(20,))
        self.assertEqual(button._native.setheight_value,(20,))

    def test_kv_assigned_columns_override_app_defaults(self):
        from tgk.kv import Builder
        grid=Builder.load_string("""ResponsiveGrid:
    cols: 8
    Button:
        text: 'First'
        span_compact: 12
    Button:
        text: 'Second'
        span_compact: 12
""")
        self.assertEqual(grid.cols,8)
        self.assertTrue(grid._explicit_columns)
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale(columns=6))
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=self.phone
        backend.render(grid)
        self.assertEqual(grid._native.args[2],8)
        with self.assertRaises(RuntimeError):grid.cols=4
        self.assertEqual(grid.cols,8)

    def test_assigning_columns_before_render_is_explicit(self):
        grid=ResponsiveGrid()
        grid.cols=5
        grid.add_widget(Button(span=12))
        backend=TermuxBackend(tg=FakeTG,layout_scale=LayoutScale(columns=6))
        backend.activity=FakeTG.Activity(None)
        backend.screen_metrics=self.phone
        backend.render(grid)
        self.assertEqual(grid.cols,5)
        self.assertEqual(grid.children[0]._native.setgridlayoutparams_value,
                         (0,0,1,5,'fill','fill'))

    def test_gutter_does_not_consume_entire_compact_viewport(self):
        scale=LayoutScale(columns=12)
        width=scale.column_width(self.phone)
        gutter=scale.gutter(self.phone)
        self.assertGreater(width,1)
        self.assertLess(gutter,scale.medium_spacing_dp)
        self.assertAlmostEqual(width*12+11*gutter,
                               min(self.phone.width_dp,scale.max_content_width_dp)
                               -2*scale.margin(self.phone))
        with self.assertRaises(ValueError):
            scale.column_width(self.phone,gutter_dp=float("nan"))

    def test_android_pixel_conversion_respects_font_scale(self):
        self.assertEqual(self.phone.dp_to_px(16),44)
        self.assertEqual(self.phone.sp_to_px(16),53)
        self.assertAlmostEqual(self.phone.px_to_dp(55),20)
        for invalid in (float("nan"),-1,True):
            with self.assertRaises(ValueError):self.phone.sp_to_px(invalid)


if __name__=="__main__":
    unittest.main()
