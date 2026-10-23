"""Event-index hot path: native Views are not necessarily hashable."""
import unittest
from types import SimpleNamespace
from tgk.widgets import Button,BoxLayout,Widget,TermuxBackend


class ProbeNative:
    __hash__=None
    equality_calls=0

    def __init__(self,identifier):self.id=identifier
    def __eq__(self,other):
        type(self).equality_calls+=1
        return self.id==other


class EventIndexTests(unittest.TestCase):
    def setUp(self):
        ProbeNative.equality_calls=0
        self.backend=TermuxBackend(tg=object())
        self.buttons=[]
        self.clicked=[]
        for i in range(500):
            button=Button(text=str(i))
            button._native=ProbeNative(i+1)
            button.bind(on_release=lambda _button,i=i:self.clicked.append(i))
            self.buttons.append(button)
            self.backend.nodes.append(button)
            self.backend._native_index[i+1]=button

    def test_last_button_dispatch_skips_full_native_view_scan(self):
        self.backend.event(SimpleNamespace(type='click',value={'id':500}))
        self.assertEqual(self.clicked,[499])
        self.assertEqual(ProbeNative.equality_calls,0)

    def test_unknown_native_id_does_not_scan_all_views(self):
        self.backend.event(SimpleNamespace(type='click',value={'id':99999}))
        self.assertEqual(self.clicked,[])
        self.assertEqual(ProbeNative.equality_calls,0)

    def test_old_nonindexed_binding_uses_equality_fallback(self):
        backend=TermuxBackend(tg=object())
        first=Button(text='legacy')
        first._native=ProbeNative(7)
        backend.nodes.append(first)
        observed=[]
        first.bind(on_release=lambda *_:observed.append(1))
        backend.event(SimpleNamespace(type='click',value={'id':7}))
        self.assertEqual(observed,[1])
        self.assertEqual(ProbeNative.equality_calls,1)

    def test_native_views_need_not_be_hashable(self):
        self.assertIsNone(ProbeNative.__hash__)
        self.assertEqual(len(self.backend._native_index),500)

    def test_widget_tree_walk_handles_more_than_recursion_limit(self):
        root=Widget()
        current=root
        for _ in range(1200):
            child=Widget()
            current.add_widget(child)
            current=child
        nodes=list(root.walk())
        self.assertEqual(len(nodes),1201)
        self.assertIs(nodes[0],root)
        self.assertIs(nodes[-1],current)

    def test_depth_first_widget_order_remains_stable(self):
        root=BoxLayout()
        a=Button(text='a')
        b=Button(text='b')
        c=Button(text='c')
        root.add_widget(a);root.add_widget(b)
        a.add_widget(c)
        self.assertEqual(list(root.walk()),[root,a,c,b])


if __name__=='__main__':
    unittest.main()
