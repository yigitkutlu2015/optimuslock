# Optimuslock

BT sınıfı için pencere tabanlı (tarayıcı gerektirmeyen) bilgisayar izleme, uygulama engelleme ve sanal kilitleme programı.
Pardus (Linux) ve Windows'ta aynı kodla çalışır. Python + PySide6.

## Özellikler
- **İzleme:** Öğretmen panelinde tüm öğrencilerin canlı ekran küçük resimleri; çift tıkla büyük canlı görünüm; açık uygulama listesi (üzerine gelince).
- **Uygulama engelleme:** Program adı listesi gönderilir (`chrome`, `firefox`, `steam`...). Öğrencide çalışırsa kapatılır.
- **Sanal kilit:** Tüm monitörleri kaplayan, her zaman üstte kilit ekranı + mesaj. Öğretmen paneli kapanır/bağlantı kopar ise 90 sn sonra kilit ve engeller otomatik kalkar.
- **Mesaj gönderme**
- **Kurulum ekranı:** Öğrenci / Öğretmen seçimi + bağlantı yöntemi (Tailscale veya IP).
- **İki bağlantı yolu:** Tailscale (Tailscale IP'lerine bağlanır, otomatik tarama) veya yerel ağ IP'si (alt ağ taraması / elle IP).
- **Güvenlik:** Tüm trafik sınıf anahtarından türetilen anahtarla şifrelenir ve doğrulanır (Fernet). Anahtarı bilmeyen bağlanamaz.
- **Şeffaflık:** Öğrenci tarafı sistem tepsisinde görünür, öğretmen bağlanınca bildirim gösterir.

## Hazır paketler (dist/)
| Dosya | Hedef | Kurulum |
|---|---|---|
| `Optimuslock-Setup-1.0.0.exe` | Windows 10 (1703+) / 11, 64 bit | Çift tıklayın (yönetici onayı). Sessiz kurulum: `Optimuslock-Setup-1.0.0.exe /S`. Güvenlik duvarı kuralı (TCP 5710), masaüstü ve başlat menüsü kısayolları otomatik eklenir. İçinde Python gömülüdür, ayrıca bir şey kurmak gerekmez. |
| `optimuslock_1.0.0_all.deb` | Pardus 21/23/25, Debian, Ubuntu | `sudo apt install ./optimuslock_1.0.0_all.deb` (kurulum sırasında internet gerekir; bağımlılıklar sanal ortama kurulur). Başlat: menüden **Optimuslock** veya `optimuslock`. Tailscale konteyneri: `sudo optimuslock-tailscale up`. |

Kaldırma: Windows'ta *Uygulamalar ve özellikler*, Linux'ta `sudo apt remove optimuslock`.

Paketleri kendiniz üretmek için: `packaging/build_deb.sh` ve `packaging/build_windows_installer.sh` (Linux'ta `nsis` ve internet gerekir).
Windows `.exe` imzasız olduğundan SmartScreen "Bilinmeyen yayıncı" uyarısı verebilir: *Daha fazla bilgi → Yine de çalıştır*.

## Hızlı başlangıç

### Pardus / Linux
```bash
sudo apt install python3-venv python3-pip libxcb-cursor0
./run_linux.sh              # veya: ./build_linux.sh  (Docker ile tek dosyalık ikili -> dist/optimuslock)
```
**Tailscale (Docker yan konteyner)** — Tailscale yöntemini seçecekseniz:
```bash
cp .env.example .env        # TS_AUTHKEY ve TS_HOSTNAME değerlerini düzenleyin
docker compose up -d
```
Uygulama, `optimuslock-tailscale` konteynerini otomatik bulur (`docker exec ... tailscale status --json`).
Docker'a erişim için kullanıcıyı `docker` grubuna ekleyin: `sudo usermod -aG docker $USER`.

### Windows
```bat
run_windows.bat             REM veya build_windows.bat -> dist\optimuslock.exe
```
**Tailscale için iki seçenek:**

**A) Docker Desktop (önerilen, Linux ile aynı mantık):**
```bat
tailscale_docker_windows.bat    REM .env düzenlenir, konteyner başlar
```
(`docker-compose.windows.yml` kullanır.) Docker Desktop'ta konteyner Windows'a Tailscale arayüzü ekleyemediği için konteyner "userspace" modunda çalışır:
- **Öğretmen:** Tailscale cihazlarına `127.0.0.1:1055` SOCKS5 proxy'si üzerinden bağlanır (uygulama otomatik algılar).
- **Öğrenci:** Konteyner, Tailscale'den gelen 5710 bağlantısını Windows'taki Optimuslock'a yönlendirir (uygulama başlarken `tailscale serve` ile otomatik ayarlar).

**B) Windows için Tailscale uygulaması:** https://tailscale.com/download adresinden kurup oturum açın; Docker gerekmez.

Optimuslock'un kendisi (ekran yakalama + kilit penceresi masaüstü gerektirdiğinden) Docker içinde değil, Windows'ta yerel çalışır.

Öğrenci bilgisayarında gelen bağlantıya izin verin (yönetici CMD):
```bat
netsh advfirewall firewall add rule name="Optimuslock" dir=in action=allow protocol=TCP localport=5710
```
Linux'ta güvenlik duvarı açıksa: `sudo ufw allow 5710/tcp`

### Kullanım
1. Her bilgisayarda programı açın → **Öğrenci** veya **Öğretmen** + bağlantı yöntemi + **aynı sınıf anahtarı**.
2. Öğretmen panelinde **Tailscale ile Tara** / **Ağı Tara (IP)** veya **IP Ekle**.
3. Öğrenci seçili değilse işlemler tüm öğrencilere uygulanır; seçerek tek tek de yönetebilirsiniz.
4. Kurulumu tekrar açmak için: `python optimuslock.py --setup`

## Bilinen sınırlar
- **Wayland:** Ekran yakalama ve tam ekran kilit Wayland'de çalışmaz. Pardus'ta X11 oturumu kullanın (giriş ekranından "Xorg/X11" seçin).
- **Kilit ekranı sert kilit değildir:** Windows tuşu, Ctrl+Alt+Del gibi sistem kısayolları engellenemez; pencere sürekli öne getirilir. Tam kilit için işletim sistemi düzeyinde (yönetici yetkili) çözüm gerekir.
- **Uygulama engelleme** süreç adına göredir; kullanıcı exe'yi yeniden adlandırırsa atlatılabilir. Yönetici olmayan kullanıcıların kapatamadığı yetkili süreçler kapatılamaz.
- Windows + Docker yönteminde öğrenci ajanı tüm arayüzlerde dinler (konteyner `host.docker.internal` üzerinden bağlanır); erişim yine sınıf anahtarıyla korunur.
- Yalnızca ilk monitör izlenir (kilit tüm monitörleri kaplar).
- IP yönteminde trafik şifrelidir ama alt ağ taraması yerel ağda port 5710'a bağlanma denemesi yapar.

## Etik/yasal not
Bu araç öğrenci ekranlarını gösterir. Kullanmadan önce okul yönetiminden izin alın ve öğrencileri/velileri bilgilendirin.
