# -*- coding: utf-8 -*-
"""Mağaza profili: metin üreticilerinin mağazaya göre değişen kısımları.

  magaza : mağazanın adı (başlık, meta açıklama ve kapanış cümlelerinde geçer)
  marka  : varsayılan marka. Ürünün kendi marka alanı doluysa o kullanılır; boşsa bu değer.

Şablonlarda {magaza} ve {marka} yer tutucuları kullanılır. Marka bilinmiyorsa {marka} geçen cümleler
seçilmez; böylece "Orijinal  ürünü" gibi boşluklu cümleler çıkmaz.
"""
import re

DEFAULT = {"magaza": "", "marka": ""}


def load(d):
    """Ayarlardaki profil sözlüğünü eksik alanları tamamlayarak döndürür."""
    out = dict(DEFAULT)
    out.update({k: v for k, v in (d or {}).items() if k in DEFAULT})
    out["magaza"] = (out["magaza"] or "").strip()
    out["marka"] = (out["marka"] or "").strip()
    return out


def product_brand(product):
    """Ürün kaydındaki marka adı (Ideasoft: brand = {"id", "name"} ya da metin)."""
    b = (product or {}).get("brand")
    if isinstance(b, dict):
        b = b.get("name")
    return (b or "").strip() if isinstance(b, str) else ""


def with_brand(prof, product=None):
    """Ürüne göre markası belirlenmiş profil: ürünün kendi markası, yoksa profildeki varsayılan marka."""
    p = load(prof)
    p["marka"] = product_brand(product) or p["marka"]
    return p


def fill(text, prof):
    """{magaza}, {marka} ve {marka_in} ("Philips'in", "Koton'un") yer tutucularını doldurur
    (str.format değil: ürün adında süslü parantez olabilir)."""
    m = prof.get("marka") or ""
    return (text.replace("{magaza}", prof.get("magaza") or "").replace("{marka_in}", gen(m) if m else "")
            .replace("{marka}", m))


def usable(text, prof):
    """Profilde karşılığı olmayan yer tutucu içeren şablon kullanılmaz."""
    return not (("{magaza}" in text and not prof.get("magaza")) or ("{marka" in text and not prof.get("marka")))


def _vowel(name):
    low = (name or "").replace("I", "ı").replace("İ", "i").lower()
    vs = [c for c in low if c in "aeıioöuü"]
    return (vs[-1] if vs else "e"), low[-1:]


def gen(name):
    """İyelik eki: Philips'in, Koton'un, Mavi'nin (son ünlüye göre; ünlüyle bitiyorsa -n-)."""
    v, last = _vowel(name)
    s = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[v]
    return f"{name}'{'n' if last in 'aeıioöuü' else ''}{s}n"


def pick(templates, prof):
    """Kullanılabilir şablonları doldurulmuş olarak döndürür (sıra korunur)."""
    return [fill(t, prof) for t in templates if usable(t, prof)]


def loc(name):
    """Bulunma eki: Butik'te, Moda Evi'nde, Pazar'da. Son ünlü ve son harfe göre (büyük ünlü uyumu, sertleşme)."""
    n = (name or "").strip()
    v, last = _vowel(n)
    # "Moda Evi", "Güzellik Dünyası": tamlamanın sonundaki iyelik ekinden sonra -n- gelir (Evi'nde, Dünyası'nda)
    buffer = "n" if len(n.split()) >= 2 and last in "ıiuü" else ""
    return f"{n}'{buffer}{'t' if last in 'fsthçşkp' else 'd'}{'a' if v in 'aıou' else 'e'}"


def brand_prefix_rx(prof):
    """Ürün adının başındaki marka adı ("Philips ...", "Philips - ..."); hedef kelimede tekrarlanmasın."""
    if not prof.get("marka"):
        return None
    m = re.escape(prof["marka"])
    return rf"^({m}\s*-?\s*)"
