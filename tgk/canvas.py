"""ctypes wrapping the C rasterizer. No numpy required, supports TG shared mmap."""
from __future__ import annotations
import ctypes as ct
from pathlib import Path

class _Surface(ct.Structure):
    _fields_ = [('pixels', ct.POINTER(ct.c_uint8)), ('width', ct.c_int),
                ('height', ct.c_int), ('stride', ct.c_int)]

def _lib():
    path = Path(__file__).with_name('libtgk.so')
    if not path.exists():
        raise RuntimeError(f'C library not built: {path}; run ./install.sh')
    lib = ct.CDLL(str(path))
    s = ct.POINTER(_Surface)
    for func, types in {
        'surface_init': [s, ct.c_void_p, ct.c_int, ct.c_int, ct.c_int],
        'clear': [s, ct.c_uint32], 'rect': [s, ct.c_int, ct.c_int, ct.c_int, ct.c_int, ct.c_uint32],
        'circle': [s, ct.c_int, ct.c_int, ct.c_int, ct.c_uint32],
        'line': [s, ct.c_int, ct.c_int, ct.c_int, ct.c_int, ct.c_uint32],
        'gradient': [s, ct.c_uint32, ct.c_uint32],
        'map_touch': [ct.c_int]*5+[ct.c_double]*2+[ct.POINTER(ct.c_int)]*2,
    }.items():
        method = getattr(lib, 'tgk_'+func)
        method.argtypes = types
        method.restype = ct.c_int if func in ('surface_init', 'map_touch') else None
    return lib

def rgba(r,g,b,a=255):
    """Pack RGBA bytes into the C renderer's 0xRRGGBBAA representation."""
    for v in (r,g,b,a):
        if not (isinstance(v,int) and 0<=v<=255): raise ValueError('expected RGBA bytes 0..255')
    return (r<<24)|(g<<16)|(b<<8)|a

class Canvas:
    def __init__(self, buffer, width, height, stride=None):
        self.width, self.height = int(width), int(height)
        self.stride = int(stride if stride is not None else 4*width)
        if self.width<=0 or self.height<=0 or self.stride<4*self.width:
            raise ValueError('invalid canvas dimensions')
        # memoryview object, bytearray and mmap all provide writable buffers.
        self._source = (ct.c_uint8 * (self.stride*self.height)).from_buffer(buffer)
        self._s = _Surface(); self._c = _lib()
        if self._c.tgk_surface_init(ct.byref(self._s), self._source,
                                     self.width, self.height, self.stride):
            raise ValueError('cannot initialize surface')
    def clear(self,color): self._c.tgk_clear(ct.byref(self._s),color)
    def rect(self,x,y,w,h,color): self._c.tgk_rect(ct.byref(self._s),int(x),int(y),int(w),int(h),color)
    def circle(self,x,y,r,color): self._c.tgk_circle(ct.byref(self._s),int(x),int(y),int(r),color)
    def line(self,x,y,x1,y1,color): self._c.tgk_line(ct.byref(self._s),int(x),int(y),int(x1),int(y1),color)
    def gradient(self,top,bottom): self._c.tgk_gradient(ct.byref(self._s),top,bottom)
    def map_touch(self,x,y,view_w,view_h,fit=False):
        px,py=ct.c_int(),ct.c_int()
        rc=self._c.tgk_map_touch(int(view_w),int(view_h),self.width,self.height,int(fit),
                                  float(x),float(y),ct.byref(px),ct.byref(py))
        return None if rc else (px.value,py.value)
    def close(self):
        self._source=None  # relinquish exported buffer before mmap.close
