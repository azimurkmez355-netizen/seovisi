# -*- coding: utf-8 -*-
"""Ek not: seçilen kategorilerdeki ürünlerin açıklamasının sonuna eklenen kısa not ve bağlantı (ör. üreticinin sitesinden
ürün kaydıyla ek garanti). Yalnızca standart kütüphane; mağazaya erişmez, app.py'deki EkNot işçisi kullanır.

- Not tek bir <div id="seovisi-not"> içindedir. Tanıma ve kaldırma bu işaretle yapılır; Ideasoft'un düzenleyicisi işareti
  silerse notun o ürüne yazılmış hâlinin metniyle (bilinenler) yapılır.
- SEO: Ideasoft'un puanı kurallardan oluşur. Not açıklamayı yalnızca uzatır; bozabileceği tek kural hedef kelime
  yoğunluğudur (%2-%3). etki() notlu ve notsuz hâli puanlar; kural tutarken notla tutmayacaksa not eklenmez.
"""
import hashlib
import html
import re

import seo_text as ST

ISARET = "seovisi-not"
SIMGELER = {"🛡️": "Kalkan", "✅": "Onay", "ℹ️": "Bilgi", "🎁": "Hediye", "⭐": "Yıldız", "": "Simge yok"}
BASLIK_UZUNLUK, METIN_UZUNLUK, LINK_YAZI_UZUNLUK, URL_UZUNLUK = 60, 300, 40, 300
_URL = re.compile(r"https?://[^\s\"'<>]+\.[^\s\"'<>]+", re.I)
_BLOK = re.compile(r"\s*<div\b[^>]*>(?:(?!<div\b).)*?</div>", re.I | re.S)
_ISARETLI = re.compile(r"\s*<div\b[^>]*\bid=[\"']?" + ISARET + r"\b[^>]*>(?:(?!<div\b).)*?</div>", re.I | re.S)


def _tek_satir(v, n):
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def url_duzelt(v):
    """http(s) ile başlayan geçerli adres; "www.ornek.com" yazılırsa başına https:// eklenir. Geçersizse boş."""
    v = _tek_satir(v, URL_UZUNLUK)
    if v and not re.match(r"https?://", v, re.I) and re.match(r"[\w-]+(\.[\w-]+)+(/|$)", v):
        v = "https://" + v
    return v if _URL.fullmatch(v) else ""


def yukle(d):
    """Kayıtlı ek not ayarını eksiksiz ve geçerli hâle getirir."""
    d = d if isinstance(d, dict) else {}
    kats = []
    for k in d.get("kategoriler") or []:
        try:
            k = int(k)
        except (TypeError, ValueError):
            continue
        if k > 0 and k not in kats:
            kats.append(k)
    return {
        "acik": d.get("acik") is True,
        "simge": d.get("simge") if d.get("simge") in SIMGELER else "🛡️",
        "baslik": _tek_satir(d.get("baslik"), BASLIK_UZUNLUK),
        "metin": _tek_satir(d.get("metin"), METIN_UZUNLUK),
        "link_yazi": _tek_satir(d.get("link_yazi"), LINK_YAZI_UZUNLUK) or "Ürününüzü kaydedin",
        "link_url": url_duzelt(d.get("link_url")),
        "kategoriler": kats[:500],
    }


def birlestir(eski, yeni):
    """Panelden gelen kısmi değişikliği kayıtlı ayara ekler."""
    out = dict(eski if isinstance(eski, dict) else {})
    out.update({k: v for k, v in (yeni if isinstance(yeni, dict) else {}).items()
                if k in ("acik", "simge", "baslik", "metin", "link_yazi", "link_url", "kategoriler")})
    return yukle(out)


def eksik(a):
    """Notun eklenebilmesi için eksik olan; tamamsa boş metin."""
    if not a["metin"]:
        return "Not metnini yazın."
    if not a["kategoriler"]:
        return "En az bir kategori seçin."
    return ""


def surum(a, renk):
    """Notun görünümünü belirleyen ayarların özeti: ürüne yazılan not bugünkü ayardan eskiyse değişir."""
    s = "|".join([a["simge"], a["baslik"], a["metin"], a["link_yazi"], a["link_url"], renk or ""])
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


def uret(a, renk, urun=""):
    """Notun HTML'i. Metindeki {urun} ürünün hedef kelimesi (yoksa adı) olur. Yalnızca basit satır içi stiller
    (Ideasoft'un düzenleyicisi bunları korur); başlık etiketi kullanılmaz, sayfanın başlık düzeni bozulmaz."""
    e = lambda t: html.escape(t, quote=False)  # noqa: E731
    parts = []
    bas = " ".join(x for x in (a["simge"], e(a["baslik"])) if x)
    if bas:
        parts.append(f"<p><strong>{bas}</strong></p>")
    parts.append("<p>" + e(a["metin"].replace("{urun}", urun or "bu ürün")) + "</p>")
    if a["link_url"]:
        parts.append(f'<p><a href="{html.escape(a["link_url"])}" target="_blank" rel="nofollow noopener">'
                     f'{e(a["link_yazi"])} →</a></p>')
    renk = renk or "#1b4f72"
    return (f'<div id="{ISARET}" style="border:1px solid {renk};border-left:4px solid {renk};padding:8px 12px;'
            f'margin-top:16px">' + "".join(parts) + "</div>")


def cikar(details, bilinenler=()):
    """Açıklamadan notu çıkarır. Dönüş: (notsuz açıklama, not vardı mı)."""
    details = details or ""
    yeni = _ISARETLI.sub("", details)
    if yeni == details:
        metinler = {ST.strip_tags(b) for b in bilinenler if b}
        if metinler:
            yeni = _BLOK.sub(lambda m: "" if ST.strip_tags(m.group(0)) in metinler else m.group(0), details)
    return (yeni.rstrip(), True) if yeni != details else (details, False)


def var_mi(details, bilinenler=()):
    return cikar(details, bilinenler)[1]


def ekle(details, not_html, bilinenler=()):
    """Notu açıklamanın en sonuna ekler; eski hâli (işaretli ya da bilinen) varsa önce çıkarılır."""
    taban = cikar(details, bilinenler)[0].rstrip()
    return (taban + "\n" if taban else "") + not_html


def etki(ad, kw, once, sonra, method):
    """Notun SEO'ya etkisi. Dönüş: once / sonra (hedef kelime yoğunluğu, hedef kelime yoksa None) ve bozar: hedef kelime
    yoğunluğu kuralı notsuz tutup notla tutmuyor mu (Ideasoft puanı düşer)."""
    if not kw:
        return {"once": None, "sonra": None, "bozar": False}
    a, b = (ST.seo_score(ad, kw, h, "", "", method) for h in (once, sonra))
    tut = lambda s: not any(f.startswith("Hedef kelime yoğunluğu") for f in s["fails"])  # noqa: E731
    return {"once": a["density"], "sonra": b["density"], "bozar": tut(a) and not tut(b)}
