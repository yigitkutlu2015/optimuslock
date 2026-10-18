"""Cloudflare Tunnel entegrasyonu (öğretmen tarafı).

Öğrenci bilgisayarı kendi tüneliyle bir alan adı (ör. pc01.okul.com -> tcp://localhost:5710) yayınlar.
Öğretmen paneli her öğrenci için `cloudflared access tcp` ile yerel bir port açar ve ajana oradan bağlanır.
Sırasıyla: bilgisayarda kurulu `cloudflared` -> yoksa Docker (cloudflare/cloudflared) kullanılır.
"""
import os
import shutil
import socket
import subprocess
import threading

IMAGE = "cloudflare/cloudflared:latest"
_WIN = (r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe")


def _kw():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def native_bin():
    for c in (shutil.which("cloudflared"), *_WIN):
        if c and os.path.exists(c):
            return c
    return None


def available() -> bool:
    return bool(native_bin() or shutil.which("docker"))


def _free_port(start=26000):
    for p in range(start, start + 2000):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("boş port yok")


class ForwardManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.ports, self.procs, self.names = {}, {}, {}

    def _alive(self, host):
        p = self.procs.get(host)
        if p is not None:
            return p.poll() is None
        name = self.names.get(host)
        if name:
            try:
                r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                                   capture_output=True, text=True, timeout=5, **_kw())
                return r.stdout.strip() == "true"
            except Exception:
                return False
        return False

    def ensure(self, host) -> int:
        """Bu tünel adresi için yerel yönlendirme portunu döndürür (gerekirse başlatır)."""
        with self.lock:
            if host in self.ports and self._alive(host):
                return self.ports[host]
            port = self.ports.get(host) or _free_port()
            nb = native_bin()
            if nb:
                self.procs[host] = subprocess.Popen(
                    [nb, "access", "tcp", "--hostname", host, "--url", f"127.0.0.1:{port}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_kw())
            elif shutil.which("docker"):
                name = f"optimuslock-cfa-{port}"
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=20, **_kw())
                r = subprocess.run(
                    ["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:{port}", IMAGE,
                     "access", "tcp", "--hostname", host, "--url", f"0.0.0.0:{port}"],
                    capture_output=True, text=True, timeout=600, **_kw())
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or r.stdout).strip()[-200:])
                self.names[host] = name
                self.procs.pop(host, None)
            else:
                raise RuntimeError("cloudflared veya Docker bulunamadı")
            self.ports[host] = port
            return port

    def stop_all(self):
        for p in self.procs.values():
            try:
                p.terminate()
            except Exception:
                pass
        for name in self.names.values():
            try:
                subprocess.Popen(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, **_kw())
            except Exception:
                pass
        self.procs.clear()
        self.names.clear()
        self.ports.clear()
