# -*- coding: utf-8 -*-
"""Blog yazarı: her ürün için Ideasoft'un blog SEO kurallarının hepsini (13 madde) tutan, Google'ın sevdiği türden
bilgilendirici bir yazı hazırlar. Yalnızca Python standart kütüphanesi; mağazaya hiçbir şey yazmaz.

Ideasoft'un blog kuralları (paneldeki iki kutu):
  hedef kelime tanımlı, blog adı dolu, hedef kelime blog başlığında, blog açıklaması (content) dolu, hedef kelime
  açıklamada, açıklama en az 50 kelime, hedef kelime yoğunluğu %2-%3; sayfa başlığı dolu, 20-60 karakter, hedef kelime
  sayfa başlığında; meta açıklama dolu, 50-155 karakter, hedef kelime meta açıklamada.

Google tarafı: yazı ürün sayfasının kopyası değil, arama niyetine (nasıl seçilir, nasıl kullanılır, nasıl bakılır, sık
sorulanlar) cevap veren özgün bir rehberdir. İçindekiler, ara başlıklar, liste ve tablolar, sık sorulan sorular ve ürün
sayfasına iç bağlantı içerir. Ürünün ürün kodu, barkodu ve mağaza adı (Ustapazar) "Ürün künyesi"nde ve metinde geçer.
Uydurma teknik değer yazılmaz: teknik bilgiler yalnızca ürünün mevcut açıklamasından okunur.

Altı biçim vardır (BICIMLER); "karisik" seçiliyse biçim ürüne göre döner, böylece yazılar birbirinin kopyası olmaz.
Yoğunluk, metindeki isteğe bağlı anma yerleri ({k}: hedef kelime ya da "bu model" gibi bir gönderme) ve ek cümlelerle
tutturulur; açıklama üreticisindeki (seo_machine.py) gibi bütün sayım yöntemlerinde %2-%3 aranır.
"""
import hashlib
import html
import random
import re

import profil as PR
import seo_machine as SM
import seo_text as ST

SURUM = 2   # yazar değiştikçe artar; eski hazırlıklar "eski" görünür

BICIMLER = {
    "rehber": {"ad": "Satın alma rehberi", "rozet": "REHBER", "ek": "Rehberi"},
    "inceleme": {"ad": "Detaylı inceleme", "rozet": "İNCELEME", "ek": "İncelemesi"},
    "ipucu": {"ad": "Pratik ipuçları", "rozet": "İPUÇLARI", "ek": "İpuçları"},
    "sss": {"ad": "Sık sorulan sorular", "rozet": "SORU & CEVAP", "ek": "Soru ve Cevaplar"},
    "bakim": {"ad": "Bakım rehberi", "rozet": "BAKIM", "ek": "Bakım Rehberi"},
    "senaryo": {"ad": "Kullanım senaryoları", "rozet": "UYGULAMA", "ek": "Kullanım Alanları"},
}
SIRA = list(BICIMLER)

BASLIKLAR = {
    "rehber": ["{kw} Alırken Nelere Dikkat Edilmeli? Kapsamlı Rehber",
               "{kw} Satın Alma Rehberi: Doğru Seçim İçin Bilmeniz Gerekenler",
               "{kw} Almadan Önce Okuyun: 6 Kritik Soru ve Cevabı"],
    "inceleme": ["{kw} İncelemesi: Özellikler, Artılar ve Kullanım Deneyimi",
                 "{kw} Detaylı İnceleme: Gerçekten Fark Yaratıyor mu?",
                 "Yakından Bakış: {kw} İncelemesi ve Uzman Notları"],
    "ipucu": ["{kw} ile Daha Verimli Çalışmanın 7 Altın Kuralı",
              "{kw} Kullanırken İşinizi Kolaylaştıracak 7 İpucu",
              "Ustalardan {kw} İçin 7 Pratik Öneri"],
    "sss": ["{kw} Hakkında En Çok Sorulan 8 Soru",
            "{kw}: Merak Edilen Soruların Net Cevapları",
            "{kw} Rehberi: Sık Sorulan Sorular ve Yanıtları"],
    "bakim": ["{kw} Bakımı: Uzun Ömürlü Kullanım İçin Pratik Öneriler",
              "{kw} Nasıl Korunur? Adım Adım Bakım Rehberi",
              "{kw} İlk Günkü Gibi Kalsın: Bakım ve Saklama Rehberi"],
    "senaryo": ["{kw} Hangi İşlerde Kullanılır? Uygulama Önerileri",
                "{kw} ile Neler Yapabilirsiniz? Gerçek Kullanım Senaryoları",
                "{kw} Sahada: Doğru İş, Doğru Kullanım"],
}

# metindeki göndermeler (hedef kelimenin yerine; yoğunluk ayarı için)
GONDERME = ["bu model", "ürün", "bu {label}"]

# yoğunluk düşük kalırsa (kısa ürün bilgisi) eklenen, hedef kelime geçmeyen cümleler
DOLGU = [
    "Doğru ürünü seçmek, işin hem kalitesini hem de süresini doğrudan etkiler.",
    "Ürün sayfasındaki görselleri ve teknik bilgileri incelemek seçiminizi kolaylaştırır.",
    "Kullanmadan önce ürünle birlikte gelen kullanım kılavuzunu okumanızı öneririz.",
    "Düzenli bakım ve doğru saklama koşulları kullanım ömrünü belirgin şekilde uzatır.",
    "Aklınıza takılan her soru için müşteri hizmetlerimize ulaşabilirsiniz.",
    "İhtiyacınızı netleştirmek, gereksiz harcamanın önüne geçmenin en kolay yoludur.",
    "Uyumlu aksesuarlar, aynı işi daha temiz ve daha hızlı bitirmenize yardımcı olur.",
    "Güvenlik uyarılarına uymak hem sizi hem de kullandığınız ekipmanı korur.",
    "Siparişinizi vermeden önce ürün kodunu ve barkodunu kontrol etmeniz yanlış ürün riskini ortadan kaldırır.",
    "Bir ürünü uzun yıllar kullanmanın sırrı, onu tanıyarak ve yerinde kullanmaktır.",
]


# yoğunluk yüksek tutulamazsa (uzun ürün bilgisi) sona eklenen, hedef kelimeli cümleler
KW_EK = [
    "{kw} ile ilgili güncel fiyat ve stok bilgisi ürün sayfasında yer alır.",
    "{kw} siparişinde ürün kodunu kontrol etmeniz doğru ürünü almanızı sağlar.",
    "{kw} için uyumlu aksesuarları da {magaza} üzerinden inceleyebilirsiniz.",
    "{kw} hakkındaki sorularınızı {magaza} ekibine iletebilirsiniz.",
    "{kw}, doğru kullanıldığında uzun yıllar sorunsuz hizmet verir.",
    "{kw} ile ilgili yeni içerikler için blogumuzu takip edin.",
    "{kw} hakkında aklınıza takılan her şeyi bu yazıda topladık.",
    "{kw} ile çalışırken güvenlik uyarılarına dikkat etmeyi unutmayın.",
    "{kw} için doğru aksesuar seçimi sonucu doğrudan etkiler.",
    "{kw} ürün sayfasında görselleri ve teknik bilgileri inceleyebilirsiniz.",
    "{kw} kutusundan çıkan parçaları ilk kullanımdan önce kontrol edin.",
    "{kw}, düzenli bakım yapıldığında performansını uzun süre korur.",
    "{kw} hakkındaki deneyimlerinizi bizimle paylaşabilirsiniz.",
]

# ürün adının başında hedef kelimeye katkısı olmayan sözcükler
BOS_SOZ = {"professional", "profesyonel", "pro", "yeni", "orijinal", "orjinal", "original", "new"}

# ---------------------------------------------------------------- yardımcılar

_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def slug(s, n=90):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").translate(_TR).lower()).strip("-")
    return s[:n].rstrip("-") or "blog"


def _rng(*parca):
    return random.Random(int(hashlib.md5("|".join(map(str, parca)).encode()).hexdigest()[:8], 16))


def bicim_sec(bicim, pid, varyant=0):
    """'karisik' ya da boşsa biçim ürüne göre döner (yan yana ürünler farklı biçimde yazılır)."""
    if bicim in BICIMLER:
        return bicim
    return SIRA[(int(pid or 0) + int(varyant or 0)) % len(SIRA)]


def kelime_sec(ad, mevcut="", prof=None, en_uzun=40):
    """Blogun hedef kelimesi: ürünün hedef kelimesi kısa ve adında geçiyorsa o, değilse addan kısa bir parça.
    Kısa kelime, yazının doğal okunmasını sağlar (%2-%3 yoğunlukta uzun bir ifade metni bozar)."""
    cur = (mevcut or "").strip()
    if cur and len(cur) <= en_uzun and ST.tr_lower(cur) in ST.tr_lower(ad) and not any(c in cur for c in SM.RISKY):
        return cur
    kw = SM.machine_keyword(ad, "", prof)
    if any(c in kw for c in SM.RISKY):
        kw = SM.safe_keyword(ad, 55) or kw
    kelimeler = kw.split()
    while len(kelimeler) > 2 and ST.tr_lower(kelimeler[0]) in BOS_SOZ:
        kelimeler = kelimeler[1:]
    out = []
    for w in kelimeler:
        if len(" ".join(out + [w])) > en_uzun:
            break
        out.append(w)
    kw = " ".join(out).strip(" ,-") or kw[:en_uzun]
    return kw


def _cumle_basi(metin, pos):
    once = metin[:pos].rstrip()
    return not once or once[-1] in ".!?:"


def _bas_harf(s):
    return s[:1].upper() + s[1:] if s else s


# ---------------------------------------------------------------- HTML

def _e(t):
    return html.escape(t or "", quote=False)


# okunaklı ve ferah yazı: büyük punto, geniş satır aralığı, bölümler arasında boşluk (stiller tek yerde, kısa)
P = "margin:0 0 18px"
LISTE = "margin:0 0 22px;padding-left:24px"


def _render(bloklar, kw, renk, link):
    """Bloklar: (tür, içerik). Satır içi stiller kısa tutulur (Ideasoft editörü TinyMCE; kelime sayımı)."""
    out = []
    kwe = _e(kw)
    for tur, v in bloklar:
        if tur == "lead":
            t = _e(v).replace(kwe, f"<strong>{kwe}</strong>", 1)
            out.append(f'<p style="font-size:20px;line-height:1.75;margin:0 0 26px">{t}</p>')
        elif tur == "h2":
            out.append(f'<h2 style="color:{renk};font-size:27px;line-height:1.3;margin:40px 0 14px">{_e(v)}</h2>')
        elif tur == "h3":
            out.append(f'<h3 style="font-size:21px;line-height:1.35;margin:28px 0 10px">{_e(v)}</h3>')
        elif tur == "p":
            if v:
                out.append(f'<p style="{P}">{_e(v)}</p>')
        elif tur in ("ul", "ol"):
            if v:
                out.append(f'<{tur} style="{LISTE}">' + "".join(f"<li>{_e(x)}</li>" for x in v) + f"</{tur}>")
        elif tur in ("check", "cross"):
            isaret = "✔" if tur == "check" else "✘"
            if v:
                out.append('<ul style="list-style:none;margin:0 0 22px;padding-left:4px">'
                           + "".join(f"<li>{isaret} {_e(x)}</li>" for x in v) + "</ul>")
        elif tur == "toc":
            out.append(f'<div style="border-left:5px solid {renk};background:#f6f7f9;padding:18px 24px;margin:26px 0 30px">'
                       f'<p style="{P}"><strong>Bu yazıda</strong></p><ol style="margin:0;padding-left:22px">'
                       + "".join(f"<li>{_e(x)}</li>" for x in v) + "</ol></div>")
        elif tur == "kunye":
            satir = "".join(f"<tr><td><strong>{_e(a)}</strong></td><td>{_e(b)}</td></tr>" for a, b in v if b)
            out.append(f'<table border="1" cellpadding="12" style="border-collapse:collapse;width:100%;margin:10px 0 28px">'
                       f"{satir}</table>")
        elif tur == "spec":
            items = []
            for t, kids in v:
                m = re.match(r"^([^:]{2,80}):\s*(.+)$", t)
                head = f"<strong>{_e(m.group(1))}:</strong> {_e(m.group(2))}" if m else _e(t)
                alt = "<ul>" + "".join(f"<li>{_e(k)}</li>" for k in kids) + "</ul>" if kids else ""
                items.append(f"<li>{head}{alt}</li>")
            out.append(f'<ul style="{LISTE}">' + "".join(items) + "</ul>")
        elif tur == "tip":
            baslik, metin = v
            out.append('<div style="background:#fff8e6;border:1px dashed #d9a933;padding:18px 22px;margin:28px 0">'
                       f'<p style="margin:0"><strong>{_e(baslik)}</strong> {_e(metin)}</p></div>')
        elif tur == "quote":
            out.append(f'<blockquote style="border-left:5px solid {renk};margin:28px 0;padding:8px 22px;font-size:20px;'
                       f'font-style:italic"><p style="margin:0">{_e(v)}</p></blockquote>')
        elif tur == "faq":
            for q, a in v:
                out.append(f'<h3 style="font-size:20px;margin:26px 0 8px">{_e(q)}</h3><p style="{P}">{_e(a)}</p>')
        elif tur == "cta":
            metin, yazi = v
            a = (f'<p style="margin:0"><a href="{_e(link)}" style="color:#fff;font-weight:bold">{_e(yazi)} →</a></p>'
                 if link else "")
            out.append(f'<div style="background:{renk};color:#fff;padding:22px 26px;margin:34px 0 24px;border-radius:10px">'
                       f'<p style="color:#fff;margin:0 0 12px">{_e(metin)}</p>{a}</div>')
        elif tur == "imza":
            out.append(f'<p style="color:#777;font-size:15px;margin:0">{_e(v)}</p>')
    return '<div style="font-size:18px;line-height:1.85">\n' + "\n".join(out) + "\n</div>"


# ---------------------------------------------------------------- içerik

def _bilgi(urun, details_html, kw, prof):
    ad = re.sub(r"\s+", " ", urun.get("name") or "").strip()
    label, uses_def = SM.machine_type(ad, prof, urun)
    ex_spec, ex_pkg, ex_use, ex_feat = SM.read_existing(details_html or "", kw, prof["magaza"])
    temiz = lambda xs: [x for x in xs if ST.count_kw(x if isinstance(x, str) else x[0] + " " + " ".join(x[1]), kw) == 0]  # noqa: E731
    uses = temiz(ex_use) or ["Günlük ve düzenli kullanım", "Yoğun tempolu profesyonel işler", "Ev, atölye ve hobi projeleri"]
    uses = [u.split(":")[0].strip() if ":" in u and len(u) > 70 else u for u in uses][:6]
    return {"ad": ad, "label": label, "spec": temiz(ex_spec)[:10], "pkg": temiz(ex_pkg)[:8], "uses": uses,
            "feat": temiz(ex_feat)[:6]}


def _kunye(urun, b, prof, kategori):
    return ("kunye", [("Ürün", b["ad"]), ("Ürün kodu", urun.get("sku") or ""), ("Barkod", urun.get("barcode") or ""),
                      ("Marka", prof["marka"]), ("Kategori", (kategori or {}).get("ad") or ""),
                      ("Satıcı", prof["magaza"])])


def _bloklar(bicim, urun, b, prof, kategori, rng):
    """Biçimin bölümleri. {k}: isteğe bağlı anma (hedef kelime ya da gönderme), {kw}: her zaman hedef kelime."""
    M, sku, bk = prof["magaza"] or "mağazamız", urun.get("sku") or "", urun.get("barcode") or ""
    at = PR.loc(prof["magaza"]) if prof["magaza"] else "mağazamızda"
    label, uses, spec, pkg, feat = b["label"], b["uses"], b["spec"], b["pkg"], b["feat"]
    marka = prof["marka"]
    kod = f"ürün kodu {sku}" + (f", barkodu {bk}" if bk else "") if sku else (f"barkodu {bk}" if bk else "")
    use_txt = ", ".join(u[:1].lower() + u[1:] for u in uses[:3])
    kunye = _kunye(urun, b, prof, kategori)
    spec_bl = [("spec", spec)] if spec else [("p", f"{{k}} için temel bilgiler aşağıdaki ürün künyesinde yer alır.")]
    pkg_bl = [("ul", pkg)] if pkg else []
    cta = ("cta", (f"{{kw}} {at}. Ürün kodu ve barkod numarasıyla doğru ürünü kolayca bulabilir, ayrıntıları ürün sayfasında "
                   "inceleyebilirsiniz.", f"{{kw}} ürün sayfasına git"))
    imza = ("imza", f"Bu yazı {M} ekibi tarafından hazırlanmıştır. {('Ürün kodu: ' + sku) if sku else ''}"
                    f"{(' · Barkod: ' + bk) if bk else ''}".strip())
    marka_t = f"{marka} kalitesini" if marka else "güvenilir bir yapıyı"

    if bicim == "rehber":
        h = [f"{{kw}} Kimler İçin Uygun?", "Satın Almadan Önce Kontrol Edilecekler", "Öne Çıkan Teknik Bilgiler",
             f"Neden {M}?", "Kısa Sorular, Net Cevaplar", "Son Söz"]
        return [
            ("lead", f"{{kw}}, {label} arayanların listesinde üst sıralarda yer alan bir seçenek. Bu rehberde {{k}} "
                     f"alırken nelere bakmanız gerektiğini, kimler için doğru tercih olduğunu ve {M} güvencesiyle nasıl "
                     "kolayca sahip olabileceğinizi adım adım anlatıyoruz."),
            ("toc", h[:5]),
            ("h2", h[0]),
            ("p", f"Her ürün her işe uygun değildir. {{k}}; {use_txt} gibi ihtiyaçlarda öne çıkar. Doğru seçimin ilk adımı, "
                  "ürünü hangi sıklıkta ve hangi koşullarda kullanacağınızı netleştirmektir."),
            ("check", [f"{u} için güvenilir bir {label} arayanlar" for u in uses[:3]]
             + [f"{marka_t} uygun bütçeyle buluşturmak isteyenler"]),
            ("h2", h[1]),
            ("p", f"{{k}} gibi bir ürünü seçerken yalnızca fiyata bakmak yanıltıcı olabilir. Aşağıdaki kontrol listesi "
                  "yanlış ürün almanızı ve sonradan pişmanlık yaşamanızı önler."),
            ("ol", ["İhtiyacınızı yazın: hangi işler, ne sıklıkla, hangi ortamda?",
                    "Teknik değerleri ürün açıklamasıyla karşılaştırın; kendi işinize yetip yetmediğini kontrol edin.",
                    "Ürün kodu ve barkodu doğrulayarak tam olarak aradığınız modeli aldığınızdan emin olun.",
                    "Elinizdeki aksesuarlarla uyumluluğu ve yedek parça bulunabilirliğini düşünün.",
                    "Garanti ve satış sonrası destek koşullarını ürün sayfasından okuyun."]),
            ("tip", ("İpucu:", f"{{k}} için kullanım senaryonuzu önceden belirlemek, gereksiz özelliklere para ödemenizi "
                               "engeller ve ürünün gerçek performansını görmenizi sağlar.")),
            ("h2", h[2]),
            *spec_bl,
            kunye,
            ("h2", h[3]),
            ("p", f"{{kw}} {at}; {kod} bilgisiyle listelenir. Bu sayede siparişinizi verirken doğru ürünü seçtiğinizden "
                  f"emin olursunuz. {M}, ürün sayfasında görselleri, teknik bilgileri ve kullanım ayrıntılarını tek yerde sunar."),
            ("h2", h[4]),
            ("faq", [(f"{{k}} nerelerde kullanılır?", f"{{k}}; {use_txt} için uygundur."),
                     ("Ürün kodu ve barkodu nedir?", f"Ürün kodu {sku or '-'}" + (f", barkod numarası {bk}." if bk else ".")),
                     ("Siparişten önce neyi kontrol etmeliyim?",
                      "Ürün kodunu, teknik bilgileri ve elinizdeki aksesuarlarla uyumluluğu kontrol etmeniz yeterlidir.")]),
            ("h2", h[5]),
            ("p", f"Doğru {label} işin kalitesini değiştirir. {{k}}, ihtiyacını bilen kullanıcı için akıllı bir yatırımdır."),
            ("fill", None),
            cta, imza,
        ]

    if bicim == "inceleme":
        h = ["İlk İzlenim", f"{{kw}} Teknik Özellikleri", "Artılar ve Dikkat Edilmesi Gerekenler", "Kimler Tercih Etmeli?",
             "Kutudan Neler Çıkıyor?", "Değerlendirme"]
        bolum = [h[0], h[1], h[2], h[3]] + ([h[4]] if pkg else []) + [h[5]]
        artilar = (feat or [f"{label} kategorisinde dengeli ve kullanışlı bir yapı",
                            "Ürün kodu ve barkodla kolay doğrulanabilir model bilgisi",
                            f"{u} için uygun kullanım" if (u := uses[0]) else "Çok yönlü kullanım"])[:5]
        return [
            ("lead", f"{{kw}}, kâğıt üzerindeki değerleriyle değil sahadaki performansıyla konuşulan ürünlerden. "
                     f"Bu incelemede {{k}} ürününü yakından ele alıyor, güçlü yanlarını ve kimler için doğru seçim olduğunu "
                     "açıkça anlatıyoruz."),
            ("toc", bolum),
            ("h2", h[0]),
            ("p", f"{{k}} ilk bakışta {label} kategorisinde aradığınız düzeni sunuyor. {marka + ' imzası, ' if marka else ''}"
                  f"özenli işçilik ve kullanıcıyı yormayan bir yapı ilk dikkat çeken noktalar."),
            ("quote", f"İyi bir {label}, işi bittiğinde varlığını unutturur; geriye yalnızca temiz bir sonuç kalır."),
            ("h2", h[1]),
            *spec_bl,
            kunye,
            ("h2", h[2]),
            ("h3", "Öne çıkan yönler"),
            ("check", artilar),
            ("h3", "Dikkat edilmesi gerekenler"),
            ("ul", ["Kullanmadan önce kılavuzdaki güvenlik uyarılarını mutlaka okuyun.",
                    "İşinize uygun aksesuarı seçmek sonucun kalitesini doğrudan etkiler.",
                    "Uzun ömür için kullanım sonrası temizlik ve doğru saklama şarttır."]),
            ("h2", h[3]),
            ("p", f"{{k}}; {use_txt} gibi işler yapan kullanıcılar için biçilmiş kaftan. Arada bir kullanacaklar da "
                  "yoğun tempoda çalışanlar da ürünü ihtiyaçlarına göre değerlendirebilir."),
            *([("h2", h[4]), ("p", f"{{k}} kutusundan çıkanlar:"), *pkg_bl] if pkg else []),
            ("h2", h[5]),
            ("p", f"Sonuç olarak {{k}}, {label} arayanlar için dengeli ve güven veren bir tercih. {{k}} ile ilgili tüm "
                  f"ayrıntılara {M} ürün sayfasından ulaşabilirsiniz."),
            ("fill", None),
            cta, imza,
        ]

    if bicim == "ipucu":
        ipuclari = [
            ("Önce kılavuzu okuyun", f"{{k}} ile çalışmaya başlamadan önce kullanım kılavuzunu okumak, ürünün tüm "
                                     "yeteneklerini keşfetmenin en hızlı yoludur."),
            ("Doğru işe doğru ürün", f"{{k}} en iyi sonucu {use_txt} gibi işlerde verir. Ürünü tasarım amacının dışında "
                                     "zorlamamak hem sonucu hem ömrü korur."),
            ("Aksesuar seçimini hafife almayın", "Uyumlu ve kaliteli aksesuarlar aynı işi daha temiz ve daha kısa sürede "
                                                 "bitirmenizi sağlar."),
            ("Güvenlik her zaman önce gelir", "İşe uygun koruyucu ekipman kullanın ve çalışma alanınızı düzenli tutun."),
            ("Kısa molalar verin", f"Uzun çalışmalarda {{k}} ile birlikte kendinize de mola verin; dinlenmiş eller daha "
                                   "hassas çalışır."),
            ("Kullanım sonrası temizlik", f"Her işten sonra {{k}} üzerindeki toz ve kalıntıları temizlemek, bir sonraki "
                                          "kullanımda sizi ilk günkü performansla karşılar."),
            ("Doğru saklayın", "Kuru, tozsuz ve çocukların erişemeyeceği bir yerde, mümkünse orijinal kutusunda saklayın."),
        ]
        rng.shuffle(ipuclari)
        out = [
            ("lead", f"{{kw}} elinizde olduğunda işin yarısı zaten hallolmuş demektir; diğer yarısı ise doğru kullanımda "
                     f"saklı. {M} olarak {{k}} ile daha verimli çalışmanız için 7 pratik ipucunu derledik."),
            ("toc", [f"{i}. {t}" for i, (t, _) in enumerate(ipuclari, 1)]),
        ]
        for i, (t, m) in enumerate(ipuclari, 1):
            out += [("h2" if i == 1 else "h3", f"{i}. {t}" if i > 1 else f"{i}. {t}: {{kw}} ile İlk Adım"), ("p", m)]
            if i == 3:
                out.append(("tip", ("Bonus ipucu:", f"{{k}} için yaptığınız işleri ve kullandığınız aksesuarları not "
                                                    "edin; bir sonraki projede doğru ayarı saniyeler içinde bulursunuz.")))
        out += [("h2", f"{{kw}} Hakkında Teknik Bilgiler"), *spec_bl, kunye,
                ("h2", "Özetle"),
                ("p", f"Bu ipuçlarıyla {{k}} size uzun yıllar eşlik eder. Sorularınız için {M} ekibine her zaman ulaşabilirsiniz."),
                ("fill", None), cta, imza]
        return out

    if bicim == "sss":
        sorular = [
            (f"{{kw}} nedir, ne işe yarar?", f"{{k}}, {label} kategorisinde yer alan bir üründür; {use_txt} için kullanılır."),
            ("Ürün kodu ve barkod numarası nedir?", f"Ürün kodu {sku or '-'}" + (f", barkod numarası {bk}." if bk else ".")
             + " Bu bilgilerle doğru ürünü kolayca doğrulayabilirsiniz."),
            (f"{{k}} hangi işlerde kullanılır?", f"{{k}} özellikle şu işlerde tercih edilir: {use_txt}."),
            ("Teknik özellikleri nelerdir?", "Öne çıkan teknik bilgiler aşağıdaki listede ve ürün sayfasında yer alır."
             if spec else "Teknik bilgiler ürün sayfasında ayrıntılı olarak yer alır."),
            ("Kutudan neler çıkıyor?", ("Paket içeriği: " + ", ".join(pkg[:5]) + ".") if pkg
             else "Paket içeriği ürün sayfasında ayrıntılı olarak listelenir."),
            (f"{{k}} nasıl bakım ister?", "Her kullanım sonrası temizlik, düzenli kontrol ve kuru bir ortamda saklama "
                                          "ürünün ömrünü uzatır."),
            ("Garanti koşulları nelerdir?", "Garanti koşulları ürün sayfasında ve ürünle birlikte gelen belgelerde yer alır."),
            (f"{{k}} nereden alınır?", f"{{k}} ürününü {M} üzerinden güvenle sipariş edebilirsiniz."),
        ]
        out = [
            ("lead", f"{{kw}} hakkında bize en çok sorulan soruları tek yerde topladık. Satın almadan önce {{k}} ile ilgili "
                     "merak ettiğiniz her şeyin net cevabı bu yazıda."),
            ("toc", [ST.strip_tags(q.replace("{kw}", "Ürün").replace("{k}", "Ürün")) for q, _ in sorular[:6]]),
            ("h2", f"{{kw}}: En Çok Sorulan Sorular"),
            ("faq", sorular[:4]),
            *spec_bl,
            kunye,
            ("h2", "Kullanım, Bakım ve Sipariş"),
            ("faq", sorular[4:]),
            ("tip", ("İpucu:", f"Sorunuzun cevabını burada bulamadıysanız ürün kodunu ({sku or '-'}) belirterek {M} "
                               "müşteri hizmetlerine yazabilirsiniz; doğru ürüne hemen ulaşırız.")),
            ("p", f"{{k}} ile ilgili yeni sorular geldikçe bu sayfayı güncelliyoruz."),
            ("fill", None), cta, imza,
        ]
        return out

    if bicim == "bakim":
        h = ["Neden Düzenli Bakım?", "Her Kullanımdan Sonra", "Periyodik Kontroller", "Doğru Saklama",
             "Sık Yapılan Hatalar", f"{{kw}} Künyesi"]
        return [
            ("lead", f"{{kw}} doğru bakımla yıllarca ilk günkü performansını korur. Bu rehberde {{k}} için günlük ve "
                     "periyodik bakım adımlarını, doğru saklama yöntemlerini ve kaçınmanız gereken hataları bulacaksınız."),
            ("toc", h[:5]),
            ("h2", h[0]),
            ("p", f"Bakım, ürünün performansını korumanın en ucuz yoludur. {{k}} düzenli bakıldığında hem daha güvenli "
                  "çalışır hem de beklenmedik arızaların önüne geçilir."),
            ("h2", h[1]),
            ("ol", [f"Ürünü kapatın ve varsa güç bağlantısını ayırın.", "Yüzeydeki toz ve kalıntıları kuru bir bezle alın.",
                    "Hava kanallarını ve hareketli parçaları yumuşak bir fırçayla temizleyin.",
                    "Aksesuarları ayrı ayrı temizleyip yerlerine yerleştirin."]),
            ("tip", ("İpucu:", f"{{k}} temizliğinde sert kimyasallar yerine kuru bez ve yumuşak fırça kullanın.")),
            ("h2", h[2]),
            ("check", ["Kablo, fiş ve bağlantı noktalarında hasar olup olmadığını kontrol edin.",
                       "Vida ve bağlantı elemanlarının sıkılığını gözden geçirin.",
                       "Aşınan aksesuarları zamanında yenileyin.",
                       "Alışılmadık ses ya da titreşim fark ederseniz kullanımı durdurun."]),
            ("h2", h[3]),
            ("p", f"{{k}} için en iyi yer kuru, tozsuz ve sıcaklık değişimlerinin az olduğu bir dolaptır. Mümkünse ürünü "
                  "orijinal kutusunda ya da taşıma çantasında saklayın."),
            ("h2", h[4]),
            ("cross", ["Ürünü kullanım amacının dışında zorlamak", "Temizliği sonraya bırakmak",
                       "Nemli ortamda saklamak", "Uyumsuz aksesuar kullanmak"]),
            ("h2", h[5]),
            ("p", f"{{k}} hakkındaki temel bilgiler:"),
            *([("spec", spec)] if spec else []),
            kunye,
            ("p", f"Bakım konusunda sorularınız için {M} ekibi her zaman yanınızda."),
            ("fill", None), cta, imza,
        ]

    # senaryo
    sahne = uses[:4] if len(uses) >= 2 else uses + ["Profesyonel kullanım", "Ev ve hobi projeleri"]
    h = [f"{{kw}} Nerelerde Fark Yaratır?"] + [f"Senaryo {i}: {u}" for i, u in enumerate(sahne, 1)] + [
        "Doğru Aksesuarla Daha İyi Sonuç", "Teknik Bilgiler"]
    out = [
        ("lead", f"{{kw}} ile neler yapabileceğinizi merak ediyorsanız doğru yerdesiniz. {{k}} ürününü farklı işlerde "
                 "nasıl kullanabileceğinizi gerçek senaryolar üzerinden anlattık."),
        ("toc", [x.replace("{kw}", "Ürün") for x in h]),
        ("h2", h[0]),
        ("p", f"{{k}} tek bir işe sıkışıp kalmayan, çok yönlü bir {label}. Aşağıdaki senaryolar en sık karşılaşılan "
              "kullanım alanlarını özetliyor."),
    ]
    anlat = ["{u} sırasında {{k}} ile kontrollü ve temiz bir sonuç elde edebilirsiniz. İşe başlamadan önce çalışma alanını "
             "hazırlamak ve doğru aksesuarı seçmek farkı belirgin şekilde artırır.",
             "{u} gibi işlerde süreklilik önemlidir. {{k}} bu tempoya ayak uydurur; doğru ayar ve kısa molalarla iş hem "
             "hızlı hem de güvenli biter.",
             "{u} için önce ölçü alın ve işi planlayın. Ardından {{k}} ile işi planladığınız gibi, tekrar uğraşmadan "
             "tamamlayabilirsiniz.",
             "{u} sonrasında ürünü temizleyip yerine kaldırmak, bir sonraki işte sizi hazır bekletir."]
    for i, u in enumerate(sahne):
        out += [("h3", h[i + 1]), ("p", anlat[i % len(anlat)].replace("{u}", u).replace("{{k}}", "{k}"))]
    out += [("h2", h[-2]),
            ("p", f"{{k}} ile alacağınız sonucun kalitesi, kullandığınız aksesuarla doğrudan ilişkilidir. İşe uygun aksesuarı "
                  "seçmek, ürünün potansiyelini tam olarak ortaya çıkarır."),
            ("tip", ("İpucu:", f"Yeni bir işe başlamadan önce {{k}} ile küçük bir deneme yapın; ayarı ve aksesuarı "
                               "işinize göre netleştirin.")),
            ("h2", h[-1]), *spec_bl, kunye,
            ("p", f"Daha fazla kullanım fikri için {M} blogunu takip edin."),
            ("fill", None), cta, imza]
    return out


def _doldur(bloklar, kw, label):
    """{kw} her zaman hedef kelime; {k} yerleri tek tek sayılır (yoğunluk ayarı)."""
    def f(t):
        return t.replace("{kw}", kw).replace("{label}", label) if isinstance(t, str) else t

    out = []
    for tur, v in bloklar:
        if isinstance(v, str):
            v = f(v)
        elif isinstance(v, tuple):
            v = tuple(f(x) for x in v)
        elif isinstance(v, list):
            v = [tuple(f(y) for y in x) if isinstance(x, tuple) and tur == "faq" else (f(x) if isinstance(x, str) else x)
                 for x in v]
        out.append((tur, v))
    return out


def _yer_sayisi(bloklar):
    n = 0
    for _, v in bloklar:
        for t in _metinler(v):
            n += t.count("{k}")
    return n


def _metinler(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _metinler(x)


def _uygula(bloklar, kw, refs, secili, dolgu, ek=()):
    """{k} yerlerine hedef kelime (secili sıradakiler) ya da gönderme; 'fill' bloğuna ek cümleler."""
    sayac = [0]

    def f(t):
        if not isinstance(t, str) or "{k}" not in t:
            return t
        parca, son = [], 0
        for m in re.finditer(r"\{k\}", t):
            i = sayac[0]
            sayac[0] += 1
            s = kw if i in secili else refs[i % len(refs)]
            if s is not kw and _cumle_basi(t, m.start()):
                s = _bas_harf(s)
            parca += [t[son:m.start()], s]
            son = m.end()
        return "".join(parca) + t[son:]

    def g(v):
        if isinstance(v, str):
            return f(v)
        if isinstance(v, tuple):
            return tuple(g(x) for x in v)
        if isinstance(v, list):
            return [g(x) for x in v]
        return v

    out = []
    for tur, v in bloklar:
        if tur == "fill":
            out.append(("p", " ".join(list(ek) + list(dolgu))))
        else:
            out.append((tur, g(v)))
    return out


def _dagit(j, n):
    """n yer içinden j tanesini eşit aralıklarla seçer."""
    if j <= 0 or n <= 0:
        return set()
    return {min(n - 1, int((t + 0.5) * n / j)) for t in range(j)}


# ---------------------------------------------------------------- başlık, meta, özet

def sayfa_basligi(kw, bicim, magaza):
    ek = BICIMLER[bicim]["ek"]
    for t in (f"{kw} {ek} | {magaza}" if magaza else "", f"{kw} {ek}", f"{kw} | {magaza}" if magaza else "",
              f"{kw} Rehberi", kw, f"{kw} Hakkında Her Şey"):
        if t and 20 <= len(t) <= 60:
            return t
    return kw[:60]


def meta_aciklama(kw, bicim, magaza, rng):
    at = PR.loc(magaza) if magaza else ""
    adaylar = {
        "rehber": [f"{kw} alırken nelere dikkat etmeli? Kontrol listesi, teknik bilgiler ve ipuçlarıyla doğru seçim rehberi {at}.",
                   f"{kw} satın alma rehberi: kimler için uygun, nelere bakılmalı? Ürün kodu ve barkoduyla {at}."],
        "inceleme": [f"{kw} incelemesi: teknik özellikler, artılar ve dikkat edilmesi gerekenler. Detaylar ve fiyat {at}.",
                     f"{kw} detaylı inceleme ve kullanım notları. Kimler tercih etmeli? Tüm ayrıntılar {at}."],
        "ipucu": [f"{kw} ile daha verimli çalışmanın 7 pratik ipucu: kullanım, aksesuar, güvenlik ve bakım önerileri {at}.",
                  f"{kw} kullanırken işinizi kolaylaştıracak 7 ipucu. Ürün kodu, barkod ve teknik bilgiler {at}."],
        "sss": [f"{kw} hakkında en çok sorulan sorular: ürün kodu, barkod, kullanım alanları, bakım ve sipariş {at}.",
                f"{kw} ile ilgili merak ettiğiniz her şeyin net cevabı. Ürün kodu, barkod ve teknik bilgiler {at}."],
        "bakim": [f"{kw} bakımı nasıl yapılır? Günlük temizlik, periyodik kontrol ve saklama önerileri {at}.",
                  f"{kw} uzun ömürlü kullanım için adım adım bakım rehberi ve sık yapılan hatalar {at}."],
        "senaryo": [f"{kw} hangi işlerde kullanılır? Gerçek kullanım senaryoları, aksesuar önerileri ve ipuçları {at}.",
                    f"{kw} ile neler yapabilirsiniz? Uygulama örnekleri, teknik bilgiler ve ürün detayları {at}."],
    }[bicim]
    rng.shuffle(adaylar)
    for a in adaylar + [f"{kw}: kullanım, bakım ve teknik bilgiler tek sayfada {at}.".replace(" .", ".")]:
        a = re.sub(r"\s+\.", ".", a)
        if 50 <= len(a) <= 155:
            return a
    a = adaylar[0]
    return (a[:152].rsplit(" ", 1)[0] + "...") if len(a) > 155 else (a + " Ürün detayları ve ipuçları.")[:155]


def ozet(kw, bicim, magaza):
    s = {"rehber": f"{kw} alırken nelere dikkat etmelisiniz? Kontrol listesi, teknik bilgiler ve uzman ipuçlarıyla doğru seçim rehberi.",
         "inceleme": f"{kw} incelemesi: öne çıkan özellikler, dikkat edilmesi gerekenler ve kimlerin tercih etmesi gerektiği.",
         "ipucu": f"{kw} ile daha verimli çalışmanız için kullanım, aksesuar, güvenlik ve bakım üzerine 7 pratik ipucu.",
         "sss": f"{kw} hakkında en çok sorulan soruların net cevapları: ürün kodu, barkod, kullanım, bakım ve sipariş.",
         "bakim": f"{kw} için günlük bakım, periyodik kontrol ve doğru saklama önerileri; sık yapılan hatalar ve çözümleri.",
         "senaryo": f"{kw} hangi işlerde kullanılır? Gerçek kullanım senaryoları, aksesuar seçimi ve pratik öneriler."}[bicim]
    return s + (f" {magaza} blogunda." if magaza else "")


def anahtar_kelimeler(kw, label, bicim, prof):
    ek = {"rehber": "nasıl seçilir", "inceleme": "inceleme", "ipucu": "kullanım ipuçları", "sss": "sık sorulan sorular",
          "bakim": "bakım", "senaryo": "kullanım alanları"}[bicim]
    items = [kw, f"{kw} {ek}", label, f"{label} {ek}"] + ([f"{prof['marka']} {label}"] if prof["marka"] else []) \
        + ([prof["magaza"]] if prof["magaza"] else [])
    seen, out = set(), []
    for i in items:
        if ST.tr_lower(i) not in seen:
            seen.add(ST.tr_lower(i))
            out.append(i)
    return ", ".join(out)


# ---------------------------------------------------------------- yazar

def yaz(urun, details_html="", mevcut_kw="", bicim="", varyant=0, prof=None, method="", hedef=2.5, renk="#1b4f72",
        kategori=None, kw=""):
    """urun: Ideasoft ürün kaydı (id, name, sku, barcode, slug, brand, categories). kategori: {"ad", "slug"} (isteğe bağlı).
    kw verilirse o hedef kelime kullanılır (kullanıcının düzenlediği). Dönüş: blog planı (mağazaya yazılmaz)."""
    prof = PR.with_brand(prof, urun)
    pid = urun.get("id") or 0
    bicim = bicim_sec(bicim, pid, varyant)
    ad = re.sub(r"\s+", " ", urun.get("name") or "").strip()
    kw = re.sub(r"\s+", " ", kw or "").strip() or kelime_sec(ad, mevcut_kw, prof)
    rng = _rng(pid, bicim, varyant)
    renk = renk if re.fullmatch(r"#[0-9a-fA-F]{6}", renk or "") else "#1b4f72"
    b = _bilgi(urun, details_html, kw, prof)
    baslik = rng.choice(BASLIKLAR[bicim]).replace("{kw}", kw)
    link = f"/urun/{urun['slug']}" if urun.get("slug") else ""

    refs = [r.replace("{label}", b["label"]) for r in GONDERME]
    dolgu = [d for d in DOLGU if ST.count_kw(d, kw) == 0]
    rng.shuffle(dolgu)
    methods = [m for m in (method or "").split(",") if m in ST.COUNT_METHODS] or list(ST.COUNT_METHODS)
    ek = [PR.fill(x, prof).replace("{kw}", kw) for x in KW_EK if PR.usable(x, prof)]
    rng.shuffle(ek)

    en_iyi = None
    # teknik liste çok uzunsa (yoğunluk %2'ye çıkamıyorsa) kısaltılır; önce bütün liste denenir
    tum_spec = b["spec"]
    for sinir in sorted({len(tum_spec), 7, 5, 3}, reverse=True):
        if sinir > len(tum_spec):
            continue
        b2 = dict(b, spec=tum_spec[:sinir])
        ham = _doldur(_bloklar(bicim, urun, b2, prof, kategori, _rng(pid, bicim, varyant)), kw, b["label"])
        n_yer = _yer_sayisi(ham)
        for m_ in range(0, len(ek) + 1):
            for n in range(0, len(dolgu) + 1):
                for j in range(0, n_yer + 1):
                    h = _render(_uygula(ham, kw, refs, _dagit(j, n_yer), dolgu[:n], ek[:m_]), kw, renk, link)
                    c = ST.count_kw(ST.strip_tags(h), kw)
                    ws = [ST.count_words(h, m) for m in methods]
                    dens = [c / w * 100 if w else 0 for w in ws]
                    pay = min(min(d - 2.0, 3.0 - d) for d in dens)
                    ort = sum(dens) / len(dens)
                    # önce güvenli aralık, sonra uzun teknik liste, hedefe yakınlık, az ek cümle (doğal metin)
                    anahtar = (min(pay, 0.25), sinir, -round(abs(ort - hedef), 1), -m_, -n, -j)
                    if en_iyi is None or anahtar > en_iyi[0]:
                        en_iyi = (anahtar, h, dens)
                    if min(dens) > 3.0:          # daha çok anma yalnızca yükseltir
                        break
                if en_iyi[0][0] >= 0.25:
                    break
            if en_iyi[0][0] >= 0.25:
                break
        if en_iyi[0][0] >= 0.25:
            break
    _, icerik, dens = en_iyi

    magaza = prof["magaza"]
    pt = sayfa_basligi(kw, bicim, magaza)
    md = meta_aciklama(kw, bicim, magaza, _rng(pid, "meta", varyant))
    plan = {"v": SURUM, "keyword": kw, "title": baslik, "slug": slug(baslik), "excerpt": ozet(kw, bicim, magaza),
            "content": icerik, "pageTitle": pt, "metaDescription": md,
            "metaKeywords": anahtar_kelimeler(kw, b["label"], bicim, prof), "bicim": bicim, "varyant": varyant,
            "rozet": BICIMLER[bicim]["rozet"], "label": b["label"],
            "densities": {m: round(d, 2) for m, d in zip(methods, dens)},
            "urun": {"id": pid, "ad": ad, "sku": urun.get("sku") or "", "barkod": urun.get("barcode") or "",
                     "link": link, "marka": prof["marka"]}}
    plan["score"] = puan(plan, method)
    return plan


def yaz_tam(urun, details_html="", mevcut_kw="", bicim="", varyant=0, kw="", **kw_args):
    """yaz() ile aynı; yazı 13 kuralın hepsini tutmazsa sırayla başka anlatım, başka biçim ve (hedef kelimeyi kullanıcı
    seçmediyse) daha kısa bir hedef kelime denenir. İlk %100 olan döner; hiçbiri olmazsa en yüksek puanlı."""
    ilk = bicim_sec(bicim, urun.get("id") or 0, varyant)
    denemeler = [(ilk, varyant, kw), (ilk, varyant + 1, kw)] + [(b, varyant, kw) for b in SIRA if b != ilk]
    if not kw:
        ad = re.sub(r"\s+", " ", urun.get("name") or "").strip()
        prof = PR.with_brand(kw_args.get("prof"), urun)
        for uz in (30, 22):
            kisa = kelime_sec(ad, mevcut_kw, prof, en_uzun=uz)
            denemeler += [(ilk, varyant, kisa)] + [(b, varyant, kisa) for b in SIRA if b != ilk]
    en_iyi = None
    for b, v, k in denemeler:
        p = yaz(urun, details_html, mevcut_kw, b, v, kw=k, **kw_args)
        if en_iyi is None or p["score"]["yuzde"] > en_iyi["score"]["yuzde"]:
            en_iyi = p
        if p["score"]["yuzde"] == 100:
            break
    return en_iyi


def puan(plan, method=""):
    """Ideasoft'un blog kuralları (13 madde): ST.seo_score'un blog karşılığı; adlar paneldeki gibi."""
    s = ST.seo_score(plan.get("title") or "", plan.get("keyword") or "", plan.get("content") or "",
                     plan.get("pageTitle") or "", plan.get("metaDescription") or "", method)
    kwl = ST.tr_lower(plan.get("keyword") or "")
    t, pt, md = plan.get("title") or "", plan.get("pageTitle") or "", plan.get("metaDescription") or ""
    plain = ST.strip_tags(plan.get("content") or "")
    kurallar = [
        (bool(kwl), "Hedef kelime tanımlandı"),
        (bool(t.strip()), "Blog adı boş bırakılamaz"),
        (bool(kwl) and kwl in ST.tr_lower(t), "Hedef kelime blog başlığı içerisinde geçiyor"),
        (bool(plain), "Blog açıklama alanı boş bırakılamaz"),
        (s["count"] > 0, "Hedef kelime blog açıklaması içerisinde geçiyor"),
        (s["words"] >= 50, f"Blog açıklaması en az 50 kelime (kelime sayısı: {s['words']})"),
        (2.0 <= s["density"] <= 3.0, f"Hedef kelime yoğunluğu %2-%3 (oran: %{s['density']:.2f})".replace(".", ",")),
        (bool(pt), "Blog sayfa başlığı dolu"),
        (20 <= len(pt) <= 60, f"Sayfa başlığı 20-60 karakter ({len(pt)} karakter)"),
        (bool(kwl) and kwl in ST.tr_lower(pt), "Hedef kelime sayfa başlığında geçiyor"),
        (bool(md), "Blog meta açıklaması dolu"),
        (50 <= len(md) <= 155, f"Meta açıklama 50-155 karakter ({len(md)} karakter)"),
        (bool(kwl) and kwl in ST.tr_lower(md), "Hedef kelime meta açıklamada geçiyor"),
    ]
    tamam = sum(ok for ok, _ in kurallar)
    return {"yuzde": round(100 * tamam / len(kurallar)), "tamam": tamam, "toplam": len(kurallar),
            "kurallar": [{"ok": ok, "ad": ad} for ok, ad in kurallar], "kelime": s["words"], "yogunluk": s["density"],
            "gecis": s["count"]}


def gonderilecek(plan, kategori_id, durum=1, gorsel=None, kw_alani="targetKeyword"):
    """Ideasoft blogs kaynağına gidecek kayıt (POST / PUT). gorsel: (dosya adı, data URL) ya da None."""
    body = {"title": plan["title"][:255], "slug": plan["slug"][:255], "excerpt": plan["excerpt"],
            "content": plan["content"], "pageTitle": plan["pageTitle"][:255],
            "metaDescription": plan["metaDescription"], "metaKeywords": plan["metaKeywords"],
            "blockVisibility": 1, "status": 1 if durum else 0,
            "categories": [{"id": int(kategori_id)}] if kategori_id else []}
    if kw_alani:
        body[kw_alani] = plan["keyword"]
    if gorsel:
        ad, veri = gorsel
        body.update(imageFileName=ad, imageExtension="jpg", attachment=veri)
    return body


# ---------------------------------------------------------------- blog görseli (panelde, canvas ile çizilir)

GORSEL_TEMALAR = {"mektup": "Mektup", "gece": "Gece mavisi", "atolye": "Atölye çizimi", "vitrin": "Vitrin", "santiye": "Şantiye",
                  "cam": "Cam (modern)", "gazete": "Gazete manşeti", "minimal": "Minimal"}
GORSEL_VARSAYILAN = {"tema": "mektup", "renk": "#b3261e", "renk2": "#1f2a44", "foto": True, "yazi": "serif",
                     "magaza": True, "rozet": True, "kod": True, "desen": True, "ust_metin": ""}


def gorsel_ayar(d):
    """Blog görseli ayarları; geçersiz değerler varsayılana döner. Bütün yazıların görseli aynı ayarla çizilir."""
    d = d if isinstance(d, dict) else {}
    out = dict(GORSEL_VARSAYILAN)
    if d.get("tema") in GORSEL_TEMALAR:
        out["tema"] = d["tema"]
    for k in ("renk", "renk2"):
        if re.fullmatch(r"#[0-9a-fA-F]{6}", str(d.get(k) or "")):
            out[k] = d[k].lower()
    for k in ("foto", "magaza", "rozet", "kod", "desen"):
        if k in d:
            out[k] = bool(d[k]) and d[k] not in ("0", "false")
    if d.get("yazi") in ("serif", "sans"):
        out["yazi"] = d["yazi"]
    out["ust_metin"] = re.sub(r"\s+", " ", str(d.get("ust_metin") or "")).strip()[:40]
    return out
