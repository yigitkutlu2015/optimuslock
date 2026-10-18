"""Tailscale entegrasyonu.

Sırasıyla şunları dener:
  1) Docker yan konteyneri (optimuslock-tailscale)  -> Pardus/Linux için önerilen yol
  2) Sistemde kurulu `tailscale` komutu              -> Windows (Program Files) veya Linux
"""
import json
import os
import shutil
import subprocess

CONTAINER = "optimuslock-tailscale"
_WIN_PATHS = (r"C:\Program Files\Tailscale\tailscale.exe", r"C:\Program Files (x86)\Tailscale\tailscale.exe")


def _kw():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}  # konsol penceresi açma


def _base():
    docker = shutil.which("docker")
    if docker:
        try:
            r = subprocess.run(
                [docker, "inspect", "-f", "{{.State.Running}}", CONTAINER],
                capture_output=True, text=True, timeout=5, **_kw(),
            )
            if r.stdout.strip() == "true":
                return [docker, "exec", CONTAINER, "tailscale"]
        except Exception:
            pass
    for c in (shutil.which("tailscale"), *_WIN_PATHS):
        if c and os.path.exists(c):
            return [c]
    return None


def available() -> bool:
    return _base() is not None


def status():
    base = _base()
    if not base:
        return None
    try:
        r = subprocess.run(base + ["status", "--json"], capture_output=True, text=True, timeout=8, **_kw())
        return json.loads(r.stdout) if r.stdout.strip() else None
    except Exception:
        return None


def is_connected() -> bool:
    st = status()
    return bool(st and st.get("BackendState") == "Running")


def my_ip():
    st = status()
    if st and st.get("BackendState") == "Running":
        for ip in (st.get("Self") or {}).get("TailscaleIPs", []):
            if "." in ip:
                return ip
    return None


def peers():
    """Çevrimiçi Tailscale cihazlarını döndürür: [{name, ip, os}]"""
    st = status()
    out = []
    if not st:
        return out
    for p in (st.get("Peer") or {}).values():
        ips = [i for i in p.get("TailscaleIPs", []) if "." in i]
        if ips and p.get("Online"):
            out.append({"name": p.get("HostName", ""), "ip": ips[0], "os": p.get("OS", "")})
    return out


def socks_proxy():
    """Docker konteyneri userspace modunda SOCKS5 sunuyorsa ("127.0.0.1", port) döndürür.
    (Windows + Docker Desktop düzeni: docker-compose.windows.yml)"""
    docker = shutil.which("docker")
    if not docker:
        return None
    try:
        r = subprocess.run(
            [docker, "inspect", "-f", "{{range .Config.Env}}{{println .}}{{end}}", CONTAINER],
            capture_output=True, text=True, timeout=5, **_kw(),
        )
        for line in r.stdout.splitlines():
            if line.startswith("TS_SOCKS5_SERVER="):
                return ("127.0.0.1", int(line.rsplit(":", 1)[1]))
    except Exception:
        pass
    return None


def expose_port(port: int) -> bool:
    """Tailnet'ten gelen TCP bağlantılarını konteynerden Windows'taki ajana yönlendirir."""
    base = _base()
    if not base:
        return False
    try:
        r = subprocess.run(
            base + ["serve", "--bg", f"--tcp={port}", f"tcp://host.docker.internal:{port}"],
            capture_output=True, text=True, timeout=15, **_kw(),
        )
        return r.returncode == 0
    except Exception:
        return False
