"""AppImage kurulum mantığı (Pardus/Linux): kullanıcıya özel veya tüm kullanıcılar için kurar, kaldırır.

Kurulum sihirbazı (installer.py) bu işlevleri kullanır. Tüm kullanıcılar için kurulum yönetici yetkisi
gerektirir: pkexec ile aynı dosya `--root-kur` / `--root-kaldir` kipinde root olarak çalıştırılır (arayüz açmaz).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Testler için kök dizin öneki (normalde "/")
SYSROOT = Path(os.environ.get("OPTIMUSLOCK_SYSROOT", "/"))
BIN_NAME = "optimuslockkurulum.cykbilisim"

SHARE = Path.home() / ".local" / "share"
INSTALL_DIR = SHARE / "optimuslock"
INSTALLED = INSTALL_DIR / BIN_NAME
DESKTOP = SHARE / "applications" / "optimuslock.desktop"
ICON = SHARE / "icons" / "hicolor" / "256x256" / "apps" / "optimuslock.png"
AUTOSTART = Path.home() / ".config" / "autostart" / "optimuslock.desktop"

SYSTEM_DIR = SYSROOT / "opt" / "optimuslock"
SYSTEM_BIN = SYSTEM_DIR / BIN_NAME
SYSTEM_DESKTOP = SYSROOT / "usr/share/applications/optimuslock.desktop"
SYSTEM_ICON = SYSROOT / "usr/share/icons/hicolor/256x256/apps/optimuslock.png"
SYSTEM_AUTOSTART = SYSROOT / "etc/xdg/autostart/optimuslock.desktop"
SYSTEM_CFGDIR = SYSROOT / "etc/optimuslock"

COMMENT = "BT sınıfı bilgisayar izleme ve kilitleme - cykbilişim"


def running_appimage():
    p = os.environ.get("APPIMAGE")
    return Path(p) if p and Path(p).is_file() else None


def is_installed_copy() -> bool:
    """Çalışan AppImage, kurulu kopyanın kendisi mi? (kurulumdan sonra menüden başlatılan)"""
    src = running_appimage()
    if not src:
        return False
    try:
        r = src.resolve()
        return any(p.exists() and p.resolve() == r for p in (INSTALLED, SYSTEM_BIN))
    except OSError:
        return False


def install_state() -> str:
    """'system' | 'user' | 'none'"""
    if SYSTEM_BIN.exists():
        return "system"
    if INSTALLED.exists():
        return "user"
    return "none"


def installed_path():
    """Otomatik başlatma / yeniden başlatma için kalıcı kopya (yoksa çalışan AppImage)."""
    for p in (SYSTEM_BIN, INSTALLED):
        if p.exists():
            return p
    return running_appimage()


def desktop_text(exec_path) -> str:
    return ("[Desktop Entry]\nType=Application\nVersion=1.0\nName=Optimuslock\nName[tr]=Optimuslock\n"
            f"GenericName=Sınıf Yönetimi\nComment={COMMENT}\n"
            f'Exec="{exec_path}"\nIcon=optimuslock\nTerminal=false\nCategories=Education;System;\n'
            "StartupNotify=false\n")


def copy_with_progress(src: Path, dst: Path, cb=None, chunk=4 * 1024 * 1024):
    """Büyük dosyayı parça parça kopyalar; cb(yüzde) çağrılır. Yarım kalırsa hedef bırakılmaz."""
    tmp = dst.with_suffix(".tmp")
    total = max(src.stat().st_size, 1)
    done = 0
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        while True:
            b = fi.read(chunk)
            if not b:
                break
            fo.write(b)
            done += len(b)
            if cb:
                cb(int(done * 100 / total))
    tmp.chmod(0o755)
    os.replace(tmp, dst)


def _refresh_caches(*dirs):
    for cmd in (["update-desktop-database", "-q"], ["gtk-update-icon-cache", "-q", "-f", "/usr/share/icons/hicolor"]):
        try:
            subprocess.run(cmd + ([str(dirs[0])] if cmd[0] == "update-desktop-database" and dirs else []),
                           timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def user_desktop_dir() -> Path:
    try:
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5).stdout.strip()
        if out and Path(out).is_dir():
            return Path(out)
    except Exception:
        pass
    for n in ("Masaüstü", "Desktop"):
        if (Path.home() / n).is_dir():
            return Path.home() / n
    return Path.home() / "Desktop"


def make_desktop_shortcut(exec_path) -> Path:
    d = user_desktop_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / "Optimuslock.desktop"
    f.write_text(desktop_text(exec_path), "utf-8")
    f.chmod(0o755)
    try:  # GNOME: "güvenilir başlatıcı" olarak işaretle
        subprocess.run(["gio", "set", str(f), "metadata::trusted", "true"], timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return f


# ------------------------------------------------------------------ kullanıcıya özel kurulum
def install_user(src: Path, appdir: str, progress):
    """progress(yüzde, mesaj). Kurulu dosyanın yolunu döndürür."""
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    progress(5, "Dosyalar kopyalanıyor...")
    if INSTALLED.exists() and INSTALLED.resolve() == src.resolve():
        pass
    else:
        copy_with_progress(src, INSTALLED, lambda p: progress(5 + int(p * 0.7), "Dosyalar kopyalanıyor..."))
    progress(78, "Menü girdisi ve simge ekleniyor...")
    icon_src = Path(appdir) / "optimuslock.png"
    if icon_src.is_file():
        ICON.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, ICON)
    DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP.write_text(desktop_text(INSTALLED), "utf-8")
    _refresh_caches(DESKTOP.parent)
    return INSTALLED


# ------------------------------------------------------------------ tüm kullanıcılar için (root)
def pkexec_cmd(src: Path, mode: str, plan_file: str = "") -> list:
    cmd = ["pkexec", str(src), mode]
    if plan_file:
        cmd.append(plan_file)
    return cmd


def root_install(plan_file: str) -> int:
    """Root olarak çalışır; her satıra 'ILERLEME <yüzde> <mesaj>' yazar."""
    def emit(p, m):
        print(f"ILERLEME {p} {m}", flush=True)

    plan = json.loads(Path(plan_file).read_text("utf-8"))
    src = running_appimage()
    if not src:
        print("HATA AppImage kaynağı bulunamadı", flush=True)
        return 2
    try:
        emit(5, "Klasörler hazırlanıyor...")
        for d in (SYSTEM_DIR, SYSTEM_DESKTOP.parent, SYSTEM_ICON.parent, SYSTEM_CFGDIR):
            d.mkdir(parents=True, exist_ok=True)
        emit(10, "Dosyalar /opt/optimuslock altına kopyalanıyor...")
        copy_with_progress(src, SYSTEM_BIN, lambda p: emit(10 + int(p * 0.6), "Dosyalar kopyalanıyor..."))
        emit(72, "Menü girdisi ve simge ekleniyor...")
        icon_src = Path(os.environ.get("APPDIR", "")) / "optimuslock.png"
        if icon_src.is_file():
            shutil.copy2(icon_src, SYSTEM_ICON)
            SYSTEM_ICON.chmod(0o644)
        SYSTEM_DESKTOP.write_text(desktop_text(SYSTEM_BIN), "utf-8")
        SYSTEM_DESKTOP.chmod(0o644)
        if plan.get("autostart"):
            emit(80, "Otomatik başlatma ekleniyor...")
            SYSTEM_AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            SYSTEM_AUTOSTART.write_text(desktop_text(SYSTEM_BIN) + "X-GNOME-Autostart-enabled=true\n", "utf-8")
            SYSTEM_AUTOSTART.chmod(0o644)
        elif SYSTEM_AUTOSTART.exists():
            SYSTEM_AUTOSTART.unlink()
        emit(88, "Ayarlar tüm kullanıcılar için kaydediliyor...")
        cfgf = SYSTEM_CFGDIR / "config.json"
        cfgf.write_text(json.dumps(plan["config"], ensure_ascii=False), "utf-8")
        cfgf.chmod(0o644)
        _refresh_caches(SYSTEM_DESKTOP.parent)
        emit(100, "Tamamlandı")
        return 0
    except OSError as e:
        print(f"HATA {e}", flush=True)
        return 1


def root_remove() -> int:
    for p in (SYSTEM_DESKTOP, SYSTEM_ICON, SYSTEM_AUTOSTART):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    shutil.rmtree(SYSTEM_DIR, ignore_errors=True)
    shutil.rmtree(SYSTEM_CFGDIR, ignore_errors=True)
    print("Sistem geneli Optimuslock kurulumu kaldırıldı.")
    return 0


# ------------------------------------------------------------------ kaldırma
def uninstall() -> int:
    """Kullanıcıya özel kurulumu siler; sistem geneli kurulum varsa pkexec ile onu da kaldırır."""
    for p in (DESKTOP, ICON, AUTOSTART, user_desktop_dir() / "Optimuslock.desktop"):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    if SYSTEM_BIN.exists():
        if os.geteuid() == 0:
            root_remove()
        else:
            print("Sistem geneli kurulum için yönetici parolası istenecek...")
            subprocess.call(pkexec_cmd(SYSTEM_BIN, "--root-kaldir"))
    print("Optimuslock kaldırıldı. (Ayarlar ~/.config/optimuslock klasöründe kaldı; silmek isterseniz o klasörü silin.)")
    return 0
