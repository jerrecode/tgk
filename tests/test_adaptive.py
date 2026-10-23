"""Responsive metrics, 12-column layout, state colors and rich table tests."""
import unittest
from types import SimpleNamespace

from tgk.adaptive import ScreenMetrics, LayoutScale, arrange_spans, measure_activity
from tgk.widgets import ResponsiveGrid, Button, Label, TextInput, TermuxBackend
from tgk.theme import PRESETS,ROLES,DERIVED_ROLES,resolve_theme,blend_color,tgui_color
from tgk.typography import PRESETS as FONTS,resolve_text_style
from tgk.style_tokens import TableStyle, ComponentStyle,DEFAULT_STYLES,table_html
from tgk.advanced import RichTable


class AdaptiveMetricsTests(unittest.TestCase):
    def setUp(self):
        self.phone=ScreenMetrics.from_configuration({
            'screenwidth':393,'screenheight':852,'orientation':'portrait',
            'density':2.75,'fontscale':1.15,'language':'en'})
        self.tablet=ScreenMetrics.from_configuration({
            'screenwidth':700,'screenheight':900,'orientation':'portrait'})
        self.landscape=ScreenMetrics.from_configuration({
            'screenwidth':915,'screenheight':412,'orientation':'landscape'})

    def test_android_configuration_units_and_unavailable_fields(self):
        self.assertEqual(self.phone.size_class,'compact')
        self.assertEqual(self.tablet.size_class,'medium')
        self.assertEqual(self.landscape.size_class,'expanded')
        self.assertEqual(self.phone.approx_window_px,(1081,2343))
        self.assertIsNone(self.phone.max_refresh_hz)
        self.assertIsNone(self.phone.physical_width_px)
        self.assertIsNone(self.phone.inset_top_dp)
        self.assertAlmostEqual(self.phone.aspect_ratio,393/852)
        self.assertEqual(self.landscape.orientation,'landscape')

    def test_metrics_validation_and_missing_screen_fields(self):
        for bad in ({'screenwidth':0,'screenheight':10},
                    {'screenwidth':100},{'screenwidth':10,'screenheight':20,'density':0}):
            with self.subTest(config=bad),self.assertRaises(ValueError):
                ScreenMetrics.from_configuration(bad)
        with self.assertRaises(ValueError):
            ScreenMetrics(100,200,max_refresh_hz=float('inf'))
        with self.assertRaises(ValueError):
            ScreenMetrics(100,200,color_depth_bits=0)
        self.assertEqual(ScreenMetrics.from_configuration(
            {'screenwidth':1000,'screenheight':400}).orientation,'landscape')
        self.assertIsNone(measure_activity(object()))

    def test_dp_spacing_and_48dp_touch_target(self):
        scale=LayoutScale()
        self.assertEqual(scale.columns,12)
        self.assertEqual(scale.touch_height(20),48)
        self.assertEqual(scale.touch_height(56),56)
        self.assertEqual(scale.dp(17),16)
        self.assertGreater(scale.column_width(self.landscape),10)
        self.assertGreaterEqual(scale.margin(self.landscape),scale.margin(self.phone))
        with self.assertRaises(ValueError):LayoutScale(columns=999)

    def test_span_positions_change_without_rebuilding(self):
        grid=ResponsiveGrid()
        for _ in range(5):
            grid.add_widget(Button(text='b',span_compact=12,
                                   span_medium=6,span_expanded=4))
        small=arrange_spans(grid.children,metrics=self.phone)
        medium=arrange_spans(grid.children,metrics=self.tablet)
        large=arrange_spans(grid.children,metrics=self.landscape)
        self.assertEqual([x[:2] for x in small],[(0,0),(1,0),(2,0),(3,0),(4,0)])
        self.assertEqual([x[:2] for x in medium],[(0,0),(0,6),(1,0),(1,6),(2,0)])
        self.assertEqual([x[:2] for x in large],[(0,0),(0,4),(0,8),(1,0),(1,4)])
        with self.assertRaises(ValueError):
            arrange_spans([Button(span_compact=20)],metrics=self.phone)

    def test_config_refresh_changes_grid_geometry_in_place(self):
        class Native:
            def __init__(self):self.calls=[]
            def setgridlayoutparams(self,*args):self.calls.append(args)
        class Activity:
            configuration={'screenwidth':393,'screenheight':852}
            def getconfiguration(self):return dict(self.configuration)
        activity=Activity()
        backend=TermuxBackend(tg=object())
        backend.activity=activity
        grid=ResponsiveGrid()
        for _ in range(4):
            child=Button(span_compact=12,span_expanded=3)
            child._native=Native()
            grid.add_widget(child)
        backend.nodes=[grid]
        self.assertEqual(backend.refresh_screen_metrics().size_class,'compact')
        self.assertEqual(grid.children[3]._native.calls[-1][:2],(3,0))
        activity.configuration={'screenwidth':950,'screenheight':400,'orientation':'landscape'}
        backend.event(SimpleNamespace(type='config',value={}))
        self.assertEqual(grid.children[3]._native.calls[-1][:2],(0,9))
        calls=sum(len(x._native.calls) for x in grid.children)
        backend.refresh_screen_metrics()
        self.assertEqual(sum(len(x._native.calls) for x in grid.children),calls)


class SemanticTokenTests(unittest.TestCase):
    def test_every_preset_has_derived_color_roles(self):
        self.assertGreaterEqual(len(DERIVED_ROLES),45)
        self.assertEqual(len(ROLES),len(set(ROLES)))
        for name in PRESETS:
            with self.subTest(name=name):
                palette=resolve_theme(name)
                self.assertEqual(set(palette.colors),set(ROLES))
                for color in palette.colors.values():self.assertEqual(len(color),9)

    def test_component_states_relative_to_base_and_overrides(self):
        original=resolve_theme('ocean')
        changed=original.override(button='#112233')
        self.assertNotEqual(changed['button_pressed'],original['button_pressed'])
        self.assertNotEqual(changed['button_active'],original['button_active'])
        self.assertEqual(changed['button_pressed'],blend_color('#112233','#000000',.26)+'FF')
        selected=original.override(button='#112233',button_pressed='#AABBCC')
        self.assertEqual(selected['button_pressed'],'#AABBCCFF')
        self.assertEqual(selected['button_active'],changed['button_active'])

    def test_extended_text_presets_have_valid_roles(self):
        for name in ('title_h1','title_h5','metadata','tabular','filesystem_link',
                     'footnote','comment','selected','unselected','table_header',
                     'button','input','notification'):
            self.assertIn(name,FONTS)
            self.assertTrue(resolve_text_style(name).css())

    def test_component_and_table_styles_validate_and_copy(self):
        self.assertGreaterEqual(len(DEFAULT_STYLES),12)
        changed=DEFAULT_STYLES['button'].override(border_width_dp=3)
        self.assertNotEqual(changed,DEFAULT_STYLES['button'])
        for opts in ({'border_width_dp':-1},{'min_touch_dp':12},{'text_fit':'overlap'}):
            with self.assertRaises(ValueError):ComponentStyle(**opts)
        with self.assertRaises(ValueError):TableStyle(line_style='javascript')

    def test_html_table_stripes_headers_borders_and_escape(self):
        colors=resolve_theme('paper')
        custom=TableStyle(shade_alternate_rows=True,shade_alternate_columns=True,
                          bold_first_row=True,bold_first_column=True,
                          header_bottom_width_dp=4,first_column_right_width_dp=3)
        markup=table_html([['label','count'],['<script>',20],['B',10]],
                          theme=colors,style=custom)
        self.assertIn('&lt;script&gt;',markup)
        self.assertNotIn('<script>',markup)
        self.assertIn('border-bottom-width:4px',markup)
        self.assertIn('border-right-width:3px',markup)
        self.assertIn(colors['table_first_column'],markup)
        with self.assertRaises(ValueError):table_html([[1,2],[3]])
        with self.assertRaises(ValueError):table_html([[1]*20100])

    def test_rich_table_updates_live_and_rejects_invalid_rows(self):
        table=RichTable(rows=[['a','b'],[1,2]])
        class Web:
            def __init__(self):self.data=None
            def setdata(self,s):self.data=s
        table._native=Web()
        table.update_rows([['a','b'],['changed',4]])
        self.assertIn('changed',table._native.data)
        with self.assertRaises(ValueError):table.update_rows([[1,2],[1]])
        self.assertIn('changed',table._native.data)


if __name__=='__main__':unittest.main()
