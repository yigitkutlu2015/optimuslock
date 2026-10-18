"""Optimuslock ÖĞRENCİ tarafı (sistem tepsisinde çalışan ajan)."""
import base64
import io
import os
import platform
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import mss
import psutil
from PIL import Image
from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

import dockerctl
import tailscale
import webblock
from common import PUBLISHER, VERSION, ProtocolError, norm_app, recv_msg, send_msg
from ui import make_icon

WATCHDOG_SECONDS = 90          # öğretmen bu kadar süre sessiz kalırsa kilit/engel/yayın kalkar
INBOX = Path.home() / "Optimuslock-Gelen"
MAX_FILE = 100 * 1024 * 1024
POWER_ACTIONS = {"shutdown", "restart", "logoff"}


def safe_name(name: str) -> str:
    n = os.path.basename(str(name).replace("\\", "/"))
    n = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", n)[:120].strip(". ")
    return n or "dosya"


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(1, 1000):
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
    return p


class LockWindow(QWidget):
    """Bir monitörü tamamen kaplayan, her zaman üstte pencere (kilit veya ekran yayını)."""

    def __init__(self, screen, text=""):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._allow_close = False
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.setStyleSheet("background:#0b1220;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color:white; font-size:34px;")
        lay.addWidget(self.label)
        if text:
            self.set_text(text)

    def set_text(self, text):
        self.label.setText(
            f"<div style='font-size:64px'>&#128274;</div><b>Ekran öğretmen tarafından kilitlendi</b>"
            f"<br><br><span style='font-size:24px;color:#9fb3d1'>{text}</span>"
        )

    def set_frame(self, pm: QPixmap):
        self.label.setPixmap(pm.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def keyPressEvent(self, e):
        e.accept()  # tüm tuşları yut

    def closeEvent(self, e):
        e.accept() if self._allow_close else e.ignore()


class Server(threading.Thread):
    def __init__(self, host, port, cipher, owner):
        super().__init__(daemon=True)
        self.host, self.port, self.cipher, self.owner = host, port, cipher, owner
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))  # hata verirse çağıran yakalar
        self.sock.listen(16)
        self._apps, self._apps_t = [], 0.0

    def run(self):
        while True:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()

    def handle(self, conn, addr):
        conn.settimeout(30)
        announced = False
        ctx = {}
        try:
            while True:
                req = recv_msg(conn, self.cipher)  # anahtar yanlışsa burada düşer
                self.owner.last_seen = time.time()
                if not announced:
                    announced = True
                    self.owner.connected.emit(addr[0])
                send_msg(conn, self.cipher, self.dispatch(req, ctx))
        except (ProtocolError, OSError, ValueError):
            pass
        finally:
            fh = ctx.get("fh")
            if fh:
                fh.close()
            conn.close()

    def dispatch(self, req, ctx):
        t = req.get("t")
        o = self.owner
        if t == "hello":
            return {"t": "hello", "name": socket.gethostname(), "os": platform.system(), "v": VERSION}
        if t == "state":
            blocked = [norm_app(str(x)) for x in req.get("blocked", []) if str(x).strip()]
            web = [str(x)[:253] for x in req.get("web", [])][:300]
            o.state_changed.emit(bool(req.get("locked")), str(req.get("lock_msg", ""))[:300], blocked, web)
            return {"t": "ok"}
        if t == "snap":
            return self.snapshot(int(req.get("w", 320)))
        if t == "msg":
            o.message.emit(str(req.get("text", ""))[:500])
            return {"t": "ok"}
        if t == "cast":
            o.cast_frame.emit(b"" if req.get("stop") else base64.b64decode(req.get("img", "")))
            return {"t": "ok"}
        if t == "file":
            return self.recv_file(req, ctx)
        if t == "power":
            if req.get("action") in POWER_ACTIONS:
                o.power_requested.emit(req["action"])
                return {"t": "ok"}
        return {"t": "err"}

    def recv_file(self, req, ctx):
        try:
            if int(req.get("seq", 0)) == 0:
                if ctx.get("fh"):
                    ctx["fh"].close()
                INBOX.mkdir(parents=True, exist_ok=True)
                path = unique_path(INBOX / safe_name(req.get("name", "")))
                ctx.update(fh=open(path, "wb"), path=path, size=0)
            fh = ctx.get("fh")
            if not fh:
                return {"t": "err"}
            data = base64.b64decode(req.get("data", ""))
            ctx["size"] += len(data)
            if ctx["size"] > MAX_FILE:
                fh.close()
                ctx["fh"] = None
                os.unlink(ctx["path"])
                return {"t": "err", "msg": "dosya çok büyük"}
            fh.write(data)
            if req.get("last"):
                fh.close()
                ctx["fh"] = None
                self.owner.file_received.emit(str(ctx["path"]))
            return {"t": "ok"}
        except (OSError, ValueError) as e:
            return {"t": "err", "msg": str(e)[:100]}

    def apps(self):
        if time.time() - self._apps_t > 10:
            try:
                me = psutil.Process().username()
                names = {
                    norm_app(p.info["name"] or "")
                    for p in psutil.process_iter(["name", "username"])
                    if p.info.get("username") == me
                }
                self._apps = sorted(n for n in names if n)[:80]
            except Exception:
                pass
            self._apps_t = time.time()
        return self._apps

    def snapshot(self, width):
        width = max(160, min(width, 1920))
        o = self.owner
        resp = {"t": "snap", "img": "", "locked": o.locked, "apps": self.apps(),
                "web_ok": o.web_ok, "web_n": len(o.web_cur)}
        try:
            with (getattr(mss, "MSS", None) or mss.mss)() as sct:
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                shot = sct.grab(mon)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            img.thumbnail((width, width))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=60)
            resp["img"] = base64.b64encode(buf.getvalue()).decode()
        except Exception as e:  # ekran yakalanamadı (ör. Wayland)
            resp["err"] = str(e)[:120]
        return resp


class StatusWindow(QWidget):
    """Sistem tepsisi olmayan masaüstleri için küçük, görünür durum penceresi."""

    def __init__(self, host, cfg):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Optimuslock – Öğrenci modu")
        self.setWindowIcon(make_icon())
        lay = QVBoxLayout(self)
        lb = QLabel(f"<b>Optimuslock</b> çalışıyor (öğrenci modu)<br>Öğretmen bu bilgisayarı izleyebilir.<br>"
                    f"<span style='color:#666'>{host}:{cfg['port']} · {PUBLISHER}</span>")
        lay.addWidget(lb)
        self.resize(360, 90)

    allow_close = False

    def closeEvent(self, e):
        if self.allow_close:
            e.accept()
        else:
            e.ignore()
            self.showMinimized()


class Agent(QObject):
    state_changed = Signal(bool, str, list, list)
    message = Signal(str)
    connected = Signal(str)
    cast_frame = Signal(bytes)
    file_received = Signal(str)
    power_requested = Signal(str)
    info = Signal(str)

    def __init__(self, cfg, cipher, bind_host):
        super().__init__()
        self.cfg = cfg
        self.blocked = set()
        self.web_cur, self.web_ok = [], True
        self.last_seen = time.time()
        self.locks, self.casts = [], []
        self._popups = []
        self._last_notice = 0.0

        self.server = Server(bind_host, int(cfg["port"]), cipher, self)
        self.state_changed.connect(self.apply_state)
        self.message.connect(self.on_message)
        self.connected.connect(self.on_connected)
        self.cast_frame.connect(self.on_cast)
        self.file_received.connect(self.on_file)
        self.power_requested.connect(self.on_power)
        self.info.connect(lambda m: self.tray.showMessage("Optimuslock", m, QSystemTrayIcon.Information, 8000))

        self.tray = QSystemTrayIcon(make_icon())
        self.tray.setToolTip("Optimuslock – Öğrenci modu etkin (öğretmen bu bilgisayarı izleyebilir)")
        menu = QMenu()
        menu.addAction("Optimuslock – Öğrenci modu").setEnabled(False)
        menu.addAction(f"Dinleniyor: {bind_host}:{cfg['port']}").setEnabled(False)
        menu.addAction("Gelen dosyalar klasörünü aç").triggered.connect(self.open_inbox)
        menu.addSeparator()
        menu.addAction("Çıkış (anahtar gerekir)").triggered.connect(self.request_quit)
        self.tray.setContextMenu(menu)
        self.tray.show()
        self._menu = menu
        # Bazı masaüstlerinde (ör. Pardus GNOME) sistem tepsisi yoktur: öğrenci görünür bir durum penceresi görsün
        self.status_win = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.status_win = StatusWindow(bind_host, cfg)
            self.status_win.show()

        self.enforce_timer = QTimer(self)
        self.enforce_timer.timeout.connect(self.enforce)
        self.enforce_timer.start(1500)
        self.raise_timer = QTimer(self)
        self.raise_timer.timeout.connect(self.keep_on_top)
        self.watchdog = QTimer(self)
        self.watchdog.timeout.connect(self.check_watchdog)
        self.watchdog.start(5000)

        webblock.apply([])  # önceki oturumdan kalmış engel varsa temizle (yetki varsa)
        self.server.start()

    def start_bootstrap(self):
        """Gerekirse Docker konteynerlerini (Tailscale / Cloudflare Tunnel) arka planda başlatır."""
        if not dockerctl.needed(self.cfg):
            return

        def done(ok, msg):
            self.info.emit(("Docker hazır. " if ok else "Docker kurulumu başarısız: ") + msg)

        dockerctl.Bootstrap(self.cfg, done).start()

    @property
    def locked(self):
        return bool(self.locks)

    # ------------------------------------------------------------ durum
    def apply_state(self, locked, text, blocked, web):
        self.blocked = set(blocked)
        if web != self.web_cur:
            self.web_cur = web
            self.web_ok, _ = webblock.apply(web)
        if locked:
            self.show_lock(text)
        else:
            self.hide_lock()

    def _open(self, lst, text=""):
        if lst:
            return
        for s in QApplication.screens():
            w = LockWindow(s, text)
            w.showFullScreen()
            lst.append(w)
        self.raise_timer.start(600)
        if lst:
            lst[0].grabKeyboard()

    def _close(self, lst):
        for w in lst:
            w.releaseKeyboard()
            w._allow_close = True
            w.close()
        lst.clear()
        if not self.locks and not self.casts:
            self.raise_timer.stop()

    def show_lock(self, text):
        if self.locks:
            for w in self.locks:
                w.set_text(text)
        else:
            self._open(self.locks, text)

    def hide_lock(self):
        self._close(self.locks)

    def keep_on_top(self):
        for w in self.locks + self.casts:
            w.raise_()
            w.activateWindow()

    def check_watchdog(self):
        if (self.locks or self.casts or self.blocked or self.web_cur) and time.time() - self.last_seen > WATCHDOG_SECONDS:
            self._close(self.casts)
            self.apply_state(False, "", [], [])

    # --------------------------------------------------- ekran yayını
    def on_cast(self, data):
        if not data:
            self._close(self.casts)
            return
        pm = QPixmap()
        if not pm.loadFromData(data):
            return
        self._open(self.casts)
        for w in self.casts:
            w.set_frame(pm)

    # --------------------------------------------------- uygulama engelleme
    def enforce(self):
        if not self.blocked:
            return
        me = psutil.Process().pid
        killed = set()
        for p in psutil.process_iter(["name"]):
            try:
                n = norm_app(p.info["name"] or "")
                if n in self.blocked and p.pid != me:
                    p.kill()
                    killed.add(n)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed and time.time() - self._last_notice > 10:
            self._last_notice = time.time()
            self.tray.showMessage("Optimuslock", "Öğretmen şu uygulamaları engelledi: " + ", ".join(sorted(killed)),
                                  QSystemTrayIcon.Warning, 4000)

    # -------------------------------------------------------- dosya / güç
    def on_file(self, path):
        self.tray.showMessage("Optimuslock", f"Öğretmenden dosya geldi:\n{path}", QSystemTrayIcon.Information, 6000)

    def open_inbox(self):
        INBOX.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(INBOX))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(INBOX)])
        except Exception:
            pass

    def on_power(self, action):
        label = {"shutdown": "kapatılıyor", "restart": "yeniden başlatılıyor", "logoff": "oturum kapatılıyor"}[action]
        self.tray.showMessage("Optimuslock", f"Öğretmen isteğiyle bilgisayar {label} (birkaç saniye içinde).",
                              QSystemTrayIcon.Warning, 5000)
        QTimer.singleShot(4000, lambda: self.run_power(action))

    @staticmethod
    def run_power(action):
        if os.name == "nt":
            cmd = {"shutdown": ["shutdown", "/s", "/t", "0"], "restart": ["shutdown", "/r", "/t", "0"],
                   "logoff": ["shutdown", "/l"]}[action]
            kw = {"creationflags": 0x08000000}
        else:
            cmd = {"shutdown": ["systemctl", "poweroff"], "restart": ["systemctl", "reboot"],
                   "logoff": ["loginctl", "terminate-user", os.environ.get("USER", "")]}[action]
            kw = {}
        try:
            subprocess.Popen(cmd, **kw)
        except Exception:
            pass

    # -------------------------------------------------------- bildirimler
    def on_connected(self, ip):
        self.tray.showMessage("Optimuslock", f"Öğretmen bilgisayarı bağlandı ({ip}).", QSystemTrayIcon.Information, 4000)

    def on_message(self, text):
        box = QMessageBox(QMessageBox.Information, "Öğretmenden mesaj", text)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        box.setWindowModality(Qt.NonModal)
        box.show()
        self._popups = [b for b in self._popups if b.isVisible()] + [box]

    def request_quit(self):
        pw, ok = QInputDialog.getText(None, "Optimuslock", "Çıkmak için sınıf anahtarını girin:", QLineEdit.Password)
        if ok and pw == self.cfg["key"]:
            self._close(self.casts)
            self.hide_lock()
            webblock.apply([])
            self.tray.hide()
            if self.status_win:
                self.status_win.allow_close = True
            QApplication.quit()


def run_agent(app, cfg, cipher):
    """Ajanı başlatır; referansı döndürür (çöpe gitmesin diye)."""
    mode = cfg.get("mode")
    host = "0.0.0.0"
    if mode == "tailscale" and not dockerctl.userspace(cfg):
        ip = tailscale.my_ip()
        if ip:
            host = ip  # Tailscale hazırsa yalnızca o arayüzde dinle
    elif mode == "cloudflare" and sys.platform.startswith("linux"):
        host = "127.0.0.1"  # cloudflared (host ağı) yerel porta bağlanır
    try:
        agent = Agent(cfg, cipher, host)
    except OSError as e:
        QMessageBox.critical(None, "Optimuslock", f"Port {cfg['port']} dinlenemedi:\n{e}")
        return None
    agent.start_bootstrap()
    return agent
