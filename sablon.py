# -*- coding: utf-8 -*-
"""Ürün açıklaması şablonu: görünüm (sade, bantlı, çizgili, kutulu), ana renk, bölümler (açık / kapalı, sıra, başlık),
madde işareti, kapanış metni, stok kodu ve barkod gösterimi. Mağaza ayarında (sablon) durur; yukle() eksik ve
geçersiz değerleri varsayılanla tamamlar.

Ideasoft panelindeki SEO yüzdesi kelime sayımına HTML'i de katar; panel_factor (1,30) Ustapazar'ın bantlı görünümüyle
ölçüldü. Ideasoft'un stilleri sayıp saymadığı bilinmediği için her görünümün her stili, ölçüm sırasındaki stille aynı
sayıda kelime üretir (STYLE_WORDS) ve her renk tek bir kelime sayılır. Yeni görünüm eklerken bu eşitliği koru;
test_sablon.py denetler. Test mağazasında Ideasoft'un sayımı ölçülünce bu sınır kalkabilir.
"""
import re

STYLE_WORDS = {"h": 6, "kutu": 7, "liste": 6}
VARSAYILAN_RENK = "#1b4f72"          # Ustapazar'ın rengi; renkli görünümlerin ilk değeri

GORUNUMLER = {
    "sade": {"ad": "Sade", "aciklama": "Başlıklar ve maddeler; her temaya uyar.", "renkli": False},
    "bantli": {"ad": "Bantlı", "aciklama": "Başlıklar renkli bant içinde.", "renkli": True},
    "cizgili": {"ad": "Çizgili", "aciklama": "Renkli başlıkların altında ince çizgi.", "renkli": True},
    "kutulu": {"ad": "Kutulu", "aciklama": "Başlıklar açık renkli kutuda, kapanış çerçeveli.", "renkli": True},
}
BOLUMLER = (("one_cikan", "Öne Çıkan Özellikler"), ("teknik", "Teknik Özellikler"), ("kullanim", "Kullanım Alanları"),
            ("paket", "Paket İçeriği"), ("neden", "Neden Tercih Etmelisiniz?"))
MADDELER = {"✔": "Onay işareti (✔)", "•": "Nokta (•)", "–": "Tire (–)", "→": "Ok (→)", "": "Temanın madde işareti"}
BASLIK_UZUNLUK, KAPANIS_UZUNLUK = 60, 300


def renk_duzelt(v):
    """#abc ya da #aabbcc biçimindeki rengi küçük harfle döndürür; geçersizse None."""
    v = (v or "").strip().lower() if isinstance(v, str) else ""
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        v = "#" + "".join(c * 2 for c in v[1:])
    return v if re.fullmatch(r"#[0-9a-f]{6}", v) else None


def _rgb(hex6):
    return [int(hex6[i:i + 2], 16) for i in (1, 3, 5)]


def _parlaklik(hex6):
    r, g, b = (c / 255 for c in _rgb(hex6))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _yazi(arka):
    """Renkli zeminde okunur yazı rengi."""
    return "#fff" if _parlaklik(arka) < 0.6 else "#222"


def _okunur(renk):
    """Beyaz zeminde yazı rengi olarak okunur hâli: çok açık renk yerine koyu gri."""
    return renk if _parlaklik(renk) < 0.6 else "#333"


def _acik(renk):
    """Kutulu başlığın zemini: rengin beyazla karışmış açık tonu."""
    return "#" + "".join(f"{round(c + (255 - c) * 0.86):02x}" for c in _rgb(renk))


def stiller(t):
    """Şablonun satır içi stilleri: h (bölüm başlığı), kutu (kapanış), liste (işaretli maddeler)."""
    ad, r = t["gorunum"], t["renk"]
    liste = "list-style:none;padding-left:6px" if t["madde"] else "list-style:disc;padding-left:20px"
    if ad == "bantli":
        return {"h": f"background:{r};color:{_yazi(r)};padding:8px", "kutu": f"border-left:4px solid {r};padding:8px",
                "liste": liste}
    if ad == "cizgili":
        return {"h": f"color:{_okunur(r)};border-bottom:2px solid", "kutu": f"border-top:2px solid {r};clear:both",
                "liste": liste}
    if ad == "kutulu":
        return {"h": f"background:{_acik(r)};color:{_okunur(r)};padding:8px", "kutu": f"border:1px solid {r};padding:8px 12px",
                "liste": liste}
    return {"h": "margin:16px 0 6px;padding:0", "kutu": "border-top:1px solid #ddd;clear:both", "liste": liste}


def yukle(d, varsayilan_gorunum="sade"):
    """Kayıtlı şablonu eksiksiz ve geçerli hâle getirir. Bölümler kayıttaki sırayla, eksikler varsayılan sırayla sona eklenir."""
    d = d if isinstance(d, dict) else {}
    adlar = dict(BOLUMLER)
    bolumler, gorulen = [], set()
    for b in d.get("bolumler") or []:
        if isinstance(b, dict) and b.get("k") in adlar and b["k"] not in gorulen:
            gorulen.add(b["k"])
            baslik = re.sub(r"\s+", " ", str(b.get("baslik") or "")).strip()[:BASLIK_UZUNLUK]
            bolumler.append({"k": b["k"], "acik": b.get("acik") is not False, "baslik": baslik or adlar[b["k"]]})
    bolumler += [{"k": k, "acik": True, "baslik": v} for k, v in BOLUMLER if k not in gorulen]
    kap = d.get("kapanis") if isinstance(d.get("kapanis"), dict) else {}
    return {
        "gorunum": d.get("gorunum") if d.get("gorunum") in GORUNUMLER else varsayilan_gorunum,
        "renk": renk_duzelt(d.get("renk")) or VARSAYILAN_RENK,
        "bolumler": bolumler,
        "madde": d.get("madde") if d.get("madde") in MADDELER else "✔",
        "kapanis": {"acik": kap.get("acik") is not False,
                    "metin": re.sub(r"\s+", " ", str(kap.get("metin") or "")).strip()[:KAPANIS_UZUNLUK]},
        "stok_kodu": d.get("stok_kodu") is not False,
        "barkod": d.get("barkod") is not False,
    }


def birlestir(eski, yeni):
    """Panelden gelen kısmi değişikliği kayıtlı şablona ekler (gönderilmeyen ayarlar korunur)."""
    out = dict(eski if isinstance(eski, dict) else {})
    out.update({k: v for k, v in (yeni if isinstance(yeni, dict) else {}).items()
                if k in ("gorunum", "renk", "bolumler", "madde", "kapanis", "stok_kodu", "barkod")})
    return out


def secenekler():
    """Panelin şablon ekranı için seçenekler."""
    return {"gorunumler": GORUNUMLER, "bolumler": [{"k": k, "baslik": v} for k, v in BOLUMLER], "maddeler": MADDELER,
            "varsayilan_renk": VARSAYILAN_RENK, "baslik_uzunluk": BASLIK_UZUNLUK, "kapanis_uzunluk": KAPANIS_UZUNLUK}


def tema_rengi(sayfa):
    """Mağazanın ana sayfasından tema rengi önerisi: önce theme-color etiketi, yoksa sayfadaki stillerde en sık geçen
    canlı renk (beyaz, siyah ve griler sayılmaz). Bulunamazsa None."""
    m = re.search(r'<meta[^>]+name=["\'](?:theme-color|msapplication-TileColor)["\'][^>]*content=["\']([^"\']+)', sayfa, re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\'](?:theme-color|msapplication-TileColor)', sayfa, re.I)
    if m and renk_duzelt(m.group(1)):
        return renk_duzelt(m.group(1))
    stil = " ".join(re.findall(r"(?is)<style[^>]*>(.*?)</style>", sayfa) + re.findall(r'style="([^"]*)"', sayfa))
    say = {}
    for h in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", stil):
        r = renk_duzelt(h)
        rgb = _rgb(r)
        if max(rgb) - min(rgb) > 40 and 0.08 < _parlaklik(r) < 0.85:   # canlı ve ne çok açık ne çok koyu
            say[r] = say.get(r, 0) + 1
    return max(say, key=say.get) if say else None
