"""Ortak arayüz parçaları: simge ve kurulum ekranı."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QRadioButton, QSpinBox, QVBoxLayout,
)

import tailscale
from common import DEFAULT_PORT


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


class SetupDialog(QDialog):
    """İlk açılışta: Öğrenci / Öğretmen + bağlantı yöntemi (Tailscale / IP)."""

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = dict(cfg)
        self.result_cfg = None
        self.setWindowTitle("Optimuslock Kurulum")
        self.setWindowIcon(make_icon())
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h2>Optimuslock</h2>BT sınıfı bilgisayar izleme ve kilitleme"))

        g1 = QGroupBox("1) Bu bilgisayar kimin?")
        v1 = QVBoxLayout(g1)
        self.r_student = QRadioButton("Öğrenci bilgisayarı")
        self.r_teacher = QRadioButton("Öğretmen bilgisayarı")
        v1.addWidget(self.r_student)
        v1.addWidget(self.r_teacher)
        lay.addWidget(g1)

        g2 = QGroupBox("2) Bağlantı yöntemi")
        v2 = QVBoxLayout(g2)
        self.r_ts = QRadioButton("Tailscale (farklı ağlar / uzaktan bağlantı, şifreli tünel)")
        self.r_ip = QRadioButton("IP adresi ile (aynı yerel ağ)")
        v2.addWidget(self.r_ts)
        v2.addWidget(self.r_ip)
        row = QHBoxLayout()
        self.ts_label = QLabel("Tailscale durumu: kontrol edilmedi")
        btn = QPushButton("Kontrol et")
        btn.clicked.connect(self.check_ts)
        row.addWidget(self.ts_label, 1)
        row.addWidget(btn)
        v2.addLayout(row)
        lay.addWidget(g2)

        g3 = QGroupBox("3) Güvenlik")
        v3 = QVBoxLayout(g3)
        v3.addWidget(QLabel("Sınıf anahtarı (öğretmen ve tüm öğrencilerde AYNI olmalı, en az 6 karakter):"))
        self.key = QLineEdit(self.cfg.get("key", ""))
        self.key.setEchoMode(QLineEdit.Password)
        v3.addWidget(self.key)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Port:"))
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(int(self.cfg.get("port", DEFAULT_PORT)))
        prow.addWidget(self.port)
        prow.addStretch(1)
        v3.addLayout(prow)
        self.autostart = QCheckBox("Bilgisayar açılınca otomatik başlat (öğrenci)")
        self.autostart.setChecked(bool(self.cfg.get("autostart", True)))
        v3.addWidget(self.autostart)
        lay.addWidget(g3)

        (self.r_teacher if self.cfg.get("role") == "teacher" else self.r_student).setChecked(True)
        (self.r_ip if self.cfg.get("mode") == "ip" else self.r_ts).setChecked(True)
        self.r_student.toggled.connect(lambda s: self.autostart.setEnabled(s))
        self.autostart.setEnabled(self.r_student.isChecked())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Kur ve Başlat")
        bb.button(QDialogButtonBox.Cancel).setText("İptal")
        bb.accepted.connect(self.finish)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def check_ts(self):
        if not tailscale.available():
            self.ts_label.setText("Tailscale bulunamadı (docker compose up -d ile Docker konteynerini başlatın)")
            return
        ip = tailscale.my_ip()
        self.ts_label.setText(f"Tailscale bağlı: {ip}" if ip else "Tailscale kurulu ama oturum açık değil")

    def finish(self):
        if len(self.key.text()) < 6:
            QMessageBox.warning(self, "Optimuslock", "Sınıf anahtarı en az 6 karakter olmalı.")
            return
        cfg = dict(self.cfg)
        cfg.update(
            role="student" if self.r_student.isChecked() else "teacher",
            mode="tailscale" if self.r_ts.isChecked() else "ip",
            key=self.key.text(),
            port=self.port.value(),
            autostart=self.autostart.isChecked(),
        )
        self.result_cfg = cfg
        self.accept()
