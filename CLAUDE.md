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
  - `test_panel.py`: panel betiğinin sözdizimi (Node.js varsa), yinelenen üst düzey adlar ve öğe kimlikleri.
  - `test_otopilot.py`: yeni ürün otopilotu (bellekteki sahte mağaza; kategori analizinin kararını belirleyen `guclu_oneri`).
  - `hepsi.py` testlerin projenin `data` klasörünü oluşturmadığını da denetler.
  - `test_yazma_guvenligi.py`: bellekteki sahte Ideasoft ile yazma güvenliği, yedek ve geri alma. Yazma koduna dokunan her değişiklikte buraya test ekle.
  - `test_cok_magaza.py`: uygulamanın kendisini iki sahte mağazayla (`sahte_ideasoft.py`) çalıştıran betik.
  - GitHub'da her push'ta `.github/workflows/testler.yml` çalışır (Python 3.8 ve 3.13, Linux ve Windows).
  - Commit öncesi kanca `.githooks/pre-commit`; bir kez `git config core.hooksPath .githooks` ile açılır.
    Yeni klonda kancanın çalıştırılabilir kalması için ilk eklemede `git add --chmod=+x .githooks/pre-commit`.

## Mimari

| Dosya | Görevi |
|---|---|
| `app.py` | Web sunucusu (`http.server`), Ideasoft Admin API istemcisi, taramalar ve arka plan işleri, uygulama / geri alma, oturum |
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
| `profil.py` | Mağaza profili (mağaza adı, varsayılan marka) ve Türkçe ekler (`loc`, `gen`). |
| `ui/index.html` | Tek sayfalık panel; saf JS (`$`, `api`, `post`, `ask`, `show`). Bütün betik tek kapsamda: yeni üst düzey ad ve öğe kimliği var olanlarla çakışmamalı (`test_panel.py`). |
| `ui/marka/` | Logo, simge ve renkler. |

### Çok mağaza yapısı

- Her mağazanın ayarları (`ayarlar.json`), veritabanı (`durum.db`, SQLite) ve kaydı (`islem.log`) `data/magazalar/<mağaza-alan-adı>/` klasöründe durur.
- Kodun geneli `CFG`, `DBI`, `API`, `SEOSCAN`, `CATSCAN`, `CATJOBS`, `SEOJOBS`, `IMG`, `OTO` adlarını tek mağaza varmış gibi kullanır. Bunlar `_Ref` vekilleridir ve o anki iş parçacığının mağazasına (`_cur.t`, bir `Tenant`) yönlenir; okuma da atama da (`CATSCAN.running = True`) o mağazanın nesnesine gider.
- İstek işleyicisi (`H._dispatch`) mağazayı oturumdan ya da yerel kipte `LOCAL["id"]` değerinden seçer.
- Arka plan işleri `spawn()` ile başlatılır ve başlatan mağazanın bağlamını taşır. **Yeni arka plan işlerinde `threading.Thread` yerine mutlaka `spawn()` kullan.**
  Paralel işler için de `ThreadPoolExecutor` yerine `pmap()`; yoksa iş parçacıkları "Mağaza seçilmedi" hatası verir.
- Ideasoft'a giden her istek `Ideasoft.call` içinde `THROTTLE.acquire(mağaza)` ile izin alır: mağaza başına ve toplam dakikalık sınır
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
- Her mağazanın kaydı `abonelik.json`; her istekte diskten okunur. Bütün kaynaklar `AB.yaz()` ile yazar. Bugün:
  `python app.py --abonelik magaza.com --paket baslangic --bitis 2027-10-31 [--durum aktif|deneme|iptal|ucretsiz]`, liste: `--abonelikler`.
- Süresi geçen, iptal edilen ya da tanınmayan kayıt ücretsiz analize düşer: analiz ve geri alma açık, mağazaya yazma kapalı.
- Mağazaya yazan her POST yolu `WRITE_ROUTES` içinde bir özelliğe bağlıdır; `route_post` başında denetlenir. **Yeni bir yazma yolu
  eklersen buraya da ekle.** Geri alma bilerek listede yok. Ürün sınırı taramalarda görülen ürün sayısıyla (`urun_sayisi()`) karşılaştırılır.

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
- Yazdıktan sonra korunan alanlar (`Ideasoft.PROTECTED`: fiyat, stok, ad…) karşılaştırılır. Biri değiştiyse ürün eski hâline yazılır ve işlem durur.
- Eski açıklama ve kategoriler yedeklenir; her değişiklik geri alınabilir.
- Kategori değişikliğinde önce `PUT products` denenir; olmazsa `product_to_categories` kullanılır.

### Ideasoft'a özgü notlar

- Panelin SEO puanı kelime sayımına HTML etiketlerini de katar. Ham HTML sayımı ile panel arasındaki oran mağaza başına `panel_factor` ayarıdır (varsayılan 1,30).
- Açıklama HTML'i Ideasoft editöründen (TinyMCE) geçer; yalnızca basit satır içi stiller güvenli.
- API'de kullanılan kaynaklar: `products`, `product_details`, `categories`, `category_images`, `product_images`, `product_to_categories`, `seo_settings`, `metafields`, `product_extra_fields`.

## Bilinen açık işler (v1'e girmeden)

- Faz 1'in kod işleri bitti. Kalan: gerçek Ideasoft test mağazasıyla uçtan uca deneme (çerçeve içi giriş, abonelik, Ideasoft'un
  HTML kelime sayımı).
- Faz 2 sürüyor; kurulum sihirbazı, açıklama şablonu ayarları, yeni ürün otopilotu, uyarılar, kopya ürün tespiti, kırık bağlantı taraması toplu şablon
  geçişi, aylık rapor ve haftalık tarama bitti. Kalan: özellik doldurma, raporun e-postayla gönderimi. Ayrıntılar `YOL_HARITASI.md` içinde.
