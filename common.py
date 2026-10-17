"""Optimuslock - ortak yardımcılar: yapılandırma, şifreli protokol, otomatik başlatma."""
import base64
import hashlib
import ipaddress
import json
import os
import socket
import struct
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

APP_NAME = "Optimuslock"
DEFAULT_PORT = 5710
VERSION = 1
MAX_FRAME = 8 * 1024 * 1024


class ProtocolError(Exception):
    pass


# ---------------------------------------------------------------- yapılandırma
def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    d = base / "optimuslock"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_FILE = config_dir() / "config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")


# ------------------------------------------------------- şifreli çerçeveleme
def make_cipher(key: str) -> Fernet:
    """Sınıf anahtarından Fernet (AES + HMAC) anahtarı türetir.
    Anahtarı bilmeyen biri ne okuyabilir ne de komut gönderebilir."""
    raw = hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), b"optimuslock-v1", 200_000, 32)
    return Fernet(base64.urlsafe_b64encode(raw))


def _recv_exact(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ProtocolError("bağlantı kapandı")
        buf += chunk
    return bytes(buf)


def send_msg(sock, cipher: Fernet, obj: dict) -> None:
    token = cipher.encrypt(json.dumps(obj).encode("utf-8"))
    sock.sendall(struct.pack(">I", len(token)) + token)


def recv_msg(sock, cipher: Fernet) -> dict:
    (n,) = struct.unpack(">I", _recv_exact(sock, 4))
    if n > MAX_FRAME:
        raise ProtocolError("çerçeve çok büyük")
    data = _recv_exact(sock, n)
    try:
        return json.loads(cipher.decrypt(data).decode("utf-8"))
    except (InvalidToken, ValueError) as e:
        raise ProtocolError("kimlik doğrulama başarısız") from e


_TAILNET = ipaddress.ip_network("100.64.0.0/10")


def is_tailnet(host: str) -> bool:
    try:
        return ipaddress.ip_address(host) in _TAILNET
    except ValueError:
        return False


def open_conn(host: str, port: int, timeout: float = 4, proxy=None):
    """TCP bağlantısı açar. proxy=(ip, port) verilmişse ve hedef Tailscale IP'siyse
    Docker konteynerindeki Tailscale SOCKS5 sunucusu üzerinden bağlanır (Windows + Docker Desktop)."""
    if not (proxy and is_tailnet(host)):
        return socket.create_connection((host, port), timeout)
    s = socket.create_connection(tuple(proxy), timeout)
    try:
        s.settimeout(timeout)
        s.sendall(b"\x05\x01\x00")
        if _recv_exact(s, 2) != b"\x05\x00":
            raise ProtocolError("SOCKS5 sunucusu kabul etmedi")
        s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(host) + struct.pack(">H", port))
        ver, rep, _, atyp = _recv_exact(s, 4)
        if rep != 0:
            raise ProtocolError(f"SOCKS5 hata kodu {rep} (öğrenci Tailscale'de çevrimiçi mi?)")
        skip = {1: 4, 4: 16}.get(atyp)
        if skip is None:
            skip = _recv_exact(s, 1)[0]
        _recv_exact(s, skip + 2)
        return s
    except Exception:
        s.close()
        raise


def norm_app(name: str) -> str:
    n = name.strip().lower()
    return n[:-4] if n.endswith(".exe") else n


# ------------------------------------------------------- otomatik başlatma
def launch_cmd() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve().parent / "optimuslock.py")]


def set_autostart(enabled: bool) -> None:
    cmd = launch_cmd()
    if os.name == "nt":
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, " ".join(f'"{c}"' for c in cmd))
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
    else:
        d = Path.home() / ".config" / "autostart"
        f = d / "optimuslock.desktop"
        if enabled:
            d.mkdir(parents=True, exist_ok=True)
            f.write_text(
                "[Desktop Entry]\nType=Application\nName=Optimuslock\n"
                "Comment=BT sinifi izleme\n"
                f"Exec={' '.join(chr(34) + c + chr(34) for c in cmd)}\n"
                "X-GNOME-Autostart-enabled=true\n",
                "utf-8",
            )
        elif f.exists():
            f.unlink()
