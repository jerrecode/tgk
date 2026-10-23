"""Closing a canvas must make retained native buffer pointers unusable."""
import unittest
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


if __name__=="__main__":unittest.main()
