"""Pardus/Linux görsel kurulum sihirbazı (AppImage): hoş geldiniz → bilgilendirme → ayarlar → seçenekler → kurulum → bitiş."""
import json
import os
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QLabel, QListWidget, QProgressBar, QRadioButton, QVBoxLayout, QWizard, QWizardPage,
)

import appimage
import dockerctl
from common import APP_VERSION, PUBLISHER, save_config, set_autostart
from ui import SetupWizard, _note, make_icon

MACHINE_KEYS = ("role", "mode", "key", "port", "autostart", "ts_via", "ts_authkey", "ts_hostname",
                "cf_token", "cf_hostname")


class WelcomePage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.setTitle("Optimuslock Kurulumuna Hoş Geldiniz")
        self.setSubTitle(f"Sürüm {APP_VERSION} · {PUBLISHER}")
        lay = QVBoxLayout(self)
        logo = QLabel()
        logo.setPixmap(make_icon().pixmap(96, 96))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        t = QLabel("Bu sihirbaz <b>Optimuslock</b>'u bilgisayarınıza kurar ve ayarlarını yapar.<br><br>"
                   "Sonraki adımlarda bu bilgisayarın rolünü (öğrenci / öğretmen), bağlantı yöntemini "
                   "(Tailscale, IP veya Cloudflare Tunnel) ve güvenlik anahtarını seçeceksiniz.<br><br>"
                   "Devam etmek için <b>İleri</b>'ye tıklayın.")
        t.setWordWrap(True)
        lay.addWidget(t)
        st = appimage.install_state()
        if st != "none":
            lay.addWidget(_note("Bu bilgisayarda Optimuslock zaten kurulu (" +
                                ("tüm kullanıcılar için" if st == "system" else "bu kullanıcı için") +
                                "). Devam ederseniz güncellenir ve yeniden yapılandırılır."))
        lay.addStretch(1)


class NoticePage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.setTitle("Kullanım bilgilendirmesi")
        self.setSubTitle("Lütfen okuyun")
        lay = QVBoxLayout(self)
        t = QLabel(
            "Optimuslock, öğrenci bilgisayarlarının ekranını görebilen ve bu bilgisayarları kilitleyip "
            "yönetebilen bir <b>sınıf yönetim aracıdır</b>.<br><br>"
            "• Kullanmadan önce okul yönetiminden izin alın; öğrencileri ve velileri bilgilendirin.<br>"
            "• Öğrenci bilgisayarında program görünür çalışır; öğretmen bağlanınca bildirim gösterilir.<br>"
            "• Tüm trafik sınıf anahtarıyla şifrelenir.<br><br>"
            f"© {PUBLISHER} · Tüm hakları saklıdır.")
        t.setWordWrap(True)
        lay.addWidget(t)
        self.ok = QCheckBox("Okudum ve kabul ediyorum")
        self.ok.toggled.connect(lambda _: self.completeChanged.emit())
        lay.addWidget(self.ok)
        lay.addStretch(1)

    def isComplete(self):
        return self.ok.isChecked()


class OptionsPage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.setTitle("Kurulum seçenekleri")
        self.setSubTitle("Optimuslock kimin için kurulsun?")
        lay = QVBoxLayout(self)
        g = QGroupBox("Kurulum kapsamı")
        v = QVBoxLayout(g)
        self.user = QRadioButton("Yalnızca bu kullanıcı için (parola gerekmez)")
        self.system = QRadioButton("Bu bilgisayardaki tüm kullanıcılar için (yönetici parolası istenir)")
        self.user.setChecked(True)
        v.addWidget(self.user)
        v.addWidget(self.system)
        v.addWidget(_note("Tüm kullanıcılar için: /opt/optimuslock altına kurulur, ayarlar ve otomatik başlatma "
                          "bilgisayardaki her kullanıcı hesabında geçerli olur."))
        lay.addWidget(g)
        self.shortcut = QCheckBox("Masaüstüne kısayol ekle")
        self.shortcut.setChecked(True)
        lay.addWidget(self.shortcut)
        lay.addStretch(1)

    def scope(self):
        return "system" if self.system.isChecked() else "user"


class InstallWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    finished_ok = Signal(bool, str)

    def __init__(self, cfg, scope, shortcut):
        super().__init__()
        self.cfg, self.scope, self.shortcut = cfg, scope, shortcut

    def run(self):
        try:
            cfg, scope = self.cfg, self.scope
            src = appimage.running_appimage()
            if not src:
                raise RuntimeError("Kurulum dosyası bulunamadı (AppImage olarak çalıştırın).")
            self.progress.emit(2, "Gereksinimler denetleniyor...")
            if os.environ.get("XDG_SESSION_TYPE") == "wayland":
                self.log.emit("UYARI: Wayland oturumu algılandı. Ekran yakalama ve kilit için X11 oturumu önerilir.")
            if dockerctl.needed(cfg) and not dockerctl.compose_cmd():
                self.log.emit("UYARI: Docker bulunamadı. Seçtiğiniz bağlantı yöntemi için gerekli: sudo apt install docker.io")
            rev = str(int(time.time()))
            machine = {k: cfg[k] for k in MACHINE_KEYS if k in cfg}
            machine["rev"] = rev
            if scope == "system":
                self.progress.emit(4, "Yönetici yetkisi isteniyor...")
                self.log.emit("Yönetici parolası istenecek...")
                fd, plan = tempfile.mkstemp(prefix="optimuslock-plan-", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"autostart": bool(cfg.get("autostart")) and cfg.get("role") == "student",
                               "config": machine}, f, ensure_ascii=False)
                os.chmod(plan, 0o600)
                try:
                    p = subprocess.Popen(appimage.pkexec_cmd(src, "--root-kur", plan), stdout=subprocess.PIPE,
                                         text=True, encoding="utf-8")
                    err = ""
                    for line in p.stdout:
                        line = line.strip()
                        if line.startswith("ILERLEME "):
                            _, n, msg = (line.split(" ", 2) + [""])[:3]
                            self.progress.emit(int(n), msg)
                        elif line.startswith("HATA"):
                            err = line[5:]
                    rc = p.wait()
                finally:
                    try:
                        os.unlink(plan)
                    except OSError:
                        pass
                if rc != 0:
                    raise RuntimeError(err or "Yönetici işlemi tamamlanamadı (parola iptal edilmiş olabilir).")
                installed = appimage.SYSTEM_BIN
                self.log.emit("Dosyalar /opt/optimuslock altına kuruldu.")
            else:
                installed = appimage.install_user(src, os.environ.get("APPDIR", ""),
                                                  lambda n, m: self.progress.emit(n, m))
                self.log.emit(f"Dosyalar {installed.parent} altına kuruldu.")
            self.log.emit("Menü girdisi ve simge eklendi.")
            if self.shortcut:
                self.progress.emit(90, "Masaüstü kısayolu ekleniyor...")
                f = appimage.make_desktop_shortcut(installed)
                self.log.emit(f"Masaüstü kısayolu eklendi: {f.name}")
            self.progress.emit(94, "Ayarlar kaydediliyor...")
            student_auto = bool(cfg.get("autostart")) and cfg.get("role") == "student"
            if scope == "user":
                set_autostart(student_auto)
                if student_auto:
                    self.log.emit("Bilgisayar açılınca otomatik başlatma etkinleştirildi.")
                user_cfg = dict(cfg)
            else:
                set_autostart(False)  # sistem geneli otomatik başlatma /etc/xdg/autostart altında
                if student_auto:
                    self.log.emit("Tüm kullanıcılar için otomatik başlatma etkinleştirildi.")
                user_cfg = {**cfg, "machine_rev": rev}
            user_cfg.pop("role_locked", None)
            save_config(user_cfg)
            self.log.emit("Ayarlar kaydedildi.")
            self.progress.emit(100, "Kurulum tamamlandı")
            self.finished_ok.emit(True, str(installed))
        except Exception as e:  # noqa: BLE001
            self.finished_ok.emit(False, str(e))


class InstallPage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.ok = False
        self.worker = None
        self.setTitle("Kuruluyor")
        self.setSubTitle("Lütfen bekleyin...")
        lay = QVBoxLayout(self)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.msg = QLabel("Hazırlanıyor...")
        self.logw = QListWidget()
        lay.addWidget(self.msg)
        lay.addWidget(self.bar)
        lay.addWidget(self.logw, 1)

    def initializePage(self):
        self.ok = False
        self.logw.clear()
        self.w.install_result = None
        self.worker = InstallWorker(self.w.build_cfg(), self.w.options.scope(), self.w.options.shortcut.isChecked())
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.logw.addItem)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.start()

    def on_progress(self, n, m):
        self.bar.setValue(n)
        self.msg.setText(m)

    def on_done(self, ok, info):
        self.w.install_result = (ok, info)
        if ok:
            self.setSubTitle("Kurulum tamamlandı")
            self.ok = True
            self.completeChanged.emit()
            self.w.next()
        else:
            self.setSubTitle("Kurulum başarısız oldu")
            self.msg.setText("Hata: " + info)
            self.logw.addItem("HATA: " + info)

    def isComplete(self):
        return self.ok


class FinishPage(QWizardPage):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.setTitle("Optimuslock kuruldu")
        self.setSubTitle("Kurulum başarıyla tamamlandı")
        lay = QVBoxLayout(self)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.start_cb = QCheckBox("Optimuslock'u şimdi başlat")
        self.start_cb.setChecked(True)
        lay.addWidget(self.start_cb)
        lay.addStretch(1)
        lay.addWidget(_note(f"© {PUBLISHER}"))

    def initializePage(self):
        ok, info = self.w.install_result or (False, "")
        where = "tüm kullanıcılar için" if self.w.options.scope() == "system" else "bu kullanıcı için"
        self.info.setText(f"Optimuslock {where} kuruldu.<br><b>Konum:</b> {info}<br><br>"
                          "Uygulama menüsünde <b>Optimuslock</b> adıyla bulabilirsiniz. "
                          "Kaldırmak için kurulu dosyayı <code>--kaldir</code> ile çalıştırın.")
        self.setCommitPage(False)


def clean_env():
    e = dict(os.environ)
    for k in ("APPIMAGE", "APPDIR", "ARGV0", "OWD", "APPIMAGE_ORIG_LD_LIBRARY_PATH", "LD_LIBRARY_PATH",
              "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        e.pop(k, None)
    return e


class InstallerWizard(SetupWizard):
    def __init__(self, cfg: dict):
        cfg = {k: v for k, v in cfg.items() if k != "role_locked"}
        self.install_result = None
        super().__init__(cfg)
        self.setWindowTitle(f"Optimuslock Kurulum Sihirbazı – {PUBLISHER}")
        self.setMinimumSize(720, 520)
        self.setButtonText(QWizard.CommitButton, "Kur")
        self.setOption(QWizard.NoCancelButtonOnLastPage, True)
        self.setOption(QWizard.DisabledBackButtonOnLastPage, True)
        self.setButtonText(QWizard.FinishButton, "Bitir")

    def arrange_pages(self, pages):
        self.welcome, self.notice = WelcomePage(self), NoticePage(self)
        self.options = OptionsPage(self)
        self.install_page, self.finish_page = InstallPage(self), FinishPage(self)
        *core, summary = pages
        summary.setCommitPage(True)
        return [self.welcome, self.notice] + core + [self.options, summary, self.install_page, self.finish_page]

    def extra_summary(self):
        return [("Kurulum kapsamı", "Tüm kullanıcılar" if self.options.scope() == "system" else "Yalnızca bu kullanıcı"),
                ("Masaüstü kısayolu", "Evet" if self.options.shortcut.isChecked() else "Hayır")]

    def accept(self):
        ok, info = self.install_result or (False, "")
        if ok and self.finish_page.start_cb.isChecked():
            try:
                subprocess.Popen([info], start_new_session=True, env=clean_env(),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        super().accept()
