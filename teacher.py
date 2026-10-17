"""Optimuslock ÖĞRETMEN tarafı (izleme paneli)."""
import base64
import ipaddress
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QInputDialog, QLabel, QListView, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QVBoxLayout,
)

import tailscale
from common import ProtocolError, load_config, make_cipher, norm_app, open_conn, recv_msg, save_config, send_msg
from ui import SetupDialog, make_icon

THUMB = QSize(240, 140)


class Hub(QObject):
    update = Signal(str, bytes, object)  # host, jpeg, bilgi
    status = Signal(str, str, str)       # host, durum, ad
    found = Signal(str, str)             # host, ad
    scan_done = Signal(int)


class StudentLink(threading.Thread):
    """Bir öğrenci bilgisayarıyla kalıcı bağlantı. İstenen durumu (kilit/engel) bağlanınca yeniden gönderir."""

    def __init__(self, host, port, cipher, hub, proxy=None):
        super().__init__(daemon=True)
        self.host, self.port, self.cipher, self.hub, self.proxy = host, port, cipher, hub, proxy
        self.alive = True
        self.wake = threading.Event()
        self.locked, self.lock_msg, self.blocked = False, "", []
        self.dirty, self.outbox = True, []
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

    def run(self):
        while self.alive:
            sock = None
            try:
                sock = open_conn(self.host, self.port, 4, self.proxy)
                sock.settimeout(10)
                self.name = self.rpc(sock, {"t": "hello"}).get("name", self.host)
                self.dirty = True
                self.hub.status.emit(self.host, "online", self.name)
                while self.alive:
                    if self.dirty:
                        self.dirty = False
                        self.rpc(sock, {"t": "state", "locked": self.locked,
                                        "lock_msg": self.lock_msg, "blocked": self.blocked})
                    while self.outbox:
                        self.rpc(sock, {"t": "msg", "text": self.outbox.pop(0)})
                    r = self.rpc(sock, {"t": "snap", "w": self.width})
                    self.hub.update.emit(self.host, base64.b64decode(r.get("img", "")), r)
                    self.wake.wait(self.interval)
                    self.wake.clear()
            except (OSError, ProtocolError, ValueError):
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
        else:
            act("Ağı Tara (IP)", self.scan_ip)
        act("IP Ekle", self.add_manual)
        tb.addSeparator()
        act("Kilitle", self.lock)
        act("Kilidi Aç", self.unlock)
        tb.addSeparator()
        act("Uygulama Engelle", self.block)
        act("Engelleri Kaldır", self.unblock)
        act("Mesaj Gönder", self.send_message)
        tb.addSeparator()
        act("Listeden Çıkar", self.remove_selected)
        act("Ayarlar", self.settings)

        self.show_ts_status()
        for h in cfg.get("students", []):
            self.add_student(h, save=False)

    # ------------------------------------------------------------ liste
    def show_ts_status(self):
        if self.cfg.get("mode") == "tailscale":
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
        link = StudentLink(host, self.port, self.cipher, self.hub, self.proxy)
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
        for l in self.links.values():
            l.stop()
        e.accept()
        QApplication.quit()


def run_teacher(app, cfg):
    w = Teacher(cfg)
    w.show()
    return w
