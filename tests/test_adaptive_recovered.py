"""Geometry helpers recovered without replacing newer responsive sizing rules."""
import unittest

from tgk.adaptive import LayoutScale, ScreenMetrics


class RecoveredGeometryTests(unittest.TestCase):
    def test_content_size_does_not_guess_android_decor(self):
        metrics=ScreenMetrics(393,852,font_scale=1.5)
        self.assertTrue(hasattr(metrics,'safe_content_size_dp'))
        self.assertEqual(metrics.safe_content_size_dp,(393,852))
        explicit=ScreenMetrics(393,852,inset_top_dp=28,inset_bottom_dp=24)
        self.assertEqual(explicit.safe_content_size_dp,(393,800))
        one_side=ScreenMetrics(393,852,inset_bottom_dp=24)
        self.assertEqual(one_side.safe_content_size_dp,(393,828))

    def test_excessive_explicit_insets_leave_positive_content_height(self):
        metrics=ScreenMetrics(393,40,inset_top_dp=28,inset_bottom_dp=24)
        self.assertTrue(hasattr(metrics,'safe_content_size_dp'))
        self.assertEqual(metrics.safe_content_size_dp,(393,1))

    def test_landscape_uses_authoritative_orientation(self):
        metrics=ScreenMetrics(900,400,orientation='portrait')
        self.assertTrue(hasattr(metrics,'is_landscape'))
        self.assertFalse(metrics.is_landscape)
        self.assertTrue(ScreenMetrics(400,900,orientation='landscape').is_landscape)

    def test_available_width_caps_content_and_applies_configured_margins(self):
        scale=LayoutScale(compact_breakpoint_dp=480,expanded_breakpoint_dp=760)
        self.assertTrue(callable(getattr(scale,'available_width',None)))
        for metrics,want in ((ScreenMetrics(400,900),368),
                             (ScreenMetrics(600,900),552),
                             (ScreenMetrics(1600,900),1136),
                             (ScreenMetrics(20,900),1)):
            with self.subTest(metrics=metrics):
                self.assertEqual(scale.available_width(metrics),want)

    def test_explicit_columns_use_bounded_gutters_for_the_effective_count(self):
        scale=LayoutScale(columns=12)
        narrow=ScreenMetrics(120,900)
        self.assertAlmostEqual(scale.column_width(narrow,columns=4),14.3)
        self.assertEqual(scale.column_width(narrow,columns=1),88)
        self.assertEqual(scale.column_width(ScreenMetrics(360,900),10,4),74.5)
        self.assertAlmostEqual(scale.column_width(narrow),4.766666666666667)
        self.assertAlmostEqual(scale.column_width(narrow,columns=12),
                               4.766666666666667)
        self.assertEqual(scale.columns,12)

    def test_explicit_columns_and_gutters_reject_invalid_values(self):
        scale=LayoutScale()
        metrics=ScreenMetrics(393,852)
        for columns in (0,33,True,4.0,'4'):
            with self.subTest(columns=columns),self.assertRaises(ValueError):
                scale.column_width(metrics,columns=columns)
        for gutter in (-1,True,float('nan'),float('inf')):
            with self.subTest(gutter=gutter),self.assertRaises(ValueError):
                scale.column_width(metrics,gutter_dp=gutter,columns=4)


if __name__=='__main__':unittest.main()
