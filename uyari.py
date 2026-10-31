# -*- coding: utf-8 -*-
"""Ürün uyarıları: fiyat hataları ve yayında olup satılamayan ürünler. Yalnızca okur; mağazaya hiçbir şey yazmaz.

Kurallar mağaza taramasında kaydedilen ürün bilgileri üzerinden her istekte yeniden hesaplanır; kural değişince yeniden
tarama gerekmez. Yalnızca yayındaki (aktif) ürünler denetlenir; pasif ürün sitede görünmez.
"""
from statistics import median

# tür -> (grup, kısa başlık). Sıra önem sırasıdır.
TURLER = {
    "fiyat_yok": ("fiyat", "Fiyatı 0"),
    "indirim": ("fiyat", "İndirim hatalı"),
    "zarar": ("fiyat", "Alış fiyatının altında"),
    "uc_fiyat": ("fiyat", "Benzerlerine göre aşırı fiyat"),
    "stok_yok": ("satilamaz", "Yayında ama stokta yok"),
}
GRUPLAR = {"fiyat": "Fiyat hataları", "satilamaz": "Yayında ama satılamaz"}
UC_KAT = 10            # kategorideki ortanca fiyatın bu kadar katı ya da bu kadarda biri: virgül / sıfır hatası olabilir
UC_EN_AZ = 8           # ortanca için kategoride en az bu kadar fiyatlı ürün
INDIRIM_SUPHE = 90     # bu yüzdenin üstündeki indirim yanlış girilmiş olabilir


def tl(v, para=""):
    s = f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{s} {para}".strip()


def _sayi(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def hesapla(urunler):
    """urunler: [{"pid", "sku", "name", "fiyat", "satis", "alis", "indirim", "indirim_tip", "stok", "aktif", "secenekli",
    "para", "kats": [kategori no]}]. Bilinmeyen (None) alanlar o alanın kuralını atlatır.
    Dönüş: önem sırasıyla [{"pid", "sku", "name", "tur", "grup", "baslik", "mesaj", "satis", "para"}]."""
    aktif = [u for u in urunler if u.get("aktif") is not False and u.get("aktif") != 0]
    # kategori ve para birimine göre fiyat ortancaları (en özel kategori: içinde en az ürün olan)
    gruplar = {}
    for u in aktif:
        s = _sayi(u.get("satis"))
        if s and s > 0:
            for k in u.get("kats") or []:
                gruplar.setdefault((k, u.get("para") or ""), []).append(s)
    orta = {g: (median(v), len(v)) for g, v in gruplar.items() if len(v) >= UC_EN_AZ}

    out = []

    def ekle(u, tur, mesaj):
        out.append({"pid": u["pid"], "sku": u.get("sku") or "", "name": u.get("name") or "", "tur": tur,
                    "grup": TURLER[tur][0], "baslik": TURLER[tur][1], "mesaj": mesaj,
                    "satis": _sayi(u.get("satis")), "para": u.get("para") or ""})

    for u in aktif:
        para = u.get("para") or ""
        fiyat, satis, alis = _sayi(u.get("fiyat")), _sayi(u.get("satis")), _sayi(u.get("alis"))
        ind, tip = _sayi(u.get("indirim")) or 0, int(_sayi(u.get("indirim_tip")) or 0)
        if fiyat is not None and fiyat <= 0:
            ekle(u, "fiyat_yok", "Fiyatı 0; ürün sepete eklenemez ya da bedava görünür.")
            continue
        if ind > 0 and fiyat:
            if tip == 1 and ind >= 100:
                ekle(u, "indirim", f"İndirim %{ind:g}: indirimli fiyat 0 ya da eksi.")
            elif tip == 1 and ind >= INDIRIM_SUPHE:
                ekle(u, "indirim", f"İndirim %{ind:g}; çok yüksek, yanlış girilmiş olabilir.")
            elif tip != 1 and ind >= fiyat:
                ekle(u, "indirim", f"İndirimli fiyat ({tl(ind, para)}) normal fiyattan ({tl(fiyat, para)}) düşük değil; "
                                   "indirim uygulanmıyor.")
            elif tip != 1 and (1 - ind / fiyat) * 100 >= INDIRIM_SUPHE:
                ekle(u, "indirim", f"İndirimli fiyat ({tl(ind, para)}) normal fiyatın ({tl(fiyat, para)}) "
                                   f"%{round(ind / fiyat * 100)}'i; yanlış girilmiş olabilir.")
        if alis and satis and satis < alis:
            ekle(u, "zarar", f"Satış fiyatı ({tl(satis, para)}) alış fiyatının ({tl(alis, para)}) altında.")
        if satis and satis > 0:
            aday = [orta[(k, para)] for k in u.get("kats") or [] if (k, para) in orta]
            if aday:
                m, _ = min(aday, key=lambda x: x[1])
                oran = satis / m if m else 0
                if oran >= UC_KAT:
                    ekle(u, "uc_fiyat", f"Kategorisindeki ürünlerin ortanca fiyatının ({tl(m, para)}) {oran:.0f} katı; "
                                        "virgül ya da sıfır hatası olabilir.")
                elif oran and oran <= 1 / UC_KAT:
                    ekle(u, "uc_fiyat", f"Kategorisindeki ürünlerin ortanca fiyatının ({tl(m, para)}) {1 / oran:.0f}'te biri; "
                                        "virgül ya da sıfır hatası olabilir.")
        stok = _sayi(u.get("stok"))
        if stok is not None and stok <= 0 and not u.get("secenekli"):
            ekle(u, "stok_yok", "Yayında ama stoğu 0; müşteri satın alamaz.")
    sira = list(TURLER)
    out.sort(key=lambda x: (sira.index(x["tur"]), x["name"].lower()))
    return out
