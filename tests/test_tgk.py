import os
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tgk.canvas import Canvas,rgba
from tgk.kv import Builder,KVError
from tgk.widgets import App,Button,Label,Clock,TermuxBackend,TextInput

class CanvasTests(unittest.TestCase):
    def test_clear_pixel_and_clip_canary(self):
        w,h=17,13
        raw=bytearray(b'Y'*19+b'\x00'*(w*h*4)+b'Z'*21)
        data=memoryview(raw)[19:-21]
        c=Canvas(data,w,h)
        c.clear(rgba(0,0,0))
        c.rect(-1000,-1000,1008,1007,rgba(255,0,0))
        self.assertEqual(list(data[:4]),[255,0,0,255]);self.assertEqual(list(data[(h-1)*w*4:][:4]),[0,0,0,255])
        c.circle(16,12,6,rgba(0,255,0,180))
        c.line(-2**30,2**30,2**30,-2**30,rgba(255,255,255))
        self.assertEqual(raw[:19],b'Y'*19);self.assertEqual(raw[-21:],b'Z'*21)
        c.close();del c;data.release()
    def test_blend_and_alpha(self):
        raw=bytearray(12)
        c=Canvas(raw,3,1);c.clear(rgba(0,0,0,0));c.rect(1,0,1,1,rgba(255,0,0,128))
        self.assertEqual(list(raw[4:8]),[255,0,0,128])
        c.rect(1,0,1,1,rgba(0,0,255,128))
        self.assertEqual(raw[7],192)
        self.assertAlmostEqual(raw[4],85,delta=2)
        self.assertAlmostEqual(raw[6],170,delta=2)
        c.close()
    def test_gradient_touch_map(self):
        raw=bytearray(4*4*4)
        c=Canvas(raw,4,4)
        c.gradient(rgba(0,0,0),rgba(255,255,255))
        self.assertEqual(list(raw[:4]),[0,0,0,255])
        self.assertEqual(list(raw[-4:]),[255,255,255,255])
        self.assertEqual(c.map_touch(100,100,200,200),(2,2))
        self.assertEqual(c.map_touch(50,100,200,200,True),(1,2))
        self.assertIsNone(c.map_touch(5,5,200,400,True))
        c.close()

class KVTests(unittest.TestCase):
    def test_parse_id_event(self):
        app=App();App._running_app=app
        try:
            app.root=Builder.load_string('''BoxLayout:
    orientation: 'vertical'
    Label:
        id: status
        text: 'Hello'
    Button:
        text: 'Change'
        on_release: app.apply()
''')
            app.apply=lambda: setattr(app.root.ids.status,'text','Changed')
            self.assertEqual(app.root.ids.status.text,'Hello')
            app.root.children[1].dispatch('on_release')
            self.assertEqual(app.root.ids.status.text,'Changed')
        finally:App._running_app=None
    def test_unsupported_expr(self):
        with self.assertRaises(KVError):Builder.load_string('Label:\n    text: __import__("os")')
    def test_duplicate_ids(self):
        with self.assertRaises(KVError):Builder.load_string('BoxLayout:\n    Label:\n        id: a\n    Button:\n        id: a')
    def test_kv_class_rule(self):
        from tgk.widgets import BoxLayout
        class CustomPane(BoxLayout):
            pass
        Builder.load_string("#:kivy 2.0\n<CustomPane>:\n    orientation: 'vertical'\n    Label:\n        id: inner\n        text: 'Rule applied'\n")
        instance=CustomPane()
        self.assertEqual(instance.orientation,'vertical')
        self.assertEqual(instance.ids.inner.text,'Rule applied')
        Builder.rules.pop('CustomPane',None)
    def test_clock(self):
        called=[];Clock.reset()
        Clock.schedule_once(lambda dt:called.append(dt),0)
        Clock.tick();self.assertEqual(len(called),1)
        Clock.reset()
    def test_custom_property(self):
        from tgk.widgets import StringProperty,EventDispatcher
        class State(EventDispatcher):
            name=StringProperty('initial')
        s=State();observed=[];s.bind(name=lambda obj,val:observed.append(val))
        self.assertEqual(s.name,'initial');s.name='next'
        self.assertEqual(observed,['next'])

class FakeTG:
    class View:
        MATCH_PARENT='MATCH_PARENT'
    class Event:
        def __init__(self,t,v):self.type=t;self.value=v
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def checkevent(self):
            if not FakeTG.events:return None
            event=FakeTG.events.pop(0)
            if callable(event):return event(FakeTG.views)
            return event
    events=[];views=[];count=0
    class Activity:
        def __init__(self,c,intercept=False):self.finished=False
        def finish(self):self.finished=True
    class _View:
        def __init__(self,*args,**kwargs):
            FakeTG.count+=1;self.id=FakeTG.count
            FakeTG.views.append(self);self.args=args
        def __eq__(self,o):return self.id==o
        __hash__=object.__hash__
        def __getattr__(self,name):
            if name.startswith('set') or name.startswith('send'):
                return lambda *args: setattr(self,name+'_value',args)
            raise AttributeError(name)
    LinearLayout=_View;GridLayout=_View;NestedScrollView=_View
    FrameLayout=_View;EditText=_View;Button=_View
    Switch=_View;Checkbox=_View;TextView=_View;ProgressBar=_View

class BackendTests(unittest.TestCase):
    def test_mock_native_render_and_event(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        class TestApp(App):
            clicked=False
            def build(self):
                root=Builder.load_string('''BoxLayout:
    orientation: 'vertical'
    Label:
        id: status
        text: 'Ready'
    Button:
        text: 'Touch'
        on_release: app.do_click()
''')
                return root
            def do_click(self):self.clicked=True;self.root.ids.status.text='Done'
        def click(views):
            b=next(v for v in views if v.args and v.args[1]=='Touch')
            return FakeTG.Event('click',{'id':b.id})
        FakeTG.events=[click,FakeTG.Event('destroy',{'finishing':True})]
        app=TestApp()
        from unittest.mock import patch
        with patch('tgk.widgets.TermuxBackend',lambda **kwargs:TermuxBackend(tg=FakeTG,**kwargs)):
            app.run()
        self.assertTrue(app.clicked)
        self.assertEqual(app.root.ids.status.text,'Done')
        self.assertIsNone(app.root.ids.status._native)


    def test_backend_cleans_up_after_event_exception(self):
        FakeTG.events = []
        FakeTG.views = []
        FakeTG.count = 0
        root = Label(text='Test cleanup')
        backend = TermuxBackend(tg=FakeTG)
        def explode(_views):
            raise RuntimeError('event failure')
        FakeTG.events = [explode]
        with self.assertRaisesRegex(RuntimeError,'event failure'):
            backend.run(root)
        self.assertIsNone(root._native)
        self.assertIsNone(backend.activity)
        self.assertIsNone(backend.connection)
        self.assertEqual(backend.nodes, [])

    def test_backend_cleans_up_after_start_exception(self):
        FakeTG.events = []
        FakeTG.views = []
        FakeTG.count = 0
        root = Label(text='Test failed start')
        backend = TermuxBackend(tg=FakeTG)
        def on_start():
            raise RuntimeError('startup failure')
        with self.assertRaisesRegex(RuntimeError,'startup failure'):
            backend.run(root,on_start)
        self.assertIsNone(root._native)
        self.assertIsNone(backend.activity)
        self.assertIsNone(backend.connection)
        self.assertEqual(backend.nodes, [])

class ImportHookTests(unittest.TestCase):
    def test_nested_transitive_import_with_pth(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            (d/'middle.py').write_text('from kivy.uix.button import Button\nvalue=Button(text="OK")\n')
            (d/'deep.py').write_text('import middle\nfrom kivy.app import App\nprint("SHIM:",middle.value.text,App.__module__)\n')
            (d/'tgk_auto.pth').write_text(str(ROOT)+'\nimport tgk.auto as a; a.maybe_activate()\n')
            env=os.environ.copy();env['TGK_ENABLE']='1'
            env['PYTHONPATH']=str(d)
            # Isolated simulated startup: site.addsitedir executes the same .pth
            # semantics used by Termux's installed site-packages on startup.
            runner='import site;site.addsitedir('+repr(str(d))+');import deep'
            done=subprocess.run([sys.executable,'-c',runner],env=env,capture_output=True,text=True,timeout=6)
            self.assertEqual(done.returncode,0,done.stderr)
            self.assertIn('SHIM: OK tgk.widgets',done.stdout)

if __name__=='__main__':unittest.main()
