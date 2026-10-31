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
  - `test_uyari.py`, `test_kopya.py`: uyarı ve kopya kuralları.
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
| `profil.py` | Mağaza profili (mağaza adı, varsayılan marka) ve Türkçe ekler (`loc`, `gen`). |
| `ui/index.html` | Tek sayfalık panel; saf JS (`$`, `api`, `post`, `ask`, `show`). |
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
- Faz 2 sürüyor; kurulum sihirbazı, açıklama şablonu ayarları, yeni ürün otopilotu, uyarılar ve kopya ürün tespiti bitti. Kalan: eski açıklamaları
  yeni şablona yedekli toplu geçirme, özellik doldurma, kırık bağlantı taraması, aylık e-posta raporu. Ayrıntılar `YOL_HARITASI.md` içinde.
