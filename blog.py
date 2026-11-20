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

import kalite as KA
import kelime as KE
import profil as PR
import seo_machine as SM
import seo_text as ST

SURUM = 5   # yazar değiştikçe artar; eski hazırlıklar "eski" görünür

# mağaza vitrinindeki adreslerin önekleri (Ideasoft); iç bağlantılar bunlarla kurulur
YOLLAR = {"urun": "/urun/", "kategori": "/kategori/", "blog": "/blog/", "blog_ana": "/blog"}

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

# girişler: aynı biçimdeki yazılar aynı cümleyle başlamasın (doğal, insan yazmış gibi okunur)
GIRIS = {
    "rehber": [
        "{kw} almayı düşünüyorsanız önce şu soruyu sorun: Bu ürünü hangi işte, ne sıklıkla kullanacağım? Bu rehberde {k} için "
        "bakmanız gereken noktaları sırayla ele alıyoruz.",
        "Doğru {label} seçmek, ilk bakışta göründüğünden daha fazla ayrıntı ister. {kw} özelinde neye dikkat etmeniz gerektiğini, "
        "kimler için uygun olduğunu ve {M} üzerinden nasıl kolayca alabileceğinizi anlattık.",
        "Bir {label} alırken çoğu kişi yalnızca fiyata bakar, sonra ihtiyacına uymadığını fark eder. {kw} alırken bu hataya "
        "düşmemeniz için kontrol listesi, teknik bilgiler ve pratik önerileri tek yazıda topladık.",
    ],
    "inceleme": [
        "{kw} hakkında karar vermeden önce ürünü yakından tanımak istiyorsanız doğru yerdesiniz. Bu incelemede {k} ürününün "
        "güçlü yanlarını ve kimler için mantıklı olduğunu açıkça anlatıyoruz.",
        "Kâğıt üzerindeki değerler bir şey, günlük kullanım başka bir şey. {kw} incelemesinde ikisine de bakıyor, dikkat "
        "edilmesi gereken noktaları saklamadan yazıyoruz.",
        "{kw}, {label} arayanların sık karşılaştırdığı modellerden. Bu yazıda {k} ürününü özellikleri, kullanım alanları ve "
        "kutu içeriğiyle birlikte ele aldık.",
    ],
    "ipucu": [
        "{kw} elinizdeyse işin yarısı hazır; diğer yarısı doğru kullanımda saklı. {M} olarak {k} ile daha verimli çalışmanız "
        "için 7 pratik ipucu derledik.",
        "Aynı aletle iki kişi çalışır, biri işi yarı sürede bitirir. Fark çoğu zaman küçük alışkanlıklarda. {kw} için işinizi "
        "kolaylaştıracak 7 ipucunu sırayla anlattık.",
        "{kw} kullanırken birkaç basit kurala uymak hem sonucu hem ürünün ömrünü değiştirir. Bu yazıda {k} için en çok işe "
        "yarayan 7 öneriyi bulacaksınız.",
    ],
    "sss": [
        "{kw} hakkında bize en çok sorulan soruları tek yerde topladık. Satın almadan önce {k} ile ilgili merak ettiğiniz "
        "her şeyin net cevabı bu yazıda.",
        "Bir ürünü almadan önce akla takılan sorular genelde aynıdır. {kw} için bu soruları kısa ve net cevaplarla "
        "yanıtladık; ayrıntılar için ürün sayfasına da bağlantı verdik.",
        "{kw} ile ilgili sorularınız mı var? En sık sorulanları seçtik, cevaplarını ürünün kendi bilgilerinden derledik.",
    ],
    "bakim": [
        "{kw} doğru bakımla yıllarca ilk günkü performansını korur. Bu rehberde {k} için günlük ve periyodik bakım "
        "adımlarını, doğru saklama yöntemlerini ve kaçınmanız gereken hataları bulacaksınız.",
        "Bakımı ihmal edilen bir {label}, beklenenden çok daha erken yorulur. {kw} için birkaç dakikanızı alacak düzenli "
        "bakım adımlarını sade bir dille anlattık.",
        "{kw} uzun yıllar sorunsuz çalışsın istiyorsanız bakım bir alışkanlık olmalı. Her kullanımdan sonra ve belirli "
        "aralıklarla yapılacakları adım adım sıraladık.",
    ],
    "senaryo": [
        "{kw} ile neler yapabileceğinizi merak ediyorsanız doğru yerdesiniz. {k} ürününü farklı işlerde nasıl "
        "kullanabileceğinizi gerçek senaryolar üzerinden anlattık.",
        "Bir {label} tek bir işe sıkışıp kalmamalı. {kw} için en sık karşılaşılan kullanım alanlarını ve her birinde nelere "
        "dikkat etmeniz gerektiğini örneklerle anlattık.",
        "{kw} hangi işte, nasıl kullanılır? Bu yazıda {k} için kullanım senaryolarını, aksesuar seçimini ve pratik "
        "önerileri tek tek ele aldık.",
    ],
}

# ek bölümler: her yazıya ürüne göre ikisi seçilir (yazılar birbirinin kopyası olmaz); {k} yoğunluk ayarına katılır
EK_BOLUMLER = {
    "sorular": ("Karar Vermeden Önce Kendinize Sorun",
                [("p", "Seçimi kolaylaştırmanın en kısa yolu ihtiyacı netleştirmektir. Şu sorulara vereceğiniz cevaplar "
                       "{k} için doğru karar olup olmadığını büyük ölçüde gösterir."),
                 ("ol", ["Bu ürünü en çok hangi işte kullanacağım?", "Haftada kaç kez, ne kadar süreyle çalışacağım?",
                         "Elimdeki aksesuarlar ve yedek parçalar uyumlu mu?",
                         "Teknik değerler işimin gerektirdiğini karşılıyor mu?"])]),
    "hatalar": ("Sık Yapılan Seçim Hataları",
                [("p", "Pişmanlıkla biten alışverişlerin çoğu aynı birkaç hatadan kaynaklanır. {k} alırken bunlardan "
                       "kaçınmanız yeterli."),
                 ("cross", ["Yalnızca fiyata bakıp ihtiyacı hesaba katmamak", "Teknik değerleri işle karşılaştırmamak",
                            "Ürün kodunu doğrulamadan sipariş vermek", "Aksesuar uyumunu sonraya bırakmak"])]),
    "guvenlik": ("Kullanırken Güvenlik",
                 [("p", "İyi sonuç güvenli çalışmayla başlar. {k} ile çalışmadan önce kısa bir kontrol yapmak hem sizi "
                        "hem ürünü korur."),
                  ("check", ["Kullanım kılavuzundaki uyarıları okuyun", "İşe uygun koruyucu ekipman kullanın",
                             "Çalışma alanını temiz ve düzenli tutun", "Çocukların erişemeyeceği yerde saklayın"])]),
    "aksesuar": ("Uyumlu Aksesuar ve Sarf Malzemesi",
                 [("p", "Aynı ürünle alınan sonuç, kullanılan aksesuara göre belirgin şekilde değişir. {k} için işe uygun, "
                        "kaliteli aksesuar seçmek hem süreyi kısaltır hem de daha temiz bir iş çıkarır."),
                  ("p", "Aksesuar alırken ölçüye, bağlantı tipine ve yaptığınız işin malzemesine bakın. Emin olamadığınızda "
                        "ürün kodunu belirterek bize sormanız en hızlı yoldur.")]),
    "ilk_kullanim": ("İlk Kullanım İçin Kısa Kontrol Listesi",
                     [("p", "Kutuyu açtıktan sonraki ilk birkaç dakika, {k} ile uzun ve sorunsuz bir başlangıç yapmanızı "
                            "sağlar."),
                      ("ol", ["Paket içeriğini kontrol edin", "Kılavuzu baştan sona bir kez okuyun",
                              "Ürünü küçük ve basit bir işte deneyin", "Ayarları ve aksesuarları işinize göre netleştirin"])]),
    "butce": ("Fiyat ve Değer Dengesi",
              [("p", "En ucuz seçenek çoğu zaman en pahalıya patlar; en pahalısı da her işe gerekmez. {k} için doğru soru, "
                     "ürünün sizin işinizde kaç yıl ve ne sıklıkla çalışacağıdır."),
               ("p", "Kullanım sıklığınızı ve beklentinizi netleştirdiğinizde, ödediğiniz bedelin karşılığını alıp "
                     "almayacağınızı kolayca görürsünüz.")]),
    "tasima": ("Taşıma ve Saklama Önerileri",
               [("p", "Ürünü bir işten diğerine taşırken korumak, ömrünü belirgin şekilde uzatır. {k} için mümkünse "
                      "orijinal kutusunu ya da bir taşıma çantasını kullanın."),
                ("ul", ["Kuru ve tozsuz bir yerde saklayın", "Üzerine ağır eşya koymayın",
                        "Kablolu ürünlerde kabloyu sıkı sarmayın", "Uzun süre kullanmayacaksanız temizleyip kaldırın"])]),
    "destek": ("Satış Sonrası Destek ve Garanti",
               [("p", "Bir ürünü alırken yalnızca bugünü değil, yarını da düşünmek gerekir. {k} için garanti koşulları ve "
                      "yedek parça bulunabilirliği ürün sayfasında ve ürünle gelen belgelerde yer alır."),
                ("p", "Sorun yaşarsanız ürün kodunu ve satın alma bilgisini hazır tutmanız, desteğin hızlı ilerlemesini "
                      "sağlar.")]),
    "kod": ("Doğru Ürünü Bulmanın Kısa Yolu",
            [("p", "Benzer adlı ürünler arasında yanlış modeli almak sık yaşanan bir durum. Ürün kodu ve barkod bu karışıklığı "
                   "ortadan kaldırır: {k} için sipariş vermeden önce sayfadaki kodu kontrol etmeniz yeterli.")]),
}

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


def kodsuz(metin, sku):
    """Ürün kodunu (stok kodu) hedef kelimeden ve başlık gövdesinden çıkarır; kod başlığın sonuna ayrıca eklenir."""
    sku = (sku or "").strip()
    if not sku:
        return metin
    kalan = [w for w in (metin or "").split() if ST.tr_lower(w.strip(",.;:()[]")) != ST.tr_lower(sku)]
    return " ".join(kalan).strip(" ,-") if kalan else metin


def kelime_sec(ad, mevcut="", prof=None, en_uzun=40, sku=""):
    """Blogun hedef kelimesi: ürünün hedef kelimesi kısa ve adında geçiyorsa o, değilse addan kısa bir parça.
    Kısa kelime, yazının doğal okunmasını sağlar (%2-%3 yoğunlukta uzun bir ifade metni bozar)."""
    ad = kodsuz(ad, sku)
    cur = kodsuz((mevcut or "").strip(), sku)
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


# okunaklı ve ferah yazı: büyük punto ve geniş satır aralığı sarmalayıcıda, boşluk başlıklarda ve kutularda. Paragraf ve
# listelere ayrı stil yazılmaz: Ideasoft HTML'deki stilleri de kelime sayar, fazla stil hedef kelimeyi gereksiz tekrarlatır.


def _render(bloklar, kw, renk, link):
    """Bloklar: (tür, içerik). Satır içi stiller kısa tutulur (Ideasoft editörü TinyMCE; kelime sayımı)."""
    out = []
    kwe = _e(kw)
    for tur, v in bloklar:
        if tur == "lead":
            t = _e(v).replace(kwe, f"<strong>{kwe}</strong>", 1)
            out.append(f'<p style="font-size:20px;line-height:1.75;margin:0 0 26px">{t}</p>')
        elif tur == "h2":
            out.append(f'<h2 style="color:{renk};margin:40px 0 14px">{_e(v)}</h2>')
        elif tur == "h3":
            out.append(f'<h3 style="margin:28px 0 10px">{_e(v)}</h3>')
        elif tur == "p":
            if v:
                out.append(f"<p>{_e(v)}</p>")
        elif tur in ("ul", "ol"):
            if v:
                out.append(f"<{tur}>" + "".join(f"<li>{_e(x)}</li>" for x in v) + f"</{tur}>")
        elif tur in ("check", "cross"):
            isaret = "✔" if tur == "check" else "✘"
            if v:
                out.append('<ul style="list-style:none;margin:0 0 22px;padding-left:4px">'
                           + "".join(f"<li>{isaret} {_e(x)}</li>" for x in v) + "</ul>")
        elif tur == "toc":
            out.append(f'<div style="border-left:5px solid {renk};background:#f6f7f9;padding:18px 24px;margin:26px 0 30px">'
                       "<p><strong>Bu yazıda</strong></p><ol>"
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
            out.append("<ul>" + "".join(items) + "</ul>")
        elif tur == "tip":
            baslik, metin = v
            out.append('<div style="background:#fff8e6;border:1px dashed #d9a933;padding:18px 22px;margin:28px 0">'
                       f'<p style="margin:0"><strong>{_e(baslik)}</strong> {_e(metin)}</p></div>')
        elif tur == "quote":
            out.append(f'<blockquote style="border-left:5px solid {renk};margin:28px 0;padding:8px 22px;font-size:20px;'
                       f'font-style:italic"><p style="margin:0">{_e(v)}</p></blockquote>')
        elif tur == "faq":
            for q, a in v:
                out.append(f'<h3 style="margin:26px 0 8px">{_e(q)}</h3><p>{_e(a)}</p>')
        elif tur == "cta":
            metin, yazi = v
            a = (f'<p style="margin:0"><a href="{_e(link)}" style="color:#fff;font-weight:bold">{_e(yazi)} →</a></p>'
                 if link else "")
            out.append(f'<div style="background:{renk};color:#fff;padding:22px 26px;margin:34px 0 24px;border-radius:10px">'
                       f'<p style="color:#fff;margin:0 0 12px">{_e(metin)}</p>{a}</div>')
        elif tur == "sosyal":
            out.append(_sosyal_html(v[0], v[1], renk))
        elif tur == "ilgili":
            out.append(_ilgili_html(v))
        elif tur == "kart":
            out.append(_kart_html(v, renk))
        elif tur == "imza":
            out.append(f'<p style="color:#777;font-size:15px;margin:0">{_e(v)}</p>')
    return '<div style="font-size:18px;line-height:1.85">\n' + "\n".join(out) + "\n</div>"


# ---------------------------------------------------------------- iç bağlantılar ve ürün kartı

def _koyu(renk, k=0.55):
    n = int(renk[1:], 16)
    return "#%02x%02x%02x" % tuple(max(0, int(((n >> s) & 255) * k)) for s in (16, 8, 0))


def _ilgili_html(v):
    """İlgili yazılar, kategori ve blog ana sayfası bağlantıları (iç bağlantılama). Stiller kısa: Ideasoft HTML'deki
    stilleri de kelime sayar."""
    li = "".join(f'<li><a href="{_e(u)}">{_e(t)}</a></li>' for t, u in v if u)
    if not li:
        return ""
    return ('<div id="seovisi-ilgili" style="margin:40px 0 12px;padding:20px 26px;border-radius:16px;background:#f4f6f8">'
            f'<p style="margin:0 0 6px"><strong>Bu konuda da ilginizi çekebilir</strong></p><ul>{li}</ul></div>')


def _kart_html(v, renk):
    """Yazının en dikkat çeken alanı: ürün fotoğrafı, ad, öne çıkan üç bilgi ve büyük düğmeyle ürün kartı. Yalnızca satır
    içi ve az sayıda stil (Ideasoft editörü; stiller kelime sayımına girer). Dar ekranda iki sütun alt alta iner."""
    koyu, link = _koyu(renk), v.get("link") or ""
    if v.get("foto"):
        resim = f'<img src="{_e(v["foto"])}" alt="{_e(v["ad"])}" style="display:block;width:100%;border-radius:12px">'
    else:
        resim = (f'<p style="margin:0;padding:60px 0;text-align:center;font-size:72px;font-weight:800;color:{renk}">'
                 f'{_e((v.get("marka") or v["ad"] or "?")[:1].upper())}</p>')
    if link:
        resim = f'<a href="{_e(link)}">{resim}</a>'
    tip = v.get("kategori") or ("" if ST.tr_lower(v.get("label") or "") in ("ürün", "urun") else v.get("label"))
    ust = " · ".join(x for x in (v.get("marka"), tip) if x)
    maddeler = "".join(f"<li>&#10003; {_e(m)}</li>" for m in v.get("maddeler") or [])
    dugme = (f'<p><a href="{_e(link)}" style="display:inline-block;padding:15px 34px;border-radius:12px;background:#fff;'
             f'color:{renk};font-size:18px;font-weight:800;text-decoration:none">'
             f'{_e(v.get("dugme") or "Ürünü incele")} &#8594;</a></p>') if link else ""
    alt = " · ".join(x for x in (f"Ürün kodu: {v['sku']}" if v.get("sku") else "", "Güncel fiyat ve stok ürün sayfasında") if x)
    return (f'<div id="seovisi-urun-karti" style="margin:48px 0 32px;padding:28px;border-radius:24px;color:#fff;'
            f'background:linear-gradient(135deg,{renk},{koyu})">'
            f'<p style="margin:0 0 18px;font-size:12px;font-weight:700;letter-spacing:2px">{_e(v.get("rozet") or "BU YAZININ ÜRÜNÜ")}</p>'
            '<div style="display:inline-block;vertical-align:middle;width:40%;min-width:220px;margin:0 3% 18px 0">'
            f'<div style="background:#fff;border-radius:18px;padding:12px">{resim}</div></div>'
            '<div style="display:inline-block;vertical-align:middle;width:55%;min-width:240px">'
            + (f'<p style="margin:0;font-size:13px;font-weight:700">{_e(ust.upper())}</p>' if ust else "")
            + f'<h3 style="margin:6px 0 14px;color:#fff;font-size:27px;line-height:1.25">{_e(v["ad"])}</h3>'
            f'<ul style="list-style:none;margin:0 0 16px;padding:0">{maddeler}</ul>{dugme}'
            f'<p style="margin:0;font-size:14px">{_e(alt)}</p></div></div>')


# ---------------------------------------------------------------- sosyal medya alanı (yazının en altı)

# ağ: (ad, düğme yazısı, yazı rengi, kartın geçiş renkleri). Simgeler emoji değil, CSS ile çizilir: Ideasoft blog içeriği
# 4 baytlık karakterleri (📸 gibi) "????" olarak kaydediyor.
SOSYAL = {
    "instagram": ("Instagram", "Takip et", "#c13584", "#4f5bd5,#962fbf,#d62976"),
    "youtube": ("YouTube", "Abone ol", "#ff0000", "#ee2a3c,#e60000"),
    "tiktok": ("TikTok", "Takip et", "#111111", "#25f4ee,#111111,#fe2c55"),
    "facebook": ("Facebook", "Beğen", "#1877f2", "#1877f2,#0b5fcc"),
}
_SOSYAL_ADRES = {"instagram": r"https://(www\.)?instagram\.com/[A-Za-z0-9_.]+/?", "youtube": r"https://(www\.)?youtube\.com/[@A-Za-z0-9_./-]+",
                 "tiktok": r"https://(www\.)?tiktok\.com/@[A-Za-z0-9_.]+/?", "facebook": r"https://(www\.)?facebook\.com/[A-Za-z0-9_.-]+/?"}


def sosyal_ayar(d):
    """{ağ: adres}; yalnızca o ağın https adresleri kabul edilir."""
    d = d if isinstance(d, dict) else {}
    out = {}
    for k, desen in _SOSYAL_ADRES.items():
        u = str(d.get(k) or "").strip().split("?")[0]
        if u and re.fullmatch(desen, u):
            out[k] = u
    return out


def sosyal_listesi(d):
    """[(ağ, adres, kullanıcı adı)] — ayar sırasıyla."""
    out = []
    for k, u in sosyal_ayar(d).items():
        tutamak = u.rstrip("/").rsplit("/", 1)[-1]
        out.append((k, u, tutamak if tutamak.startswith("@") else "@" + tutamak))
    return out


def sosyal_izi(liste):
    return "|".join(u for _, u, _ in liste or [])


_Z = "&#8203;"     # boş span'ı editör silmesin diye görünmez karakter


def _simge(k):
    """Ağın simgesi, yalnızca satır içi stillerle (resim ve emoji yok)."""
    if k == "instagram":
        return ('<span style="display:inline-block;position:relative;width:22px;height:22px;border:2.5px solid #c13584;'
                f'border-radius:7px;vertical-align:middle;box-sizing:border-box;font-size:0">{_Z}'
                '<span style="position:absolute;left:4px;top:4px;width:9px;height:9px;border:2.5px solid #c13584;'
                f'border-radius:50%;box-sizing:border-box">{_Z}</span><span style="position:absolute;right:2px;top:2px;'
                f'width:3px;height:3px;border-radius:50%;background:#c13584">{_Z}</span></span>')
    if k == "youtube":
        return ('<span style="display:inline-block;position:relative;width:28px;height:20px;border-radius:6px;'
                f'background:#ff0000;vertical-align:middle;font-size:0">{_Z}<span style="position:absolute;left:11px;'
                'top:5px;width:0;height:0;border-left:8px solid #fff;border-top:5px solid transparent;'
                f'border-bottom:5px solid transparent">{_Z}</span></span>')
    if k == "tiktok":
        return ('<span style="display:inline-block;width:24px;height:24px;line-height:24px;border-radius:7px;'
                'background:#111;color:#fff;text-align:center;font-size:15px;font-weight:bold;vertical-align:middle;'
                'text-shadow:-1px -1px 0 #25f4ee,1px 1px 0 #fe2c55">&#9834;</span>')
    return ('<span style="display:inline-block;width:24px;height:24px;line-height:26px;border-radius:50%;'
            'background:#1877f2;color:#fff;text-align:center;font:bold 17px Arial,sans-serif;vertical-align:middle">f</span>')


def _sosyal_html(magaza, liste, renk):
    """Instagram'dan YouTube'a yatay renk geçişli kart: küçük üst yazı, başlık, bir cümle, sade beyaz düğmeler.
    Yazı tipi sitenin kendi yazı tipi (inherit)."""
    renkler = ",".join(SOSYAL[k][3] for k, _, _ in liste)
    dugmeler = " ".join(
        f'<a href="{_e(u)}" target="_blank" rel="noopener" title="{_e(SOSYAL[k][0])} {_e(t)}" style="display:inline-block;'
        'margin:6px;padding:12px 26px 12px 18px;border-radius:14px;background:#fff;color:#1d1d1f;font-weight:700;'
        f'font-size:16px;text-decoration:none;box-shadow:0 8px 20px rgba(0,0,0,.18)">{_simge(k)}'
        f'<span style="vertical-align:middle;margin-left:10px">{_e(SOSYAL[k][0])}</span>'
        f'<span style="vertical-align:middle;margin-left:8px;color:{SOSYAL[k][2]};font-weight:600">{_e(SOSYAL[k][1])}</span></a>'
        for k, u, t in liste)
    kim = f"{magaza} hesaplarını" if magaza else "hesaplarımızı"
    return (f'<div style="margin:48px 0 10px;padding:34px 24px 30px;border-radius:24px;text-align:center;color:#fff;'
            f'font-family:inherit;background:linear-gradient(90deg,{renkler})">'
            '<p style="display:inline-block;margin:0 0 12px;padding:5px 14px;border-radius:99px;background:rgba(255,255,255,.2);'
            'font-size:12px;font-weight:700;letter-spacing:2px;color:#fff">SOSYAL MEDYA</p>'
            '<h3 style="margin:0 0 8px;color:#fff;font-size:28px;font-weight:800;letter-spacing:-.3px">Bizi takip edin</h3>'
            f'<p style="margin:0 auto 20px;max-width:520px;color:rgba(255,255,255,.92);font-size:16px">Yeni ürünler, kullanım '
            f'videoları ve pratik ipuçları için {_e(kim)} takip edin.</p><p style="margin:0">{dugmeler}</p></div>')


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
                    "{k} için ürün kodu ve barkodu doğrulayarak tam olarak aradığınız modeli aldığınızdan emin olun.",
                    "{k} ile elinizdeki aksesuarların uyumunu ve yedek parça bulunabilirliğini düşünün.",
                    "{k} için garanti ve satış sonrası destek koşullarını ürün sayfasından okuyun."]),
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
            ("p", rng.choice([
                f"{{k}} ilk bakışta {label} kategorisinde aradığınız düzeni sunuyor. {marka + ' imzası, ' if marka else ''}"
                "özenli işçilik ve kullanıcıyı yormayan bir yapı ilk dikkat çeken noktalar.",
                f"Kutudan çıkarınca ilk fark edilen, {{k}} ürününün derli toplu yapısı oluyor. "
                f"{(marka + ' çizgisini taşıyan ') if marka else ''}tasarım, işe hızlı başlamanızı kolaylaştırıyor.",
                f"{{k}} ile ilgili ilk izlenimimiz net: {label} kategorisinde gösterişten çok işe odaklanan bir ürün. "
                "Yapısı, ilk kullanımda bile alışmayı kolaylaştırıyor."])),
            ("quote", rng.choice([f"İyi bir {label}, işi bittiğinde varlığını unutturur; geriye yalnızca temiz bir sonuç kalır.",
                                  "Doğru alet, işin yarısıdır; diğer yarısı onu tanıyıp yerinde kullanmaktır.",
                                  f"Bir {label} değerini ilk günde değil, yüzüncü kullanımda gösterir.",
                                  "Sağlam bir ürün, kendisini değil yaptığınız işi konuşturur."])),
            ("h2", h[1]),
            *spec_bl,
            kunye,
            ("h2", h[2]),
            ("h3", "Öne çıkan yönler"),
            ("check", artilar),
            ("h3", "Dikkat edilmesi gerekenler"),
            ("ul", rng.choice([["Kullanmadan önce kılavuzdaki güvenlik uyarılarını mutlaka okuyun.",
                                "İşinize uygun aksesuarı seçmek sonucun kalitesini doğrudan etkiler.",
                                "Uzun ömür için kullanım sonrası temizlik ve doğru saklama şarttır."],
                               ["Teknik değerleri kendi işinizin gerektirdiğiyle karşılaştırın.",
                                "Aksesuar ve sarf malzemesi seçimini işin malzemesine göre yapın.",
                                "Düzenli bakım yapılmazsa performans zamanla düşer."],
                               ["İlk kullanımdan önce paket içeriğini ve kılavuzu kontrol edin.",
                                "Ürünü tasarım amacının dışındaki işlerde zorlamayın.",
                                "Kuru ve tozsuz bir yerde saklamak ömrünü uzatır."]])),
            ("h2", h[3]),
            ("p", rng.choice([f"{{k}}; {use_txt} gibi işler yapan kullanıcılar için biçilmiş kaftan. Arada bir kullanacaklar da "
                              "yoğun tempoda çalışanlar da ürünü ihtiyaçlarına göre değerlendirebilir.",
                              f"Bu ürünü en çok {use_txt} gibi işlerle uğraşanlara öneriyoruz. {{k}}, düzenli kullanımda "
                              "beklentiyi karşılayan dengeli bir seçenek.",
                              f"{use_txt[:1].upper() + use_txt[1:]} gibi işler sizin için günlük rutinse {{k}} listenizde "
                              "üst sıralarda olmalı. Arada bir kullanacaklar için de rahat bir seçenek."])),
            *([("h2", h[4]), ("p", f"{{k}} kutusundan çıkanlar:"), *pkg_bl] if pkg else []),
            ("h2", h[5]),
            ("p", rng.choice([f"Sonuç olarak {{k}}, {label} arayanlar için dengeli ve güven veren bir tercih. {{k}} ile ilgili tüm "
                              f"ayrıntılara {M} ürün sayfasından ulaşabilirsiniz.",
                              f"Toparlarsak: {{k}}, ihtiyacını bilen kullanıcı için mantıklı bir {label}. Karar vermeden önce "
                              f"teknik bilgileri işinizle karşılaştırmanız yeterli; ayrıntılar {M} ürün sayfasında.",
                              f"Kısacası {{k}}, vaat ettiğini yapan bir ürün. Ürün kodu ve barkodla doğru modeli seçtiğinizden "
                              f"emin olun; güncel bilgiler {M} ürün sayfasında."])),
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
            (rng.choice([f"{{kw}} nedir, ne işe yarar?", f"{{kw}} ne için kullanılır?", f"{{kw}} kimlere uygun?"]),
             rng.choice([f"{{k}}, {label} kategorisinde yer alan bir üründür; {use_txt} için kullanılır.",
                         f"Kısaca {label} kategorisinde bir ürün: {{k}} özellikle {use_txt} için tercih ediliyor."])),
            ("Ürün kodu ve barkod numarası nedir?", f"Ürün kodu {sku or '-'}" + (f", barkod numarası {bk}." if bk else ".")
             + " Bu bilgilerle doğru ürünü kolayca doğrulayabilirsiniz."),
            (f"{{k}} hangi işlerde kullanılır?", f"{{k}} özellikle şu işlerde tercih edilir: {use_txt}."),
            ("Teknik özellikleri nelerdir?", "Öne çıkan teknik bilgiler aşağıdaki listede ve ürün sayfasında yer alır."
             if spec else "Teknik bilgiler ürün sayfasında ayrıntılı olarak yer alır."),
            ("Kutudan neler çıkıyor?", ("Paket içeriği: " + ", ".join(pkg[:5]) + ".") if pkg
             else "Paket içeriği ürün sayfasında ayrıntılı olarak listelenir."),
            (rng.choice([f"{{k}} nasıl bakım ister?", "Bakım için ne yapmalıyım?"]),
             rng.choice(["Her kullanım sonrası temizlik, düzenli kontrol ve kuru bir ortamda saklama ürünün ömrünü uzatır.",
                         "Kullanımdan sonra tozu ve kalıntıyı alın, bağlantı noktalarını ara ara kontrol edin ve nemsiz bir "
                         "yerde saklayın."])),
            (rng.choice(["Garanti koşulları nelerdir?", "Garanti ve destek nasıl işliyor?"]),
             "Garanti koşulları ürün sayfasında ve ürünle birlikte gelen belgelerde yer alır."),
            (rng.choice([f"{{k}} nereden alınır?", "Siparişi nereden verebilirim?"]),
             rng.choice([f"{{k}} ürününü {M} üzerinden güvenle sipariş edebilirsiniz.",
                         f"Ürün sayfasından {M} üzerinden sipariş verebilirsiniz; ürün kodunu kontrol etmeyi unutmayın."])),
        ]
        son = sorular[5:]
        rng.shuffle(son)
        sorular[5:] = son
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
            ("ol", ["İşiniz bitince {k} ile çalışmayı bırakın ve varsa güç bağlantısını ayırın.", "{k} yüzeyindeki toz ve kalıntıları kuru bir bezle alın.",
                    "Hava kanallarını ve hareketli parçaları yumuşak bir fırçayla temizleyin.",
                    "{k} aksesuarlarını ayrı ayrı temizleyip yerlerine yerleştirin."]),
            ("tip", ("İpucu:", f"{{k}} temizliğinde sert kimyasallar yerine kuru bez ve yumuşak fırça kullanın.")),
            ("h2", h[2]),
            ("check", ["{k} üzerindeki kablo, fiş ve bağlantı noktalarında hasar olup olmadığını kontrol edin.",
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


def _spec_kisa(t):
    m = re.match(r"^([^:]{2,40}):\s*(.{1,40})$", t.strip())
    return f"{m.group(1).strip().lower()} {m.group(2).strip().rstrip('.')}" if m else (t.strip().rstrip(".") if len(t) <= 50 else "")


def _ozel_paragraf(b):
    """Ürünün kendi bilgilerinden kurulan paragraf: her yazıda farklıdır (özgünlük) ve uydurma değer içermez."""
    spec = [x for x in (_spec_kisa(t if isinstance(t, str) else t[0]) for t in b["spec"]) if x][:3]
    if len(spec) >= 2:
        liste = ", ".join(spec[:-1]) + " ve " + spec[-1]
        return (f"Ürünün teknik bilgilerinde {liste} öne çıkıyor. {{label}} karşılaştırırken bu değerleri kendi işinizin "
                "ihtiyacıyla yan yana koyun; {k} için doğru karar çoğu zaman burada netleşir.")
    uses = [u[:1].lower() + u[1:] for u in b["uses"][:3]]
    if uses:
        return (f"{{k}} en çok {', '.join(uses)} gibi işlerde tercih ediliyor. Kendi işinizi bu listeyle karşılaştırmak, "
                "beklentinizi doğru kurmanın en kolay yolu.")
    return ""


def _kart_maddeleri(b):
    for kaynak in (b["feat"], [t if isinstance(t, str) else t[0] for t in b["spec"]], b["uses"]):
        m = [re.sub(r"\s+", " ", x).strip().rstrip(".") for x in kaynak if x and len(x) <= 80][:3]
        if len(m) >= 2:
            return m
    return ["Ürün kodu ve barkodla doğrulanabilir model bilgisi", "Teknik bilgiler ürün sayfasında"]


def _zenginlestir(bloklar, bicim, urun, b, prof, rng, ilgili, kart):
    """Biçimin iskeletini kişiselleştirir: başka bir giriş, ürüne özel paragraf, iki ek bölüm, iç bağlantılar ve ürün kartı."""
    M = prof["magaza"] or "mağazamız"
    out = list(bloklar)
    for i, (tur, v) in enumerate(out):
        if tur == "lead":
            out[i] = ("lead", rng.choice(GIRIS[bicim] + [v]).replace("{M}", M))
            break
    ozel = _ozel_paragraf(b)
    k_i = next((i for i, (t, _) in enumerate(out) if t == "kunye"), None)
    if ozel and k_i is not None:
        out.insert(k_i, ("p", ozel))
    havuz = [k for k in EK_BOLUMLER if not (bicim == "bakim" and k == "ilk_kullanim")]
    rng.shuffle(havuz)
    ek = []
    for k in havuz[:2]:
        baslik, govde = EK_BOLUMLER[k]
        ek += [("h2", baslik)] + govde
    f_i = next(i for i, (t, _) in enumerate(out) if t == "fill")
    son_h2 = max((i for i, (t, _) in enumerate(out[:f_i]) if t == "h2"), default=f_i)
    out[son_h2:son_h2] = ek
    toc = next((i for i, (t, _) in enumerate(out) if t == "toc"), None)
    if toc is not None and len(out[toc][1]) < 7:
        out[toc] = ("toc", list(out[toc][1]) + [baslik for baslik, _ in (EK_BOLUMLER[k] for k in havuz[:2])])
    yeni = []
    for tur, v in out:
        if tur == "cta":
            if ilgili:
                yeni.append(("ilgili", ilgili))
            yeni.append(("kart", kart))
        else:
            yeni.append((tur, v))
    return yeni


def _doldur(bloklar, kw, label):
    """{kw} her zaman hedef kelime; {k} yerleri tek tek sayılır (yoğunluk ayarı)."""
    def f(t):
        return t.replace("{kw}", kw).replace("{label}", label) if isinstance(t, str) else t

    out = []
    for tur, v in bloklar:
        if isinstance(v, dict):
            pass
        elif isinstance(v, str):
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
            out.append(("p", " ".join(dolgu)))
        else:
            out.append((tur, g(v)))
    # hedef kelimeli ek cümleler tek paragrafa yığılmaz; yazının paragraflarına sırayla dağıtılır (doğal okunur)
    yerler = [i for i, (tur, v) in enumerate(out) if tur == "p" and v and i > 1]
    if ek and yerler:
        adim = max(1, len(yerler) // len(ek))
        for n, cumle in enumerate(ek):
            i = yerler[(n * adim) % len(yerler)]
            out[i] = ("p", out[i][1].rstrip() + " " + cumle)
    elif ek:
        out.append(("p", " ".join(ek)))
    return out


def _dagit(j, n):
    """n yer içinden j tanesini eşit aralıklarla seçer."""
    if j <= 0 or n <= 0:
        return set()
    return {min(n - 1, int((t + 0.5) * n / j)) for t in range(j)}


# ---------------------------------------------------------------- başlık, meta, özet

SAYFA_EK = {"rehber": ["Rehberi", "Satın Alma Rehberi", "Nasıl Seçilir?"],
            "inceleme": ["İncelemesi", "Detaylı İnceleme", "Artıları ve Özellikleri"],
            "ipucu": ["İpuçları", "Kullanım İpuçları", "7 Pratik Öneri"],
            "sss": ["Soru ve Cevaplar", "Sık Sorulan Sorular", "Merak Edilenler"],
            "bakim": ["Bakım Rehberi", "Bakımı Nasıl Yapılır?", "Bakım ve Saklama"],
            "senaryo": ["Kullanım Alanları", "Nerelerde Kullanılır?", "Kullanım Örnekleri"]}


def sayfa_basligi(kw, bicim, magaza, rng=None):
    """Hedef kelimeyle başlayan, 20-60 karakterlik sayfa başlığı; ek ürüne göre döner (aynı kalıp her yazıda tekrar etmez)."""
    ekler = list(SAYFA_EK[bicim])
    if rng:
        rng.shuffle(ekler)
    adaylar = [f"{kw} {e} | {magaza}" for e in ekler if magaza] + [f"{kw} {e}" for e in ekler] \
        + ([f"{kw} | {magaza}"] if magaza else []) + [f"{kw} Rehberi", kw, f"{kw} Hakkında Her Şey"]
    for t in adaylar:
        if t and 20 <= len(t) <= 60:
            return t
    return kw[:60]


META_GIRIS = {
    "rehber": ["{kw} alırken nelere dikkat etmeli?", "{kw} seçerken bilmeniz gerekenler.", "Doğru {kw} seçimi için kısa rehber.",
               "{kw} işinize uygun mu?"],
    "inceleme": ["{kw} incelemesi.", "{kw} yakından: artılar ve dikkat edilecekler.", "{kw} gerçekten fark yaratıyor mu?",
                 "{kw} detaylı inceleme."],
    "ipucu": ["{kw} ile daha verimli çalışmanın 7 yolu.", "{kw} kullanırken işinizi kolaylaştıran ipuçları.",
              "{kw} için ustalardan pratik öneriler.", "{kw} kullananlara 7 ipucu."],
    "sss": ["{kw} hakkında en çok sorulanlar.", "{kw}: merak edilen soruların cevapları.", "{kw} ile ilgili net cevaplar.",
            "{kw} hakkında bilmeniz gerekenler."],
    "bakim": ["{kw} bakımı nasıl yapılır?", "{kw} uzun ömürlü nasıl kullanılır?", "{kw} için adım adım bakım.",
              "{kw} ilk günkü gibi kalsın."],
    "senaryo": ["{kw} hangi işlerde kullanılır?", "{kw} ile neler yapabilirsiniz?", "{kw} için gerçek kullanım örnekleri.",
                "{kw} sahada nasıl kullanılır?"],
}


def _meta_govdeler(bicim, b, sku, marka):
    """Ürünün kendi bilgilerinden meta gövdeleri: aynı biçimdeki iki ürünün metası birbirine benzemesin."""
    spec = [x for x in (_spec_kisa(t if isinstance(t, str) else t[0]) for t in b["spec"]) if x]
    uses = [u[:1].lower() + u[1:] for u in b["uses"] if len(u) <= 45]
    pkg = [x for x in b["pkg"] if len(x) <= 30]
    out = []
    if len(spec) >= 2:
        out.append(f"{_bas_harf(spec[0])} ve {spec[1]} gibi teknik bilgiler.")
    if spec:
        out.append(f"Öne çıkan değer: {spec[0]}.")
    if uses:
        out.append(f"{_bas_harf(uses[0])} için kullanım önerileri.")
        if len(uses) > 1:
            out.append(f"{_bas_harf(uses[0])} ve {uses[1]} için öneriler.")
    if pkg:
        out.append(f"Kutudan {pkg[0].lower()} ve fazlası çıkıyor.")
    if sku:
        out.append(f"Ürün kodu {sku} ile doğru model.")
    out += {"rehber": ["Kontrol listesi ve teknik bilgiler.", f"{b['label'].capitalize()} seçiminde dikkat edilecekler."],
            "inceleme": ["Artılar, dikkat edilecekler ve kutu içeriği.", "Kimler tercih etmeli?"],
            "ipucu": ["Kullanım, aksesuar ve bakım önerileri.", "Güvenlik ve verim ipuçları."],
            "sss": ["Kullanım, bakım ve sipariş soruları.", "Ürün kodu, barkod ve kullanım bilgisi."],
            "bakim": ["Temizlik, kontrol ve saklama adımları.", "Sık yapılan bakım hataları."],
            "senaryo": ["Uygulama örnekleri ve aksesuar önerileri.", "Gerçek kullanım senaryoları."]}[bicim]
    if marka:
        out.append(f"{marka} güvencesiyle.")
    return out


def meta_aciklama(kw, bicim, magaza, rng, b=None, sku="", marka="", digerleri=None, haric=None):
    """Hedef kelimeli, 50-155 karakterlik meta açıklama. Adaylar ürünün kendi bilgileriyle kurulur ve mağazanın diğer
    yazılarının metalarıyla karşılaştırılır; benzerliği sınırın altındaki ilk aday seçilir (kopya meta olmaz)."""
    at = PR.loc(magaza) if magaza else ""
    if b is not None:
        girisler = [g.replace("{kw}", kw) for g in META_GIRIS[bicim]]
        govdeler = _meta_govdeler(bicim, b, sku, marka)
        kapanis = [f"Detaylar {at}." if at else "Detaylar yazıda.", f"{magaza} blogunda." if magaza else "Hepsi tek yazıda.", ""]
        adaylar = [re.sub(r"\s+", " ", f"{g} {gv} {k}").strip() for g in girisler for gv in govdeler for k in kapanis]
        adaylar = [a for a in adaylar if 50 <= len(a) <= 155 and ST.tr_lower(kw) in ST.tr_lower(a)]
        rng.shuffle(adaylar)
        if adaylar:
            en_iyi, dz = None, KA.dizin(digerleri)
            for a in adaylar[:60]:
                sim, _ = dz.meta_benzerlik(a, kw, haric)
                if sim < KA.SINIRLAR["meta_benzerlik"] * 0.8:
                    return a
                if en_iyi is None or sim < en_iyi[0]:
                    en_iyi = (sim, a)
            return en_iyi[1]
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


def ozet(kw, bicim, magaza, rng=None, b=None):
    """Blog listesinde görünen özet: biçimin cümlesi ve (varsa) ürünün kendi bilgisinden bir cümle."""
    if rng is not None and b is not None:
        spec = [x for x in (_spec_kisa(t if isinstance(t, str) else t[0]) for t in b["spec"]) if x]
        uses = [u[:1].lower() + u[1:] for u in b["uses"] if len(u) <= 45]
        ek = ([f"Öne çıkan bilgiler: {', '.join(spec[:2])}."] if spec else []) + \
             ([f"Özellikle {uses[0]} için pratik öneriler."] if uses else [])
        if ek:
            return ozet(kw, bicim, "") + " " + rng.choice(ek) + (f" {magaza} blogunda." if magaza else "")
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
        kategori=None, kw="", sosyal=None, foto="", ilgili=None, digerleri=None, yollar=None, arastirma=None):
    """urun: Ideasoft ürün kaydı (id, name, sku, barcode, slug, brand, categories). kategori: {"ad", "slug"} (isteğe bağlı).
    kw verilirse o hedef kelime kullanılır (kullanıcının düzenlediği). foto: ürün fotoğrafının adresi (ürün kartında).
    ilgili: [(başlık, adres)] mağazanın ilgili yazıları (iç bağlantı). digerleri: diğer yazıların izleri (kalite.iz);
    meta özgünlüğü ve kalite raporu bunlarla karşılaştırılır. Dönüş: blog planı (mağazaya yazılmaz)."""
    prof = PR.with_brand(prof, urun)
    pid = urun.get("id") or 0
    bicim = bicim_sec(bicim, pid, varyant)
    ad = re.sub(r"\s+", " ", urun.get("name") or "").strip()
    sku = (urun.get("sku") or "").strip()
    kw = kodsuz(re.sub(r"\s+", " ", kw or "").strip(), sku) or kelime_sec(ad, mevcut_kw, prof, sku=sku)
    rng = _rng(pid, bicim, varyant)
    renk = renk if re.fullmatch(r"#[0-9a-fA-F]{6}", renk or "") else "#1b4f72"
    b = _bilgi(urun, details_html, kw, prof)
    gorsel_baslik = rng.choice(BASLIKLAR[bicim]).replace("{kw}", kw)
    # ürün kodu başlığın sonunda: kodla yapılan aramalarda yazı bulunur (görselde kod ayrıca yazdığı için orada yok)
    baslik = f"{gorsel_baslik} {sku}" if sku and ST.tr_lower(sku) not in ST.tr_lower(gorsel_baslik) else gorsel_baslik
    sosyal = sosyal_listesi(sosyal)
    yollar = dict(YOLLAR, **(yollar or {}))
    link = f"{yollar['urun']}{urun['slug']}" if urun.get("slug") else ""
    # iç bağlantılar: ilgili yazılar, ürünün kategorisi, blog ana sayfası (ürün sayfası ürün kartında)
    baglantilar = [(t, u) for t, u in (ilgili or [])[:3] if t and u]
    if kategori and kategori.get("slug") and kategori.get("ad"):
        baglantilar.append((f"Tüm {kategori['ad']} ürünleri", f"{yollar['kategori']}{kategori['slug']}"))
    if prof["magaza"]:
        baglantilar.append((f"{prof['magaza']} blogundaki diğer rehberler", yollar["blog_ana"]))
    kart = {"ad": ad, "link": link, "foto": foto or "", "marka": prof["marka"], "label": b["label"],
            "sku": sku, "maddeler": _kart_maddeleri(b), "dugme": "Ürünü incele", "rozet": "BU YAZININ ÜRÜNÜ",
            "kategori": (kategori or {}).get("ad") or ""}

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
        iskelet = _bloklar(bicim, urun, b2, prof, kategori, _rng(pid, bicim, varyant))
        ham = _doldur(_zenginlestir(iskelet, bicim, urun, b2, prof, _rng(pid, bicim, varyant, "zengin"), baglantilar,
                                    dict(kart, maddeler=_kart_maddeleri(b2))), kw, b["label"])
        if sosyal:
            ham.append(("sosyal", (prof["magaza"], sosyal)))
        n_yer = _yer_sayisi(ham)
        for m_ in range(0, len(ek) + 1):
            for n in range(0, len(dolgu) + 1):
                olculen = {}

                def olc(j):
                    if j not in olculen:
                        h = _render(_uygula(ham, kw, refs, _dagit(j, n_yer), dolgu[:n], ek[:m_]), kw, renk, link)
                        c = ST.count_kw(ST.strip_tags(h), kw)
                        ws = [ST.count_words(h, m) for m in methods]
                        dens = [c / w * 100 if w else 0 for w in ws]
                        olculen[j] = (h, dens, min(min(d - 2.0, 3.0 - d) for d in dens), sum(dens) / len(dens))
                    return olculen[j]
                # yoğunluk anma sayısıyla neredeyse doğrusal artar: iki uçtan hedefe denk gelen sayı tahmin edilir,
                # yalnızca çevresi denenir (her sayıyı tek tek çizmek yerine)
                o0, oN = olc(0)[3], olc(n_yer)[3]
                tahmin = round((hedef - o0) / ((oN - o0) / n_yer)) if n_yer and oN > o0 else 0
                for j in sorted({max(0, min(n_yer, tahmin + d)) for d in (-3, -2, -1, 0, 1, 2, 3)} | {0, n_yer}):
                    h, dens, pay, ort = olc(j)
                    # önce güvenli aralık, sonra uzun teknik liste, hedefe yakınlık, az ek cümle (doğal metin)
                    anahtar = (min(pay, 0.25), sinir, -round(abs(ort - hedef), 1), -m_, -n, -j)
                    if en_iyi is None or anahtar > en_iyi[0]:
                        en_iyi = (anahtar, h, dens)
                if en_iyi[0][0] >= 0.25:
                    break
                if min(olc(n_yer)[1]) < 2.25:
                    break               # bütün anmalarla bile düşük: dolgu cümlesi yalnızca düşürür, sıradaki ek cümleye geç
            if en_iyi[0][0] >= 0.25:
                break
        if en_iyi[0][0] >= 0.25:
            break
    _, icerik, dens = en_iyi

    magaza = prof["magaza"]
    pt = sayfa_basligi(kw, bicim, magaza, _rng(pid, "pt", varyant))
    digerleri = KA.dizin(digerleri)
    md = meta_aciklama(kw, bicim, magaza, _rng(pid, "meta", varyant), b, sku, prof["marka"], digerleri, pid)
    mk = anahtar_kelimeler(kw, b["label"], bicim, prof)
    if arastirma:
        kws = set(ST.tr_lower(kw).split())
        ek_kw = [x for x in arastirma.get("ilgili") or [] if kws & set(ST.tr_lower(x).split())][:3]
        mk = ", ".join([mk] + ek_kw) if ek_kw else mk
    plan = {"v": SURUM, "keyword": kw, "title": baslik, "gorsel_baslik": gorsel_baslik, "sosyal_iz": sosyal_izi(sosyal),
            "slug": slug(f"{kw} {BICIMLER[bicim]['ek']} {sku}", 75),
            "excerpt": ozet(kw, bicim, magaza, _rng(pid, "ozet", varyant), b),
            "content": icerik, "pageTitle": pt, "metaDescription": md,
            "metaKeywords": mk, "bicim": bicim, "varyant": varyant,
            "rozet": BICIMLER[bicim]["rozet"], "label": b["label"],
            "densities": {m: round(d, 2) for m, d in zip(methods, dens)},
            "urun": {"id": pid, "ad": ad, "sku": urun.get("sku") or "", "barkod": urun.get("barcode") or "",
                     "link": link, "marka": prof["marka"], "foto": foto or ""},
            "ilgili": baglantilar}
    if arastirma:
        plan["arastirma"] = {k: arastirma.get(k) for k in ("adaylar", "ilgili", "google")}
    plan["score"] = puan(plan, method)
    plan["imza"] = KA.icerik_imzasi(icerik, kw)
    plan["kalite"] = KA.degerlendir(plan, digerleri, plan["score"], pid)
    return plan


EN_COK_DENEME = 16


def _daha_iyi(a, b):
    """İki planın karşılaştırması: önce Ideasoft'un 13 kuralı, sonra seovisi kalite kapısı, sonra seovisi puanı."""
    if b is None:
        return True
    ka, kb = a.get("kalite") or {}, b.get("kalite") or {}
    return (a["score"]["yuzde"], ka.get("gecti", False), ka.get("puan", 0)) > \
           (b["score"]["yuzde"], kb.get("gecti", False), kb.get("puan", 0))


def yaz_tam(urun, details_html="", mevcut_kw="", bicim="", varyant=0, kw="", kw_adaylar=None, bicim_sabit=False, **kw_args):
    """Kalite kapısıyla yazar: yazı Ideasoft'un 13 kuralını ve seovisi sınırlarını (kalite.SINIRLAR: SEO puanı,
    okunabilirlik, meta ve içerik özgünlüğü, yamyamlaşma) geçene kadar başka anlatım, başka biçim ve (hedef kelimeyi
    kullanıcı seçmediyse) araştırmanın sıradaki hedef kelimesiyle baştan yazılır. Geçen ilk yazı döner; hiçbiri geçmezse
    en iyisi (kalite raporunda neden geçmediği görünür)."""
    ilk = bicim_sec(bicim, urun.get("id") or 0, varyant)
    if kw:
        kelimeler = [kw]
    else:
        ad = re.sub(r"\s+", " ", urun.get("name") or "").strip()
        prof = PR.with_brand(kw_args.get("prof"), urun)
        if not kw_adaylar:     # araştırma verilmediyse Google'sız (yerel ölçütlerle) sıralanan adaylar
            label = SM.machine_type(ad, prof, urun)[0]
            kw_adaylar = [a["kelime"] for a in KE.arastir(ad, mevcut_kw, urun.get("sku") or "", label,
                                                           prof.get("marka") or "")["adaylar"]]
        kelimeler = [k for k in (kw_adaylar or []) if k][:3]
        for uz in (40, 30, 22):
            kisa = kelime_sec(ad, mevcut_kw, prof, en_uzun=uz, sku=urun.get("sku") or "")
            if ST.tr_lower(kisa) not in {ST.tr_lower(x) for x in kelimeler}:
                kelimeler.append(kisa)
    denemeler = []
    for i, k in enumerate(kelimeler):
        if i == 0:
            denemeler += [(ilk, varyant, k), (ilk, varyant + 1, k), (ilk, varyant + 2, k)]
            denemeler += [(b, varyant, k) for b in SIRA if b != ilk]
        else:
            denemeler += [(ilk, varyant, k), (ilk, varyant + 1, k)] + [(b, varyant, k) for b in SIRA if b != ilk][:2]
    if "digerleri" in kw_args:
        kw_args["digerleri"] = KA.dizin(kw_args["digerleri"])
    if bicim_sabit:          # kullanıcı biçimi kendisi seçti: yalnızca anlatım ve hedef kelime değişir
        denemeler = [(ilk, v, k) for k in kelimeler for v in range(varyant, varyant + 4)]
    en_iyi, n = None, 0
    for b, v, k in denemeler[:EN_COK_DENEME]:
        p = yaz(urun, details_html, mevcut_kw, b, v, kw=k, **kw_args)
        n += 1
        if _daha_iyi(p, en_iyi):
            en_iyi = p
        if p["score"]["yuzde"] == 100 and p["kalite"]["gecti"]:
            break
    en_iyi["kalite"]["deneme"] = n
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

GORSEL_TEMALAR = {"lacivert_bant": "Lacivert · bantlı", "beyaz_bant": "Beyaz · bantlı", "kirmizi_bant": "Kırmızı · bantlı",
                  "pano_bant": "Atölye panosu · bantlı", "lacivert_kutu": "Lacivert · kutu", "beyaz_kutu": "Beyaz · kutu",
                  "bolunmus_kutu": "İki renk · kutu", "vitrin_kutu": "Vitrin · kutu"}
GORSEL_VARSAYILAN = {"tema": "lacivert_bant", "renk": "#e30613", "renk2": "#0c2c57", "foto": True, "yazi": "sans",
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
