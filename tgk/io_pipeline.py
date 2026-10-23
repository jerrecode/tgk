"""Bounded, cancellable binary I/O and FFprobe adapters for TGK applications.

The streaming contract is deliberately narrow: local files, explicit HTTP(S)
downloads and local ffprobe. Network transfers require the caller to opt in.
Never pass user strings through a shell or open an unbounded stderr/stdout pipe.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Event, BoundedSemaphore
import time
from urllib.parse import urlsplit
from urllib.request import urlopen


@dataclass(frozen=True)
class Limits:
    chunk_bytes: int = 64 * 1024
    max_bytes: int = 256 * 1024 * 1024
    timeout: float = 30.0
    workers: int = 2
    pending: int = 4

    def __post_init__(self):
        for name,lower,upper in (("chunk_bytes",1024,8*1024*1024),
                                 ("max_bytes",1,1024*1024*1024*1024),
                                 ("workers",1,32),("pending",0,128)):
            value=getattr(self,name)
            if type(value) is not int or not lower<=value<=upper:
                raise ValueError(f"{name} must be an integer in [{lower},{upper}]")
        if isinstance(self.timeout,bool) or not isinstance(self.timeout,(int,float)) or (
                not math.isfinite(self.timeout) or not 0 < self.timeout <= 3600):
            raise ValueError("timeout must be finite in (0,3600]")


@dataclass(frozen=True)
class TransferResult:
    bytes_copied: int
    sha256: str
    elapsed: float


def transfer(source, sink, *, limits=None, cancelled=None, progress=None):
    """Copy bytes from an opened binary source to a binary sink with backpressure.

    Never reads more than chunk_bytes (+ one overflow-detection byte), and
    writes a chunk completely before requesting the next chunk.
    """
    limits=limits or Limits()
    start=time.monotonic()
    deadline=start+limits.timeout
    digest=hashlib.sha256()
    total=0
    while True:
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("transfer cancelled")
        if time.monotonic()>=deadline:
            raise TimeoutError("transfer deadline exceeded")
        remaining=limits.max_bytes-total
        data=source.read(min(limits.chunk_bytes,remaining+1))
        if not isinstance(data,(bytes,bytearray,memoryview)):
            raise TypeError("binary source must return bytes")
        if not data:break
        if len(data)>remaining:raise ValueError("maximum transfer size exceeded")
        view=memoryview(data)
        while view:
            if cancelled is not None and cancelled.is_set():
                raise InterruptedError("transfer cancelled")
            if time.monotonic()>=deadline:
                raise TimeoutError("transfer deadline exceeded")
            written=sink.write(view)
            if written is None:
                raise OSError("binary sink did not report bytes written")
            if type(written) is not int or not 0 < written <= len(view):
                raise OSError("binary sink made no forward progress")
            view=view[written:]
        digest.update(data)
        total+=len(data)
        if progress is not None:progress(total)
    return TransferResult(total,digest.hexdigest(),time.monotonic()-start)


def copy_file(source, target, *, limits=None, cancelled=None, progress=None,
              overwrite=False):
    """Bounded, atomic, sibling-temp-file copy. Existing target protected by default."""
    source=Path(source).expanduser()
    target=Path(target).expanduser()
    if source.resolve()==target.resolve():
        raise ValueError("source and target must differ")
    if not source.is_file():raise FileNotFoundError(source)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    if not target.parent.is_dir():raise FileNotFoundError(target.parent)
    fd,tmp=tempfile.mkstemp(prefix=".tgk-copy-",dir=target.parent)
    try:
        with os.fdopen(fd,"wb") as out,source.open("rb") as inp:
            result=transfer(inp,out,limits=limits,cancelled=cancelled,progress=progress)
            out.flush();os.fsync(out.fileno())
        # recheck because another process might have created target meanwhile
        if not overwrite and target.exists():raise FileExistsError(target)
        os.replace(tmp,target)
        return result
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass


def hash_file(path, *, limits=None,cancelled=None,progress=None):
    """Hash a local file without retaining its data in memory."""
    class NullSink:
        def write(self,view):return len(view)
    with Path(path).expanduser().open("rb") as source:
        return transfer(source,NullSink(),limits=limits,cancelled=cancelled,
                        progress=progress)


def download(url,target,*,limits=None,allow_http=False,allow_hosts=None,
             cancelled=None,progress=None,overwrite=False):
    """Stream one HTTP(S) resource into a local file with a fixed memory budget.

    Redirects are disabled to avoid unintentionally changing hosts or schemes.
    Callers accessing untrusted URLs must additionally apply DNS/IP allowlists
    or route requests through their own SSRF-safe network layer.
    """
    from urllib.request import build_opener,HTTPRedirectHandler,Request
    limits=limits or Limits()
    parsed=urlsplit(url)
    schemes=("https","http") if allow_http else ("https",)
    if parsed.scheme.lower() not in schemes or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid or unsupported download URL")
    if allow_hosts is not None and parsed.hostname.lower() not in set(x.lower() for x in allow_hosts):
        raise ValueError("host not in configured allowlist")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):
            raise ValueError("HTTP redirects disabled; provide the final URL")
    opener=build_opener(NoRedirect)
    req=Request(url,headers={"User-Agent":"TGK/0.2"})
    target=Path(target).expanduser()
    if target.exists() and not overwrite:raise FileExistsError(target)
    if not target.parent.is_dir():raise FileNotFoundError(target.parent)
    fd,tmp=tempfile.mkstemp(prefix=".tgk-download-",dir=target.parent)
    try:
        with os.fdopen(fd,"wb") as out,opener.open(req,timeout=limits.timeout) as response:
            result=transfer(response,out,limits=limits,cancelled=cancelled,
                            progress=progress)
            out.flush();os.fsync(out.fileno())
        if not overwrite and target.exists():raise FileExistsError(target)
        os.replace(tmp,target)
        return result
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass


def ffprobe(path,*,binary="ffprobe",timeout=15.0,max_json_bytes=8*1024*1024):
    """Run FFprobe on a local file, returning a bounded JSON dictionary.

    The executable must be installed separately (Termux: pkg install ffmpeg).
    The default protocol whitelist prevents loading remote URLs from metadata.
    """
    path=Path(path).expanduser().resolve(strict=True)
    if not path.is_file():raise ValueError("ffprobe input must be a regular local file")
    if not isinstance(binary,str) or not binary or os.path.basename(binary)!=binary:
        raise ValueError("ffprobe binary must be a simple executable name")
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=3600:
        raise ValueError("invalid ffprobe timeout")
    if type(max_json_bytes) is not int or not 1024<=max_json_bytes<=128*1024*1024:
        raise ValueError("invalid ffprobe output size")
    command=[binary,"-hide_banner","-v","error","-protocol_whitelist","file,pipe",
             "-show_format","-show_streams","-of","json","-i",str(path)]
    # Drain both pipes concurrently so metadata never occupies uncapped
    # memory OR disk and stderr cannot deadlock a blocked child process.
    import selectors
    proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          close_fds=True)
    limit=time.monotonic()+timeout
    stdout=bytearray();stderr=bytearray()
    selector=selectors.DefaultSelector()
    try:
        selector.register(proc.stdout,selectors.EVENT_READ,"stdout")
        selector.register(proc.stderr,selectors.EVENT_READ,"stderr")
        while selector.get_map():
            remaining=limit-time.monotonic()
            if remaining<=0:raise TimeoutError("ffprobe exceeded timeout")
            for key,_ in selector.select(remaining):
                block=os.read(key.fd,65536)
                if not block:
                    selector.unregister(key.fileobj)
                elif key.data=="stdout":
                    if len(stdout)+len(block)>max_json_bytes:
                        raise ValueError("ffprobe JSON too large")
                    stdout.extend(block)
                elif len(stderr)<4096:
                    stderr.extend(block[:4096-len(stderr)])
        remaining=limit-time.monotonic()
        if remaining<=0:raise TimeoutError("ffprobe exceeded timeout")
        try:exit_code=proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("ffprobe exceeded timeout") from exc
        if exit_code:
            raise RuntimeError(f"ffprobe exited {exit_code}: "+stderr.decode("utf-8","replace"))
        data=json.loads(stdout)
        if not isinstance(data,dict):raise ValueError("ffprobe JSON must be an object")
        return data
    except BaseException:
        if proc.poll() is None:proc.kill()
        proc.wait()
        raise
    finally:
        selector.close()
        proc.stdout.close()
        proc.stderr.close()


class BoundedPool:
    """Small thread pool with a bounded submission queue and explicit shutdown."""

    def __init__(self, limits=None):
        self.limits=limits or Limits()
        self._slots=BoundedSemaphore(self.limits.workers+self.limits.pending)
        self._pool=ThreadPoolExecutor(max_workers=self.limits.workers,
                                      thread_name_prefix="tgk-io")
        self._closed=False

    def submit(self,task,*args,timeout=None,**kwargs):
        if self._closed:raise RuntimeError("pool already closed")
        if not self._slots.acquire(timeout=self.limits.timeout if timeout is None else timeout):
            raise TimeoutError("TGK I/O queue saturated")
        try:
            if self._closed:raise RuntimeError("pool already closed")
            future=self._pool.submit(task,*args,**kwargs)
            future.add_done_callback(lambda _future:self._slots.release())
            return future
        except BaseException:
            self._slots.release()
            raise

    def shutdown(self,wait=True,cancel_futures=False):
        self._closed=True
        self._pool.shutdown(wait=wait,cancel_futures=cancel_futures)

    def __enter__(self):return self
    def __exit__(self,*args):self.shutdown(wait=True,cancel_futures=True)
