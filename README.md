[Uploading README.md…]()
# Optimuslock
**Yayıncı: cykbilişim** · cykdigital@outlook.com.tr

BT sınıfı için pencere tabanlı (tarayıcı gerektirmeyen) bilgisayar izleme, kilitleme ve yönetim programı.
Pardus/Linux ve Windows'ta çalışır. Python + PySide6.

## Özellikler
- **Öğretmen hesabı:** kurulum sırasında oluşturulan yerel bir hesap (ad, e-posta, parola); öğretmen paneli her açılışta bu bilgilerle giriş ister. Bulutta doğrulanmaz, yalnızca bu bilgisayara özgüdür.
- **Wake-on-LAN:** kapalı/uykudaki öğrenci bilgisayarlarını uyandırma (yalnızca aynı yerel ağda)
- **Canlı izleme:** tüm öğrencilerin ekran küçük resimleri; çift tıkla büyük canlı görünüm; açık uygulama listesi
- **Uzaktan müdahale:** canlı görünümde "Kontrolü Al" ile öğrencinin fare ve klavyesi kullanılabilir (bkz. aşağıdaki bölüm)
- **Sanal kilit:** tüm monitörleri kaplayan kilit ekranı + mesaj
- **Uygulama engelleme** (program adına göre) ve **web sitesi engelleme** (hosts dosyası; izin kurulum sırasında verilir — bkz. aşağıda)
- **Ekran yayını:** öğretmen ekranını öğrencilere gösterme
- **Dosya gönderme** (≤100 MB, öğrencide `Optimuslock-Gelen` klasörüne), **mesaj gönderme**
- **Uzaktan kapatma / yeniden başlatma / oturum kapatma** (öğretmen onayıyla)
- **Üç bağlantı yöntemi:** Tailscale · IP adresi · Cloudflare Tunnel
- **E-posta ile kurulum daveti:** öğretmen panelinden SMTP ile gönderilen bir koddan bağlantı ayarları otomatik dolar
- **Güncelleme denetimi:** tanımlı bir adresten yeni sürüm kontrolü; AppImage kurulumlarında yerinde güncelleme
- **Güvenlik:** tüm trafik sınıf anahtarıyla şifrelenir ve doğrulanır. Öğrenci tarafında **"Çıkış" seçeneği yoktur** —
  tepsi menüsünden program kapatılamaz; yalnızca **kaldırma** (`--kaldir`) sınıf anahtarını ister. Öğretmen bağlanınca
  öğrenci tarafında bildirim gösterilmez (sessiz, ama trafik yine şifrelidir).
- Docker (Tailscale / Cloudflare konteynerleri) **uygulama tarafından otomatik** kurulur; ayrı betik/komut yoktur

## Kurulum – tek sihirbaz
| Dosya | Hedef |
|---|---|
| `optimuslock-ogretmen_1.7.0_all.deb` | **Öğretmen bilgisayarı** — Pardus 23/25, Debian 12/13, Ubuntu 22.04+ |
| `optimuslock-ogrenci_1.7.0_all.deb` | **Öğrenci bilgisayarı** — aynı sistemler |
| `Optimuslock-Setup-1.7.0.exe` | Windows 10 (1703+) / 11, 64 bit (imzalı: yayıncı cykbilişim); rol sihirbazda seçilir |

Her `.deb` rolünü bilir: kurulum sihirbazı **rol sormaz**, doğrudan bağlantı yöntemiyle başlar. Python kütüphaneleri pakete
gömülüdür (internetsiz kurulur; uymazsa internetten denenir). Bir bilgisayarda yalnızca biri kurulabilir; diğerini kurmak onun yerine geçer.

**Pardus görsel kurulum sihirbazı (AppImage) — `optimuslockkurulum.cykbilisim.AppImage`:** Tek dosya; Python ve Qt kütüphaneleri içindedir
(Pardus 23/25 gibi x86_64 Linux). Çift tıklayınca Windows'takine benzer bir kurulum sihirbazı açılır:
*Hoş geldiniz → Kullanım bilgilendirmesi (onay) → Rol → Öğretmen hesabı (yalnızca öğretmen) → E-posta kurulum kodu (isteğe bağlı) → Bağlantı yöntemi → Ayrıntılar → Güvenlik → Kurulum seçenekleri (kapsam + web izni) → Özet → Kurulum (ilerleme çubuğu) → Bitir*.
- **Kurulum kapsamı:** *yalnızca bu kullanıcı için* (parola gerekmez; `~/.local/share/optimuslock`) ya da *tüm kullanıcılar için*
  (yönetici parolası istenir; `/opt/optimuslock`, ayarlar ve otomatik başlatma tüm hesaplarda geçerli olur).
- Menüye **Optimuslock** girdisi, isteğe bağlı masaüstü kısayolu ve (öğrenci için) otomatik başlatma eklenir; **Bitir**'de uygulama başlatılabilir.
- **Tek tıkla çalıştırma:** `optimuslockkurulum.zip` dosyasını indirip Pardus'un kendi arşiv aracıyla (sağ tık → *Buraya Çıkart*)
  açın; `.AppImage` dosyası zaten çalıştırma izniyle gelir, çift tıklayınca doğrudan açılır — ayrıca bir şey yapmanız gerekmez.
  Dosyayı doğrudan (zip'siz) indirirseniz tarayıcılar güvenlik gereği çalıştırma iznini sıfırlar; bu durumda bir kerelik
  sağ tık → Özellikler → *Çalıştırmaya izin ver* (ya da `chmod +x optimuslockkurulum.cykbilisim.AppImage`) gerekir.
- **Kaldırma:** `optimuslockkurulum.cykbilisim --kaldir` (kurulu kopyayla çalıştırın). **Sınıf anahtarını sorar.** Öğrenci
  tarafında program içinde bunun dışında bir kapatma yolu yoktur — tepsi menüsünde "Çıkış" bilerek bulunmaz. Sistem geneli
  kurulumda ayrıca yönetici parolası da istenir. Ayarlar `~/.config/optimuslock` içinde kalır. (`.deb` paketlerinde kaldırma
  `sudo apt remove optimuslock-...` iledir; zaten sistem yöneticisi parolası gerektirdiğinden ayrıca sınıf anahtarı
  sorulmaz. Windows'ta *Uygulamalar ve özellikler*'den kaldırmak için de yönetici onayı istenir.)
- AppImage açılmazsa: `sudo apt install libfuse2` ya da `APPIMAGE_EXTRACT_AND_RUN=1 ./optimuslockkurulum.cykbilisim.AppImage`.
- Hata olursa nedeni ekranda gösterilir ve `~/.config/optimuslock/optimuslock.log` dosyasına yazılır. Gereksinim: glibc 2.34+ (Pardus 23/25).

**Windows:** `.exe`'yi çalıştırın. Sihirbaz sırayla sorar: **rol** (öğrenci/öğretmen) → **bağlantı yöntemi** →
Tailscale auth key veya Cloudflare tünel token'ı → **sınıf anahtarı**, port, otomatik başlatma. Bitince masaüstü simgesiyle başlatın;
ayrıca bir kurulum ekranı açılmaz. Güvenlik duvarı kuralı ve otomatik başlatma sihirbaz tarafından eklenir.

*Toplu/sessiz kurulum:*
`Optimuslock-Setup-1.7.0.exe /S /ROLE=student /MODE=ip /KEY=anahtar123 /PORT=5710 /AUTOSTART=1`
(diğer parametreler: `/TSVIA=docker|native /TSAUTH= /TSHOST= /CFTOKEN= /CFHOST=`). Sessiz kurulumda anahtarda **boşluk kullanmayın**.

**Windows yetki (UAC) ekranında yayıncı adı:** Windows yayıncı adını yalnızca dijital imzadan gösterir. Kurulum dosyası
*cykbilişim* adına imzalıdır; ancak sertifika kendinden imzalı olduğundan, **sertifikayı güvenen bilgisayarlarda** (yönetici CMD)
"Doğrulanmış yayıncı: cykbilişim" görünür:
`certutil -addstore -f Root cykbilisim-sertifika.cer` ve `certutil -addstore -f TrustedPublisher cykbilisim-sertifika.cer`
(okul bilgisayarlarına grup ilkesiyle de dağıtılabilir). Güvenmeyen bilgisayarlarda "Bilinmeyen yayıncı" görünmeye devam eder;
herkes için çözüm, bir sertifika otoritesinden satın alınan kod imzalama sertifikasıdır.

**Pardus/Linux:** `sudo apt install ./optimuslock-ogretmen_1.7.0_all.deb` (öğretmen) veya `./optimuslock-ogrenci_1.7.0_all.deb` (öğrenci). Menüden **Optimuslock**'u açın; ilk açılışta sihirbaz gelir.

Komut satırına girmek istemiyorsanız, iki `.deb` dosyasıyla **aynı klasöre** `optimuslock-kur.sh` dosyasını koyup çalıştırın: `./optimuslock-kur.sh` (rolü sorar) ya da doğrudan `./optimuslock-kur.sh ogretmen` / `./optimuslock-kur.sh ogrenci`. Betik doğru `.deb`'i kendisi bulur ve `sudo apt install` ile kurar; yönetici parolası istenir.
Hata olursa nedeni ekranda gösterilir ve `~/.config/optimuslock/optimuslock.log` dosyasına yazılır.

**Kaynaktan çalıştırma:** `pip install -r requirements.txt` ardından `python optimuslock.py` (Pardus'ta önce `sudo apt install python3-venv python3-pip libxcb-cursor0`).

## Bağlantı yöntemleri
- **IP:** aynı yerel ağ. Öğretmen panelinde *Ağı Tara (IP)* veya *IP Ekle*. Öğrencide seçilen port açık olmalı (Windows sihirbazı kuralı ekler).
  **Okulda bazı bilgisayarlar kablolu, bazıları kablosuz (farklı alt ağ) ise** tarama her ikisini de bulamayabilir — bunun
  için **okul sunucusu** özelliğini kullanın (bkz. aşağıdaki bölüm): tarama yerine öğrenciler kendilerini otomatik bildirir.
- **Tailscale:** *Docker* (önerilen; konteyner uygulama açılırken kendiliğinden başlar) ya da bilgisayardaki Tailscale uygulaması.
  Auth key: https://login.tailscale.com/admin/settings/keys . Windows'ta Docker Desktop açık olmalı.
- **Cloudflare Tunnel:** Öğrencide: Cloudflare Zero Trust → Networks → Tunnels'ta tünel oluşturup token'ı sihirbaza girin; tünele
  *Public hostname* ekleyin (Service = **TCP**, URL = `localhost:5710`; Windows + Docker Desktop'ta `host.docker.internal:5710`).
  Öğretmen panelinde *Tünel Öğrencisi Ekle* ile her öğrencinin alan adını (ör. `pc01.okul.com`) girin. Öğretmen bilgisayarında
  `cloudflared` ya da Docker gerekir (uygulama otomatik seçer).

## Uzaktan müdahale (fare/klavye kontrolü)
Öğrenci küçük resmine çift tıklayıp büyük canlı görünümü açın, üstteki **Kontrolü Al** düğmesine tıklayın. Bundan sonra pencere
içindeki fare hareketi/tıklaması, tekerlek kaydırması ve klavye (yazılabilir karakterler + Enter/Backspace/Tab/Esc/Delete/ok
tuşları/Space/Home/End) öğrencinin bilgisayarında uygulanır. **Kontrolü Bırak**'a basınca ya da pencereyi kapatınca durur.
- Öğrenci ekranının üstünde kırmızı bir şerit her zaman görünür: *"Öğretmen bu bilgisayarı uzaktan yönetiyor"*. Bu şeffaflık
  kasıtlıdır ve kapatılamaz.
- Gecikme ağ durumuna göre birkaç yüz milisaniyeye kadar çıkabilir; oyun kumandası hassasiyetinde değildir, temel müdahale
  (bir pencereyi kapatmak, bir ayarı değiştirmek, yazı yazmak) için yeterlidir.
- Karmaşık tuş kombinasyonları (Ctrl+Alt+Del, Alt+Tab gibi) desteklenmez; yalnızca tek karakterler ve listedeki özel tuşlar.
- Öğrenci tarafında `pynput` kütüphanesi gerekir (tüm paketlerde gömülüdür); Linux'ta yalnızca X11 oturumunda çalışır.
- 90 saniye öğretmenden haber alınmazsa (bağlantı koptuysa) kilit ve engellerle birlikte kontrol da otomatik sona erer.

## Web sitesi engelleme izni
Özellik, öğrenci hesabının `hosts` dosyasına yazabilmesini gerektirir. Bu izin artık **kurulum sırasında otomatik verilir**,
ayrıca bir şey yapmanız gerekmez:
- **Windows ve `.deb` paketleri:** kurulum zaten yönetici yetkisiyle çalıştığından izin sorulmadan verilir.
- **AppImage:** Kurulum seçenekleri sayfasında "Web sitesi engelleme izni şimdi verilsin" işaretliyse (varsayılan açık),
  ayrı bir yönetici parolası istenir (yalnızca bu adım için; "yalnızca bu kullanıcı" kapsamını seçseniz bile).
- İzin verilmemişse veya sonradan geri alınmışsa panelde `[WEB: yetki yok]` görünür; Linux'ta elle vermek için:
  `sudo setfacl -m u:KULLANICI_ADI:rw /etc/hosts`

## E-posta ile kurulum daveti
Öğretmen panelinde **Yardım → E-posta ile kurulum daveti** (veya araç çubuğundaki **E-posta Daveti**): SMTP bilgilerinizi
(ör. `smtp.office365.com`, port 587, STARTTLS, `cykdigital@outlook.com.tr` + uygulama parolası) girin, öğrenci e-postalarını
alt alta yazın, **Gönder**'e basın. Her öğrenciye geçerli bağlantı ayarlarını (yöntem, port, sınıf anahtarı, varsa Tailscale
auth key) içeren bir "kurulum kodu" (`OPL1:...`) gider.
- Öğrenci, kurulum sihirbazındaki **"E-posta kurulum kodu"** sayfasına bu kodu yapıştırır; sonraki sayfalar otomatik dolu
  gelir. Kurulumdan sonra da tepsi menüsünden **"E-posta kodundan ayarla..."** ile uygulanabilir.
- **Önemli:** kod sınıf anahtarını (şifrelemenin temeli) açık biçimde içerir. Yalnızca gerçek öğrenci adreslerine gönderin;
  e-posta hesabının güvenliği sizin sorumluluğunuzdadır. Bu, canlı bir kimlik doğrulama sistemi değil, ayarları güvenli
  biçimde dağıtan bir yöntemdir — Cloudflare tüneli her öğrencide farklı olduğundan, o alan hiç kodun içine konmaz.
- SMTP parolası varsayılan olarak kaydedilmez (her seferinde girilir); "Parolayı bu bilgisayarda sakla" işaretlenirse düz
  metin olarak yerel ayarlarda tutulur.

## Güncelleme sistemi
Optimuslock'un kendiliğinden erişebileceği bir güncelleme sunucusu yoktur; **cykbilişim'in kendi barındırdığı** bir
`update.json` adresi gerekir. Öğretmen panelinde **Yardım → Güncelleme adresini ayarla** ile bu adresi girin (e-posta kodu
içine de eklenebilir, böylece öğrencilerde otomatik ayarlanır). Dosya biçimi:
```json
{
  "version": "1.7.0",
  "notes": "Bu sürümde neler değişti",
  "download_page": "https://cykbilisim.com/optimuslock/indir",
  "appimage": {"url": "https://.../optimuslockkurulum.cykbilisim.AppImage", "sha256": "<dosyanın sha256 özeti>"}
}
```
- Hem öğretmen hem öğrenci açılışta sessizce denetler; yeni sürüm varsa durum çubuğunda/tepside bir satır görünür.
  **Yardım/tepsi menüsünden "Güncellemeleri denetle"** ile elle de denetlenebilir.
- **AppImage** kurulumlarında "Şimdi güncelle" dosyayı indirir, `sha256` ile doğrular ve kurulu kopyanın **yerine koyar**
  (sistem geneli kurulumda yönetici parolası ister). `sha256` alanı olmadan indirme reddedilmez ama doğrulama da yapılmaz —
  alanı daima doldurmanız önerilir.
- **Windows `.exe` ve `.deb`** için otomatik değiştirme yapılmaz; "İndirme sayfasını aç" tarayıcıyı `download_page`
  adresine açar, yeni sürümü siz kurarsınız.
- `update_url` boşsa hiçbir denetim yapılmaz (varsayılan budur).

## Öğretmen hesabı ve giriş
Kurulum sihirbazında rol **Öğretmen** seçilince (ya da öğretmen paketinde otomatik) bir "Öğretmen hesabı" sayfası gelir:
Ad Soyad, E-posta, Parola. Bu bilgiler yalnızca **bu bilgisayarda**, parola asla düz metin olarak değil PBKDF2 ile
özetlenerek saklanır — bulutta bir sunucuya gönderilmez, cihazlar arasında paylaşılmaz. Öğretmen paneli her açıldığında
bu e-posta/parola sorulur (5 yanlış denemeden sonra uygulama kapanır). **Parolayı unutursanız:** kurulum sihirbazını
`--setup` ile yeniden çalıştırıp hesabı sıfırlayabilirsiniz (işletim sistemi oturumunuza zaten erişiminiz olduğundan bu
kasıtlıdır — Optimuslock, bilgisayarınıza fiziksel/OS erişimi olan birine karşı değil, panele rastgele erişime karşı korur).
Öğrenci bilgisayarlarında hesap sayfası hiç çıkmaz (gerek yoktur).

## Okul sunucusu (kablolu + kablosuz karışık ağlar için)
Bir okulda bazı bilgisayarlar kabloyla, bazıları Wi-Fi ile (çoğunlukla **farklı bir alt ağ/VLAN** üzerinden) bağlanıyorsa,
öğretmenin "Ağı Tara (IP)" ile tek seferde her ikisini de bulması mümkün olmayabilir (tarama tek bir IP aralığına bakar).
**IP bağlantı yönteminde** bunu çözmek için: öğrenci kurulum sihirbazında **"Öğretmen bilgisayarı IP'si"** alanına öğretmenin
IP adresini yazın (ör. `10.0.5.20`). Bundan sonra:
- Öğretmen uygulaması, kendi IP portunun bir fazlasında (`port + 1`, varsayılan **5711**) sessizce bir **okul sunucusu**
  (kayıt servisi) çalıştırır.
- Öğrenci, açılışta ve her 30 saniyede bir bu adrese bağlanıp kendini (ad, MAC, port) **otomatik bildirir** — sınıf
  anahtarıyla şifrelenmiş, doğrulanmış bir bağlantıdır; farklı alt ağda olsa da okul ağında normal yönlendirme (routing)
  olduğu sürece çalışır (çoğu okul ağında kablolu/kablosuz segmentler zaten aynı internet geçidini paylaştığı için
  birbirine yönlendirilmiştir — yayın/broadcast gerekmez, sıradan bir bağlantıdır).
- Öğretmen panelinde bu öğrenci **otomatik olarak listeye eklenir**, ayrıca taramaya ya da elle IP girmeye gerek kalmaz.
- Öğretmen bilgisayarında bu yeni port (`5711`) için de güvenlik duvarı izni gerekir — Windows kurulum sihirbazı bunu
  otomatik ekler; Pardus'ta güvenlik duvarı (ufw vb.) açıksa `sudo ufw allow 5711/tcp` gerekebilir.
- Bu alan boş bırakılırsa davranış tamamen eskisi gibidir (tarama/elle ekleme).
- Tailscale veya Cloudflare Tunnel kullanıyorsanız bu özelliğe gerek yoktur; onlar zaten alt ağ farkı gözetmeden çalışır.

## Wake-on-LAN
Öğretmen panelinde bir veya birden fazla öğrenci seçip **Uyandır (WOL)**'a tıklayın. MAC adresi, öğrenci bir kez
bağlandığında (ya da okul sunucusuna kaydolduğunda) otomatik öğrenilir; hiç bağlanmamışsa **MAC Adresi Düzenle** ile elle
girebilirsiniz (ör. cihaz etiketinden).

Optimuslock her uyandırmada **iki paket** gönderir: biri genel yayın (`255.255.255.255`, öğretmenle aynı alt ağdakiler
için), biri de öğrencinin **son bilinen IP'sinin alt ağına yönelik** yayın (ör. `10.0.5.255`) — bu ikincisi, kablosuz gibi
**farklı bir alt ağdaki** bilgisayarı uyandırmayı dener. **Bunun gerçekten işe yaraması için okul ağının yönlendiricisinde/
L3 switch'inde "directed broadcast" (yönlendirilmiş yayın) iletiminin açık olması gerekir** — bu bir ağ yöneticisi ayarıdır,
çoğu tüketici/ev tipi router'da kapalıdır ama okul/kurumsal ağ cihazlarının çoğunda (Mikrotik, Cisco, pfSense vb.) mevcuttur;
okulunuzun ağ yöneticisinden "WOL için directed broadcast" veya "ip directed-broadcast" özelliğini ilgili alt ağ için
açmasını isteyin. Bu ayar yapılmadan, farklı alt ağdaki kapalı bir bilgisayar WOL ile uyandırılamaz — bu yazılımın değil,
ağ donanımının bir sınırıdır.

Her durumda öğrenci bilgisayarının BIOS/UEFI'sinde ve işletim sisteminde "Wake on LAN" / "Wake on magic packet" ayarının
açık olması, ayrıca ağ kablosunun (kablosuz WOL güvenilir değildir) takılı olması gerekir.

## Bilinen sınırlar
- Pardus'ta **X11 oturumu** gerekir (Wayland'de ekran yakalama/kilit/müdahale çalışmaz; başlatıcı XWayland'i kullanır).
- Kilit ekranı sert kilit değildir (Windows tuşu, Ctrl+Alt+Del engellenemez). Uygulama engelleme süreç adına göredir.
- Tepsi menüsünde "Çıkış" olmaması uygulamayı kapatılamaz yapmaz: Görev Yöneticisi/`taskkill` (Windows) ya da `kill`/Sistem
  İzleyici (Linux) ile teknik bilgisi olan bir öğrenci süreci sonlandırabilir. Bu, işletim sistemi düzeyinde bir sınırdır;
  tamamen engellemek için ajanın yönetici yetkisiyle çalışan bir sistem hizmeti olması gerekir (bu sürümde yok).
- DNS-over-HTTPS kullanan tarayıcılar web engellemeyi atlayabilir; ağ düzeyinde DNS filtreleme daha sağlamdır.
- Sınıf anahtarı öğrenci bilgisayarında saklanır; teknik bilgisi olan bir öğrenci okuyabilir. Daha sert koruma için ajanın hizmet olarak çalışması gerekir.
- Windows `.exe` *cykbilişim* adına imzalıdır ama sertifika kendinden imzalıdır; sertifika bilgisayara ayrıca tanıtılmadıkça
  SmartScreen "Bilinmeyen yayıncı" uyarısı verebilir (bkz. kurulum bölümü).
- Yalnızca ilk monitör izlenir/yayınlanır/kontrol edilir (kilit tüm monitörleri kaplar).
- E-posta gönderimi ve güncelleme denetimi internet erişimi gerektirir; okul ağı dışarıyı engelliyorsa çalışmaz.

## Sürüm notları
**1.7.0**
- Okul sunucusu (kayıt servisi) eklendi: kablolu/kablosuz farklı alt ağdaki öğrenciler artık taramaya gerek kalmadan
  kendilerini öğretmene otomatik bildirir (IP yönteminde, isteğe bağlı "Öğretmen bilgisayarı IP'si" alanı ile)
- Wake-on-LAN artık öğrencinin kendi alt ağına yönelik yayın da gönderir (yönlendiricide "directed broadcast" açıksa
  farklı alt ağdaki bilgisayarları da uyandırabilir)
- Windows kurulum sihirbazı, öğretmen rolünde okul sunucusu portu (varsayılan 5711) için güvenlik duvarı kuralı ekler

**1.6.2**
- AppImage dosyası `.AppImage` uzantısıyla adlandırıldı (`optimuslockkurulum.cykbilisim.AppImage`) ve çalıştırma izni
  korunarak `optimuslockkurulum.zip` içinde de sunuluyor — arşivden çıkarınca çift tıkla doğrudan açılır

**1.6.1**
- Öğrenci tepsi menüsünden "Çıkış" seçeneği tamamen kaldırıldı; program yalnızca kaldırma (`--kaldir`, sınıf anahtarı ister) ile durdurulabilir

**1.6.0**
- Kurulum sırasında öğretmen hesabı oluşturma (ad/e-posta/parola) ve panelde giriş ekranı
- Wake-on-LAN: öğretmen panelinden kapalı/uykudaki öğrenci bilgisayarları uyandırma; MAC otomatik öğrenilir/elle girilebilir

**1.5.0**
- Uzaktan müdahale: canlı görünümde "Kontrolü Al" ile öğrencinin fare/klavyesi kullanılabilir; öğrenci ekranında şeffaflık şeridi
- E-posta ile kurulum daveti (SMTP) ve sihirbaz/tepsi menüsünde "e-posta kodu" uygulama
- Güncelleme sistemi: `update.json` denetimi, AppImage'de yerinde güncelleme
- Çıkış artık parola istemez; parola yalnızca kaldırmada istenir
- Öğretmen bağlanınca "bağlandı" bildirimi kaldırıldı
- Web sitesi engelleme izni artık kurulum sırasında otomatik verilir (Windows/`.deb` otomatik; AppImage'de seçime bağlı)

