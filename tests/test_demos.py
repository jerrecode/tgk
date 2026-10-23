"""Offline construction and interaction smoke checks for every lab scenario."""
import unittest

from tgk.demos import Laboratory, SCENARIOS, main, mix
from tgk.theme import PRESETS
from tgk.widgets import BoxLayout, Slider, ScrollView, Button, GridLayout


class DemoTests(unittest.TestCase):
    def test_all_scenarios_build_and_have_consistent_parent_links(self):
        self.assertGreaterEqual(len(SCENARIOS),12)
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                app=Laboratory(scenario=scenario)
                root=app.build()
                nodes=list(root.walk())
                self.assertGreater(len(nodes),5)
                self.assertEqual(len({id(x) for x in nodes}),len(nodes))
                self.assertIsNone(root.parent)
                for parent in nodes:
                    for child in parent.children:
                        self.assertIs(child.parent,parent)
                self.assertIsInstance(nodes[-1], (Button,BoxLayout,Slider,ScrollView,GridLayout,
                                                   type(app.status)))

    def test_scenarios_produce_increasing_interaction_density(self):
        simple=Laboratory(scenario="01_basics")
        complex_app=Laboratory(scenario="13_workbench")
        self.assertLess(len(list(simple.build().walk())),len(list(complex_app.build().walk())))

    def test_status_updates_from_nested_callback(self):
        app=Laboratory(scenario="04_nesting")
        root=app.build()
        button=next(node for node in root.walk()
                    if isinstance(node,Button) and node.text=="Deep event")
        button.dispatch("on_release")
        self.assertIn("Nested callback",app.status.text)

    def test_sliders_update_progress_and_labels(self):
        app=Laboratory(scenario="07_sliders")
        root=app.build()
        slider=next(node for node in root.walk() if isinstance(node,Slider))
        slider.value=88
        self.assertIn("88",app.status.text)

    def test_theme_studio_presets_and_rgb_controls(self):
        app=Laboratory(scenario="12_studio")
        root=app.build()
        self.assertEqual(len(app.swatches),11)
        self.assertEqual(len(app.rgb_sliders),3)
        self.assertGreaterEqual(len([w for w in root.walk() if isinstance(w,Button)]),12)
        app.pick("terminal")
        self.assertEqual(app.theme.name,"terminal")
        expected=app.theme["accent"]
        app.pick("paper")
        self.assertEqual(app.theme.name,"paper")
        self.assertNotEqual(app.theme["accent"],expected)
        app.rgb_sliders[0].value=155
        self.assertEqual(app.theme["accent"][:3],"#9B")

    def test_custom_override_validates_and_updates(self):
        app=Laboratory(scenario="12_studio")
        app.build()
        app.role_input.text="accent"
        app.color_input.text="#12AB34"
        app.apply_custom()
        self.assertEqual(app.theme["accent"],"#12AB34FF")
        app.role_input.text="does_not_exist"
        app.apply_custom()
        self.assertIn("Invalid override",app.status.text)

    def test_color_mix_endpoints(self):
        self.assertEqual(mix("#000000","#FFFFFF",0),"#000000")
        self.assertEqual(mix("#000000","#FFFFFF",1),"#FFFFFF")
        self.assertEqual(mix("#000000","#FFFFFF",.5),"#808080")

    def test_lab_listing_runs_without_android(self):
        from unittest.mock import patch
        from io import StringIO
        with patch("sys.stdout",new_callable=StringIO) as stdout:
            self.assertEqual(main(["--list"]),0)
        self.assertIn("13_workbench",stdout.getvalue())


if __name__=="__main__":
    unittest.main()
