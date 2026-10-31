# seovisi yol haritası

Hedef: seovisi'yi Ideasoft App Store'da satılan, her sektörden mağazanın kullandığı ücretli bir SEO ve katalog bakım uygulaması yapmak.
Süreler tahminidir; tek geliştirici ve tam zamanlı çalışma varsayılmıştır. Yayına çıkış tahmini: yaklaşık 5 ay.

İşaretler: [x] bitti · [ ] yapılacak · (S) sizin işiniz · (K) kod tarafı · (?) Ideasoft'un cevabına bağlı

---

## Alınan kararlar

### Yayın ve şirket
- **Kanal:** Ideasoft App Store. seovisi.com.tr tanıtım sitesi; panel app.seovisi.com.tr.
- **Şirket:** Ayrı şirket kurulmaz; uygulama Ustapazar'ın şirketi üzerinden, Tufan Bey'in onayıyla yayınlanır. Marka seovisi.
- **Bilgisayara kurulan sürüm** (baslat.bat) müşteriye sunulmaz; yalnızca Ustapazar ve geliştirme için kalır.
- **Panel adresi:** Tek adres (her mağazaya ayrı alt adres yok). Panel Ideasoft'un içinde bir çerçevede de açılır; "Tam ekranda aç" ile ayrı sekmede de çalışır.
- **Giriş:** Şifre yok; mağaza Ideasoft üzerinden tanınır.

### Ödeme ve fiyat
- **Ödeme yalnızca App Store üzerinden.** Kendi sitemizde ödeme alınmaz.
- **Yıllık ödeme ana seçenek** (aylık karşılığı gösterilir). Müşteri bir yıllık bedeli baştan öder.
- **Paketler ürün sayısına göre üç kademe.** Fiyatlar rakip Digifirst'e yakın ya da biraz altında; Ideasoft komisyonu ve yapay zekâ maliyeti öğrenilince kesinleşir.
- **Deneme:** Ideasoft deneme süresi veriyorsa o kullanılır; vermiyorsa yeni mağazalar "ücretsiz analiz" modunda başlar (sorunları görür, düzeltemez).
- **Aboneliği taşıyan değer:** Tek seferlik temizlik değil, sürekli bakım: yeni ürün otopilotu, aylık rapor, haftalık taramalar.
- **Vaat:** "Sizi 1. sıraya çıkarırız" denmez. Vaat: "Google'ın önerdiği temel kuralları ürünlerinize eksiksiz uygular."

### Rakip
**Digifirst AI Otonom SEO & İçerik Üretim Motoru** (Ideasoft App Store, Ekim 2026 itibarıyla 10 indirme):

| Paket | Ürün sınırı | Aylık | Yıllık |
|---|---|---|---|
| Starter | 1.000 | 2.042 ₺ | 24.500 ₺ |
| Business | 5.000 | 3.708 ₺ | 44.500 ₺ |
| Expert | 10.000 | 5.792 ₺ | 69.500 ₺ |

**seovisi'nin farkı:**
- Kategori analizi ve düzeltme
- Güvenli yazma ve tek tuşla geri alma
- Yeni ürün otopilotu
- Açıklamaların mağazanın kendi görünümünde olması
- Ölçülebilir sonuç (Ustapazar önce / sonra verisi)

### Google Search Console
Ürüne hemen eklenmez. Önce Ustapazar'da kendimiz 8–12 hafta ölçeriz: seovisi ile düzeltilen ürünler ile dokunulmayan benzer ürünler karşılaştırılır. Sonuç iyiyse v2'de ürüne eklenir; değilse yöntem düzeltilir.

---

## İlk sürüm (v1) özellikleri

**Hazır olanlar (cilalanacak):**
- [x] Genel bakış ve mağaza SEO puanı
- [x] Ürün SEO'su: başlık, meta açıklama, açıklama
- [x] Kategori analizi: yanlış ve kategorisiz ürünler, yeni kategori açma (SEO ve görselle)
- [x] Görseli eksik ürünler listesi
- [x] Her değişikliği geri alma

**Eklenecekler:**
- [x] Kurulum sihirbazı
- [x] Yeni ürün otopilotu: yeni ürünler fark edilir, SEO'su ve kategorisi hazırlanır; onaylı ya da otomatik onaylı gönderim
- [ ] Aylık e-posta raporu
- [ ] Yapay zekâ ile ürüne özel açıklama; marka sesi seçimi (samimi, kurumsal, genç)
- [ ] Açıklama şablonu ayarlama:
  - [x] hazır şablonlar: sade, bantlı, çizgili, kutulu
  - [x] ana renk (sitenin tema rengi önerilir)
  - [x] bölümleri açma, kapama ve sıralama; başlık metinleri
  - [x] madde işareti, kapanış metni, stok kodu / barkod gösterimi
  - [x] canlı önizleme ve SEO puanı tahmini
  - [ ] eski açıklamaları yeni şablona toplu geçirme (yedekli)
- [x] Kopya ürün tespiti
- [ ] Özellik doldurma: renk, malzeme, beden gibi bilgileri ürün adından ek alanlara yazma
- [x] Kırık bağlantı ve 404 taraması (sitenin herkese açık sayfaları üzerinden; API gerekmez)
- [x] Uyarılar: fiyat hataları, aktif ama satılamaz ürünler (yalnızca okur)
- [ ] Paketler, kota ve abonelik durumu

**v2 (yayından sonraki ilk büyük güncelleme):**
- Google Search Console (Ustapazar ölçümü olumluysa)
- Varyant önerisi, ürün adı standardı
- Kategori sayfası metinleri, sık sorulan sorular
- Görsel alt metni (?), görsel kalite kontrolü
- Google için teknik kontroller, sayfa hızı ve mobil uyum
- Kategoriye göre farklı açıklama şablonu
- 301 yönlendirme (?), marka sayfaları SEO'su (?)

**v3:**
- Arama talebi önerileri, çeviri (?)
- Arka plan temizleme
- Satmayan ürünler (sipariş verisi gerekir) (?)
- Google Alışveriş ve pazar yeri uygunluğu

**Çıkarılanlar:** ekip ve iş akışı (onay akışı, çoklu kullanıcı, ajans paketi, WhatsApp bildirimi), rakip fiyat takibi, reklam yönetimi.

---

## Ideasoft'a sorulacaklar

**A. Kurulum ve giriş**
1. Uygulama panel içinde (çerçevede) açılırken hangi mağazanın ve kullanıcının açtığını bize nasıl iletiyorsunuz? İmzalı bir parametre ya da kimlik bilgisi var mı?
2. Kurulumda OAuth izni dışında bir adım var mı? Kurulum tamamlanınca bize bildirim geliyor mu?
3. Tek bir uygulama anahtarı (client ID / secret) tüm mağazalarda geçerli mi?

**B. Ödeme ve abonelik**

4. Ücretli uygulamada deneme süresi verilebiliyor mu, kaç gün?
5. Mağazanın aldığı paketi ve abonelik durumunu (aktif, süresi doldu, iptal) bize nasıl bildiriyorsunuz: API ile mi, bildirimle mi?
6. Paket yükseltme ve düşürme nasıl işliyor?
7. Komisyon oranı nedir, ödemeler bize ne zaman yapılır, müşteriye faturayı kim keser?
8. Aylık ödeme seçeneği var mı, yoksa yalnızca yıllık mı?

**C. Teknik**

9. Yeni ürün eklenince, ürün güncellenince ve uygulama kaldırılınca bize bildirim (webhook) gönderiliyor mu?
10. API hız sınırları nedir: mağaza başına mı, uygulama başına mı?
11. Şu kaynaklar API'de var mı: URL yönlendirme (301), markalar, siparişler, ürün yorumları, görsel alt metni?
12. Ürün ve kategori SEO puanını (panelde görünen yüzdeyi) API'den okuyabilir miyiz?

**D. Süreç**

13. Geliştirme için test (sandbox) mağazası veriyor musunuz?
14. Uygulama inceleme süreci nasıl işliyor, ne kadar sürüyor?
15. Uygulama sayfası için (görsel, video, açıklama) kurallar nelerdir?

**Ekran görüntülerinden öğrenilenler:**
- Uygulamalar Ideasoft panelinin içinde açılıyor ve "Tam Ekranda Aç" düğmesi var.
- Bir uygulamada birden çok paket olabiliyor ve "Satın Al" App Store'un kendi düğmesi.
- Fiyatlar yıllık, yanında aylık karşılığı gösteriliyor.

---

## Değişikliğe uygun tasarım: Ideasoft'a bağlı konular için "kapılar"

Programın geri kalanı yalnızca kapıyla konuşur. Ideasoft'un cevabı ne olursa olsun yalnızca kapının arkasındaki küçük parça değişir. Böylece cevapları beklemeden geliştirme sürer.

| Konu (soru no) | Tasarım |
|---|---|
| Giriş (1, 2) | Üç yol: Ideasoft'un imzalı bilgisi, çerçeve içinde çalışan özel çerez, mağaza adresiyle Ideasoft izni. "Tam ekranda aç" her zaman çalışır. |
| Abonelik durumu (5, 6, 8) | Her mağazanın tek bir abonelik kaydı: paket, durum, bitiş tarihi. Kaydı Ideasoft bildirimi, API sorgusu ya da yönetici panelinden elle giriş besler. Program yalnızca bu kayda bakar. |
| Deneme (4) | Kayıtta "deneme" durumu. Ideasoft vermiyorsa "ücretsiz analiz" modu. |
| Paketler (6) | Ayar dosyasında: ürün sınırı, yapay zekâ hakkı, açık özellikler. Fiyat değişince yalnızca dosya değişir. |
| Yeni ürün haberi (9) | Tek iş sırası. Webhook varsa anında, yoksa birkaç saatte bir kısa kontrolle beslenir. |
| Uygulama kaldırma (9) | Bildirim gelirse ya da erişim anahtarı reddedilirse mağaza "kaldırıldı" olur; veri 30 gün sonra silinir. |
| Hız sınırları (10) | Ayardan okunur: mağaza başına ve toplam. |
| Eksik kaynaklar (11, 12) | Bağlanınca hangi kaynakların çalıştığı denenir; olmayan özellik panelde görünmez, sonradan eklenirse kendiliğinden açılır. |
| Tek anahtar (3) | Bugün de destekleniyor: ortak sunucu anahtarı, gerekirse mağazaya özel anahtar. |

**Teknik not:** Panel Ideasoft'un içinde bir çerçevede açıldığı için oturum çerezi HTTPS'te `SameSite=None`; çerçevenin içinde verilen çerez ayrıca `Partitioned`. Üçüncü taraf çerezleri tamamen engelleyen tarayıcılarda (ör. Safari) panel "Tam ekran" ile kendi sekmesinde açılır.

---

## Faz 0 — İş ve hukuk temeli (hemen, diğer fazlarla paralel)

- [ ] (S) Tufan Bey ile kısa yazılı anlaşma: sizin payınız, ayrılık durumu, masrafları kimin karşılayacağı
- [ ] (S) seovisi.com.tr ve seovisi.com alan adları (kimin adına alınacağına karar verin)
- [ ] (S) TÜRKPATENT'te "seovisi" marka araştırması
- [ ] (S) Ideasoft'a Ustapazar olarak başvuru ve yukarıdaki soruların gönderilmesi
- [ ] (S) Hukuki metinler (Ustapazar şirket bilgileriyle): kullanım koşulları, gizlilik ve KVKK aydınlatma metni, veri işleme sözleşmesi, VERBİS kontrolü
- [ ] (S) Ustapazar Search Console erişimi ve önce / sonra ölçümünün başlatılması
- [ ] (S) Beta için farklı sektörlerden 3–5 gönüllü mağaza

## Faz 1 — Ürünü sağlamlaştırma (2–3 hafta)

- [x] (K) Otomatik test paketi ve her commit'te çalışması
- [x] (K) Mağaza anahtarlarının diskte şifrelenmesi
- [x] (K) Girişte deneme sınırı, güvenlik başlıkları, istek boyutu sınırı
- [x] (K) Ideasoft hız sınırına uyan adil iş sırası
- [x] (K) Giriş kapısı: çerçeve içinde çalışan oturum (çerçeve içi çerez, yeni sekmede giriş + kapı kodu, tam ekran)
  - [ ] (?) Ideasoft'un imzalı açılış bilgisi: `ideasoft_launch()` Ideasoft'un 1. soruya cevabıyla doldurulacak
- [x] (K) Abonelik kaydı, paket ayar dosyası ve kota (ürün sınırı; yapay zekâ hakkı Faz 4'te)
  - [ ] (?) Kaydı Ideasoft'un bildirimi / API'si besleyecek (5, 6, 8. sorular); o zamana kadar `python app.py --abonelik`
- [x] (K) Açıklama şablonundaki Ustapazar renginin ve sabit düzenin kaldırılması (şablon sistemi gelene kadar sade görünüm)
  - Not: sade stiller, panel katsayısı (1,30) ölçülürkenki stillerle aynı sayıda kelime üretir. Ideasoft'un HTML'i nasıl saydığı
    test mağazasında ölçülünce (aşağıdaki uçtan uca deneme) şablon sistemi bu sınırdan kurtulur.
- [ ] (S+K) Gerçek bir Ideasoft test mağazasıyla uçtan uca deneme

## Faz 2 — v1 özellikleri (5–6 hafta)

- [x] (K) Kurulum sihirbazı: mağaza adı ve marka, açıklama görünümü (sade / bantlı, canlı önizleme), ilk tarama ve özet, paket bilgisi
  - [ ] (S) Ustapazar'da bulunan hedef kelime yerinin sunucu.json'a varsayılan olarak girilmesi (`kw_loc`)
- [ ] (K) Açıklama şablonu ayarlama — ayarlar ekranı, 4 görünüm, renk, bölümler, önizleme bitti; eski açıklamaların toplu geçirilmesi kaldı
- [x] (K) Yeni ürün otopilotu ve iş sırası (saatlik kontrol; yayına alınıp 30 dk geçen ürün; onaylı / otomatik; şüpheli öneri her zaman onaya)
  - [ ] (?) Ideasoft yeni ürün bildirimi (webhook) varsa kontrol() bildirimle de çağrılacak (9. soru)
- [x] (K) Kopya ürün tespiti (aynı stok kodu, barkod, ad, sayfa başlığı, meta açıklama; neredeyse aynılar v2 varyant önerisinde)
- [ ] (K) Özellik doldurma
- [x] (K) Kırık bağlantı taraması (ana sayfa + site haritası; sayfa, görsel ve dış bağlantılar; robots.txt'ye uyar)
  - [ ] (K) Haftalık otomatik tarama (aboneliği taşıyan "haftalık taramalar" değeri; aylık raporla birlikte)
- [x] (K) Fiyat ve satılamaz ürün uyarıları (fiyatı 0, hatalı indirim, alış fiyatı altı, kategorisine göre aşırı fiyat; yayında ama stokta yok)
- [ ] (K) Aylık e-posta raporu

## Faz 3 — Sunucu altyapısı (3–4 hafta)

- [ ] (S) Türkiye'de bir sanal sunucu
- [ ] (K) Çekirdek modüller kalır; web katmanı FastAPI, veritabanı PostgreSQL, ayrı iş kuyruğu
- [ ] (K) Ideasoft bağlantısı platform adaptörü arkasına
- [ ] (K) Docker, Caddy ile HTTPS, app.seovisi.com.tr; test ve canlı ortam
- [ ] (K) Günlük yedek, izleme ve alarmlar
- [ ] (K) Uygulama kaldırılınca veri silme
- [ ] (K) Yönetici paneli: mağazalar, abonelikler, kullanım, hatalar

## Faz 4 — Yapay zekâ (2–3 hafta)

- [ ] (K) Claude ile ürüne özel açıklama ve marka sesi; mevcut SEO denetimi metni kontrol eder
- [ ] (K) Maliyet ölçümü, pakete göre aylık hak, önbellek
- [ ] (K) Fiyatların kesinleşmesi (komisyon ve yapay zekâ maliyetiyle)

## Faz 5 — Beta (4–6 hafta)

- [ ] (S) 3–5 mağazayla kapalı beta, haftalık görüşme; Ustapazar ilk beta mağazası
- [ ] (K) Ölçümler: kurulumdan ilk düzeltmeye süre, haftalık aktif mağaza, düzeltilen ürün sayısı
- [ ] (S+K) Yardım sayfaları, sık sorulanlar, kısa videolar
- [ ] (S) Destek kanalı: e-posta ve WhatsApp
- [ ] (K) Geri bildirime göre düzeltmeler

## Faz 6 — Yayın (2–3 hafta)

- [ ] (S+K) App Store sayfası: açıklama, ekran görüntüleri, video, paketler
- [ ] (K) seovisi.com.tr tanıtım sitesi: özellikler, fiyatlar, örnek sonuçlar, hukuki metinler
- [ ] (S) Ustapazar ve beta mağazalarından referans, önce / sonra örnekleri

## Faz 7 — Büyüme (yayından sonra)

- v2 ve v3 listesindeki özellikler, beta geri bildirimine göre sıralanarak

---

## Riskler ve önlemler

| Risk | Önlem |
|---|---|
| Ideasoft başvuruyu reddeder ya da gecikir | Hemen başvurmak; bu arada Ustapazar ve beta mağazaları yönetici panelinden elle açılır |
| Ideasoft API'si ya da App Store kuralları değişir | Kapılar ve platform adaptörü; her gece test mağazasında otomatik kontrol |
| Program mağazaya yanlış veri yazar | Önce oku, sonra doğrula, yedekle, geri al; test paketi; kademeli yayın |
| Şablon açıklamalar Google'da tekrar eden içerik sayılır | Yapay zekâ ile ürüne özgü metin; Ustapazar'da önce / sonra ölçümü |
| Rakip (Digifirst) ya da Ideasoft'un kendisi aynı işi yapar | Taklidi zor özelliklere odak: kategori analizi, otopilot, güvenli yazma |
| Pazar küçük çıkar (rakipte yalnızca 10 indirme) | Beta ile talebi erken doğrulamak; ileride diğer altyapılara açılabilmek |
| Yapay zekâ maliyeti fiyatı aşar | Ürün başı maliyet ölçümü, paket kotası, önbellek |
| Veri sızıntısı | Şifreli anahtarlar, mağaza ayrımı testleri, şifreli yedekler |
| Uygulama ile Ustapazar arasındaki hak ve gelir belirsizliği | Tufan Bey ile kısa yazılı anlaşma (Faz 0) |

## Netleşmesi kalan konular

1. ~~Hasan Bey'in ilk göreceği ekran~~: kurulum sihirbazı yapıldı (4 adım)
2. Paketlerin içeriği: hangi özellik hangi pakette, kaç yapay zekâ açıklaması
3. Ustapazar Search Console erişimi ve ölçümün başlangıç tarihi
4. Ideasoft e-postasının gönderilme tarihi
5. Alan adlarının kimin adına alınacağı
