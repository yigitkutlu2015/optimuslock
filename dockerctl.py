"""Docker yönetimi: Tailscale / Cloudflare Tunnel konteynerlerini uygulama kendisi kurar.
Ayrı betik/komut yoktur; compose dosyası burada üretilir ve uygulama açılırken `up -d` çalıştırılır."""
import os
import shutil
import subprocess
import sys
import threading
import time

import tailscale
from common import config_dir

PROJECT = "optimuslock"
LINUX = sys.platform.startswith("linux")


def _kw():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def userspace(cfg) -> bool:
    """Windows/Mac + Docker Desktop: Tailscale konteyneri userspace + SOCKS5 köprüsüyle çalışır."""
    return cfg.get("mode") == "tailscale" and cfg.get("ts_via", "docker") == "docker" and not LINUX


def needed(cfg) -> bool:
    if cfg.get("mode") == "tailscale":
        return cfg.get("ts_via", "docker") == "docker"
    return cfg.get("mode") == "cloudflare" and cfg.get("role") == "student"


def compose_cmd():
    d = shutil.which("docker")
    if d:
        try:
            r = subprocess.run([d, "compose", "version"], capture_output=True, timeout=10, **_kw())
            if r.returncode == 0:
                return [d, "compose"]
        except Exception:
            pass
    dc = shutil.which("docker-compose")
    return [dc] if dc else None


def compose_yaml(cfg):
    parts = []
    if cfg.get("mode") == "tailscale" and cfg.get("ts_via", "docker") == "docker":
        if LINUX:
            parts.append("""  tailscale:
    image: tailscale/tailscale:stable
    container_name: optimuslock-tailscale
    network_mode: host
    cap_add: [NET_ADMIN, NET_RAW]
    devices: ["/dev/net/tun:/dev/net/tun"]
    volumes: ["ts-state:/var/lib/tailscale"]
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_HOSTNAME=${TS_HOSTNAME}
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=false
    restart: unless-stopped""")
        else:
            parts.append("""  tailscale:
    image: tailscale/tailscale:stable
    container_name: optimuslock-tailscale
    hostname: ${TS_HOSTNAME}
    volumes: ["ts-state:/var/lib/tailscale"]
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_HOSTNAME=${TS_HOSTNAME}
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=true
      - TS_SOCKS5_SERVER=0.0.0.0:1055
    ports: ["127.0.0.1:1055:1055"]
    extra_hosts: ["host.docker.internal:host-gateway"]
    restart: unless-stopped""")
    if cfg.get("mode") == "cloudflare" and cfg.get("role") == "student":
        net = "    network_mode: host" if LINUX else '    extra_hosts: ["host.docker.internal:host-gateway"]'
        parts.append(f"""  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: optimuslock-cloudflared
    command: tunnel run
{net}
    environment:
      - TUNNEL_TOKEN=${{TUNNEL_TOKEN}}
    restart: unless-stopped""")
    if not parts:
        return None
    y = "services:\n" + "\n".join(parts) + "\n"
    if "ts-state" in y:
        y += "volumes:\n  ts-state: {}\n"
    return y


def ensure(cfg):
    """Gerekli konteynerleri başlatır. (başarılı_mı, mesaj) döndürür."""
    y = compose_yaml(cfg)
    if not y:
        return True, ""
    cc = compose_cmd()
    if not cc:
        return False, ("Docker bulunamadı. Windows'ta Docker Desktop'ı kurup açın; Linux'ta "
                       "'sudo apt install docker.io' ve kullanıcıyı docker grubuna ekleyin.")
    d = config_dir() / "docker"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "docker-compose.yml"
    f.write_text(y, "utf-8")
    env = dict(os.environ,
               TS_AUTHKEY=cfg.get("ts_authkey", ""),
               TS_HOSTNAME=cfg.get("ts_hostname") or "optimuslock-pc",
               TUNNEL_TOKEN=cfg.get("cf_token", ""))
    try:
        r = subprocess.run(cc + ["-p", PROJECT, "-f", str(f), "up", "-d"], env=env, capture_output=True,
                           text=True, timeout=600, **_kw())
    except Exception as e:
        return False, str(e)[:300]
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[-400:]
        if "permission denied" in err.lower() and LINUX:
            err += "\nÇözüm: sudo usermod -aG docker $USER  (sonra oturumu kapatıp açın)"
        return False, err
    return True, "Docker konteynerleri çalışıyor"


class Bootstrap(threading.Thread):
    """Arka planda konteynerleri başlatır; Windows'ta Tailscale -> ajan yönlendirmesini de ayarlar."""

    def __init__(self, cfg, done):
        super().__init__(daemon=True)
        self.cfg, self.done = cfg, done

    def run(self):
        ok, msg = ensure(self.cfg)
        if ok and self.cfg.get("role") == "student" and userspace(self.cfg):
            for _ in range(12):
                if tailscale.expose_port(int(self.cfg["port"])):
                    break
                time.sleep(4)
            else:
                ok, msg = False, "Tailscale konteyneri hazır değil (TS_AUTHKEY doğru mu? docker logs optimuslock-tailscale)"
        self.done(ok, msg)
