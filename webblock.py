"""Web sitesi engelleme: hosts dosyasına işaretli bir blok yazar/siler.

DİKKAT: hosts dosyasını yazmak yönetici (Windows) / root (Linux) yetkisi gerektirir.
Yetki yoksa apply() (False, hata) döndürür ve öğretmen panelinde "yetki yok" uyarısı görünür.
Not: DNS-over-HTTPS kullanan tarayıcılar hosts dosyasını atlayabilir.
"""
import os
import re
import subprocess

BEGIN = "# >>> OPTIMUSLOCK BEGIN (otomatik, elle duzenlemeyin)"
END = "# <<< OPTIMUSLOCK END"
_DOM = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$")
_BLOCK = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\r?\n?", re.S)


def hosts_path() -> str:
    return os.environ.get("OPTIMUSLOCK_HOSTS") or (
        r"C:\Windows\System32\drivers\etc\hosts" if os.name == "nt" else "/etc/hosts")


def clean(d: str):
    d = re.sub(r"^[a-z]+://", "", d.strip().lower())
    d = d.split("/")[0].split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d if "." in d and _DOM.match(d) else None


def apply(domains):
    """Verilen alan adlarını engeller (boş liste = engeli kaldır). (başarılı_mı, mesaj) döndürür."""
    doms = sorted({c for c in map(clean, domains) if c})
    path = hosts_path()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            old = f.read()
    except OSError as e:
        return False, str(e)
    has_block = BEGIN in old
    if not doms and not has_block:
        return True, "engel yok"
    base = _BLOCK.sub("", old).rstrip() + "\n"
    new = base
    if doms:
        lines = [BEGIN]
        for d in doms:
            for h in (d, "www." + d):
                lines += [f"127.0.0.1 {h}", f"::1 {h}"]
        lines.append(END)
        new = base + "\n".join(lines) + "\n"
    if new == old:
        return True, "değişiklik yok"
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
    except OSError as e:
        return False, str(e)
    if os.name == "nt":
        try:
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10, creationflags=0x08000000)
        except Exception:
            pass
    return True, "ok"
