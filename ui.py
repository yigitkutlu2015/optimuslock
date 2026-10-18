"""Ortak arayüz parçaları: simge ve tek kurulum sihirbazı."""
import socket

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QMessageBox, QRadioButton, QSpinBox,
    QVBoxLayout, QWidget, QWizard, QWizardPage,
)

from common import DEFAULT_PORT, PUBLISHER


def make_icon(color: str = "#1e66f5") -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)
    p.setPen(QColor("white"))
    f = QFont()
    f.setPixelSize(40)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "O")
    p.end()
    return QIcon(pm)


def _note(text):
    lb = QLabel(text)
    lb.setWordWrap(True)
    lb.setStyleSheet("color:#555;")
    return lb


class RolePage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.setTitle("Bu bilgisayar kimin?")
        self.setSubTitle(f"Optimuslock – {PUBLISHER}. Bu bilgisayarda hangi rolde çalışacak?")
        lay = QVBoxLayout(self)
        self.student = QRadioButton("Öğrenci bilgisayarı\n(öğretmen ekranı izleyebilir, kilitleyebilir, uygulama/web engelleyebilir)")
        self.teacher = QRadioButton("Öğretmen bilgisayarı\n(izleme ve yönetim paneli)")
        lay.addWidget(self.student)
        lay.addWidget(self.teacher)
        (self.teacher if w.cfg.get("role") == "teacher" else self.student).setChecked(True)


class ModePage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.setTitle("Bağlantı yöntemi")
        self.setSubTitle("Öğretmen ve öğrenciler birbirine nasıl bağlanacak?")
        lay = QVBoxLayout(self)
        self.ts = QRadioButton("Tailscale – farklı ağlardan/uzaktan, şifreli özel ağ")
        self.ip = QRadioButton("IP adresi – aynı yerel ağ (en basit)")
        self.cf = QRadioButton("Cloudflare Tunnel – port açmadan, alan adı üzerinden")
        for r in (self.ts, self.ip, self.cf):
            lay.addWidget(r)
        {"ip": self.ip, "cloudflare": self.cf}.get(w.cfg.get("mode"), self.ts).setChecked(True)

    def mode(self):
        return "ip" if self.ip.isChecked() else "cloudflare" if self.cf.isChecked() else "tailscale"


class DetailPage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        c = w.cfg
        lay = QVBoxLayout(self)

        self.g_ts = QGroupBox("Tailscale")
        v = QVBoxLayout(self.g_ts)
        self.ts_docker = QRadioButton("Docker ile (önerilen – uygulama konteyneri kendisi kurar)")
        self.ts_native = QRadioButton("Bilgisayarda kurulu Tailscale uygulamasını kullan")
        v.addWidget(self.ts_docker)
        v.addWidget(self.ts_native)
        (self.ts_native if c.get("ts_via") == "native" else self.ts_docker).setChecked(True)
        f = QFormLayout()
        self.ts_auth = QLineEdit(c.get("ts_authkey", ""))
        self.ts_auth.setEchoMode(QLineEdit.Password)
        self.ts_auth.setPlaceholderText("tskey-auth-...")
        self.ts_host = QLineEdit(c.get("ts_hostname") or socket.gethostname())
        f.addRow("Tailscale Auth Key:", self.ts_auth)
        f.addRow("Cihaz adı:", self.ts_host)
        v.addLayout(f)
        v.addWidget(_note("Auth key: https://login.tailscale.com/admin/settings/keys (\"reusable\" anahtar önerilir)."))
        lay.addWidget(self.g_ts)

        self.g_cf = QGroupBox("Cloudflare Tunnel")
        v = QVBoxLayout(self.g_cf)
        self.cf_note = _note("")
        v.addWidget(self.cf_note)
        f = QFormLayout()
        self.cf_token = QLineEdit(c.get("cf_token", ""))
        self.cf_token.setEchoMode(QLineEdit.Password)
        self.cf_token.setPlaceholderText("eyJhIjoi...")
        self.cf_host = QLineEdit(c.get("cf_hostname", ""))
        self.cf_host.setPlaceholderText("pc01.okul.com")
        self.row_token = ("Tünel token:", self.cf_token)
        self.row_host = ("Genel alan adı:", self.cf_host)
        f.addRow(*self.row_token)
        f.addRow(*self.row_host)
        self.cf_form = f
        v.addLayout(f)
        lay.addWidget(self.g_cf)

        self.g_ip = QGroupBox("IP adresi")
        v = QVBoxLayout(self.g_ip)
        v.addWidget(_note("Ek ayar gerekmez. Öğretmen panelinden \"Ağı Tara (IP)\" ile öğrenciler bulunur. "
                          "Güvenlik duvarında seçtiğiniz port (varsayılan 5710) öğrencilerde açık olmalıdır."))
        lay.addWidget(self.g_ip)

    def initializePage(self):
        mode, role = self.w.mode_page.mode(), "teacher" if self.w.role_page.teacher.isChecked() else "student"
        self.setTitle({"tailscale": "Tailscale ayarları", "cloudflare": "Cloudflare Tunnel ayarları",
                       "ip": "IP ile bağlantı"}[mode])
        self.setSubTitle("Bilgileri girin; Docker gerekiyorsa uygulama ilk açılışta konteyneri kendisi başlatır.")
        self.g_ts.setVisible(mode == "tailscale")
        self.g_cf.setVisible(mode == "cloudflare")
        self.g_ip.setVisible(mode == "ip")
        student = role == "student"
        for lbl_widget in (self.cf_token, self.cf_host):
            lbl_widget.setVisible(student)
            lab = self.cf_form.labelForField(lbl_widget)
            if lab:
                lab.setVisible(student)
        if student:
            self.cf_note.setText(
                "Cloudflare Zero Trust → Networks → Tunnels'ta bir tünel oluşturun, token'ı buraya yapıştırın. "
                "Tünele bir \"Public hostname\" ekleyin: Service = TCP, URL = localhost:5710 "
                "(Windows + Docker Desktop kullanıyorsanız host.docker.internal:5710).")
        else:
            self.cf_note.setText(
                "Öğrencileri panelden tünel alan adlarıyla (ör. pc01.okul.com) ekleyeceksiniz. "
                "Bu bilgisayarda Docker veya cloudflared kurulu olmalıdır.")

    def validatePage(self):
        mode = self.w.mode_page.mode()
        student = self.w.role_page.student.isChecked()
        if mode == "tailscale" and self.ts_docker.isChecked() and not self.ts_auth.text().strip():
            r = QMessageBox.question(self, "Optimuslock",
                                     "Tailscale Auth Key boş. Konteyner oturum açmanızı bekler (docker logs ile bağlantıyı görürsünüz).\nYine de devam edilsin mi?")
            return r == QMessageBox.Yes
        if mode == "cloudflare" and student and not self.cf_token.text().strip():
            QMessageBox.warning(self, "Optimuslock", "Cloudflare tünel token'ı gerekli.")
            return False
        return True


class SecurityPage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.setTitle("Güvenlik")
        self.setSubTitle("Tüm trafik bu anahtarla şifrelenir. Öğretmen ve öğrencilerde AYNI olmalıdır.")
        lay = QVBoxLayout(self)
        f = QFormLayout()
        self.key = QLineEdit(w.cfg.get("key", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("en az 6 karakter")
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(int(w.cfg.get("port", DEFAULT_PORT)))
        f.addRow("Sınıf anahtarı:", self.key)
        f.addRow("Port:", self.port)
        lay.addLayout(f)
        self.auto = QCheckBox("Bilgisayar açılınca otomatik başlat")
        self.auto.setChecked(bool(w.cfg.get("autostart", True)))
        lay.addWidget(self.auto)

    def initializePage(self):
        self.auto.setVisible(self.w.role_page.student.isChecked())

    def validatePage(self):
        if len(self.key.text()) < 6:
            QMessageBox.warning(self, "Optimuslock", "Sınıf anahtarı en az 6 karakter olmalı.")
            return False
        return True


class SummaryPage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.setTitle("Hazır")
        self.setSubTitle("Aşağıdaki ayarlarla kurulum tamamlanacak.")
        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)
        lay.addWidget(_note(f"© {PUBLISHER}"))

    def initializePage(self):
        c = self.w.build_cfg()
        mode = {"tailscale": "Tailscale", "ip": "IP adresi", "cloudflare": "Cloudflare Tunnel"}[c["mode"]]
        rows = [("Rol", "Öğrenci" if c["role"] == "student" else "Öğretmen"), ("Bağlantı", mode), ("Port", c["port"])]
        if c["mode"] == "tailscale":
            rows.append(("Tailscale", "Docker" if c["ts_via"] == "docker" else "Yerel uygulama"))
        if c["mode"] == "cloudflare" and c["role"] == "student":
            rows.append(("Tünel alan adı", c.get("cf_hostname") or "(girilmedi)"))
        rows += self.w.extra_summary()
        self.lbl.setText("<br>".join(f"<b>{k}:</b> {v}" for k, v in rows))


class SetupWizard(QWizard):
    """Tek kurulum sihirbazı: rol → bağlantı yöntemi → ayrıntılar → güvenlik → özet."""

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = dict(cfg)
        self.result_cfg = None
        self.setWindowTitle(f"Optimuslock Kurulum Sihirbazı – {PUBLISHER}")
        self.setWindowIcon(make_icon())
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(640, 480)
        self.setButtonText(QWizard.NextButton, "İleri >")
        self.setButtonText(QWizard.BackButton, "< Geri")
        self.setButtonText(QWizard.CancelButton, "İptal")
        self.setButtonText(QWizard.FinishButton, "Kur ve Başlat")
        # Role özel paketlerde (öğretmen/öğrenci .deb) rol sabittir; sihirbaz rol sorusunu atlar
        locked = cfg.get("role") if str(cfg.get("role_locked")).lower() in ("1", "true") else None
        self.locked_role = locked if locked in ("student", "teacher") else None
        self.role_page, self.mode_page = RolePage(self), ModePage(self)
        self.detail_page, self.sec_page = DetailPage(self), SecurityPage(self)
        self.sum_page = SummaryPage(self)
        pages = [self.mode_page, self.detail_page, self.sec_page, self.sum_page]
        if self.locked_role:
            (self.role_page.teacher if self.locked_role == "teacher" else self.role_page.student).setChecked(True)
            self.setWindowTitle(f"Optimuslock Kurulum Sihirbazı – "
                                f"{'Öğretmen' if self.locked_role == 'teacher' else 'Öğrenci'} bilgisayarı – {PUBLISHER}")
        else:
            pages.insert(0, self.role_page)
        for p in self.arrange_pages(pages):
            self.addPage(p)
        self.setPixmap(QWizard.LogoPixmap, make_icon().pixmap(48, 48))

    def arrange_pages(self, pages):
        """Alt sınıflar (kurulum sihirbazı) sayfa listesini değiştirebilir."""
        return pages

    def extra_summary(self):
        return []

    def build_cfg(self) -> dict:
        c = dict(self.cfg)
        d, s = self.detail_page, self.sec_page
        c.update(
            role="teacher" if self.role_page.teacher.isChecked() else "student",
            mode=self.mode_page.mode(),
            key=s.key.text(), port=s.port.value(), autostart=s.auto.isChecked(),
            ts_via="docker" if d.ts_docker.isChecked() else "native",
            ts_authkey=d.ts_auth.text().strip(), ts_hostname=d.ts_host.text().strip(),
            cf_token=d.cf_token.text().strip(), cf_hostname=d.cf_host.text().strip(),
        )
        return c

    def accept(self):
        self.result_cfg = self.build_cfg()
        super().accept()


# Eski ad ile uyumluluk (öğretmen paneli "Ayarlar")
SetupDialog = SetupWizard
