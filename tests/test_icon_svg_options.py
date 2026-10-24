"""Public SVG styling must affect the actual rendered geometry."""
import unittest
from xml.etree import ElementTree as ET
from tgk.icons import svg

NS={'s':'http://www.w3.org/2000/svg'}

class SvgOptionTests(unittest.TestCase):
    def test_requested_color_applies_to_primary_and_secondary_paths(self):
        for name in ('refresh','sync','run','play','star_filled'):
            with self.subTest(name=name):
                root=ET.fromstring(svg(name,color='#E12345'))
                paints={e.get(key) for e in root.iter() for key in ('stroke','fill')
                        if e.get(key) not in (None,'none')}
                self.assertEqual(paints,{'#E12345FF'})

    def test_stroke_argument_changes_visible_vector_width(self):
        thin=ET.fromstring(svg('refresh',stroke=.5))
        thick=ET.fromstring(svg('refresh',stroke=8))
        a=float(thin.find('s:g',NS).get('stroke-width'))
        b=float(thick.find('s:g',NS).get('stroke-width'))
        self.assertAlmostEqual(b/a,16)

    def test_vertical_chevrons_have_no_arrow_shaft(self):
        for direction in ('up','down'):
            root=ET.fromstring(svg('chevron_'+direction))
            path=root.find('s:g/s:path',NS).get('d')
            self.assertEqual(path.count('M'),1)
            self.assertEqual(path.count('L'),2)
            self.assertNotIn('V',path)
            self.assertNotEqual(path,ET.fromstring(svg('arrow_'+direction)).find('s:g/s:path',NS).get('d'))

    def test_copy_and_sync_share_overlapping_documents_with_small_sync_overlay(self):
        from tgk.icon_builder import render_svg
        copy=ET.fromstring(render_svg('copy'))
        sync=ET.fromstring(render_svg('sync'))
        self.assertEqual(copy.find('s:g/s:path',NS).get('d'),
                         sync.find('s:g/s:path',NS).get('d'))
        self.assertIsNone(copy.find('s:g/s:g',NS))
        overlay=sync.find('s:g/s:g',NS)
        self.assertIsNotNone(overlay)
        self.assertIn('scale(0.25)',overlay.get('transform'))
        self.assertGreaterEqual(len(overlay.findall('s:path',NS)),2)
