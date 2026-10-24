"""Backend shutdown must finish after native resource or model reset failures."""
from contextlib import redirect_stderr,redirect_stdout
import io
import unittest
from unittest.mock import patch

from tgk.advanced import InfiniteCanvas
from tgk.widgets import BoxLayout,Clock,Label,Slider,TermuxBackend
from test_slider import FakeBuffer,FakeView
from test_tgk import FakeTG


class BackendCleanupTests(unittest.TestCase):
    def setUp(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        Clock.reset()
        self.addCleanup(Clock.reset)
        self.calls=[]
        self.buffers=[]
        self.failures={}
        self.connection_failure=None
        self.connection_errors=[]
        test=self
        class Buffer(FakeBuffer):
            def __init__(self,*args):
                super().__init__(*args)
                self.number=len(test.buffers)
                test.buffers.append(self)
            def __exit__(self,*args):
                test.calls.append(('buffer',self.number))
                # Resizing fails if Canvas still exports this Python buffer.
                self.data.extend(b'released')
                super().__exit__(*args)
                error=test.failures.get(('buffer',self.number))
                if error is not None:raise error
        class Connection(FakeTG.Connection):
            def __exit__(self,*args):
                test.calls.append(('connection',None))
                test.connection_errors.append(args)
                if test.connection_failure is not None:
                    raise test.connection_failure
        class TG(FakeTG):
            ImageView=FakeView
        TG.Buffer=Buffer
        TG.Connection=Connection
        self.tg=TG
        self.backend=TermuxBackend(tg=TG)
        self.root=BoxLayout()
        self.sliders=[Slider(),Slider()]
        self.viewports=[InfiniteCanvas(width=32,height=32),
                        InfiniteCanvas(width=32,height=32)]
        for node in self.sliders+self.viewports:self.root.add_widget(node)
        self.states=[]

    def start(self):
        Clock.schedule_once(lambda dt:self.fail('stale callback ran'),200)
        for slider in self.sliders:slider._drag_pointer=7
        for viewport in self.viewports:
            viewport._touch_points={7:(1,2)}
            viewport._last_pinch_distance=1
        # Exercise all native references even on ordinary Widget subclasses.
        self.root._sync_views=lambda:None
        self.root._tab_bar=object()
        self.root._inherited_text_style=object()
        self.backend._tab_index[99]=self.root
        for _,buffer,canvas in (self.backend._slider_resources+
                                self.backend._canvas_resources):
            close=canvas.close
            def tracked_close(close=close,number=buffer.number):
                self.calls.append(('canvas',number))
                self.states.append((
                    all(s._slider_draw is None and s._drag_pointer is None
                        for s in self.sliders),
                    all(v._draw_viewport is None and not v._touch_points
                        and v._last_pinch_distance is None
                        for v in self.viewports),
                    not Clock._jobs and not Clock._active,
                    all(n._theme_hook is None for n in self.root.walk())
                    and self.root._sync_views is None))
                close()
                error=self.failures.get(('canvas',number))
                if error is not None:raise error
            canvas.close=tracked_close

    def assert_clean(self,initial_calls=()):
        self.assertEqual(self.calls,list(initial_calls)+[('canvas',1),('buffer',1),
                                    ('canvas',0),('buffer',0),
                                    ('canvas',3),('buffer',3),
                                    ('canvas',2),('buffer',2),
                                    ('connection',None)])
        self.assertEqual(self.states,[(True,True,True,True)]*4)
        self.assertTrue(all(buffer.closed for buffer in self.buffers))
        self.assertEqual(self.backend._slider_resources,[])
        self.assertEqual(self.backend._canvas_resources,[])
        self.assertEqual(self.backend.nodes,[])
        self.assertEqual(self.backend._native_index,{})
        self.assertEqual(self.backend._tab_index,{})
        for node in self.root.walk():
            self.assertIsNone(node._native)
            self.assertIsNone(node._theme_hook)
            self.assertIsNone(node._effective_theme)
            self.assertEqual(node._applied_native_style,{})
        self.assertIsNone(self.root._sync_views)
        self.assertIsNone(self.root._tab_bar)
        self.assertIsNone(self.root._inherited_text_style)
        self.assertIsNone(self.backend.activity)
        self.assertIsNone(self.backend.connection)

    def test_each_resource_failure_still_closes_remaining_resources(self):
        for kind,number in [('canvas',1),('buffer',1),('canvas',3),('buffer',3)]:
            with self.subTest(kind=kind,number=number):
                self.setUp()
                failure=RuntimeError('resource close failed')
                self.failures[(kind,number)]=failure
                def start():
                    self.start()
                    self.backend.stop()
                with self.assertRaises(RuntimeError) as raised:
                    self.backend.run(self.root,start)
                self.assertIs(raised.exception,failure)
                self.assert_clean()

    def test_original_start_and_event_errors_survive_cleanup_failures(self):
        for phase in ('start','event'):
            with self.subTest(phase=phase):
                self.setUp()
                original=ValueError(phase+' failed')
                self.failures={('canvas',1):RuntimeError('canvas close failed'),
                               ('buffer',1):RuntimeError('buffer close failed'),
                               ('canvas',3):RuntimeError('viewport close failed')}
                self.connection_failure=RuntimeError('connection close failed')
                def explode(*args):raise original
                def start():
                    self.start()
                    if phase=='start':explode()
                FakeTG.events=[explode]
                stdout=io.StringIO();stderr=io.StringIO()
                with redirect_stdout(stdout),redirect_stderr(stderr):
                    with self.assertRaises(ValueError) as raised:
                        self.backend.run(self.root,start)
                self.assertIs(raised.exception,original)
                self.assertEqual(stdout.getvalue(),'')
                for message in ('canvas close failed','buffer close failed',
                                'viewport close failed','connection close failed'):
                    self.assertIn(message,stderr.getvalue())
                self.assert_clean()

    def test_first_cleanup_failure_survives_later_failures(self):
        first=RuntimeError('first close failed')
        self.failures={('canvas',1):first,
                       ('buffer',1):ValueError('secondary close failed')}
        self.connection_failure=ValueError('connection close failed')
        def start():
            self.start()
            self.backend.stop()
        with self.assertLogs('tgk',level='ERROR') as logs:
            with self.assertRaises(RuntimeError) as raised:
                self.backend.run(self.root,start)
        self.assertIs(raised.exception,first)
        self.assertIn('secondary close failed','\n'.join(logs.output))
        self.assertIn('connection close failed','\n'.join(logs.output))
        self.assert_clean()

    def test_model_reset_failure_does_not_leave_other_native_references(self):
        failure=RuntimeError('style reset failed')
        class BrokenStyle(dict):
            def clear(self):raise failure
        def start():
            self.start()
            self.root._applied_native_style=BrokenStyle()
            self.backend.stop()
        with self.assertRaises(RuntimeError) as raised:
            self.backend.run(self.root,start)
        self.assertIs(raised.exception,failure)
        self.assert_clean()

    def test_canvas_construction_error_survives_unregistered_buffer_exit_failure(self):
        from tgk.canvas import Canvas
        for failing_node in (Slider(),InfiniteCanvas(width=32,height=32)):
            with self.subTest(widget=type(failing_node).__name__):
                self.setUp()
                self.root.add_widget(failing_node)
                original=ValueError('canvas construction failed')
                secondary=RuntimeError('unregistered buffer exit failed')
                self.failures[('buffer',4)]=secondary
                def construct(memory,width,height):
                    if len(self.buffers)==5:
                        # Four native resources are registered before the
                        # fifth Canvas constructor fails during real render.
                        self.start()
                        raise original
                    return Canvas(memory,width,height)
                stdout=io.StringIO();stderr=io.StringIO()
                with patch('tgk.canvas.Canvas',side_effect=construct):
                    with redirect_stdout(stdout),redirect_stderr(stderr):
                        with self.assertRaises(BaseException) as raised:
                            self.backend.run(self.root)
                self.assertIs(raised.exception,original)
                self.assertEqual(len(self.connection_errors),1)
                kind,error,traceback=self.connection_errors[0]
                self.assertIs(kind,ValueError)
                self.assertIs(error,original)
                self.assertIsNotNone(traceback)
                self.assertEqual(stdout.getvalue(),'')
                self.assertIn('unregistered buffer exit failed',stderr.getvalue())
                self.assert_clean(initial_calls=[('buffer',4)])

    def test_activity_creation_failure_resets_connection(self):
        original=RuntimeError('activity creation failed')
        def activity(*args,**kwargs):raise original
        self.tg.Activity=activity
        with self.assertRaises(RuntimeError) as raised:
            self.backend.run(Label())
        self.assertIs(raised.exception,original)
        self.assertIsNone(self.backend.connection)
        self.assertIsNone(self.backend.activity)
        self.assertEqual(self.calls,[('connection',None)])

    def test_real_canvas_load_error_releases_unregistered_buffer(self):
        for node in (Slider(),InfiniteCanvas(width=32,height=32)):
            with self.subTest(widget=type(node).__name__):
                self.setUp()
                original=OSError('native rasterizer could not load')
                stderr=io.StringIO();stdout=io.StringIO()
                with patch('tgk.canvas._lib',side_effect=original):
                    with redirect_stdout(stdout),redirect_stderr(stderr):
                        with self.assertRaises(OSError) as raised:
                            self.backend.run(node)
                self.assertIs(raised.exception,original)
                self.assertEqual(len(self.connection_errors),1)
                kind,error,traceback=self.connection_errors[0]
                self.assertIs(kind,OSError)
                self.assertIs(error,original)
                # Keep the original traceback (and partially initialized
                # Canvas) alive while checking that buffer exit succeeded.
                self.assertIsNotNone(traceback)
                self.assertEqual(self.calls,[('buffer',0),('connection',None)])
                self.assertEqual(len(self.buffers),1)
                self.assertTrue(self.buffers[0].closed)
                self.buffers[0].data.extend(b'no live export')
                self.assertEqual(stderr.getvalue(),'')
                self.assertEqual(stdout.getvalue(),'')
                self.assertEqual(self.backend._slider_resources,[])
                self.assertEqual(self.backend._canvas_resources,[])
                self.assertEqual(self.backend.nodes,[])
                self.assertEqual(self.backend._native_index,{})
                self.assertIsNone(self.backend.connection)
                self.assertIsNone(self.backend.activity)
                self.assertIsNone(node._native)


if __name__=='__main__':unittest.main()
