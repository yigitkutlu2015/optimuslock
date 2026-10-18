# Optimuslock
**Yayıncı: CYK Bilişim** · cykdigital@outlook.com.tr

BT sınıfı için pencere tabanlı (tarayıcı gerektirmeyen) bilgisayar izleme, kilitleme ve yönetim programı.
Pardus/Linux ve Windows'ta çalışır. Python + PySide6.

## Özellikler
- **Canlı izleme:** tüm öğrencilerin ekran küçük resimleri; çift tıkla büyük canlı görünüm; açık uygulama listesi
- **Sanal kilit:** tüm monitörleri kaplayan kilit ekranı + mesaj
- **Uygulama engelleme** (program adına göre) ve **web sitesi engelleme** (hosts dosyası; yönetici/root yetkisi gerekir)
- **Ekran yayını:** öğretmen ekranını öğrencilere gösterme
- **Dosya gönderme** (≤100 MB, öğrencide `Optimuslock-Gelen` klasörüne), **mesaj gönderme**
- **Uzaktan kapatma / yeniden başlatma / oturum kapatma** (öğretmen onayıyla)
- **Üç bağlantı yöntemi:** Tailscale · IP adresi · Cloudflare Tunnel
- **Güvenlik:** tüm trafik sınıf anahtarıyla şifrelenir ve doğrulanır; öğrenci tarafı görünür ve bildirim verir
- Docker (Tailscale / Cloudflare konteynerleri) **uygulama tarafından otomatik** kurulur; ayrı betik/komut yoktur

## Kurulum – tek sihirbaz
| Dosya | Hedef |
|---|---|
| `optimuslock-ogretmen_1.3.0_all.deb` | **Öğretmen bilgisayarı** — Pardus 23/25, Debian 12/13, Ubuntu 22.04+ |
| `optimuslock-ogrenci_1.3.0_all.deb` | **Öğrenci bilgisayarı** — aynı sistemler |
| `Optimuslock-Setup-1.3.0.exe` | Windows 10 (1703+) / 11, 64 bit (imzalı: yayıncı cykbilişim); rol sihirbazda seçilir |

Her `.deb` rolünü bilir: kurulum sihirbazı **rol sormaz**, doğrudan bağlantı yöntemiyle başlar. Python kütüphaneleri pakete
gömülüdür (internetsiz kurulur; uymazsa internetten denenir). Bir bilgisayarda yalnızca biri kurulabilir; diğerini kurmak onun yerine geçer.

**Pardus görsel kurulum sihirbazı (AppImage) — `optimuslockkurulum.cykbilisim`:** Tek dosya; Python ve Qt kütüphaneleri içindedir
(Pardus 23/25 gibi x86_64 Linux). Çift tıklayınca Windows'takine benzer bir kurulum sihirbazı açılır:
*Hoş geldiniz → Kullanım bilgilendirmesi (onay) → Rol → Bağlantı yöntemi → Ayrıntılar → Güvenlik → Kurulum seçenekleri → Özet → Kurulum (ilerleme çubuğu) → Bitir*.
- **Kurulum kapsamı:** *yalnızca bu kullanıcı için* (parola gerekmez; `~/.local/share/optimuslock`) ya da *tüm kullanıcılar için*
  (yönetici parolası istenir; `/opt/optimuslock`, ayarlar ve otomatik başlatma tüm hesaplarda geçerli olur).
- Menüye **Optimuslock** girdisi, isteğe bağlı masaüstü kısayolu ve (öğrenci için) otomatik başlatma eklenir; **Bitir**'de uygulama başlatılabilir.
- Önce dosyayı çalıştırılabilir yapın: sağ tık → Özellikler → *Çalıştırmaya izin ver* (ya da `chmod +x optimuslockkurulum.cykbilisim`).
- **Kaldırma:** `optimuslockkurulum.cykbilisim --kaldir` (kurulu kopyayla çalıştırın; sistem geneli kurulumda yönetici parolası ister). Ayarlar `~/.config/optimuslock` içinde kalır.
- AppImage açılmazsa: `sudo apt install libfuse2` ya da `APPIMAGE_EXTRACT_AND_RUN=1 ./optimuslockkurulum.cykbilisim`.
- Hata olursa nedeni ekranda gösterilir ve `~/.config/optimuslock/optimuslock.log` dosyasına yazılır. Gereksinim: glibc 2.34+ (Pardus 23/25).

**Windows:** `.exe`'yi çalıştırın. Sihirbaz sırayla sorar: **rol** (öğrenci/öğretmen) → **bağlantı yöntemi** →
Tailscale auth key veya Cloudflare tünel token'ı → **sınıf anahtarı**, port, otomatik başlatma. Bitince masaüstü simgesiyle başlatın;
ayrıca bir kurulum ekranı açılmaz. Güvenlik duvarı kuralı ve otomatik başlatma sihirbaz tarafından eklenir.

*Toplu/sessiz kurulum:*
`Optimuslock-Setup-1.3.0.exe /S /ROLE=student /MODE=ip /KEY=anahtar123 /PORT=5710 /AUTOSTART=1`
(diğer parametreler: `/TSVIA=docker|native /TSAUTH= /TSHOST= /CFTOKEN= /CFHOST=`). Sessiz kurulumda anahtarda **boşluk kullanmayın**.

**Windows yetki (UAC) ekranında yayıncı adı:** Windows yayıncı adını yalnızca dijital imzadan gösterir. Kurulum dosyası
*cykbilişim* adına imzalıdır; ancak sertifika kendinden imzalı olduğundan, **sertifikayı güvenen bilgisayarlarda** (yönetici CMD)
"Doğrulanmış yayıncı: cykbilişim" görünür:
`certutil -addstore -f Root cykbilisim-sertifika.cer` ve `certutil -addstore -f TrustedPublisher cykbilisim-sertifika.cer`
(okul bilgisayarlarına grup ilkesiyle de dağıtılabilir). Güvenmeyen bilgisayarlarda "Bilinmeyen yayıncı" görünmeye devam eder;
herkes için çözüm, bir sertifika otoritesinden satın alınan kod imzalama sertifikasıdır.

**Pardus/Linux:** `sudo apt install ./optimuslock-ogretmen_1.3.0_all.deb` (öğretmen) veya `./optimuslock-ogrenci_1.3.0_all.deb` (öğrenci). Menüden **Optimuslock**'u açın; ilk açılışta sihirbaz gelir.
Hata olursa nedeni ekranda gösterilir ve `~/.config/optimuslock/optimuslock.log` dosyasına yazılır.

**Kaynaktan çalıştırma:** `pip install -r requirements.txt` ardından `python optimuslock.py` (Pardus'ta önce `sudo apt install python3-venv python3-pip libxcb-cursor0`).

## Bağlantı yöntemleri
- **IP:** aynı yerel ağ. Öğretmen panelinde *Ağı Tara (IP)* veya *IP Ekle*. Öğrencide seçilen port açık olmalı (Windows sihirbazı kuralı ekler).
- **Tailscale:** *Docker* (önerilen; konteyner uygulama açılırken kendiliğinden başlar) ya da bilgisayardaki Tailscale uygulaması.
  Auth key: https://login.tailscale.com/admin/settings/keys . Windows'ta Docker Desktop açık olmalı.
- **Cloudflare Tunnel:** Öğrencide: Cloudflare Zero Trust → Networks → Tunnels'ta tünel oluşturup token'ı sihirbaza girin; tünele
  *Public hostname* ekleyin (Service = **TCP**, URL = `localhost:5710`; Windows + Docker Desktop'ta `host.docker.internal:5710`).
  Öğretmen panelinde *Tünel Öğrencisi Ekle* ile her öğrencinin alan adını (ör. `pc01.okul.com`) girin. Öğretmen bilgisayarında
  `cloudflared` ya da Docker gerekir (uygulama otomatik seçer).

## Bilinen sınırlar
- Pardus'ta **X11 oturumu** gerekir (Wayland'de ekran yakalama/kilit çalışmaz; başlatıcı XWayland'i kullanır).
- Kilit ekranı sert kilit değildir (Windows tuşu, Ctrl+Alt+Del engellenemez). Uygulama engelleme süreç adına göredir.
- **Web engelleme** hosts dosyasını yazabilmek için ajanın yönetici/root olmasını gerektirir; yetki yoksa panelde `[WEB: yetki yok]`
  görünür. DNS-over-HTTPS kullanan tarayıcılar atlayabilir; ağ düzeyinde DNS filtreleme daha sağlamdır.
- Sınıf anahtarı öğrenci bilgisayarında saklanır; teknik bilgisi olan bir öğrenci okuyabilir. Daha sert koruma için ajanın hizmet olarak çalışması gerekir.
- Windows `.exe` kod imzalı değildir: SmartScreen "Bilinmeyen yayıncı" uyarısı verebilir (yayıncı adı dosya özelliklerinde ve
  Programlar listesinde *cykbilişim* görünür; UAC penceresindeki "doğrulanmış yayıncı" ancak kod imzalama sertifikasıyla olur).
- Yalnızca ilk monitör izlenir/yayınlanır (kilit tüm monitörleri kaplar).

## Sürüm notları
**1.4.0**
- Pardus için görsel kurulum sihirbazı (AppImage, `optimuslockkurulum.cykbilisim`): hoş geldiniz, bilgilendirme onayı, ayarlar, kapsam seçimi (kullanıcı / tüm kullanıcılar), ilerleme çubuğu, bitiş; `--kaldir` ile kaldırma

**1.3.0**
- `.deb` ikiye ayrıldı: **öğretmen** ve **öğrenci** paketleri (rol pakette sabit, sihirbaz rol sormaz)
- Her iki pakette kütüphaneler gömülü; Windows kurulum dosyası aynı sürüme getirildi

**1.2.0**
- Tek kurulum sihirbazı: rol, bağlantı yöntemi (Tailscale / IP / Cloudflare Tunnel), anahtar ve port tek akışta seçilir
- Cloudflare Tunnel entegrasyonu
- Ekran yayını, dosya gönderme, uzaktan kapatma/yeniden başlatma ve web sitesi engelleme
- `.deb` iki sürüm: tam (internetsiz) ve hafif (internetten); açılış hataları ekranda gösterilir; eksik Qt bağımlılıkları tamamlandı
- Windows kurulum dosyası cykbilişim adına imzalandı

**İletişim:** cykdigital@outlook.com.tr

## Etik/yasal not
Bu araç öğrenci ekranlarını gösterir. Kullanmadan önce okul yönetiminden izin alın ve öğrencileri/velileri bilgilendirin.
