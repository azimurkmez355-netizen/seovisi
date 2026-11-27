# seovisi

Ideasoft e-ticaret mağazaları için SEO ve katalog bakım uygulaması. Hedef: Ideasoft App Store'da her sektöre satılan,
yıllık abonelikli bir uygulama. Kararlar, ilk sürüm (v1) listesi, Ideasoft'a sorulacaklar ve fazlar `YOL_HARITASI.md` içinde;
yeni bir işe başlamadan önce oraya bak ve biten maddeleri [x] yap.

## Kullanıcıyla çalışma

- Kullanıcı Türkçe konuşur ve teknik değildir. Sade Türkçe yaz; her işin sonunda şu sırayla özetle:
  1. ne değişti,
  2. ekranda nerede görülür,
  3. kullanıcının yapması gereken.
- Commit yalnızca kullanıcı isteyince yapılır.
- Kullanıcı "konuşalım" dediğinde kod yazma, komut çalıştırma; önce konuşarak netleştir.
- Gerçek mağazaya (Ustapazar) asla test amaçlı yazma. Testler yalnızca sahte Ideasoft ve kopya / uydurma veriyle yapılır.
- Proje klasöründeki `data/` kullanıcının kendi çalışan kurulumu olabilir (programı buradan açıp gerçek mağazasına bağlanıyor).
  İçindekileri asla silme, taşıma ya da değiştirme; test artığı gibi görünse bile önce `islem.log` tarihlerine bak ve kullanıcıya sor.

## Kurulum ve çalıştırma

- Yalnızca Python 3.8+ standart kütüphanesi; dışarıdan paket yok.
- Yerel kip: `baslat.bat` ya da `python app.py`. Panel http://localhost:8765 adresinde açılır; giriş istemez.
  Mağazanın kendi Ideasoft API anahtarıyla çalışır.
- Sunucu kipi: `python app.py --sunucu --port 8080 [--host 127.0.0.1]`. Mağazalar Ideasoft OAuth ile giriş yapar;
  oturum imzalı bir çerezle (`sv`) tutulur. `data/sunucu.json` dosyasında `client_id`, `client_secret` ve `public_url`
  bulunmalı. Ideasoft'taki yönlendirme adresi `<public_url>/callback` olur.
- Testler: `python -X utf8 testler/hepsi.py` (hepsi) ya da `--hizli` (yalnızca birim testleri). Gerçek Ideasoft'a hiç istek gitmez.
  - `test_seo_metin.py`, `test_aciklama.py`: metin üreticileri ve SEO kuralları.
  - `test_sifre.py`: şifreleme ve ayar dosyalarındaki gizli bilgiler.
  - `test_hiz.py`: hız sınırı, adil sıra, 429 ve paralel işlerde mağaza bağlamı.
  - `test_abonelik.py`: paketler, abonelik kaydı ve yazma izni (geçici paket dosyasıyla).
  - `test_sablon.py`: açıklama şablonu; varsayılanın eski açıklamaları birebir üretmesi, SEO sayımının kaymaması.
  - `test_uyari.py`, `test_kopya.py`, `test_baglanti.py`: uyarı, kopya ve kırık bağlantı kuralları.
  - `test_gecis.py`: toplu şablon geçişi ve SEO geri alma.
  - `test_rapor.py`: aylık rapor, olay kaydı, haftalık tarama.
  - `test_yedek.py`: günlük yedek.
  - `test_yonetim.py`: yönetici parolası, çerezi ve hata listesi.
  - `test_ortam.py`: ortam değişkenlerinden sunucu ayarları ve yönetici parolası, müşteri adresi başlığı (`SEOVISI_IP_BASLIGI`).
  - `test_silme.py`: uygulama kaldırılınca işaretleme, iptal ve süre dolunca silme (geçici klasörde).
  - `test_platform.py`: platform adaptörü sınırı (app.py'de Ideasoft adresi ve doğrudan istek yok), Ideasoft adaptörünün arayüzü.
  - `test_panel.py`: panel ve yönetici sayfası betiklerinin sözdizimi (Node.js varsa), yinelenen üst düzey adlar ve öğe kimlikleri.
  - `test_eknot.py`: ek not; notun üretimi, tanınması, kategori grubu, SEO koruması, ekle / güncelle / kaldır, yazma güvenliği.
  - `test_blog.py`: blog yazarı (13 kural her biçimde, ürün kodu / barkod / mağaza adı, hariç kategoriler), hazırlama yazmaz, gönderim / güncelleme / yayından kaldırma, %100 olmayan ve bozuk görselli yazı gönderilmez.
  - `test_blog_kalite.py`: anahtar kelime araştırması (model bölünmez, Google talebi, yamyamlaşma, önbellek), kalite kapısı
    (her biçim geçer, okunabilirlik, ürün kartı, iç bağlantılar), benzer ürünlerde kopya meta / içerik yok, blog otomasyonu
    (vakitler, seçili saatte bir kez, görselsiz / kalitesiz / izinsiz yayın yok, eski yazıya iç bağlantı, yayımlanan adres değişmez).
  - Testler `SEOVISI_TEST=1` ile çalışır (`hepsi.py` koyar): anahtar kelime araştırması Google'a istek göndermez.
  - `test_otopilot.py`: yeni ürün otopilotu (bellekteki sahte mağaza; kategori analizinin kararını belirleyen `guclu_oneri`).
  - `hepsi.py` testlerin projenin `data` klasörünü oluşturmadığını da denetler.
  - `test_yazma_guvenligi.py`: bellekteki sahte Ideasoft ile yazma güvenliği, yedek ve geri alma. Yazma koduna dokunan her değişiklikte buraya test ekle.
  - `test_cok_magaza.py`: uygulamanın kendisini iki sahte mağazayla (`sahte_ideasoft.py`) çalıştıran betik.
  - GitHub'da her push'ta `.github/workflows/testler.yml` çalışır (Python 3.8 ve 3.13, Linux ve Windows).
  - Commit öncesi kanca `.githooks/pre-commit`; bir kez `git config core.hooksPath .githooks` ile açılır.
    Yeni klonda kancanın çalıştırılabilir kalması için ilk eklemede `git add --chmod=+x .githooks/pre-commit`.

- Sunucu kurulumu: `Dockerfile`, `docker-compose.yml` (canlı + test + Caddy + yedek), `Caddyfile`, `.env.ornek`; adımlar `KURULUM.md`.
  Kap içinde `SEOVISI_VEKIL` Docker ağını güvenilen ters vekil yapar (`guvenilir_vekil`); `/saglik` dış izleme içindir.
  `python app.py --yedek KLASOR [--dongu] [--sakla 14]`. GitHub'daki "docker" işi görüntüyü kurup çalıştırarak denetler.
- Railway (deneme dönemi; `KURULUM.md` A): `railway.json` Dockerfile ile kurar, sağlık `/saglik`. Dosya düzenlenemediği için
  `ortamdan_ayarla()` açılışta `SEOVISI_CLIENT_ID`, `SEOVISI_CLIENT_SECRET`, `SEOVISI_PUBLIC_URL` değerlerini `sunucu.json`a,
  `SEOVISI_YONETICI_PAROLA`yı (farklıysa) `yonetici.json`a yazar. Sunucu kipinde `--port` yoksa `PORT` ortam değişkeni. Railway
  müşteri adresini `X-Real-IP` ile verir (`SEOVISI_IP_BASLIGI`); disk root ile bağlandığı için `RAILWAY_RUN_UID=0`. Yedek Railway'in kendisinde.
  Her push yeniden kurar; veri yalnızca `/app/data`ya bağlı volume ile korunur. `veri_kalicilik()` bunu denetler (Railway'de
  `RAILWAY_VOLUME_MOUNT_PATH`); `/saglik` `kalici_disk` ve açılış sayısını (`data/acilis.json`) verir, yönetici panelinde uyarı çıkar.

## Mimari

| Dosya | Görevi |
|---|---|
| `app.py` | Web sunucusu (`http.server`), taramalar ve arka plan işleri, uygulama / geri alma, yazma güvenliği, oturum |
| `platformlar/` | Platform adaptörleri. `__init__.py`: ortak arayüz (`Platform`), `ApiError`, `store_host`, kayıt (`PLATFORMLAR`). `ideasoft.py`: Ideasoft girişi, anahtar, istek gönderme ve kaynak işlemleri. |
| `kategori.py` | Kategori analizi. Ürün adlarından öğrenen sınıflandırıcı (Naive Bayes + kategori adı benzerliği); yanlış ve kategorisiz ürünler, yeni kategori önerileri. Sektöre özel kelime listesi yok; yaygın ve "seri" kelimeler mağazanın kendi verisinden çıkarılır. |
| `seo_text.py` | Başlık, meta açıklama, anahtar kelimeler, kelime sayımı, SEO puanı. `panel_factor()` mağaza ayarından okunur. |
| `seo_machine.py` | Ürün açıklaması (HTML) üretimi. Hedef kelime yoğunluğunu %2–3 aralığına oturtur; görünüm ve bölümler şablondan. |
| `sablon.py` | Açıklama şablonu: görünümler, renk, bölümler, madde işareti, kapanış; stillerin SEO sayımını sabit tutar. |
| `sifre.py` | Diskteki gizli bilgilerin şifrelenmesi (HMAC-SHA256 sayaç kipi + HMAC imza). Ana anahtar `SEOVISI_ANAHTAR` ortam değişkeninden, yoksa `data/anahtar.key` dosyasından. |
| `abonelik.py` | Abonelik kaydı (mağaza klasöründe `abonelik.json`), geçerli paket ve yazma izni. Paketler `paketler.json` içinde. |
| `uyari.py` | Ürün uyarıları (yalnızca okur): fiyatı 0, hatalı indirim, alış fiyatı altı, kategorisine göre aşırı fiyat, yayında ama stokta yok. |
| `kopya.py` | Kopya ürün grupları (yalnızca okur): aynı stok kodu, barkod, ad, sayfa başlığı, meta açıklama. |
| `baglanti.py` | Kırık bağlantı taraması: herkese açık siteyi gezer (ana sayfa, site haritası, robots.txt); ağ erişimi dışarıdan verilir. |
| `rapor.py` | Aylık rapor hesabı: olay sayıları ve durum fotoğraflarının ay başı / ay sonu karşılaştırması. |
| `yedek.py` | Günlük yedek: data klasörünün tutarlı zip kopyası (anahtar hariç), eski yedeklerin silinmesi. |
| `yonetim.py` | Yönetici paneli yardımcıları: parola karması (`data/yonetici.json`), oturum çerezi, kayıtlardaki hatalar. |
| `eknot.py` | Ek not: ürün açıklamasının sonuna eklenen not ve bağlantının HTML'i, tanınması / çıkarılması, SEO etkisi (yalnızca hesaplar). |
| `blog.py` | Blog yazarı: ürün başına Ideasoft'un 13 blog kuralını tutan yazı (6 biçim), başlık / meta / özet, yoğunluk ayarı, iç bağlantılar, ürün kartı, blog görseli ayarları. Yalnızca hesaplar. |
| `kelime.py` | Blog hedef kelimesi araştırması: ürün adından adaylar, Google arama önerileri (hız sınırı, hata kesici), yerel puan, yamyamlaşma cezası. |
| `kalite.py` | seovisi kalite kapısı: kendi SEO puanı, Türkçe okunabilirlik (Ateşman), meta / içerik özgünlüğü (MinHash dizini), sınırlar (`SINIRLAR`). Yalnızca hesaplar. |
| `profil.py` | Mağaza profili (mağaza adı, varsayılan marka) ve Türkçe ekler (`loc`, `gen`). |
| `ui/index.html` | Tek sayfalık panel; saf JS (`$`, `api`, `post`, `ask`, `show`). Bütün betik tek kapsamda: yeni üst düzey ad ve öğe kimliği var olanlarla çakışmamalı (`test_panel.py`). |
| `ui/giris.html` | Mağaza giriş sayfası (sunucu kipi, oturumsuz `/`). Koyu, hareketli; `login_page()` hata iletisini `HATA_ALANI` yerine yazar (dosyada bu ad tek kez geçmeli). Çerçeve içi kapı girişi betiği buradadır. |
| `ui/yonetim.html` | Yönetici paneli (`/yonetim`); mağaza panelinden ayrı, tek sayfa. Giriş koyu ve altın vurgulu ("Yönetici konsolu"); panel açık temalı, sol menü ve `#genel`, `#magazalar`, `#abonelikler`, `#hatalar` sayfaları; abonelik formu ve silme sağdan açılan çekmecede. |
| `ui/marka/` | Logo (açık ve koyu zemin), simge, renkler ve Plus Jakarta Sans yazı tipi (`/marka/` altında; dışarıdan yazı tipi yüklenmez). |

### Çok mağaza yapısı

- Her mağazanın ayarları (`ayarlar.json`), veritabanı (`durum.db`, SQLite) ve kaydı (`islem.log`) `data/magazalar/<mağaza-alan-adı>/` klasöründe durur.
- Kodun geneli `CFG`, `DBI`, `API`, `SEOSCAN`, `CATSCAN`, `CATJOBS`, `SEOJOBS`, `IMG`, `OTO` adlarını tek mağaza varmış gibi kullanır. Bunlar `_Ref` vekilleridir ve o anki iş parçacığının mağazasına (`_cur.t`, bir `Tenant`) yönlenir; okuma da atama da (`CATSCAN.running = True`) o mağazanın nesnesine gider.
- İstek işleyicisi (`H._dispatch`) mağazayı oturumdan ya da yerel kipte `LOCAL["id"]` değerinden seçer.
- Arka plan işleri `spawn()` ile başlatılır ve başlatan mağazanın bağlamını taşır. **Yeni arka plan işlerinde `threading.Thread` yerine mutlaka `spawn()` kullan.**
  Paralel işler için de `ThreadPoolExecutor` yerine `pmap()`; yoksa iş parçacıkları "Mağaza seçilmedi" hatası verir.
- Ideasoft'a giden her istek platformun `call`'ı içinde `THROTTLE.acquire(mağaza)` ile izin alır (`_PlatformOrtami.izin`): mağaza başına ve toplam dakikalık sınır
  (`sunucu.json`: `hiz_magaza_dk`, `hiz_toplam_dk`; varsayılanlar tahmin). Toplam sınırda mağazalar sırayla izin alır. 429 gelirse
  `THROTTLE.pause()` o mağazanın bütün işlerini `Retry-After` kadar bekletir. Ideasoft'a başka yoldan istek gönderme.
- Eski kurulumdaki `data/ayarlar.json` ve `durum.db`, ilk açılışta `migrate_legacy()` ile mağaza klasörüne taşınır.

### Gizli bilgiler

- `Config.SECRET` alanları (`access_token`, `refresh_token`, `client_secret`, `secret`) diskte `sifreli:v1:` ile başlayan
  şifreli metin olarak durur; programın geri kalanı `CFG.get()` ile düz metin görür. Yeni bir gizli ayar eklenirse bu listeye ekle.
- Eski kurulumdaki düz metin değerler ilk açılışta şifrelenir. Açılamayan değer (anahtar kaybı) silinmez; mağaza yeniden bağlanana kadar
  bağlantı yok sayılır.
- Testler anahtarı geçici klasörde üretir (`sifre.KEY_PATH`); projenin `data` klasörüne test yazmamalı.

### İstek güvenliği (`app.py`, "istek güvenliği" bölümü)

- İstek gövdesi en çok `MAX_BODY` (5 MB); fazlası ya da bozuk `Content-Length` okunmadan 413 döner. Gövdeyi her zaman `H._body()` ile oku.
- Her yanıtta `H._security_headers()`: CSP, `nosniff`, `Referrer-Policy`, sunucuda HTTPS ise HSTS. Panel yalnızca `frame_ancestors()`
  adreslerinde çerçevede açılır: mağazanın kendi adresi, `FRAME_HOSTS` ve `sunucu.json`daki `frame_hosts`. Giriş sayfası her HTTPS sayfasında açılabilir.
  Panel dışarıdan yeni bir kaynak (yazı tipi, betik) yüklerse CSP'ye eklenmeli.
- `/giris` aynı adresten 10 dakikada en çok 20 deneme (`LOGIN_TRIES`). Adres, yerel ters vekil (Caddy) varsa `X-Forwarded-For`'un son değeri.
- `/giris` dışındaki her POST `X-Seovisi: 1` başlığı ister (panelin `api()` işlevi ekler); başka sitelerden sahte isteği keser.
  Oturum çerezi HTTPS'te `SameSite=None` olduğu için bu kontrol şart; hiçbir POST yolunu bundan muaf tutma.

### Giriş kapısı (`app.py`, "giriş kapısı" bölümü)

- Panel Ideasoft'un içinde (çerçevede) açılır. Ideasoft'un izin sayfası çerçevede açılmadığı için çerçevedeki giriş sayfası girişi
  yeni sekmede yapar; rastgele bir kapı kodu gönderir ve giriş bitince `/kapi/al` ile çerçeveye özel (`Partitioned`) çerezi alır.
  Kod tek kullanımlık, 5 dakika geçerli ve yalnızca girişi başlatan internet adresine verilir.
- `ideasoft_launch()`: Ideasoft panel açılışında imzalı mağaza bilgisi gönderiyorsa doğrulanacak yer; cevap gelene kadar hep `None`.
- Çerçevedeyken panelde "Tam ekran" bağlantısı görünür; çerez engelleyen tarayıcılarda panel kendi sekmesinde çalışır.

### Abonelik ve paketler

- Yalnızca sunucu kipinde geçerli; yerel kip (Ustapazar, geliştirme) sınırsızdır.
- `paketler.json`: paketler (ad, ürün sınırı, özellikler) ve yeni mağazanın başlangıç kaydı (`yeni_magaza`: ücretsiz ya da N günlük deneme).
  Dosya değişince yeniden başlatmadan okunur; düzenlerken bozulursa son geçerli hâli kullanılır. Fiyat burada yok (App Store'da).
- Her mağazanın kaydı `abonelik.json`; her istekte diskten okunur. Bütün kaynaklar `AB.yaz()` ile yazar. Bugün: yönetici paneli
  ya da `python app.py --abonelik magaza.com --paket baslangic --bitis 2027-10-31 [--durum aktif|deneme|iptal|ucretsiz]`, liste: `--abonelikler`.
- Süresi geçen, iptal edilen ya da tanınmayan kayıt ücretsiz analize düşer: analiz ve geri alma açık, mağazaya yazma kapalı.
- Mağazaya yazan her POST yolu `WRITE_ROUTES` içinde bir özelliğe bağlıdır; `route_post` başında denetlenir. **Yeni bir yazma yolu
  eklersen buraya da ekle.** Geri alma bilerek listede yok. Ürün sınırı taramalarda görülen ürün sayısıyla (`urun_sayisi()`) karşılaştırılır.

### Yönetici paneli (`app.py`, "yönetici paneli" bölümü)

- Yalnızca sunucu kipinde, `/yonetim` altında; mağaza oturumundan tamamen ayrı. Parola `python app.py --yonetici-parola` ile
  belirlenir, `data/yonetici.json`da yalnızca karması durur ve her girişte diskten okunur. Parola belirlenmeden panel kapalı.
- Çerez `svy`: `Path=/yonetim`, `SameSite=Strict`, 12 saat; imza parola karmasını da kapsar (parola değişince oturumlar kapanır).
  Giriş aynı adresten 15 dakikada en çok 10 deneme (`ADMIN_TRIES`). Sayfa hiçbir çerçevede açılmaz (`frame-ancestors 'none'`).
  Buradaki POST'lar da `X-Seovisi` başlığı ister.
- Mağaza listesi `yonetim_durum()`: abonelik, ürün sayısı, bağlantı, otopilot, süren işler, bugünkü Ideasoft isteği
  (`THROTTLE.bugun`), son işlem ve son 7 günün hataları (`islem.log`'daki `[err]` satırları). Hiç giriş yapmamış mağazanın
  klasörüne ayar yazılmaz (`tenant()` çağrılmaz). Abonelik `AB.yaz(..., kaynak="yonetici")` ile yazılır.
- İstek işlenirken beklenmeyen hata (500) mağazanın kaydına `err` olarak düşer; yönetici panelinde görünür.

### Uygulama kaldırılınca veri silme (`app.py`, aynı adlı bölüm)

- Yalnızca sunucu kipinde. Ideasoft yenileme anahtarını 400 / 401 ile reddederse `uygulama_kaldirildi()`: anahtarlar silinir,
  `kaldirildi` (zaman) ve `kaldirma_nedeni` ayarlanır, otopilot ve haftalık tarama durur. Ağ hatası ve 5xx işaretlemez.
  Ideasoft kaldırma bildirimi gelirse webhook da bu işlevi çağıracak.
- Yeniden bağlanınca (`save_token`) işaret kalkar. `silme_turu()` (zamanlayıcıda, saatte bir) `silme_gun` (sunucu.json, 30) dolan
  mağazanın klasörünü `magaza_sil()` ile tamamen siler; işi süren mağaza sonraki tura kalır. Silinenler `data/silme.log`'a.
- Yönetici panelinde kaldırılanlar ve silinecekleri gün görünür; "Verileri kalıcı olarak sil" (onay için adres yazılır) ve
  "Silmeyi iptal et".
- Yerel kurulumda (Ustapazar) hiçbir veri kendiliğinden silinmez; bu kural gevşetilmemeli.

### Kurulum sihirbazı ve hedef kelime yeri

- Yalnızca sunucuda, ilk girişte tam ekran açılır (`kurulum_gerekli()`, `ui/index.html` içinde `wOpen`): 1 mağaza adı ve marka,
  2 açıklama görünümü (şablonun görünüm seçimi, canlı önizleme), 3 ilk tarama ve özet, 4 paket bilgisi. Bitince ya da "Şimdilik geç"
  ile `/api/kurulum/bitti`. `kurulum_bitti` hiç yazılmamış ve taranmış mağazaya (bu ayardan önce kurulmuş) gösterilmez.
- Hedef kelime yeri `kw_loc()`: mağazanın keşfettiği, yoksa `sunucu.json`daki `kw_loc` (Ustapazar'da bulunan). Mağaza sahibi keşif yapmaz.
  Doğrudan `CFG.get("kw_loc")` kullanma.

### Açıklama şablonu (`sablon.py`)

- Mağaza ayarı `sablon`: görünüm (sade, bantlı, çizgili, kutulu), ana renk, bölümler (açık / kapalı, sıra, başlık), madde işareti,
  kapanış (açık / kapalı, kendi metni: `{urun}` hedef kelime, `{magaza}`), stok kodu ve barkod gösterimi. `app.sablon()` okur;
  kaydedilmediyse sunucuda sade, bilgisayardaki Ustapazar kurulumunda lacivert bantlı. Ayarlar > Açıklama şablonu ekranı (canlı önizleme,
  SEO puanı tahmini, sitenin tema rengi önerisi) ve sihirbazın görünüm adımı kullanır. `/api/settings` kısmi şablonu kayıtlıyla birleştirir;
  değişince hazırlanıp gönderilmemiş açıklamalar yeniden hazırlanır.
- Varsayılan şablon (sade ve bantlı #1b4f72) şablon sisteminden önceki açıklamaları birebir üretir; `test_sablon.py` parmak iziyle denetler.
- Her görünümün stilleri, panel katsayısı (1,30) ölçülürkenki bantlı görünümle aynı sayıda kelime üretir (`TPL.STYLE_WORDS`; her renk tek
  kelime). Ideasoft HTML'deki stilleri sayıyorsa farklı stil yoğunluğu yüzdeyi kaydırırdı. Yeni görünüm eklerken bu eşitliği koru.
  Ideasoft'un sayımı test mağazasında ölçülünce (stilli ve stilsiz aynı açıklama gönderilip paneldeki yüzde karşılaştırılarak) sınır kalkabilir.
- Tema rengi önerisi mağazanın ana sayfasını okur; yalnızca internetteki adreslere (`public_host`) ve yönlendirmelere izin verilir.

### Yeni ürün otopilotu (`app.py`, "yeni ürün otopilotu" bölümü)

- Mağaza ayarı `otopilot` (`oto_ayar()`): açık / kapalı, mod (onay | otomatik), otomatikte yapılacak işler (seo, kategorisiz, tasi).
  Paketlerde `otopilot` özelliği; ürün sınırı aşılınca da açılmaz (`Otopilot.izin`).
- Açılırken o ana kadarki son ürün numarası kaydedilir (`oto_son_id`); yalnızca daha yeni ürünler işlenir, eski ürünlere dokunulmaz.
- `oto_zamanlayici` / `oto_tur`: her mağazada en çok `otopilot_dk` (sunucu.json, 60) dakikada bir `kontrol()`. Yeni ürün `oto` tablosuna
  "bekliyor" girer; yayında (aktif) ve `OTO_BEKLE_DK` (30) dakika geçmişse işlenir; `OTO_PASIF_GUN` gün pasif kalan düşer.
- İşleme: SEO %100 değilse `prepare_plan`; kategori listesi tazelenir, yeni ürünler `catprod`a eklenir, analiz kayıtlı verilerle
  yeniden yapılır. Otomatikte yalnızca emin olunan öneriler (kategorisizde "güçlü", yanlış kategoride "taşı") yazılır; şüpheli,
  "olası" ve "ekle" önerileri onaya kalır. Yazma `send_plan` / `cat_fix` ile, her yazmadan önce `yazma_engeli` denetlenir.
- Kategori geri alması, ürün düzeltmeden önce kategorisizse onu yine kategorisiz bırakabilir (`apply_categories(bos_olabilir=True)`).

### Ek not (`eknot.py`, `app.py` "ek not" bölümü)

- Mağaza ayarı `ek_not`: açık / kapalı, simge, başlık, metin (`{urun}` hedef kelime), bağlantı yazısı ve adresi, kategoriler.
  Ürünler seçilen kategoriler ve alt kategorilerinden (`eknot_grup`), yerel taramalardan (`urunbilgi`, `catprod`). Tablo `eknot`:
  durum ('' eklenecek | eklendi | atlandi | hata | kaldirildi), haric, yazilan (o ürüne yazılan not), surum, yedek.
- Not `<div id="seovisi-not">`; işaret silinirse `yazilan` metniyle tanınır. Yazma `_seo_yaz(kw_yaz=False)` ile (hedef kelimeye
  dokunmaz); hedef kelime yoğunluğu kuralını notsuz tutup notla bozacak ürüne yazılmaz (`EN.etki`). Paket özelliği `ek_not`
  (`/api/eknot/yaz`); kaldırma geri almadır, paketten bağımsız. Yeni ürünler onaysız eklenmez.
- Açıklama üretimi (`prepare_plan`, `repair_plan`, `gecir`) notu olan ürünün açıklamasını notla kurar (`eknot_param`);
  "Notla SEO hazırla" (`ek_not_zorla`) atlanan ürün için. Notlu plan gönderilince `eknot_yazildi`, SEO / şablon geri alınınca `eknot_kalkti`.

### Blog Düzenle (`blog.py`, `app.py` "blog yazıları" bölümü)

- Her ürüne bir yazı: `blog_hazirla` ürünü ve açıklamasını okur, `BL.yaz` yazıyı kurar (mağazaya yazmaz). Biçimler: rehber, inceleme,
  ipucu, sss, bakim, senaryo; ayar "karisik"ta biçim ürüne göre döner. Teknik bilgi yalnızca ürünün mevcut açıklamasından; uydurma
  değer yazılmaz. Künyede ürün kodu, barkod, mağaza adı; ürün sayfasına `/urun/<slug>` iç bağlantısı.
- Hedef kelime kısa tutulur (`kelime_sec`, en çok 40 karakter); yoğunluk `{k}` anma yerleri, ek cümleler ve gerekirse teknik listenin kısaltılmasıyla bütün sayım yöntemlerinde %2-%3. `yaz_tam` %100 olmazsa başka anlatım, başka biçim ve daha kısa hedef kelime dener; panelde "%100 olmayanları düzelt".
- Gönderim (`blog_gonder`, `/api/blog/gonder`, paket özelliği `blog`) yalnızca kullanıcının isteğiyle ve SEO %100 ise; daha önce
  gönderildiyse aynı blog kaydı PUT ile güncellenir. Hedef kelime `targetKeyword` (ürünün kw_loc alanı) ile gider; Ideasoft yanıtında
  yoksa mesajla bildirilir. Yayından kaldırma (`/api/blog/kaldir`) blogu pasif yapar, silmez; geri almadır.
- Görsel panelde canvas ile çizilir (`blCiz`, 8 tema: lacivert ve beyaz bantlı, "Editoryal · minimal" (`editoryal`), "Gece · ışıltılı"
  (`gece_isik`) ve dört kutulu `*_kutu`; ayar `blog.gorsel`; kaldırılan temalar varsayılana döner). Oran 3:2 (tasarım 1200×800, gönderim 1500×1000 JPEG, kalite 0,95): Ideasoft blog kartında kesilmez; kenarlarda güvenli boşluk. Görselde ürün kodu "Ürün Kodu: …"
  `attachment` olarak gider. Ürün fotoğrafı `/api/blog/urun_gorsel` üzerinden (aynı köken; mağaza klasöründe `blog_gorsel/` önbellek).
- Blog başlığı ürünün kendi adıyla kurulur (`BL.blog_basligi`, `BL.urun_kisa_ad`: stok kodu, parantezler, baştaki marka
  atılır; kısa kalırsa marka eklenir) ve sonunda ürün kodu (stok kodu) yer alır (`plan.title`); hedef kelime başlıkta mutlaka
  geçer. Görseldeki başlık (`gorsel_baslik`) aynı başlığın kodsuz hâlidir.
- Yazının en altında sosyal medya kartı (`blog.sosyal`: instagram, youtube, tiktok, facebook; `BL.sosyal_ayar` yalnızca o ağın https adresini kabul eder):
  sitenin kartları gibi beyaz kutu, ağların logoları `cdn.simpleicons.org` beyaz SVG, renkli zemin ayrı `span`da (resme iç boşluk verilmez:
  sitelerdeki `box-sizing` kuralı simgeyi küçültür). Emoji yok: Ideasoft blog içeriği 4 baytlık karakterleri "????" kaydediyor.
- Sosyal kartın üstünde hizmetler kutusu (`blog.hizmet`, `BL.hizmet_ayar`): adres (https ya da /yol), koşul kelimesi (varsayılan "bosch";
  ürün adında ya da kategori yolunda geçmeli, `blog_hizmet`), rozet ({magaza}), başlık, metin, düğme. Adres yoksa kutu yok. İzi `sosyal_iz`e eklenir.
- Görsel rengi kategoriye göre (`gorsel.kat_renk`, `gorsel.gruplar`, `BL.RENK_GRUPLARI`: beyaz aksesuar, kırmızı ölçme, yeşil bahçe / hafif hizmet,
  mavi profesyonel / dremel; üstteki önce). Sunucu ürünün grubunu `renk_grup` olarak verir (`blog_renk_grubu`), panel `blGrup` ile
  zemini değiştirir; beyaz grupta açık tema. Mağaza logosu `/api/blog/logo` (mağaza klasöründe `blog_logo.*`, ayarda özeti `gorsel.logo`);
  `blLogoCiz` saydam kenarları kırpar, zeminle karışırsa (kontrast) en uygun renkte plakaya koyar.
- Kartlarda "Yayından kaldır" ve "Sil" düğmeleri (yazıyı açmadan).
  Mağaza adı girilmemişse adresten alınır (`blog_profil`).
  Ayar ya da yazar sürümü (`BL.SURUM`) değişince yazılar "eski" sayılır; "Eski yazıları yenile" yeniden hazırlar, gönderilenler "Değişenleri gönder" ile güncellenir.
- Paragraf ve listelere ayrı stil yazılmaz (Ideasoft stilleri de kelime sayar; fazla stil hedef kelimeyi tekrarlatır). Hedef kelimeli ek cümleler paragraflara dağıtılır.
- Hariç kategoriler `blog.haric`; None ise adında "bosch aksesuar" geçenler ve alt kategorileri. Pasif ürünlere yazılmaz.
- Blog kategorisi Ideasoft `blog_categories`'ten seçilir ya da açılır. Ideasoft uygulamasında blog_read / blog_create / blog_update izinleri gerekir.
- Sayfa `#v-blog`; stiller `bl-`, betik adları `bl` önekli. Yazı tipleri Fraunces, Caveat, Special Elite (Google Fonts).
- Hedef kelime araştırması (`kelime.py`, `blog_hazirla`): kullanıcı kelime seçmediyse adaylar ürün adından çıkarılır, Google
  önerileriyle (mağaza veritabanında `kelime_onbellek`, 30 gün) ve yerel ölçütlerle puanlanır; model adı bölünmez, ifade ürünün ana
  ismiyle biter, başka yazının hedef kelimesi seçilmez. Ürünün model adı (`KE.model_dizisi`: GWS 18V-8, GDR 120-Li) en güçlü
  adaydır; yalnızca marka (Bosch, Bosch Professional) aday olamaz. Aynı yazar sürümünde hazırlanmış yazının kelimesi korunur.
  Ayar `blog.google` (varsayılan açık).
  Kelime seçimiyle kayıt arası `BLOG.hazirla_kilit` altında (paralel hazırlıkta iki yazı aynı kelimeyi almaz).
- Kalite kapısı (`kalite.py`): `blog.yaz_tam` yazıyı Ideasoft'un 13 kuralı ve `KA.SINIRLAR` (seovisi puanı 94, okunabilirlik 50,
  meta benzerliği < 0,5, içerik benzerliği < 0,7, yamyamlaşma yok, anahtar kelime kaplaması) geçene kadar başka anlatım / biçim /
  hedef kelimeyle (en çok `EN_COK_DENEME`) yazar. Kullanıcı biçimi seçtiyse (`bicim_sabit`) biçim değişmez. Her yazının izi
  (`blog.iz`: hedef kelime, meta izi, içerik MinHash imzası, başlık, adres, kalite, görsel bilgisi) `BLOG.dizin_al()` dizinindedir;
  `_blog_kaydet` planla birlikte izi de yazar. Yoğunluk hesabı HTML stillerini de saydığı için ürün kartı ve kutularda stil az tutulur.
- İç bağlantılar: vitrin önekleri `API.vitrin_yollari()` (Ideasoft: `/urun/`, `/kategori/`, `/blog/icerik/`, `/blog`). Yazıya
  **yalnızca mağazanın sitesinde gerçekten açılan** adresler girer: `vitrin_acik` adresi sitede dener (200 ve "sayfa bulunamadı"
  değil; sonuç `vitrin_link` tablosunda, açılan 72, açılmayan 2 saat). Ürün ve kategori için önek açılmazsa `/<slug>` denenir;
  hiçbiri açılmazsa bağlantı verilmez. Gönderimden hemen önce (`blog_gonder_ic`) yazıdaki bütün site içi bağlantılar yeniden
  denenir; açılmayan varsa yazı yeniden kurulur, siteye ulaşılamıyorsa gönderilmez. Testler `VITRIN_GETIR` ile sahte site verir
  (`SEOVISI_TEST` varken ve sahte yoksa her adres açık sayılır). Ilgili yazılar yalnızca gönderilmişlerden (`blog_ilgili`);
  gönderimden sonra Ideasoft'un verdiği adres (slug) saklanır. Yayımlanmış yazının adresi yeniden hazırlanınca değişmez.
- Ürün kartı (`id="seovisi-urun-karti"`) yazının en dikkat çeken alanıdır: beyaz, 2 px belirgin çerçeveli (telefonda gölge görünmez), gölgeli, Poppins; vurgu rengi blog görselinin
  ana rengi (`vurgu`) yalnızca küçük ayrıntılarda, teknik bilgiler çip, düğme siyah; esnek (flex) düzen telefonda alt alta iner.
  "Bu konuda da ilginizi çekebilir" kutusu (`seovisi-ilgili`) her bağlantıyı çerçeveli, oklu bir satır olarak gösterir.
  Mağaza siteleri Poppins yüklemediği için yazının başında `BL.FONT_YUKLE` (Google Fonts `<link>` ve `@import`) bulunur.
  Fotoğraf ürünün ilk görselinin adresi (`blog_urun_foto`).
- Yoğunluk %2'ye çıkamazsa (HTML'i ağır yazı) yazar önce ek bölümü, sonra teknik listeyi kısaltır, son çare olarak sosyal medya
  kartını çıkarır; Ideasoft'un 13 kuralı her sayım yönteminde tutulur (`test_blog_kalite.Baslik`).
- Silme (`blog_sil`, `/api/blog/sil`): hazır yazı panelden kalkar (ürün "Yazılacak"a döner); gönderilmiş yazı yalnızca onayla ve
  Ideasoft'taki blogla birlikte silinir (`API.blog_sil`); Ideasoft silmeye izin vermezse blog pasif yapılır. Geri alma gibi
  paketten bağımsızdır.
- Periyodik otomasyon (`app.py` "blog otomasyonu", ayar `blog.oto`): Blog Düzenle'nin en üstteki kartındaki "PERİYODİK OTOMASYON"
  düğmesi aynı sayfada `#bl-oto` panosunu açar (`#v-blog.oto`; stiller `blo-`). Günler ve saatler Türkiye saatiyle (`TR_SAAT`);
  gün dört eşit vakte bölünür (`BLOG_VAKITLER`). `blog_oto_tur` zamanlayıcıda her dakika: seçili gün ve saatte, saat başına bir kez
  (`kv.blog_oto_slot`) `blog_oto_yayinla`. Yalnızca %100, kalite kapısını geçen ve görseli hazır yazı gider; görsel tarayıcıda
  çizildiği için pano açıkken eksikler çizilip `/api/blog/oto/gorsel` ile mağaza klasörüne (`blog_oto_gorsel/`) kaydedilir; görsel
  ayarı ya da başlık değişince eskir. Yayından sonra aynı kategorideki en çok iki eski yazı yeni yazıya bağlantıyla güncellenir
  (`blog_oto_baglanti_tazele`, elle düzenlenenler hariç). İzin: `blog_oto_engel` (bağlantı, blog kategorisi, paket özelliği `blog`).
  Geçmiş `blog_oto_log` tablosunda.

### Uyarılar (`uyari.py`)

- SEO taraması ürün kayıtlarından fiyat, indirim, alış fiyatı, stok, durum, seçenek ve kategori bilgisini `urunbilgi` tablosuna yazar
  (ek Ideasoft isteği yok). `app.uyarilar()` kuralları her istekte bu bilgilerden hesaplar; kural değişince yeniden tarama gerekmez.
- Yalnızca yayındaki ürünler denetlenir; seçenekli ürünlerin stoğu varyantlarda olduğu için stok kuralı onları atlar. Bilinmeyen alan
  o alanın kuralını atlatır. Aşırı fiyat, ürünün en az ürünlü (en özel) kategorisinin ortancasıyla ve aynı para biriminde karşılaştırılır.
- Uyarılar sayfası ve genel bakıştaki maddeler; mağazaya yazmaz, düzeltme "Panelde aç" ile Ideasoft'ta yapılır.
- Kopyalar (`kopya.py`, `/api/kopyalar`) aynı `urunbilgi` tablosundan (barkod, başlık, meta da orada). Stok kodu ve barkod
  bütün ürünlerde, ad / başlık / meta yalnızca yayındakilerde; aynı ürün kümesi daha önemli türde bildirildiyse tekrar edilmez.
  Yalnızca renk / beden farkıyla ayrılan ürünler bilerek işaretlenmez (v2: varyant önerisi).

### Kırık bağlantı taraması (`baglanti.py`, `LinkScanner`)

- Mağazanın herkese açık sitesi gezilir (Ideasoft API'si değil): ana sayfa ve site haritasından başlar, yalnızca aynı alan adındaki
  sorgusuz sayfaları gezer, görselleri ve dış bağlantıları yalnızca durum için ister. robots.txt'ye uyar; istekler arası `LINK_BEKLE`,
  en çok `link_sinir` (sunucu.json, 10.000) sayfa. Sonuç `kirik` tablosunda; durdurulan taramada önceki sonuç korunur.
- Ağ erişimi `site_getirici()` ile: her alan adı `public_host` ile denetlenir (taramada bir kez), yönlendirmeler `_PublicRedirects`
  ile; sitedeki bir bağlantı iç ağı gösterse de istek gönderilmez. Testler `site_getirici`'yi sahte siteyle değiştirir.

### Toplu şablon geçişi ve SEO geri alma

- Bütün SEO yazmaları `_seo_yaz()` üzerinden: gönderim (`send_plan`), şablon geçişi (`gecir`, `gecis_geri`) ve geri alma (`seo_geri_al`).
  Korunan alan değişirse ürün eski hâline yazılır, `SEOJOBS` ve `GECIS` durur. Yeni bir SEO yazma yolu bunu kullanmalı.
- `SablonGecisi` (`/api/sablon/gecis*`): yalnızca seovisi'nin gönderdiği (pstate gonderildi, plan ve özgün yedek olan) açıklamalar;
  açıklama özgün yedekten aynı hedef kelime ve varyantla bugünkü şablonla yeniden kurulur, yalnızca `details` değişir. Gönderildikten
  sonra açıklaması, başlığı, metası ya da hedef kelimesi değişmiş ürün, zaten bu şablonda olan ve yeni hâli SEO kurallarını tutmayan
  atlanır. Bir önceki açıklama `seo.onceki`de; `gecis`: gecti | atlandi | hata | geri.
- `seo_geri_al` (`/api/seo/undo`): ürünü seovisi'den önceki hâline (açıklama, başlık, meta, anahtar kelimeler, hedef kelime) döndürür;
  geri almalar abonelikten bağımsızdır (WRITE_ROUTES'ta yok).

### Aylık rapor ve haftalık tarama

- `olay(tur, pid)`: seovisi'nin yaptığı her iş `olay` tablosuna (seo, kategori, kategori_ac, gecis, geri). Mağazaya yazan yeni bir
  özellik eklersen başarılı yazmadan sonra olay da kaydet; rapor ona bakar.
- `anlik_al()`: tam SEO taramasının sonunda durum fotoğrafı (`anlik`). `rapor_al(ay)` → `rapor.hesapla`.
- `haftalik_tur()` (zamanlayıcıda, otopilotla birlikte): bağlı ve ücretli paketteki mağazada 7 günde bir SEO, kategori ve kırık bağlantı
  taraması; başka bir iş sürüyorsa sonraki tura kalır. E-posta gönderimi henüz yok.

### Mağazaya yazma güvenliği

Bu kurallar hiçbir zaman gevşetilmemeli:
- Yazmadan önce ürün yeniden okunur.
- Yazdıktan sonra korunan alanlar (`API.PROTECTED`, Ideasoft'ta `platformlar/ideasoft.py`: fiyat, stok, ad…) karşılaştırılır. Biri değiştiyse ürün eski hâline yazılır ve işlem durur.
- Eski açıklama ve kategoriler yedeklenir; her değişiklik geri alınabilir.
- Kategori değişikliğinde önce `PUT products` denenir; olmazsa `product_to_categories` kullanılır.

### Ideasoft'a özgü notlar

- Panelin SEO puanı kelime sayımına HTML etiketlerini de katar. Ham HTML sayımı ile panel arasındaki oran mağaza başına `panel_factor` ayarıdır (varsayılan 1,30).
- Açıklama HTML'i Ideasoft editöründen (TinyMCE) geçer; yalnızca basit satır içi stiller güvenli.
- API'de kullanılan kaynaklar: `products`, `product_details`, `categories`, `category_images`, `product_images`, `product_to_categories`, `seo_settings`, `metafields`, `product_extra_fields`, `blogs`, `blog_categories`.

### Platform adaptörü (`platformlar/`)

- `app.py` mağazaya yalnızca platform nesnesi `API` üzerinden ulaşır (`API.get_product`, `API.urunler_sonra`, `API.urun_yaz`,
  `API.aciklama_yaz`, `API.kategorileri_yaz`, `API.gorseller`, `API.kategori*`, `API.liste` / `kayit_yaz` / `kayit_ekle`,
  `API.panel_adresleri`…). `API.call(` ya da Ideasoft adresi app.py'de yazılmaz (`test_platform.py` denetler).
- Mağazanın platformu `yeni_platform()` ile, mağaza ayarı `platform` (yoksa ideasoft). Adaptör programdan ihtiyacını
  `_PlatformOrtami` ile alır; yeni bir ihtiyaç hem oraya hem `platformlar/__init__.py` başındaki listeye yazılır.
- Yazma güvenliği (yeniden okuma, `fingerprint` karşılaştırması, geri yazma, yedek) app.py'de kalır; adaptör yalnızca nasıl okunup
  yazılacağını bilir.
- Henüz yapılmayan (ikinci altyapı eklenirken): ürün / kategori kayıtları Ideasoft alan adlarıyla gelir (name, price1, pageTitle,
  details…); hedef kelime yeri (`kw_loc`) ve SEO kural kaynakları (`seo_settings`, `metafields`) Ideasoft'a göre. Bunlar ortak
  alan adlarına adaptörde çevrilecek. Panelin "Panelde aç" bağlantıları sunucudan gelen `panel.urun` / `panel.kategori` önekleriyle.
- `test_cok_magaza.py` uygulamayı kopyalarken `platformlar/` klasörünü de kopyalar; Dockerfile da.

## Bilinen açık işler (v1'e girmeden)

- Faz 1'in kod işleri bitti. Kalan: gerçek Ideasoft test mağazasıyla uçtan uca deneme (çerçeve içi giriş, abonelik, Ideasoft'un
  HTML kelime sayımı).
- Faz 2 sürüyor; kurulum sihirbazı, açıklama şablonu ayarları, yeni ürün otopilotu, uyarılar, kopya ürün tespiti, kırık bağlantı taraması toplu şablon
  geçişi, aylık rapor, haftalık tarama, ek not ve Blog Düzenle bitti. Kalan: özellik doldurma, raporun e-postayla gönderimi. Ayrıntılar `YOL_HARITASI.md` içinde.
