# -*- coding: utf-8 -*-
"""Kopya ürün tespiti: aynı stok kodu, barkod, ürün adı, sayfa başlığı ya da meta açıklamayı taşıyan ürün grupları.
Yalnızca okur; mağazaya hiçbir şey yazmaz.

Stok kodu ve barkod bütün ürünlerde (veri hatası), ad / başlık / meta yalnızca yayındaki ürünlerde (Google'da yinelenen
içerik) aranır. Yalnızca renk ya da beden farkıyla ayrılan "neredeyse aynı" ürünler burada işaretlenmez; onlar çoğu zaman
ayrı ürün ya da varyant adayıdır (v2: varyant önerisi).
"""
import re

TURLER = {
    "ayni_sku": ("Aynı stok kodu", "{n} ürün aynı stok kodunu taşıyor; stok ve siparişler karışabilir."),
    "ayni_barkod": ("Aynı barkod", "{n} ürün aynı barkodu taşıyor; aynı ürün iki kez açılmış olabilir."),
    "ayni_ad": ("Aynı ürün adı", "{n} yayındaki ürün aynı adı taşıyor; Google aynı içerikli sayfalardan yalnızca birini gösterebilir."),
    "ayni_baslik": ("Aynı sayfa başlığı", "{n} yayındaki ürünün sayfa başlığı aynı; arama sonuçlarında birbirinden ayrılamazlar."),
    "ayni_meta": ("Aynı meta açıklama", "{n} yayındaki ürünün meta açıklaması aynı; Google bunları yinelenen içerik sayar."),
}


def _kucuk(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def ad_anahtari(s):
    """Büyük / küçük harf, noktalama, fazla boşluk ve kelime sırası farkı yok sayılır."""
    return " ".join(sorted(re.findall(r"\w+", _kucuk(s))))


def metin_anahtari(s):
    return re.sub(r"\s+", " ", _kucuk(s)).strip()


def kod_anahtari(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def _gecerli_barkod(b):
    return len(b) >= 6 and len(set(b)) > 1            # "0", "000000" gibi yer tutucular sayılmaz


def hesapla(urunler):
    """urunler: [{"pid", "sku", "name", "barkod", "baslik", "meta", "aktif"}]. Bilinmeyen (boş) değerler gruplanmaz.
    Dönüş: [{"tur", "baslik", "deger", "mesaj", "urunler": [{"pid", "sku", "name", "aktif"}]}]; önem ve büyüklük sırasıyla.
    Aynı ürün kümesi daha önemli bir türde zaten bildirildiyse (aynı ad → aynı başlık) yeniden bildirilmez."""
    aktif = lambda u: u.get("aktif") is not False and u.get("aktif") != 0      # noqa: E731
    kurallar = [
        ("ayni_sku", lambda u: True, lambda u: kod_anahtari(u.get("sku")), lambda k: bool(k)),
        ("ayni_barkod", lambda u: True, lambda u: kod_anahtari(u.get("barkod")), _gecerli_barkod),
        ("ayni_ad", aktif, lambda u: ad_anahtari(u.get("name")), lambda k: bool(k)),
        ("ayni_baslik", aktif, lambda u: metin_anahtari(u.get("baslik")), lambda k: bool(k)),
        ("ayni_meta", aktif, lambda u: metin_anahtari(u.get("meta")), lambda k: bool(k)),
    ]
    out, bildirilen = [], set()
    for tur, kim, anahtar, gecerli in kurallar:
        gruplar = {}
        for u in urunler:
            if kim(u):
                k = anahtar(u)
                if gecerli(k):
                    gruplar.setdefault(k, []).append(u)
        bulunan = []
        for k, us in gruplar.items():
            pids = frozenset(u["pid"] for u in us)
            if len(pids) < 2 or (tur not in ("ayni_sku", "ayni_barkod") and pids in bildirilen):
                continue
            bildirilen.add(pids)
            ilk = us[0]
            deger = {"ayni_sku": ilk.get("sku"), "ayni_barkod": ilk.get("barkod"), "ayni_ad": ilk.get("name"),
                     "ayni_baslik": ilk.get("baslik"), "ayni_meta": ilk.get("meta")}[tur]
            bulunan.append({"tur": tur, "baslik": TURLER[tur][0], "deger": (deger or "").strip(),
                            "mesaj": TURLER[tur][1].format(n=len(pids)),
                            "urunler": sorted(({"pid": u["pid"], "sku": u.get("sku") or "", "name": u.get("name") or "",
                                                "aktif": aktif(u)} for u in us), key=lambda x: x["pid"])})
        bulunan.sort(key=lambda g: (-len(g["urunler"]), g["deger"].lower()))
        out += bulunan
    return out
