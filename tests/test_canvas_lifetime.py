"""Closing a canvas must make retained native buffer pointers unusable."""
import unittest
from unittest.mock import patch
from tgk.canvas import Canvas,rgba


class CanvasLifetimeTests(unittest.TestCase):
    def test_every_operation_rejects_a_closed_canvas(self):
        pixels=bytearray(16)
        canvas=Canvas(pixels,2,2)
        canvas.close()
        canvas.close()
        for operation in (
            lambda:canvas.clear(rgba(255,0,0)),
            lambda:canvas.rect(0,0,1,1,rgba(255,0,0)),
            lambda:canvas.circle(0,0,1,rgba(255,0,0)),
            lambda:canvas.line(0,0,1,1,rgba(255,0,0)),
            lambda:canvas.gradient(rgba(0,0,0),rgba(255,255,255)),
            lambda:canvas.map_touch(1,1,2,2),
        ):
            with self.subTest(operation=operation),self.assertRaisesRegex(RuntimeError,"closed"):
                operation()
        self.assertFalse(any(pixels))

    def test_close_releases_the_exported_python_buffer(self):
        pixels=bytearray(16)
        canvas=Canvas(pixels,2,2)
        canvas.close()
        pixels.extend(b"released")
        self.assertEqual(len(pixels),24)

    def test_surface_rejection_releases_export_and_partial_native_pointer(self):
        from tgk.canvas import _lib
        native=_lib()
        class RejectSurface:
            def tgk_surface_init(self,*args):
                # Initialize the real pointer before reporting failure, so
                # constructor cleanup must invalidate a partial surface too.
                native.tgk_surface_init(*args)
                return 1
        pixels=bytearray(16)
        retained=None
        with patch('tgk.canvas._lib',return_value=RejectSurface()):
            try:Canvas(pixels,2,2)
            except ValueError as error:retained=error
        self.assertIsNotNone(retained)
        traceback=retained.__traceback__
        while traceback.tb_frame.f_code is not Canvas.__init__.__code__:
            traceback=traceback.tb_next
        partial=traceback.tb_frame.f_locals['self']
        try:pixels.extend(b'released')
        except BufferError:self.fail('failed Canvas still exports its buffer')
        self.assertFalse(partial._s.pixels)
        partial.close()
        partial.close()
        with self.assertRaisesRegex(RuntimeError,'closed'):
            partial.clear(rgba(255,0,0))


if __name__=="__main__":unittest.main()
