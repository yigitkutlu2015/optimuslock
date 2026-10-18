"""Optimuslock ÖĞRETMEN tarafı (izleme paneli)."""
import base64
import io
import ipaddress
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QInputDialog, QLabel, QListView, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QVBoxLayout,
)

import cloudflare
import dockerctl
import tailscale
from common import ProtocolError, load_config, make_cipher, norm_app, open_conn, recv_msg, save_config, send_msg
from ui import SetupDialog, make_icon

THUMB = QSize(240, 140)
CHUNK = 384 * 1024
MAX_FILE = 100 * 1024 * 1024


class Hub(QObject):
    update = Signal(str, bytes, object)  # host, jpeg, bilgi
    status = Signal(str, str, str)       # host, durum, ad
    found = Signal(str, str)             # host, ad
    scan_done = Signal(int)
    cast_error = Signal(str)
    info = Signal(str)


class StudentLink(threading.Thread):
    """Bir öğrenci bilgisayarıyla kalıcı bağlantı. İstenen durumu (kilit/engel) bağlanınca yeniden gönderir."""

    def __init__(self, host, port, cipher, hub, proxy=None, resolver=None):
        super().__init__(daemon=True)
        self.host, self.port, self.cipher, self.hub, self.proxy = host, port, cipher, hub, proxy
        self.resolver = resolver  # Cloudflare: (127.0.0.1, yerel_port) döndürür
        self.alive = True
        self.wake = threading.Event()
        self.locked, self.lock_msg, self.blocked, self.web = False, "", [], []
        self.dirty, self.outbox = True, []
        self.files, self.power = [], []
        self.cast, self.frame, self.casting = False, None, False
        self.width, self.interval = 320, 3.0
        self.name = host

    def push(self):
        self.dirty = True
        self.wake.set()

    def say(self, text):
        self.outbox.append(text)
        self.wake.set()

    def stop(self):
        self.alive = False
        self.wake.set()

    def rpc(self, sock, obj):
        send_msg(sock, self.cipher, obj)
        return recv_msg(sock, self.cipher)

    def send_file(self, sock, path):
        name = os.path.basename(path)
        seq = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK)
                last = len(chunk) < CHUNK
                r = self.rpc(sock, {"t": "file", "name": name, "seq": seq, "last": last,
                                    "data": base64.b64encode(chunk).decode()})
                if r.get("t") != "ok" or last:
                    break
                seq += 1

    def run(self):
        while self.alive:
            sock = None
            try:
                h, p = self.resolver() if self.resolver else (self.host, self.port)
                sock = open_conn(h, p, 4, self.proxy)
                sock.settimeout(10)
                self.name = self.rpc(sock, {"t": "hello"}).get("name", self.host)
                self.dirty = True
                self.casting = False
                self.hub.status.emit(self.host, "online", self.name)
                while self.alive:
                    if self.dirty:
                        self.dirty = False
                        self.rpc(sock, {"t": "state", "locked": self.locked, "lock_msg": self.lock_msg,
                                        "blocked": self.blocked, "web": self.web})
                    while self.outbox:
                        self.rpc(sock, {"t": "msg", "text": self.outbox.pop(0)})
                    while self.files:
                        self.send_file(sock, self.files.pop(0))
                    while self.power:
                        self.rpc(sock, {"t": "power", "action": self.power.pop(0)})
                    if self.cast and self.frame:
                        self.rpc(sock, {"t": "cast", "img": self.frame})
                        self.casting = True
                    else:
                        if self.casting:
                            self.rpc(sock, {"t": "cast", "stop": True})
                            self.casting = False
                        r = self.rpc(sock, {"t": "snap", "w": self.width})
                        self.hub.update.emit(self.host, base64.b64decode(r.get("img", "")), r)
                    self.wake.wait(1.0 if self.cast else self.interval)
                    self.wake.clear()
            except (OSError, ProtocolError, ValueError, RuntimeError):
                if self.alive:
                    self.hub.status.emit(self.host, "offline", self.name)
            finally:
                if sock:
                    sock.close()
            if self.alive:
                self.wake.wait(3)
                self.wake.clear()


def probe(host, port, cipher, timeout=0.7, proxy=None):
    """Bu adreste doğru anahtarla çalışan bir Optimuslock öğrencisi var mı?"""
    try:
        s = open_conn(host, port, 4 if proxy else timeout, proxy)
        s.settimeout(4)
        try:
            send_msg(s, cipher, {"t": "hello"})
            r = recv_msg(s, cipher)
            return r.get("name") if r.get("t") == "hello" else None
        finally:
            s.close()
    except (OSError, ProtocolError, ValueError):
        return None


class Scanner(threading.Thread):
    def __init__(self, hosts, port, cipher, hub, proxy=None):
        super().__init__(daemon=True)
        self.hosts, self.port, self.cipher, self.hub, self.proxy = hosts, port, cipher, hub, proxy

    def run(self):
        n = 0
        with ThreadPoolExecutor(64) as ex:
            for host, name in zip(self.hosts, ex.map(lambda h: probe(h, self.port, self.cipher, proxy=self.proxy), self.hosts)):
                if name:
                    n += 1
                    self.hub.found.emit(host, name)
        self.hub.scan_done.emit(n)


def local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:3]) + ".0/24"
    except OSError:
        return "192.168.1.0/24"


class Viewer(QDialog):
    """Tek öğrencinin ekranını büyük ve daha sık güncellenen şekilde gösterir."""

    def __init__(self, link, hub, parent):
        super().__init__(parent)
        self.link, self.hub = link, hub
        self.setWindowTitle(f"{link.name} – canlı ekran")
        self.resize(1100, 700)
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Bağlanıyor...")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setMinimumSize(320, 200)
        lay.addWidget(self.lbl)
        link.width, link.interval = 1280, 1.0
        link.wake.set()
        hub.update.connect(self.on_update)

    def on_update(self, host, img, info):
        if host != self.link.host or not img:
            return
        pm = QPixmap()
        pm.loadFromData(img)
        self.lbl.setPixmap(pm.scaled(self.lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def done(self, r):
        self.hub.update.disconnect(self.on_update)
        self.link.width, self.link.interval = 320, 3.0
        super().done(r)


def placeholder(color="#3a3f4b"):
    pm = QPixmap(THUMB)
    pm.fill(QColor(color))
    return QIcon(pm)


class Teacher(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.port = int(cfg["port"])
        self.cipher = make_cipher(cfg["key"])
        self.hub = Hub()
        self.proxy = tailscale.socks_proxy() if cfg.get("mode") == "tailscale" else None
        self.links, self.items = {}, {}
        self.cast_links, self.cast_ev = [], None
        self.fwd = cloudflare.ForwardManager()

        self.setWindowTitle("Optimuslock – Öğretmen Paneli")
        self.setWindowIcon(make_icon())
        self.resize(1100, 700)

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setSpacing(10)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.setGridSize(QSize(THUMB.width() + 20, THUMB.height() + 50))
        self.list.itemDoubleClicked.connect(self.open_viewer)
        self.setCentralWidget(self.list)

        self.hub.update.connect(self.on_update)
        self.hub.status.connect(self.on_status)
        self.hub.cast_error.connect(self.on_cast_error)
        self.hub.info.connect(lambda m: self.statusBar().showMessage(m, 15000))
        self.hub.found.connect(lambda h, n: self.add_student(h, n))
        self.hub.scan_done.connect(lambda n: self.statusBar().showMessage(f"Tarama bitti: {n} öğrenci bulundu.", 8000))

        tb = self.addToolBar("Araçlar")
        tb.setMovable(False)

        def act(text, fn):
            a = QAction(text, self)
            a.triggered.connect(fn)
            tb.addAction(a)
            return a

        if cfg.get("mode") == "tailscale":
            act("Tailscale ile Tara", self.scan_tailscale)
            act("IP Ekle", self.add_manual)
        elif cfg.get("mode") == "cloudflare":
            act("Tünel Öğrencisi Ekle", self.add_manual)
        else:
            act("Ağı Tara (IP)", self.scan_ip)
            act("IP Ekle", self.add_manual)
        tb.addSeparator()
        act("Kilitle", self.lock)
        act("Kilidi Aç", self.unlock)
        tb.addSeparator()
        act("Uygulama Engelle", self.block)
        act("Engelleri Kaldır", self.unblock)
        act("Web Engelle", self.block_web)
        act("Web Engelini Kaldır", self.unblock_web)
        tb.addSeparator()
        act("Ekran Yayını Başlat", self.cast_start)
        act("Yayını Durdur", self.cast_stop)
        act("Dosya Gönder", self.send_file)
        act("Mesaj Gönder", self.send_message)
        tb.addSeparator()
        act("Listeden Çıkar", self.remove_selected)
        act("Ayarlar", self.settings)

        power = self.menuBar().addMenu("Güç")
        for text, action in (("Bilgisayarları kapat", "shutdown"), ("Yeniden başlat", "restart"),
                             ("Oturumu kapat", "logoff")):
            a = QAction(text, self)
            a.triggered.connect(lambda _=False, t=text, ac=action: self.power_cmd(ac, t))
            power.addAction(a)

        self.show_ts_status()
        for h in cfg.get("students", []):
            self.add_student(h, save=False)

    # ------------------------------------------------------------ liste
    def start_bootstrap(self):
        if dockerctl.needed(self.cfg):
            dockerctl.Bootstrap(self.cfg, lambda ok, msg: self.hub.info.emit(
                ("Docker hazır. " if ok else "Docker kurulumu başarısız: ") + msg)).start()
        if self.cfg.get("mode") == "cloudflare" and not cloudflare.available():
            self.statusBar().showMessage("Cloudflare modu için Docker veya cloudflared kurulu olmalı.")

    def show_ts_status(self):
        if self.cfg.get("mode") == "cloudflare":
            self.statusBar().showMessage("Bağlantı yöntemi: Cloudflare Tunnel (öğrencileri alan adlarıyla ekleyin)")
        elif self.cfg.get("mode") == "tailscale":
            ip = tailscale.my_ip()
            via = " – Docker SOCKS5 köprüsü" if self.proxy else ""
            self.statusBar().showMessage(f"Tailscale: bağlı ({ip}){via}" if ip else
                                         "Tailscale: bağlı DEĞİL – önce Tailscale'i açın (docker compose up -d)")
        else:
            self.statusBar().showMessage("Bağlantı yöntemi: IP adresi")

    def add_student(self, host, name=None, save=True):
        if host in self.links:
            return
        item = QListWidgetItem(placeholder(), f"{name or host}\n{host}")
        item.setData(Qt.UserRole, host)
        item.setTextAlignment(Qt.AlignHCenter)
        self.list.addItem(item)
        resolver = (lambda h=host: ("127.0.0.1", self.fwd.ensure(h))) if self.cfg.get("mode") == "cloudflare" else None
        link = StudentLink(host, self.port, self.cipher, self.hub, self.proxy, resolver)
        self.items[host], self.links[host] = item, link
        link.start()
        if save:
            self.save_students()

    def save_students(self):
        self.cfg["students"] = list(self.links)
        save_config(self.cfg)

    def targets(self):
        sel = [i.data(Qt.UserRole) for i in self.list.selectedItems()]
        return [self.links[h] for h in (sel or list(self.links))]

    def on_update(self, host, img, info):
        item = self.items.get(host)
        if not item:
            return
        if img:
            pm = QPixmap()
            pm.loadFromData(img)
            item.setIcon(QIcon(pm.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        tag = "  [KİLİTLİ]" if info.get("locked") else ""
        if self.links[host].web and not info.get("web_ok", True):
            tag += "  [WEB: yetki yok]"
        item.setText(f"{self.links[host].name}{tag}\n{host}")
        item.setToolTip("Açık uygulamalar:\n" + ", ".join(info.get("apps", [])[:40]))

    def on_status(self, host, state, name):
        item = self.items.get(host)
        if not item:
            return
        if state == "offline":
            item.setIcon(placeholder("#5a2a2a"))
            item.setText(f"{name}  (çevrimdışı)\n{host}")

    def open_viewer(self, item):
        Viewer(self.links[item.data(Qt.UserRole)], self.hub, self).exec()

    # ------------------------------------------------------------ keşif
    def scan_tailscale(self):
        peers = tailscale.peers()
        if not peers:
            QMessageBox.information(self, "Optimuslock", "Çevrimiçi Tailscale cihazı bulunamadı.\n"
                                    "Tailscale'in açık ve öğrencilerin aynı hesapta/ağda olduğundan emin olun.")
            return
        self.statusBar().showMessage(f"{len(peers)} Tailscale cihazı taranıyor...")
        Scanner([p["ip"] for p in peers], self.port, self.cipher, self.hub, self.proxy).start()

    def scan_ip(self):
        text, ok = QInputDialog.getText(self, "Ağı Tara", "Alt ağ (CIDR):", text=local_subnet())
        if not ok:
            return
        try:
            net = ipaddress.ip_network(text.strip(), strict=False)
        except ValueError:
            QMessageBox.warning(self, "Optimuslock", "Geçersiz alt ağ.")
            return
        if net.num_addresses > 1024:
            QMessageBox.warning(self, "Optimuslock", "En fazla /22 (1024 adres) taranabilir.")
            return
        self.statusBar().showMessage(f"{net} taranıyor...")
        Scanner([str(h) for h in net.hosts()], self.port, self.cipher, self.hub).start()

    def add_manual(self):
        if self.cfg.get("mode") == "cloudflare":
            text, ok = QInputDialog.getText(self, "Tünel Öğrencisi Ekle",
                                            "Öğrencinin Cloudflare tünel alan adı (ör. pc01.okul.com):")
        else:
            text, ok = QInputDialog.getText(self, "IP Ekle", "Öğrenci IP adresi (Tailscale IP'si de olur):")
        if ok and text.strip():
            self.add_student(text.strip())

    def remove_selected(self):
        for it in self.list.selectedItems():
            h = it.data(Qt.UserRole)
            self.links.pop(h).stop()
            self.items.pop(h)
            self.list.takeItem(self.list.row(it))
        self.save_students()

    # ------------------------------------------------------- komutlar
    def lock(self):
        text, ok = QInputDialog.getText(self, "Kilitle", "Öğrenci ekranında gösterilecek mesaj:",
                                        text="Lütfen öğretmeni dinleyin.")
        if ok:
            for l in self.targets():
                l.locked, l.lock_msg = True, text
                l.push()

    def unlock(self):
        for l in self.targets():
            l.locked = False
            l.push()

    def block(self):
        default = self.cfg.get("last_blocked", "chrome\nfirefox\nmsedge\nsteam\ndiscord")
        text, ok = QInputDialog.getMultiLineText(
            self, "Uygulama Engelle",
            "Engellenecek program adları (her satıra bir tane; Windows'ta .exe yazmak gerekmez):", default)
        if ok:
            names = sorted({norm_app(x) for x in text.splitlines() if x.strip()})
            self.cfg["last_blocked"] = "\n".join(names)
            save_config(self.cfg)
            for l in self.targets():
                l.blocked = names
                l.push()

    def unblock(self):
        for l in self.targets():
            l.blocked = []
            l.push()

    def block_web(self):
        default = self.cfg.get("last_web", "youtube.com\nfacebook.com\ninstagram.com\ntiktok.com")
        text, ok = QInputDialog.getMultiLineText(
            self, "Web Sitesi Engelle",
            "Engellenecek alan adları (her satıra bir tane).\n"
            "Not: öğrenci bilgisayarında Optimuslock'un yönetici/root yetkisi olması gerekir.", default)
        if ok:
            from webblock import clean
            doms = sorted({c for c in map(clean, text.splitlines()) if c})
            self.cfg["last_web"] = "\n".join(doms)
            save_config(self.cfg)
            for l in self.targets():
                l.web = doms
                l.push()

    def unblock_web(self):
        for l in self.targets():
            l.web = []
            l.push()

    def send_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Öğrencilere gönderilecek dosya")
        if not path:
            return
        if os.path.getsize(path) > MAX_FILE:
            QMessageBox.warning(self, "Optimuslock", "Dosya 100 MB'tan büyük olamaz.")
            return
        ls = self.targets()
        for l in ls:
            l.files.append(path)
            l.wake.set()
        self.statusBar().showMessage(f"{os.path.basename(path)} {len(ls)} bilgisayara gönderiliyor...", 8000)

    def power_cmd(self, action, label):
        ls = self.targets()
        if not ls:
            return
        if QMessageBox.question(self, "Onay", f"{len(ls)} bilgisayar için \"{label}\" uygulanacak. Emin misiniz?") \
                != QMessageBox.Yes:
            return
        for l in ls:
            l.power.append(action)
            l.wake.set()

    # ---- ekran yayını (öğretmen ekranı -> öğrenciler)
    def cast_start(self):
        if self.cast_ev:
            return
        self.cast_links = self.targets()
        for l in self.cast_links:
            l.cast, l.frame = True, None
        self.cast_ev = threading.Event()
        threading.Thread(target=self._cast_loop, args=(self.cast_ev, self.cast_links), daemon=True).start()
        self.statusBar().showMessage(f"Ekran yayını: {len(self.cast_links)} bilgisayar", 8000)

    def cast_stop(self):
        if self.cast_ev:
            self.cast_ev.set()
        for l in self.cast_links:
            l.cast, l.frame = False, None
            l.wake.set()
        self.cast_ev, self.cast_links = None, []

    def on_cast_error(self, msg):
        self.cast_stop()
        QMessageBox.warning(self, "Optimuslock", f"Ekran yakalanamadı, yayın durduruldu:\n{msg}")

    def _cast_loop(self, ev, links):
        import mss
        from PIL import Image
        Grab = getattr(mss, "MSS", None) or mss.mss
        while not ev.is_set():
            try:
                with Grab() as sct:
                    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    shot = sct.grab(mon)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                img.thumbnail((1280, 1280))
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=55)
                frame = base64.b64encode(buf.getvalue()).decode()
                for l in links:
                    l.frame = frame
                    l.wake.set()
            except Exception as e:
                self.hub.cast_error.emit(str(e)[:150])
                return
            ev.wait(1.0)

    def send_message(self):
        text, ok = QInputDialog.getText(self, "Mesaj Gönder", "Mesaj:")
        if ok and text.strip():
            for l in self.targets():
                l.say(text.strip())

    def settings(self):
        dlg = SetupDialog(self.cfg)
        if dlg.exec() and dlg.result_cfg:
            save_config(dlg.result_cfg)
            QMessageBox.information(self, "Optimuslock", "Ayarlar kaydedildi. Değişiklik için programı yeniden başlatın.")

    def closeEvent(self, e):
        self.cast_stop()
        for l in self.links.values():
            l.stop()
        self.fwd.stop_all()
        e.accept()
        QApplication.quit()


def run_teacher(app, cfg):
    w = Teacher(cfg)
    w.show()
    w.start_bootstrap()
    return w
