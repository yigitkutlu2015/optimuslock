#!/usr/bin/env bash
# Pardus/Debian/Ubuntu için optimuslock_<sürüm>_all.deb üretir.
# Paket uygulamayı + kurulumda internetten sanal ortam (venv) kuran bir postinst içerir;
# böylece Pardus 21/23/25 gibi farklı Python/glibc sürümlerinde çalışır.
set -euo pipefail
VERSION="${1:-1.0.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
B="$ROOT/packaging/build"; PKG="$B/deb"; OUT="$ROOT/dist"
rm -rf "$PKG"; mkdir -p "$PKG"/{DEBIAN,opt/optimuslock/app,opt/optimuslock/docker,usr/bin,usr/share/applications,usr/share/icons/hicolor/256x256/apps,usr/share/doc/optimuslock} "$OUT"
python3 "$ROOT/packaging/make_assets.py" "$B"

cp "$ROOT"/{common,tailscale,ui,agent,teacher,optimuslock}.py "$PKG/opt/optimuslock/app/"
cp "$ROOT/requirements.txt" "$PKG/opt/optimuslock/"
cp "$ROOT/docker-compose.yml" "$ROOT/.env.example" "$PKG/opt/optimuslock/docker/"
cp "$ROOT/README.md" "$PKG/usr/share/doc/optimuslock/README.md"
cp "$B/optimuslock.png" "$PKG/usr/share/icons/hicolor/256x256/apps/optimuslock.png"

cat > "$PKG/usr/bin/optimuslock" <<'X'
#!/bin/sh
exec /opt/optimuslock/venv/bin/python /opt/optimuslock/app/optimuslock.py "$@"
X

cat > "$PKG/usr/bin/optimuslock-tailscale" <<'X'
#!/bin/sh
# Tailscale Docker yan konteynerini yönetir.  Kullanım: sudo optimuslock-tailscale [up|down|status|logs]
set -e
CFG=/etc/optimuslock/tailscale.env
DIR=/opt/optimuslock/docker
if [ "$(id -u)" -ne 0 ]; then echo "root gerekli: sudo optimuslock-tailscale $*"; exit 1; fi
mkdir -p /etc/optimuslock
if [ ! -f "$CFG" ]; then
  cp "$DIR/.env.example" "$CFG"
  echo "$CFG oluşturuldu. TS_AUTHKEY ve TS_HOSTNAME değerlerini düzenleyip komutu tekrar çalıştırın."
  exit 0
fi
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
cd "$DIR"
case "${1:-up}" in
  up) $DC --env-file "$CFG" up -d ;;
  down) $DC --env-file "$CFG" down ;;
  logs) $DC --env-file "$CFG" logs --tail 50 ;;
  status) docker exec optimuslock-tailscale tailscale status ;;
  *) echo "kullanım: optimuslock-tailscale [up|down|status|logs]"; exit 1 ;;
esac
X

cat > "$PKG/usr/share/applications/optimuslock.desktop" <<'X'
[Desktop Entry]
Type=Application
Name=Optimuslock
Comment=BT sınıfı bilgisayar izleme ve kilitleme
Exec=optimuslock
Icon=optimuslock
Terminal=false
Categories=Education;System;
X

cat > "$PKG/DEBIAN/control" <<X
Package: optimuslock
Version: $VERSION
Section: education
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-venv, python3-pip, libxcb-cursor0, libegl1, libgl1, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libdbus-1-3, libfontconfig1
Recommends: docker.io | docker-ce
Maintainer: Optimuslock <optimuslock@localhost>
Description: BT sınıfı bilgisayar izleme, uygulama engelleme ve ekran kilitleme
 Öğretmen paneli ve öğrenci ajanı. Tailscale veya IP ile bağlanır.
 Kurulum sırasında Python bağımlılıkları için internet bağlantısı gerekir.
X

cat > "$PKG/DEBIAN/postinst" <<'X'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
  V=/opt/optimuslock/venv
  [ -x "$V/bin/python" ] || python3 -m venv "$V"
  if ! "$V/bin/pip" install --disable-pip-version-check -q -r /opt/optimuslock/requirements.txt; then
    echo "Optimuslock: Python paketleri kurulamadı. İnternet bağlantısını kontrol edip 'sudo dpkg --configure -a' çalıştırın." >&2
    exit 1
  fi
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q 2>/dev/null || true
fi
exit 0
X

cat > "$PKG/DEBIAN/postrm" <<'X'
#!/bin/sh
set -e
case "$1" in remove|purge) rm -rf /opt/optimuslock/venv ;; esac
[ "$1" = "purge" ] && rm -rf /etc/optimuslock || true
exit 0
X

chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm" "$PKG/usr/bin/optimuslock" "$PKG/usr/bin/optimuslock-tailscale"
find "$PKG" -type d -exec chmod 755 {} +
find "$PKG/opt" "$PKG/usr/share" -type f -exec chmod 644 {} +
dpkg-deb --root-owner-group -b "$PKG" "$OUT/optimuslock_${VERSION}_all.deb"
echo "Hazır: $OUT/optimuslock_${VERSION}_all.deb"
