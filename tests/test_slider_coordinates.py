"""Regression: Termux:GUI ImageView touch coordinates already use image pixels."""
import unittest
from types import SimpleNamespace
from tgk.widgets import Slider, TermuxBackend
from test_tgk import FakeTG


class ImageViewCoordinatesTests(unittest.TestCase):
    def test_view_dimensions_must_not_rescale_image_pixels(self):
        for display_width in (320, 512, 1080, 1440):
            with self.subTest(display_width=display_width):
                slider = Slider(min=0, max=100, value=0, step=0)
                def unexpected_dimensions():
                    raise AssertionError('ImageView already maps touch to pixel coordinates')
                slider._native = SimpleNamespace(getdimensions=unexpected_dimensions)
                backend = TermuxBackend(tg=FakeTG)
                def emit(action, x):
                    backend._slider_touch(slider, FakeTG.Event('touch', {
                        'action': action, 'index': 0,
                        'pointers': [{'id': 7, 'x': x, 'y': 36}]}))
                emit('down', 22)
                self.assertEqual(slider.value, 0)
                emit('move', 255.5)
                self.assertAlmostEqual(slider.value, 50, places=6)
                emit('move', 489)
                self.assertEqual(slider.value, 100)
                emit('move', 700)
                self.assertEqual(slider.value, 100)
                emit('move', -50)
                self.assertEqual(slider.value, 0)
                emit('up', 255.5)
                self.assertAlmostEqual(slider.value, 50, places=6)
                self.assertIsNone(slider._drag_pointer)

    def test_invalid_input_is_ignored(self):
        slider = Slider(min=0, max=100, value=27, step=1)
        slider._native = SimpleNamespace()
        backend = TermuxBackend(tg=FakeTG)
        for x in (float('nan'), float('inf'), 'invalid', None):
            with self.subTest(x=x):
                backend._slider_touch(slider, FakeTG.Event('touch', {
                    'action': 'down', 'index': 0,
                    'pointers': [{'id': 1, 'x': x, 'y': 36}]}))
                self.assertEqual(slider.value, 27)
                backend._slider_touch(slider, FakeTG.Event('touch', {
                    'action': 'cancel', 'pointers': []}))


if __name__ == '__main__':
    unittest.main()
