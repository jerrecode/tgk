"""Bounded file/HTTP/media adapters: errors, cleanup and resource limits."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch

from tgk.io_pipeline import Limits, transfer, copy_file, hash_file, download, ffprobe, BoundedPool


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def test_limits_reject_unsafe_config(self):
        for choices in ({"chunk_bytes":10},{"max_bytes":0},{"workers":0},
                        {"pending":-1},{"timeout":float('inf')},
                        {"timeout":0},{"chunk_bytes":True}):
            with self.subTest(choices=choices),self.assertRaises(ValueError):
                Limits(**choices)

    def test_bounded_copy_and_digest_with_short_writes(self):
        source=io.BytesIO(b'Hello! '*400)
        seen=[]
        class SlowSink:
            def __init__(self):self.buffer=bytearray()
            def write(self,part):
                n=min(7,len(part));self.buffer.extend(part[:n]);return n
        sink=SlowSink()
        result=transfer(source,sink,limits=Limits(chunk_bytes=1024),progress=seen.append)
        self.assertEqual(bytes(sink.buffer),b'Hello! '*400)
        self.assertEqual(result.bytes_copied,len(sink.buffer))
        self.assertEqual(result.sha256,hashlib.sha256(sink.buffer).hexdigest())
        self.assertGreater(len(seen),1)
        self.assertEqual(seen[-1],len(sink.buffer))

    def test_rejects_source_overflow_without_writing_oversized_output(self):
        sink=io.BytesIO()
        with self.assertRaisesRegex(ValueError,'maximum transfer'):
            transfer(io.BytesIO(b'x'*1025),sink,
                     limits=Limits(chunk_bytes=1024,max_bytes=1024))
        self.assertEqual(len(sink.getvalue()),1024)

    def test_cancel_and_nonconforming_stream(self):
        aborted=Event();aborted.set()
        with self.assertRaises(InterruptedError):
            transfer(io.BytesIO(b'abc'),io.BytesIO(),cancelled=aborted)
        with self.assertRaises(TypeError):
            transfer(io.StringIO('text'),io.BytesIO())
        class BadSink:
            def write(self,p):return 0
        with self.assertRaises(OSError):
            transfer(io.BytesIO(b'data'),BadSink())

    def test_atomic_copy_hash_and_overwrite(self):
        source=self.root/'a.bin';source.write_bytes(b'\0' * 128_000)
        target=self.root/'b.bin'
        expected=hash_file(source)
        copied=copy_file(source,target)
        self.assertEqual(expected.sha256,copied.sha256)
        self.assertEqual(target.read_bytes(),source.read_bytes())
        with self.assertRaises(FileExistsError):
            copy_file(source,target)
        source.write_bytes(b'new')
        copy_file(source,target,overwrite=True)
        self.assertEqual(target.read_bytes(),b'new')
        self.assertFalse(list(self.root.glob('.tgk-copy-*')))

    def test_failed_copy_preserves_previous_target(self):
        src=self.root/'big';src.write_bytes(b'x'*2048)
        dst=self.root/'dst';dst.write_bytes(b'old')
        with self.assertRaises(ValueError):
            copy_file(src,dst,overwrite=True,limits=Limits(max_bytes=1024))
        self.assertEqual(dst.read_bytes(),b'old')
        self.assertFalse(list(self.root.glob('.tgk-copy-*')))

    def test_https_only_and_allow_hosts(self):
        for url in ('http://example.test/data','file:///etc/passwd',
                    'ftp://test/file','https://user:pass@example.test/x',
                    'https:///invalid'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                download(url,self.root/'dest')
        with self.assertRaises(ValueError):
            download('https://untrusted.invalid/file',self.root/'dest',
                     allow_hosts={'allowed.invalid'})

    def test_http_stream_mock_and_atomic_destination(self):
        class Opener:
            def open(self,request,timeout):
                self.assert_timeout=timeout
                return io.BytesIO(b'download payload')
        opener=Opener()
        with patch('urllib.request.build_opener',return_value=opener):
            result=download('https://trusted.invalid/file',self.root/'download',
                            allow_hosts={'trusted.invalid'})
        self.assertEqual(result.bytes_copied,16)
        self.assertEqual((self.root/'download').read_bytes(),b'download payload')

    def test_ffprobe_parses_bounded_json_and_error(self):
        import os
        source=self.root/'film.mkv';source.write_bytes(b'dummy')
        class Process:
            payload=b'{"streams":[{"codec_name":"h264"}],"format":{}}'
            def __init__(self,argv,stdin,stdout,stderr,close_fds):
                self.argv=argv
                read,write=os.pipe()
                os.write(write,self.payload);os.close(write)
                self.stdout=os.fdopen(read,'rb',buffering=0)
                read,write=os.pipe()
                os.close(write)
                self.stderr=os.fdopen(read,'rb',buffering=0)
            def wait(self,timeout=None):return 0
            def poll(self):return 0
            def kill(self):pass
        with patch('subprocess.Popen',side_effect=Process):
            data=ffprobe(source)
        self.assertEqual(data['streams'][0]['codec_name'],'h264')
        class OversizeProcess(Process):
            payload=b'x'*2048
        with patch('subprocess.Popen',side_effect=OversizeProcess):
            with self.assertRaisesRegex(ValueError,'too large'):
                ffprobe(source,max_json_bytes=1024)
    def test_ffprobe_rejects_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            ffprobe(self.root/'missing')

    def test_pool_submission_is_bounded(self):
        limits=Limits(workers=1,pending=0,timeout=.2)
        gate=Event()
        with BoundedPool(limits) as pool:
            running=pool.submit(gate.wait,.5)
            with self.assertRaises(TimeoutError):
                pool.submit(lambda:None,timeout=.01)
            gate.set()
            self.assertTrue(running.result(timeout=1))
            self.assertEqual(pool.submit(lambda:42).result(timeout=1),42)
        with self.assertRaises(RuntimeError):
            pool.submit(lambda:99)


if __name__=="__main__":
    unittest.main()
