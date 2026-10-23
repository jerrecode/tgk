"""Offline contracts for navigation, typography, symbolic icons and canvas."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tgk.advanced import (Screen,Tab,ScreenManager,TabbedPanel,Popup,
                          RichTextLabel,IconLabel,InfiniteCanvas)
from tgk.typography import (TextStyle,TextSpan,PRESETS,resolve_text_style,rich_html)
from tgk.icons import (ICONS,CATEGORIES,icon_for_path,glyph,svg,icon_names)
from tgk.widgets import Button,Label,TermuxBackend
from test_tgk import FakeTG
from tgk.canvas import Canvas


class NavigationTests(unittest.TestCase):
    def test_screen_lifecycle_and_visibility(self):
        manager=ScreenManager()
        first=Screen(name="home",title="Home")
        second=Screen(name="settings",title="Settings")
        manager.add_widget(first);manager.add_widget(second)
        events=[]
        first._native=SimpleNamespace(visibility=None,setvisibility=lambda v:setattr(first._native,"visibility",v))
        second._native=SimpleNamespace(visibility=None,setvisibility=lambda v:setattr(second._native,"visibility",v))
        manager._sync()
        self.assertEqual(manager.current,"home")
        self.assertEqual([first._native.visibility,second._native.visibility],[2,0])
        manager.bind(on_switch=lambda _sender,name:events.append(name))
        manager.switch("settings")
        self.assertEqual(manager.active_screen,second)
        self.assertEqual([first._native.visibility,second._native.visibility],[0,2])
        self.assertEqual(manager.next(),"home")
        self.assertEqual(manager.previous(),"settings")
        self.assertEqual(events,["settings","home","settings"])

    def test_invalid_screen_and_duplicate_names(self):
        mgr=ScreenManager()
        mgr.add_widget(Screen(name="one"))
        with self.assertRaises(ValueError):mgr.add_widget(Screen(name="one"))
        with self.assertRaises(TypeError):mgr.add_widget(Label(text="no"))
        with self.assertRaises(ValueError):mgr.switch("missing")

    def test_tabbed_panel_dispatch_and_native_visibility(self):
        FakeTG.views=[];FakeTG.count=0
        # FakeTG matches the native method names; no hashable Button required.
        class TabNative(FakeTG._View):
            def selecttab(self,index):
                self.selected=index
        class TabTG:
            Activity=FakeTG.Activity
            View=FakeTG.View
            LinearLayout=FakeTG._View
            FrameLayout=FakeTG._View
            TabLayout=TabNative
            TextView=FakeTG._View
            Button=FakeTG._View
        tg=TabTG()
        backend=TermuxBackend(tg=tg)
        backend.activity=tg.Activity(None)
        panel=TabbedPanel()
        a=Tab(name="first",title="First")
        b=Tab(name="second",title="Second")
        a.add_widget(Label(text="Page one"))
        b.add_widget(Button(text="Page two"))
        panel.add_widget(a);panel.add_widget(b)
        backend.render(panel)
        self.assertEqual(panel.current,"first")
        self.assertEqual(a._native.setvisibility_value,(2,))
        self.assertEqual(b._native.setvisibility_value,(0,))
        # Protocol TabLayout itemselected reports numeric tab index.
        backend.event(FakeTG.Event("itemselected",{
            "id":panel._tab_bar.id,"selected":1}))
        self.assertEqual(panel.current,"second")
        self.assertEqual(a._native.setvisibility_value,(0,))
        self.assertEqual(b._native.setvisibility_value,(2,))
        panel.next()
        self.assertEqual(panel.current,"first")

    def test_popup_is_hidden_and_toggled_without_widget_recreation(self):
        popup=Popup()
        fake=SimpleNamespace(calls=[],setvisibility=lambda v:fake.calls.append(v))
        popup._native=fake
        popup.open()
        self.assertTrue(popup.visible)
        popup.dismiss()
        self.assertFalse(popup.visible)
        self.assertEqual(fake.calls,[2,0])

class TypographyTests(unittest.TestCase):
    def test_every_preset_is_valid(self):
        self.assertGreaterEqual(len(PRESETS),12)
        for name in PRESETS:
            with self.subTest(name=name):
                self.assertIsInstance(resolve_text_style(name).css(),str)
        with self.assertRaises(ValueError):resolve_text_style("untrusted")

    def test_font_parameters_and_no_arbitrary_css(self):
        style=TextStyle(family="mono",size=18,weight=700,
                        underline=True,italic=True)
        css=style.css()
        self.assertIn("font-size:18px",css)
        self.assertIn("font-family:monospace",css)
        for options in (dict(family="url(evil)"),dict(size=0),
                        dict(weight=550),dict(align="inject"),
                        dict(line_height=float("nan"))):
            with self.subTest(options=options),self.assertRaises(ValueError):
                TextStyle(**options)

    def test_rich_markup_escapes_active_content_and_nonascii(self):
        result=rich_html([TextSpan('<script>evil()</script> & Grüße',
                        style="emphasis",color="#FA12BC"),
                          TextSpan("line\nsecond",style="code")])
        self.assertNotIn("<script>",result)
        self.assertIn("&lt;script&gt;",result)
        self.assertIn("&#",result)
        self.assertIn("style-src",result)
        self.assertIn("font-family:monospace",result)
        self.assertIn("<br>",result)
        with self.assertRaises(ValueError):
            rich_html("x"*250001)

    def test_rich_text_widget_updates_markup(self):
        class Web:
            rendered=""
            def setdata(self,value):self.rendered=value
        widget=RichTextLabel(text="First",style="title")
        widget._native=Web()
        widget.text="Second"
        self.assertIn("Second",widget._native.rendered)

class WindowTests(unittest.TestCase):
    def test_overlay_event_loop_exits_without_destroy_event(self):
        FakeTG.views=[];FakeTG.events=[];FakeTG.count=0
        backend=TermuxBackend(tg=FakeTG,window_mode="overlay")
        root=Label(text="Overlay")
        backend.run(root,on_start=backend.stop)
        self.assertIsNone(backend.activity)
        self.assertIsNone(root._native)
        self.assertTrue(backend._stop_requested)

    def test_rich_text_uses_inherited_text_style(self):
        from tgk.typography import resolve_text_style
        backend=TermuxBackend(tg=FakeTG,text_style="title")
        node=RichTextLabel(text="Inherit")
        class Web:
            markup=""
            def setdata(self,source):self.markup=source
            def setbackgroundcolor(self,*args):pass
        node._native=Web()
        backend.nodes=[node]
        backend.apply_text_style("title")
        self.assertIn("font-size:26px",node._native.markup)
        backend.apply_text_style("caption")
        self.assertIn("font-size:12px",node._native.markup)


class IconTests(unittest.TestCase):
    def test_catalog_covers_requested_categories(self):
        self.assertGreaterEqual(len(ICONS),200)
        for category in ("files","directories","actions","media","view","navigation"):
            self.assertIn(category,CATEGORIES)
            self.assertGreater(len(icon_names(category)),15)
        for key in ("jsonl","sqlite","postgres","hdf5","tar","folder_lib",
                    "frame_forward","fullscreen_exit","select_all","zoom_reset"):
            self.assertIn(key,ICONS)
            self.assertTrue(glyph(key))
        with self.assertRaises(KeyError):icon_names("invalid")

    def test_filename_and_linux_directory_roles(self):
        expected={"a.jsonl":"jsonl","Makefile":"makefile","a.tar.gz":"tar",
                  "foo.py":"python",".env":"config","data.h5":"hdf5",
                  "README.md":"markdown"}
        for name,kind in expected.items():
            with self.subTest(name=name):
                self.assertEqual(icon_for_path(name,is_dir=False),kind)
        self.assertEqual(icon_for_path("/usr/lib",is_dir=True),"folder_lib")

    def test_small_vector_svg_and_icon_label(self):
        source=svg("play",color="#12AB34",size=48)
        self.assertIn("<svg",source)
        self.assertIn("#12AB34FF",source)
        with self.assertRaises(KeyError):svg("unsupported_svg")
        item=IconLabel(icon="file_text",text="Readme")
        item.set_icon("settings","Options")
        self.assertIn("Options",item.text)

class CanvasWorldTests(unittest.TestCase):
    def test_inverse_transform_and_zoom_anchor(self):
        view=InfiniteCanvas(width=320,height=240)
        self.assertEqual(view.world_to_screen(0,0),(160,120))
        view.pan(24,-12)
        self.assertEqual(view.screen_to_world(160,120),(-24,12))
        anchor=view.screen_to_world(120,90)
        view.zoom_at(2,120,90)
        after=view.screen_to_world(120,90)
        self.assertAlmostEqual(anchor[0],after[0])
        self.assertAlmostEqual(anchor[1],after[1])

    def test_canvas_draws_and_marks_without_unbounded_framebuffer(self):
        viewport=InfiniteCanvas(width=320,height=240)
        viewport.add_marker(0,0,role="accent")
        payload=bytearray(320*240*4)
        canvas=Canvas(payload,320,240)
        viewport.render_to(canvas)
        self.assertTrue(any(payload))
        canvas.close()
        with self.assertRaises(ValueError):
            InfiniteCanvas(width=2048,height=2048)
        with self.assertRaises(ValueError):
            viewport.add_marker(float("inf"),0)

    def test_repaint_coalesced_per_pan_and_zoom(self):
        view=InfiniteCanvas(width=320,height=240)
        redraws=[]
        view._draw_viewport=lambda:redraws.append(1)
        view.pan(32,12)
        self.assertEqual(len(redraws),1)
        view.zoom_at(1.5)
        self.assertEqual(len(redraws),2)

    def test_grid_scale_and_marker_validation(self):
        for value in (0,1e-12,1e308,float("inf"),float("nan")):
            with self.subTest(grid_step=value),self.assertRaises(ValueError):
                InfiniteCanvas(grid_step=value)
        view=InfiniteCanvas(width=128,height=128)
        with self.assertRaises(ValueError):view.add_marker(1,1,role="not_a_role")
        with self.assertRaises(ValueError):view.add_marker(1,1,radius=0)
        payload=bytearray(128*128*4)
        c=Canvas(payload,128,128)
        view.render_to(c)
        c.close()

    def test_touch_pan_and_pinching(self):
        view=InfiniteCanvas(width=320,height=240)
        def touch(action,pts,index=0):
            view._touch(SimpleNamespace(value={"action":action,"pointers":pts,"index":index}))
        point=lambda pid,x,y:{"id":pid,"x":x,"y":y}
        touch("down",[point(1,100,100)])
        touch("move",[point(1,125,100)])
        self.assertLess(view.center_x,0)
        touch("pointer_down",[point(1,125,100),point(2,200,100)],index=1)
        touch("move",[point(1,100,100),point(2,230,100)])
        self.assertGreater(view.zoom,1)
        touch("cancel",[])
        self.assertEqual(view._touch_points,{})


if __name__=="__main__":
    unittest.main()
