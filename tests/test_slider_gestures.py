"""Protocol-level gesture ownership: pointer indices are not pointer IDs."""
import unittest
from types import SimpleNamespace

from tgk.widgets import Slider, TermuxBackend
from test_tgk import FakeTG


class SliderGestureTests(unittest.TestCase):
    def setUp(self):
        self.slider = Slider(value=25)
        self.backend = TermuxBackend(tg=FakeTG)

    def emit(self, action, points, index=0):
        self.backend._slider_touch(self.slider, SimpleNamespace(
            type='touch', value={'action': action, 'pointers': points, 'index': index}))

    @staticmethod
    def point(pointer, x):
        return {'id': pointer, 'x': x, 'y': 36}

    def test_secondary_release_does_not_end_primary_drag(self):
        primary = self.point(7, 22)
        secondary = self.point(42, 489)
        self.emit('down', [[primary]])
        self.emit('pointer_down', [[primary, secondary]], index=1)
        self.emit('pointer_up', [[primary, secondary]], index=1)
        self.assertEqual(self.slider._drag_pointer, 7)
        self.emit('move', [[self.point(7, 489)]])
        self.assertEqual(self.slider.value, 100)

    def test_primary_release_uses_action_index_after_pointer_reordering(self):
        self.emit('down', [[self.point(7, 22)]])
        self.emit('pointer_up', [[self.point(42, 22), self.point(7, 489)]], index=1)
        self.assertEqual(self.slider.value, 100)
        self.assertIsNone(self.slider._drag_pointer)
        self.emit('move', [[self.point(42, 22)]])
        self.assertEqual(self.slider.value, 100)

    def test_malformed_down_does_not_capture_pointer(self):
        for x in (None, 'bad', float('nan'), float('inf')):
            with self.subTest(x=x):
                self.emit('down', [[self.point(7, x)]])
                self.assertIsNone(self.slider._drag_pointer)
                self.assertEqual(self.slider.value, 25)

    def test_release_always_clears_owner_even_without_valid_coordinates(self):
        for points in ([], [[self.point(7, 'bad')]], [[self.point(7, float('nan'))]]):
            with self.subTest(points=points):
                self.emit('down', [[self.point(7, 22)]])
                self.emit('up', points)
                self.assertIsNone(self.slider._drag_pointer)
                self.emit('down', [[self.point(42, 489)]])
                self.assertEqual(self.slider.value, 100)

    def test_invalid_pointer_index_does_not_release_another_pointer(self):
        for index in (-1, 2, 'bad', True):
            with self.subTest(index=index):
                self.emit('down', [[self.point(7, 22)]])
                self.emit('pointer_up', [[self.point(7, 489)]], index=index)
                self.assertEqual(self.slider._drag_pointer, 7)
                self.assertEqual(self.slider.value, 0)

    def test_cancel_then_move_cannot_restart_drag(self):
        self.emit('down', [[self.point(7, 22)]])
        self.emit('cancel', [])
        self.emit('move', [[self.point(7, 489)]])
        self.assertIsNone(self.slider._drag_pointer)
        self.assertEqual(self.slider.value, 0)

    def test_move_uses_latest_batched_frame_and_stable_pointer_id(self):
        self.emit('down', [[self.point(7, 22)]])
        self.emit('move', [[self.point(7, 100), self.point(42, 22)],
                           [self.point(42, 22), self.point(7, 489)]])
        self.assertEqual(self.slider.value, 100)


if __name__ == '__main__':
    unittest.main()
