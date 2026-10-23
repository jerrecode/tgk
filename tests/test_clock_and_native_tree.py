"""Native deep-tree construction, linear child placement and bounded clock jobs."""
import unittest
from tgk.widgets import (Clock,_Clock,TermuxBackend,BoxLayout,GridLayout,
                         Label,Button,Widget)
from test_tgk import FakeTG


class NoIndexList(list):
    def index(self,*args,**kwargs):
        raise AssertionError("native renderer used quadratic list.index()")


class ClockBudgetTests(unittest.TestCase):
    def setUp(self):
        Clock.reset()
        self.addCleanup(Clock.reset)

    def test_zero_delay_self_rescheduling_cannot_starve_gui_event_loop(self):
        calls=[]
        def again(delta):
            calls.append(delta)
            Clock.schedule_once(again,0)
        Clock.schedule_once(again,0)
        self.assertEqual(Clock.tick(max_callbacks=7),7)
        self.assertEqual(len(calls),7)
        self.assertEqual(Clock.tick(max_callbacks=9),9)
        self.assertEqual(len(calls),16)
        self.assertGreater(len(Clock._jobs),0)

    def test_cancelled_timer_does_not_run_or_leak_cancel_marker(self):
        calls=[]
        handle=Clock.schedule_once(lambda dt:calls.append(dt),0)
        handle.cancel()
        self.assertEqual(Clock.tick(),0)
        self.assertEqual(calls,[])
        self.assertFalse(Clock._cancel)
        self.assertFalse(Clock._active)
        handle.cancel()
        self.assertFalse(Clock._cancel)

    def test_cancel_running_repeating_job_from_its_callback(self):
        clock=_Clock()
        calls=[]
        handle=None
        def callback(dt):
            calls.append(dt)
            handle.cancel()
        handle=clock.schedule_interval(callback,0.000001)
        # Deliberately force due without timing-sensitive sleeps.
        due,ident,fn,interval=clock._jobs[0]
        clock._jobs[0]=(0,ident,fn,interval)
        self.assertEqual(clock.tick(),1)
        self.assertEqual(clock.tick(),0)
        self.assertEqual(len(calls),1)
        self.assertFalse(clock._active)

    def test_validation_and_callback_errors(self):
        with self.assertRaises(ValueError):Clock.tick(max_callbacks=0)
        with self.assertRaises(ValueError):Clock.tick(max_callbacks=1.5)
        with self.assertRaises(ValueError):Clock.schedule_once(lambda _:None,float("nan"))
        with self.assertRaises(ValueError):Clock.schedule_interval(lambda _:None,float("inf"))
        with self.assertRaises(TypeError):Clock.schedule_once("not-callable",0)
        def faulty(dt):raise RuntimeError("boom")
        Clock.schedule_once(faulty,0)
        with self.assertRaisesRegex(RuntimeError,"boom"):Clock.tick()
        self.assertFalse(Clock._active)

    def test_activity_shutdown_removes_pending_clock_jobs(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0
        backend=TermuxBackend(tg=FakeTG)
        done=[]
        def start():
            Clock.schedule_once(lambda dt:done.append("stale"),200)
            backend.stop()
        backend.run(Label(text="test"),start)
        self.assertFalse(Clock._jobs)
        self.assertFalse(Clock._active)
        self.assertEqual(done,[])


class NativeTreeTests(unittest.TestCase):
    def setUp(self):
        FakeTG.events=[];FakeTG.views=[];FakeTG.count=0

    def test_native_render_works_for_depth_above_python_recursion_limit(self):
        root=BoxLayout(orientation="vertical")
        node=root
        for _ in range(1100):
            child=BoxLayout(orientation="vertical")
            node.add_widget(child)
            node=child
        node.add_widget(Label(text="last"))
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        first=backend.render(root)
        self.assertIs(first,root._native)
        self.assertEqual(len(backend.nodes),1102)
        self.assertIsNotNone(node.children[0]._native)
        self.assertEqual(len(backend._native_index),1102)

    def test_many_siblings_use_child_position_not_list_index(self):
        root=BoxLayout(orientation="vertical",spacing=3)
        for i in range(120):root.add_widget(Button(text=str(i),height=48))
        root.children=NoIndexList(root.children)
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        backend.render(root)
        self.assertEqual(len(backend.nodes),121)
        self.assertNotIn("setmargin_value",root.children[0]._native.__dict__)
        self.assertEqual(root.children[119]._native.setmargin_value,(3,'top'))

    def test_grid_positions_are_bounded_and_stable(self):
        root=GridLayout(cols=8)
        for i in range(64):root.add_widget(Button(text=str(i)))
        root.children=NoIndexList(root.children)
        backend=TermuxBackend(tg=FakeTG)
        backend.activity=FakeTG.Activity(None)
        backend.render(root)
        self.assertEqual(root.children[-1]._native.setgridlayoutparams_value,
                         (7,7,1,1,'center','center'))


if __name__=="__main__":
    unittest.main()
