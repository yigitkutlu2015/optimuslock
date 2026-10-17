"""Optimuslock ÖĞRENCİ tarafı (sistem tepsisinde çalışan ajan)."""
import base64
import io
import platform
import socket
import threading
import time

import mss
import psutil
from PIL import Image
from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

import tailscale
from common import VERSION, ProtocolError, norm_app, recv_msg, send_msg
from ui import make_icon

WATCHDOG_SECONDS = 90  # öğretmen bu kadar süre sessiz kalırsa kilit/engeller kalkar


class LockWindow(QWidget):
    """Bir monitörü tamamen kaplayan, her zaman üstte kilit penceresi."""

    def __init__(self, screen, text):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._allow_close = False
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.setStyleSheet("background:#0b1220;")
        lay = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color:white; font-size:34px;")
        lay.addWidget(self.label)
        self.set_text(text)

    def set_text(self, text):
        self.label.setText(
            f"<div style='font-size:64px'>&#128274;</div><b>Ekran öğretmen tarafından kilitlendi</b>"
            f"<br><br><span style='font-size:24px;color:#9fb3d1'>{text}</span>"
        )

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
        try:
            while True:
                req = recv_msg(conn, self.cipher)  # anahtar yanlışsa burada düşer
                self.owner.last_seen = time.time()
                if not announced:
                    announced = True
                    self.owner.connected.emit(addr[0])
                send_msg(conn, self.cipher, self.dispatch(req))
        except (ProtocolError, OSError, ValueError):
            pass
        finally:
            conn.close()

    def dispatch(self, req):
        t = req.get("t")
        o = self.owner
        if t == "hello":
            return {"t": "hello", "name": socket.gethostname(), "os": platform.system(), "v": VERSION}
        if t == "state":
            blocked = [norm_app(str(x)) for x in req.get("blocked", []) if str(x).strip()]
            o.state_changed.emit(bool(req.get("locked")), str(req.get("lock_msg", ""))[:300], blocked)
            return {"t": "ok"}
        if t == "snap":
            return self.snapshot(int(req.get("w", 320)))
        if t == "msg":
            o.message.emit(str(req.get("text", ""))[:500])
            return {"t": "ok"}
        return {"t": "err"}

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
        resp = {"t": "snap", "img": "", "locked": self.owner.locked, "apps": self.apps()}
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


class Agent(QObject):
    state_changed = Signal(bool, str, list)
    message = Signal(str)
    connected = Signal(str)

    def __init__(self, cfg, cipher, bind_host):
        super().__init__()
        self.cfg = cfg
        self.locked = False
        self.blocked = set()
        self.last_seen = time.time()
        self.locks = []
        self._popups = []
        self._last_notice = 0.0

        self.server = Server(bind_host, int(cfg["port"]), cipher, self)
        self.state_changed.connect(self.apply_state)
        self.message.connect(self.on_message)
        self.connected.connect(self.on_connected)

        self.tray = QSystemTrayIcon(make_icon())
        self.tray.setToolTip("Optimuslock – Öğrenci modu etkin (öğretmen bu bilgisayarı izleyebilir)")
        menu = QMenu()
        menu.addAction("Optimuslock – Öğrenci modu").setEnabled(False)
        menu.addAction(f"Dinleniyor: {bind_host}:{cfg['port']}").setEnabled(False)
        menu.addSeparator()
        menu.addAction("Çıkış (anahtar gerekir)").triggered.connect(self.request_quit)
        self.tray.setContextMenu(menu)
        self.tray.show()
        self._menu = menu

        self.enforce_timer = QTimer(self)
        self.enforce_timer.timeout.connect(self.enforce)
        self.enforce_timer.start(1500)
        self.raise_timer = QTimer(self)
        self.raise_timer.timeout.connect(self.keep_on_top)
        self.watchdog = QTimer(self)
        self.watchdog.timeout.connect(self.check_watchdog)
        self.watchdog.start(5000)

        self.server.start()

    # ------------------------------------------------------------ durum
    def apply_state(self, locked, text, blocked):
        self.blocked = set(blocked)
        if locked:
            self.show_lock(text)
        else:
            self.hide_lock()

    def show_lock(self, text):
        if not self.locks:
            for s in QApplication.screens():
                w = LockWindow(s, text)
                w.showFullScreen()
                self.locks.append(w)
            self.raise_timer.start(600)
            if self.locks:
                self.locks[0].grabKeyboard()
        else:
            for w in self.locks:
                w.set_text(text)
        self.locked = True

    def hide_lock(self):
        self.raise_timer.stop()
        for w in self.locks:
            w.releaseKeyboard()
            w._allow_close = True
            w.close()
        self.locks = []
        self.locked = False

    def keep_on_top(self):
        for w in self.locks:
            w.raise_()
            w.activateWindow()

    def check_watchdog(self):
        if (self.locked or self.blocked) and time.time() - self.last_seen > WATCHDOG_SECONDS:
            self.apply_state(False, "", [])

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
            self.hide_lock()
            self.tray.hide()
            QApplication.quit()


def run_agent(app, cfg, cipher):
    """Ajanı başlatır; referansı döndürür (çöpe gitmesin diye)."""
    host = "0.0.0.0"
    if cfg.get("mode") == "tailscale":
        if tailscale.socks_proxy():
            # Windows + Docker Desktop: konteyner (userspace) gelen Tailscale bağlantısını bu ajana yönlendirir
            if not tailscale.expose_port(int(cfg["port"])):
                QMessageBox.warning(
                    None, "Optimuslock",
                    "Tailscale konteyneri yapılandırılamadı (oturum açık mı? TS_AUTHKEY doğru mu?).\n"
                    "docker compose -f docker-compose.windows.yml logs  komutuyla bakın.",
                )
        else:
            ip = tailscale.my_ip()
            if ip:
                host = ip  # sadece Tailscale arayüzünde dinle
            else:
                QMessageBox.warning(
                    None, "Optimuslock",
                    "Tailscale bağlı değil. Tailscale açılana kadar tüm ağ arayüzlerinde dinlenecek.\n"
                    "(Bağlantılar yine sınıf anahtarıyla korunur.)",
                )
    try:
        return Agent(cfg, cipher, host)
    except OSError as e:
        QMessageBox.critical(None, "Optimuslock", f"Port {cfg['port']} dinlenemedi:\n{e}")
        return None
