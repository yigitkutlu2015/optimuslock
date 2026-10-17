"""Optimuslock – BT sınıfı bilgisayar izleme ve kilitleme (Pardus + Windows).

Kullanım:
    python optimuslock.py            # ilk açılışta kurulum ekranı, sonra seçilen rolde başlar
    python optimuslock.py --setup    # kurulum ekranını yeniden aç
"""
import sys

from common import config_dir, load_config, make_cipher, save_config, set_autostart

# pythonw.exe (konsolsuz) altında hatalar kaybolmasın: günlük dosyasına yaz
if sys.stderr is None or sys.stdout is None:
    _log = open(config_dir() / "optimuslock.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

from PySide6.QtWidgets import QApplication  # noqa: E402
from ui import SetupDialog, make_icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Optimuslock")
    app.setWindowIcon(make_icon())
    app.setQuitOnLastWindowClosed(False)

    cfg = load_config()
    if "--setup" in sys.argv or not cfg.get("role"):
        dlg = SetupDialog(cfg)
        if not dlg.exec() or not dlg.result_cfg:
            return 0
        cfg = dlg.result_cfg
        save_config(cfg)
        if cfg["role"] == "student":
            try:
                set_autostart(cfg.get("autostart", True))
            except Exception:
                pass

    keep = None
    if cfg["role"] == "student":
        from agent import run_agent

        keep = run_agent(app, cfg, make_cipher(cfg["key"]))
        if keep is None:
            return 1
    else:
        from teacher import run_teacher

        keep = run_teacher(app, cfg)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
