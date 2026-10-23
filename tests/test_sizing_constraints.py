"""Adaptive width classes, configured grid columns, orientation resizing.

Tests use native fake objects; never claim physical Android display coverage.
"""
from types import SimpleNamespace
import unittest

from tgk import SizeSpec,resolve_size
from tgk.adaptive import ScreenMetrics,arrange_spans
from tgk.widgets import Button,ResponsiveGrid,TermuxBackend


class SizingTests(unittest.TestCase):
    phone=ScreenMetrics(393,852,density=2.75)
    landscape=ScreenMetrics(915,412,density=2.75,orientation="landscape")

    def test_width_fraction_height_cap_and_intrinsic_ratio(self):
        spec=SizeSpec(width_fraction=.5,height_fraction=.5,
                      max_height_fraction=.2)
        small=resolve_size(spec,self.phone)
        self.assertEqual(small.width_dp,197)
        self.assertEqual(small.height_dp,171)
        wide=resolve_size(spec,self.landscape)
        self.assertEqual(wide.width_dp,458)
        self.assertEqual(wide.height_dp,83)

    def test_aspect_contain_only_shrinks(self):
        spec=SizeSpec(width_dp=240,height_dp=120,aspect_ratio=1)
        fitted=resolve_size(spec,self.phone)
        self.assertEqual((fitted.width_dp,fitted.height_dp),(120,120))
        tall=SizeSpec(width_dp=120,height_dp=240,aspect_ratio=2)
        fitted=resolve_size(tall,self.phone)
        self.assertEqual((fitted.width_dp,fitted.height_dp),(120,60))
        one=SizeSpec(width_dp=120,aspect_ratio=2)
        self.assertEqual(resolve_size(one,self.phone).height_dp,60)

    def test_touch_minimum_and_known_insets_only(self):
        spec=SizeSpec(width_dp=24,height_dp=12,margin_horizontal_dp=20,
                      margin_vertical_dp=10)
        sized=resolve_size(spec,self.phone,interactive=True,touch_target_dp=56)
        self.assertEqual((sized.width_dp,sized.height_dp),(56,56))
        inset=ScreenMetrics(393,852,inset_top_dp=24,inset_bottom_dp=30)
        planned=resolve_size(SizeSpec(height_fraction=1),inset)
        self.assertEqual(planned.height_dp,798)
        self.assertEqual(resolve_size(SizeSpec(),self.phone).width_dp,None)

    def test_reject_conflicts_and_invalid_limits(self):
        for opts in (
            {"width_dp":100,"width_fraction":.5},
            {"min_width_dp":80,"max_width_dp":70},
            {"width_fraction":1.1},{"height_fraction":0},
            {"aspect_ratio":float("nan")},
            {"margin_vertical_dp":-1},{"fit":"crop"},
        ):
            with self.subTest(opts=opts),self.assertRaises(ValueError):
                SizeSpec(**opts)
        with self.assertRaises(TypeError):resolve_size(object(),self.phone)

    def test_grid_columns_map_logical_spans_consistently(self):
        items=[SimpleNamespace(span_compact=6) for _ in range(5)]
        p=arrange_spans(items,columns=8,span_units=12,metrics=self.phone)
        self.assertEqual([item[:2] for item in p],
                         [(0,0),(0,4),(1,0),(1,4),(2,0)])
        self.assertEqual([item[3] for item in p],[4]*5)
        for bad in (0,33):
            with self.assertRaises(ValueError):
                arrange_spans(items,columns=bad)
        with self.assertRaises(ValueError):
            arrange_spans(items,columns=8,span_units=0)

    def test_responsive_grid_honors_custom_columns(self):
        grid=ResponsiveGrid(cols=8)
        self.assertEqual(grid.cols,8)
        self.assertEqual(grid.span_units,12)
        with self.assertRaises(ValueError):ResponsiveGrid(cols=0)

    def test_native_reflow_and_size_updates_only_after_real_metric_changes(self):
        class Native:
            def __init__(self):self.calls=[]
            def setwidth(self,value):self.calls.append(("width",value))
            def setheight(self,value):self.calls.append(("height",value))
            def setgridlayoutparams(self,*args):self.calls.append(("grid",args))
        class Activity:
            config={"screenwidth":393,"screenheight":852}
            def getconfiguration(self):return self.config
        activity=Activity()
        backend=TermuxBackend(tg=object())
        backend.activity=activity
        grid=ResponsiveGrid(cols=8)
        child=Button(text="OK",span_compact=6,span_expanded=4,
                     size_spec=SizeSpec(width_fraction=.5,max_height_fraction=.2,
                                        height_fraction=.2))
        child._native=Native()
        grid.add_widget(child)
        backend.nodes=[grid,child]
        backend.refresh_screen_metrics()
        self.assertIn(("grid",(0,0,1,4,"fill","fill")),child._native.calls)
        self.assertIn(("width",197),child._native.calls)
        n=len(child._native.calls)
        backend.refresh_screen_metrics()
        self.assertEqual(len(child._native.calls),n)
        activity.config={"screenwidth":915,"screenheight":412,
                         "orientation":"landscape"}
        backend.refresh_screen_metrics()
        self.assertIn(("width",458),child._native.calls)
        self.assertIn(("height",83),child._native.calls)
        self.assertIn(("grid",(0,0,1,3,"fill","fill")),child._native.calls)
        self.assertEqual(len(child._native.calls),n+3)


if __name__=="__main__":
    unittest.main()
