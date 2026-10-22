"""Regression tests for native-buffer Slider and KV bindings."""
import importlib
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tgk.widgets import App,Slider,TermuxBackend,ProgressBar
from tgk.kv import Builder
from test_tgk import FakeTG

buffers=[]
class FakeView(FakeTG._View):
    def getdimensions(self):return (512,72)
    def refresh(self):self.refresh_count=getattr(self,'refresh_count',0)+1

class FakeBuffer:
    def __init__(self,c,w,h):
        self.data=bytearray(w*h*4)
        self.blits=0;self.closed=False
        buffers.append(self)
    def __enter__(self):return self.data
    def __exit__(self,*exc):self.closed=True
    def blit(self):self.blits+=1

class SliderTG(FakeTG):
    ImageView=FakeView
    Buffer=FakeBuffer

class SliderTests(unittest.TestCase):
    def setUp(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        buffers.clear()

    def test_normalization_and_callback_signatures(self):
        slider=Slider(min=20,max=80,value=40,step=5)
        direct=[];kv=[]
        slider.bind(value=lambda widget,value:direct.append(value))
        slider.bind(on_value=lambda widget,value:kv.append(value))
        slider.value=47
        slider.value=120
        self.assertEqual(slider.value,80)
        self.assertEqual(direct,[45,80])
        self.assertEqual(kv,[45,80])
        with self.assertRaises(ValueError):Slider(min=100,max=100)
        with self.assertRaises(ValueError):Slider(step=-1)
        with self.assertRaises(ValueError):slider.value=float('nan')
        with self.assertRaises(ValueError):slider.value=float('inf')
        with self.assertRaises(ValueError):setattr(slider,'max',20)
        with self.assertRaises(ValueError):setattr(slider,'step',float('nan'))

    def test_touch_drags_update_and_cleanup(self):
        slider=Slider(min=0,max=100,value=25,step=1)
        updates=[]
        slider.bind(on_value=lambda widget,value:updates.append(value))
        def ev(action,x):
            return lambda views:FakeTG.Event('touch',{
                'id':slider._native.id,'action':action,'index':0,
                'pointers':[{'id':7,'x':x,'y':36}]})
        FakeTG.events=[ev('down',120),ev('move',400),ev('up',400),
                       FakeTG.Event('destroy',{'finishing':True})]
        TermuxBackend(tg=SliderTG).run(slider)
        self.assertAlmostEqual(slider.value,81,delta=1)
        self.assertGreaterEqual(len(updates),2)
        self.assertGreaterEqual(buffers[0].blits,2)
        self.assertTrue(buffers[0].closed)
        self.assertIsNone(slider._native)
        self.assertIsNone(slider._slider_draw)
        self.assertIsNone(slider._drag_pointer)
        self.assertGreaterEqual(FakeTG.views[0].refresh_count,2)

    def test_kv_demo_updates_progress(self):
        root=Builder.load_file(ROOT/'examples/demo.kv')
        slider=root.ids.level
        self.assertIsInstance(slider,Slider)
        self.assertIsInstance(root.ids.level_progress,ProgressBar)
        app=App()
        App._running_app=app
        app.root=root
        def update(value):
            root.ids.slider_status.text=f'Level: {value:.0f}'
            root.ids.level_progress.value=value
        app.update_slider=update
        try:
            slider.value=82.8
            self.assertEqual(slider.value,83)
            self.assertEqual(root.ids.slider_status.text,'Level: 83')
            self.assertEqual(root.ids.level_progress.value,83)
        finally:
            App._running_app=None

    def test_kivy_bridge_import(self):
        from tgk.compat.importer import activate,deactivate
        activate()
        try:
            module=importlib.import_module('kivy.uix.slider')
            self.assertIs(module.Slider,Slider)
        finally:
            deactivate()
            for name in ('kivy.uix.slider','kivy.uix','kivy'):
                sys.modules.pop(name,None)

if __name__=='__main__':unittest.main()
