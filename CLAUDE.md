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
| `seo_machine.py` | Ürün açıklaması (HTML) üretimi. Hedef kelime yoğunluğunu %2–3 aralığına oturtur. |
| `sifre.py` | Diskteki gizli bilgilerin şifrelenmesi (HMAC-SHA256 sayaç kipi + HMAC imza). Ana anahtar `SEOVISI_ANAHTAR` ortam değişkeninden, yoksa `data/anahtar.key` dosyasından. |
| `profil.py` | Mağaza profili (mağaza adı, varsayılan marka) ve Türkçe ekler (`loc`, `gen`). |
| `ui/index.html` | Tek sayfalık panel; saf JS (`$`, `api`, `post`, `ask`, `show`). |
| `ui/marka/` | Logo, simge ve renkler. |

### Çok mağaza yapısı

- Her mağazanın ayarları (`ayarlar.json`), veritabanı (`durum.db`, SQLite) ve kaydı (`islem.log`) `data/magazalar/<mağaza-alan-adı>/` klasöründe durur.
- Kodun geneli `CFG`, `DBI`, `API`, `SEOSCAN`, `CATSCAN`, `CATJOBS`, `SEOJOBS`, `IMG` adlarını tek mağaza varmış gibi kullanır. Bunlar `_Ref` vekilleridir ve o anki iş parçacığının mağazasına (`_cur.t`, bir `Tenant`) yönlenir.
- İstek işleyicisi (`H._dispatch`) mağazayı oturumdan ya da yerel kipte `LOCAL["id"]` değerinden seçer.
- Arka plan işleri `spawn()` ile başlatılır ve başlatan mağazanın bağlamını taşır. **Yeni arka plan işlerinde `threading.Thread` yerine mutlaka `spawn()` kullan.**
- Eski kurulumdaki `data/ayarlar.json` ve `durum.db`, ilk açılışta `migrate_legacy()` ile mağaza klasörüne taşınır.

### Gizli bilgiler

- `Config.SECRET` alanları (`access_token`, `refresh_token`, `client_secret`, `secret`) diskte `sifreli:v1:` ile başlayan
  şifreli metin olarak durur; programın geri kalanı `CFG.get()` ile düz metin görür. Yeni bir gizli ayar eklenirse bu listeye ekle.
- Eski kurulumdaki düz metin değerler ilk açılışta şifrelenir. Açılamayan değer (anahtar kaybı) silinmez; mağaza yeniden bağlanana kadar
  bağlantı yok sayılır.
- Testler anahtarı geçici klasörde üretir (`sifre.KEY_PATH`); projenin `data` klasörüne test yazmamalı.

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

- `seo_machine.py` içindeki açıklama görünümü (`H` ve `BOX`), Ustapazar'ın rengi `#1b4f72` ve sabit bölüm düzeniyle yazılmış. v1'de bunun yerine ayarlanabilir "açıklama şablonu" gelecek.
- Panel Ideasoft'un içinde bir çerçevede açılacak. Bugünkü `SameSite=Lax` çerezi çerçeve içinde gönderilmeyebilir; giriş kapısı buna göre yapılmalı.
- Faz 1 sürüyor; test paketi ve anahtar şifreleme bitti. Sırada giriş deneme sınırı ve güvenlik başlıkları, abonelik kaydı. Ayrıntılar `YOL_HARITASI.md` içinde.
