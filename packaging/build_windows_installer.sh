#!/usr/bin/env bash
# Linux üzerinde Windows kurulum dosyası (Optimuslock-Setup-<sürüm>.exe) üretir.
# Gerekenler: nsis (makensis), zstd gerekmez, pip, internet.
# İçerik: Windows için hazır Python 3.11 (python-build-standalone) + Windows wheel'leri + uygulama.
set -euo pipefail
VERSION="${1:-1.0.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; P="$ROOT/packaging"; B="$P/build"; C="$P/cache"
PYTAG="20261013"; PYVER="3.11.17"
PYURL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTAG}/cpython-${PYVER}%2B${PYTAG}-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
command -v makensis >/dev/null || { echo "makensis yok: sudo apt install nsis"; exit 1; }
mkdir -p "$B" "$C" "$ROOT/dist"
python3 "$P/make_assets.py" "$B"

[ -f "$C/python.tar.gz" ] || curl -fsSL -o "$C/python.tar.gz" "$PYURL"
if ! ls "$C"/wheels/*.whl >/dev/null 2>&1; then
  mkdir -p "$C/wheels"
  pip download -q --only-binary=:all: --platform win_amd64 --python-version 3.11 --implementation cp --abi cp311 \
      -d "$C/wheels" -r "$ROOT/requirements.txt" msvc-runtime
fi

S="$B/stage"; rm -rf "$S"; mkdir -p "$S/app" "$S/docker"
tar xzf "$C/python.tar.gz" -C "$S"                       # -> $S/python
SP="$S/python/Lib/site-packages"; mkdir -p "$SP"
for w in "$C"/wheels/*.whl; do
  case "$w" in
    *msvc_runtime*) T="$(mktemp -d)"; unzip -q "$w" -d "$T"; cp "$T"/*.data/data/*.dll "$S/python/"; rm -rf "$T" ;;  # msvcp140.dll vb.
    *) unzip -q -o "$w" -d "$SP" ;;
  esac
done
# Gereksiz Qt parçalarını ayıkla (kurulum boyutu)
PS="$SP/PySide6"
rm -rf "$PS"/{qml,translations,typesystems,include,glue,scripts,examples,metatypes,doc} 2>/dev/null || true
find "$PS" -maxdepth 1 \( -name "*.exe" -o -name "*.pyi" \) -delete 2>/dev/null || true
rm -f "$PS"/Qt6Quick*.dll "$PS"/Qt6Qml*.dll "$PS"/Qt6Designer*.dll "$PS"/Qt6Pdf*.dll "$PS"/QtQuick*.pyd "$PS"/QtQml*.pyd "$PS"/QtDesigner*.pyd "$PS"/QtPdf*.pyd 2>/dev/null || true

cp "$ROOT"/{common,tailscale,ui,agent,teacher,optimuslock}.py "$S/app/"
cp "$ROOT/docker-compose.windows.yml" "$ROOT/tailscale_docker_windows.bat" "$ROOT/.env.example" "$ROOT/README.md" "$S/docker/"
# Kurulum dizininden çalışacak şekilde .bat'ı uyarla (compose dosyası aynı klasörde)

echo "--- sağlama kontrolleri"
for f in python/pythonw.exe python/msvcp140.dll python/Lib/site-packages/PySide6/Qt6Widgets.dll \
         python/Lib/site-packages/PySide6/plugins/platforms/qwindows.dll python/Lib/site-packages/PySide6/QtWidgets.pyd \
         python/Lib/site-packages/psutil/__init__.py python/Lib/site-packages/mss/__init__.py \
         python/Lib/site-packages/PIL/__init__.py python/Lib/site-packages/cryptography/fernet.py; do
  [ -e "$S/$f" ] && echo "tamam  $f" || { echo "EKSİK  $f"; exit 1; }
done
cd "$P" && makensis -V2 -DVERSION="$VERSION" installer.nsi
ls -la "$ROOT/dist"
