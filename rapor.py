# -*- coding: utf-8 -*-
"""Aylık rapor: o ay seovisi'nin yaptıkları (olaylar) ve mağazanın durumunun ay başına göre değişimi (durum fotoğrafları).

Durum fotoğrafı her tam SEO taramasının sonunda alınır (haftalık otomatik tarama da dahil). Ay başındaki durum, aydan önceki
son fotoğraf; yoksa ayın ilk fotoğrafıdır. Ay sonundaki durum ayın son fotoğrafıdır.
"""
from collections import Counter

METRIKLER = [  # anahtar, ad, artması iyi mi
    ("seo_tamam", "SEO'su tam ürün", True),
    ("seo_eksik", "SEO'su eksik ürün", False),
    ("kategori_sorun", "Kategori sorunu olan ürün", False),
    ("gorselsiz", "Görseli olmayan ürün", False),
    ("fiyat_uyari", "Fiyat uyarısı", False),
    ("stok_uyari", "Yayında ama stokta yok", False),
    ("kopya", "Kopya ürün grubu", False),
    ("kirik", "Kırık bağlantı", False),
]
OLAYLAR = {"seo": "SEO açıklaması gönderildi", "kategori": "Ürünün kategorisi düzeltildi", "kategori_ac": "Yeni kategori açıldı",
           "gecis": "Açıklama yeni şablona geçirildi", "geri": "Değişiklik geri alındı"}
AY_ADLARI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def ay_araligi(ay):
    """"2026-11" -> ("2026-11-01", "2026-12-01")"""
    y, m = (int(x) for x in ay.split("-"))
    return f"{y:04d}-{m:02d}-01", (f"{y + 1:04d}-01-01" if m == 12 else f"{y:04d}-{m + 1:02d}-01")


def ay_adi(ay):
    y, m = ay.split("-")
    return f"{AY_ADLARI[int(m) - 1]} {y}"


def aylar(zamanlar):
    return sorted({z[:7] for z in zamanlar if z}, reverse=True)


def _yuzde(d):
    return round(100 * d.get("seo_tamam", 0) / d["taranan"]) if d and d.get("taranan") else None


def hesapla(ay, anliklar, olaylar):
    """anliklar: [(zaman "YYYY-MM-DD HH:MM", {metrik: sayı, "taranan": n})] zamana göre sıralı;
    olaylar: [(zaman, tür)]. Dönüş: ayın raporu."""
    bas, son = ay_araligi(ay)
    once = [a for a in anliklar if a[0] < bas]
    icinde = [a for a in anliklar if bas <= a[0] < son]
    a0 = once[-1] if once else (icinde[0] if icinde else None)
    a1 = icinde[-1] if icinde else None
    say = Counter(t for z, t in olaylar if bas <= z < son)
    metrik = []
    for k, ad, artis_iyi in METRIKLER:
        v0 = a0[1].get(k) if a0 else None
        v1 = a1[1].get(k) if a1 else None
        fark = v1 - v0 if v0 is not None and v1 is not None else None
        metrik.append({"k": k, "ad": ad, "once": v0, "sonra": v1, "fark": fark,
                       "iyi": None if not fark else (fark > 0) == artis_iyi})
    return {"ay": ay, "ay_adi": ay_adi(ay), "once_zaman": a0[0] if a0 else None, "sonra_zaman": a1[0] if a1 else None,
            "seo_yuzde": [_yuzde(a0[1]) if a0 else None, _yuzde(a1[1]) if a1 else None],
            "olaylar": [{"tur": t, "ad": ad, "n": say.get(t, 0)} for t, ad in OLAYLAR.items()],
            "metrikler": metrik, "tarama_sayisi": len(icinde)}
