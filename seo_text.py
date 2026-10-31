# -*- coding: utf-8 -*-
"""Hedef kelime, açıklama ve SEO alanlarını üreten / puanlayan modül.

Sadece Python standart kütüphanesi kullanır.
Ideasoft paneldeki SEO kriterleri burada birebir yeniden hesaplanır:
  Üst kutu (7 kriter)  : hedef kelime, ad, başlıkta kelime, açıklama dolu,
                         açıklamada kelime, en az 50 kelime, yoğunluk %2-%3
  SEO bilgileri (6 kr.): sayfa başlığı dolu, 20-60 karakter, başlıkta kelime,
                         meta açıklama dolu, 50-155 karakter, meta'da kelime
"""
import html
import re

import profil as PR

# ---------------------------------------------------------------- yardımcılar

def tr_lower(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def strip_tags(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h or "")
    h = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h).replace("\xa0", " ")
    return re.sub(r"\s+", " ", h).strip()


def word_count(text):
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _ascii_split(t):
    return len([w for w in re.split(r"[^A-Za-z0-9_]+", t) if w])


def _uni_split(t):
    return len([w for w in re.split(r"[\W_]+", t) if w])


# Ideasoft'un paneldeki "Kelime Sayısı"nı nasıl hesapladığı belgelenmemiş. Olası yöntemler:
COUNT_METHODS = {
    "ws_text":  ("Metin, boşluklara göre", lambda h: word_count(strip_tags(h))),
    "uni_text": ("Metin, noktalama ve boşluklara göre", lambda h: _uni_split(strip_tags(h))),
    "asc_text": ("Metin, Türkçe harfler ayırıcı (JS \\W)", lambda h: _ascii_split(strip_tags(h))),
    "ws_html":  ("Ham HTML, boşluklara göre", lambda h: word_count(h or "")),
    "uni_html": ("Ham HTML, noktalama ve boşluklara göre", lambda h: _uni_split(h or "")),
    "asc_html": ("Ham HTML, Türkçe harfler ayırıcı (JS \\W)", lambda h: _ascii_split(h or "")),
    "panel": ("Ideasoft paneli tahmini (ham HTML sayımı / panel katsayısı)",
              lambda h: max(1, round(_ascii_split(h or "") / panel_factor()))),
    "panel_lo": ("Panel tahmini (düşük katsayı)", lambda h: max(1, round(_ascii_split(h or "") / (panel_factor() * 0.88)))),
    "panel_hi": ("Panel tahmini (yüksek katsayı)", lambda h: max(1, round(_ascii_split(h or "") / (panel_factor() * 1.12)))),
    "asc_noattr": ("HTML (etiket özellikleri hariç), Türkçe harfler ayırıcı",
                   lambda h: _ascii_split(re.sub(r"<(/?\w+)[^>]*>", r"<\1>", h or ""))),
}


# Gönderilen ürünlerde panelin gösterdiği oranlar, ham HTML sayımıyla bulunan oranın ~1,3 katı çıktı
# (%2,25 -> %3,00; %2,42 -> %3,20; %2,43 -> %3,07). Katsayı mağazaya göre değişir; uygulama bu işlevi
# o anki mağazanın ayarından okuyan biriyle değiştirir.
def panel_factor():
    return 1.30


def count_words(html_str, method):
    return COUNT_METHODS.get(method, COUNT_METHODS["ws_text"])[1](html_str or "")


def count_kw(text, kw):
    """Hedef kelimenin metinde kaç kez geçtiği (büyük/küçük harf duyarsız)."""
    if not kw:
        return 0
    t, k = tr_lower(text), tr_lower(kw.strip())
    n, i = 0, t.find(k)
    while i != -1:
        n += 1
        i = t.find(k, i + len(k))
    return n


def density(text, kw):
    w = word_count(text)
    return (count_kw(text, kw) / w * 100.0) if w else 0.0


# ------------------------------------------------------------ hedef kelime

_STOP_CHARS = set('(["\'/|–-+:;')


def _bad_tok(t):
    return (any(c.isdigit() for c in t) or t[0] in _STOP_CHARS or t in ("x", "X", "Ø", "ø", "&")
            or any(c in t.rstrip(",;:.") for c in '"()[]/&'))


def extract_keyword(name, max_words=7, max_len=55):
    """Ürün adının başından, ilk ölçü/sayı/model bilgisine kadar olan kısmı alır.
    'Kadın Çiçek Desenli Midi Elbise 36-44 Beden' -> 'Kadın Çiçek Desenli Midi Elbise'
    Sonuç her zaman ürün adının içinde birebir geçer (başlık kriteri için)."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name:
        return ""
    toks = name.split(" ")
    # ad içindeki "temiz" (sayısız) kelime gruplarını çıkar
    runs, cur = [], []
    for t in toks:
        if _bad_tok(t):
            if cur:
                runs.append(cur)
            cur = []
            continue
        clean = t.rstrip(",;:.")
        cur.append(clean)
        if clean != t:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    cleaned = []
    for r in runs:
        r = r[:max_words]
        while r and (len(r[-1]) <= 1 or r[-1].isupper() and len(r[-1]) <= 2):
            r = r[:-1]  # sondaki 'T', 'S', 'B' gibi model harflerini at
        while len(" ".join(r)) > max_len and len(r) > 2:
            r = r[:-1]
        if r:
            cleaned.append(r)
    kw = ""
    if cleaned:
        first = cleaned[0]
        if len(first) >= 2 and toks[0].rstrip(",;:.") == first[0]:
            kw = " ".join(first)
        else:
            best = max(cleaned, key=len)
            kw = " ".join(best if len(best) >= 2 else first)
    if len(kw.split()) < 2 or tr_lower(kw) not in tr_lower(name):
        kw = name if len(name) <= max_len else name[:max_len].rsplit(" ", 1)[0]
    return kw.strip()


# ----------------------------------------------------- ürün tipi

# Ürün tipi bilinmez (her sektör olabilir); etiket ürünün kategorisinden gelir.
GENERIC = ("urun", "", "ürün",
           ["günlük kullanım", "farklı ihtiyaçlara uygun kullanım", "uzun süreli ve sorunsuz kullanım"],
           ["özenli üretimi uzun kullanım ömrü sunar",
            "kullanışlı tasarımı günlük kullanımı kolaylaştırır",
            "kaliteli malzemesi her kullanımda aynı memnuniyeti sağlar"])


def detect_type(name, prof=None, product=None):
    """(anahtar, desen, etiket, kullanım alanları, özellikler); etiket ürünün en alt kategorisinin adı."""
    cats = [c.get("name") for c in (product or {}).get("categories") or [] if isinstance(c, dict) and c.get("name")]
    label = tr_lower(cats[-1]) if cats else "ürün"
    # kategori adları çoğuldur; cümlede tekil gerekir ("bir elbiseler modeli" değil "bir elbise modeli")
    label = re.sub(r"(\w{3,})(ler|lar)\b$", r"\1", label)
    return GENERIC[:2] + (label,) + GENERIC[3:]


# ------------------------------------------------------------ başlık, meta, anahtar kelimeler

def make_title(name, kw, prof=None):
    """Sayfa başlığı (20-60 karakter): ad uygunsa adın kendisi, değilse mağaza adıyla tamamlanır."""
    prof = PR.load(prof)
    if 20 <= len(name) <= 60:
        return name
    if len(name) > 60:
        for t in PR.pick([f"{kw} | {{magaza}}"], prof) + [kw]:
            if 20 <= len(t) <= 60:
                return t
        return kw[:60]
    for t in PR.pick([f"{name} | {{magaza}}", f"{name} - {{marka}} | {{magaza}}"], prof):
        if 20 <= len(t) <= 60:
            return t
    return re.sub(r"\s+", " ", PR.fill(name + " | {magaza} {marka}", prof)).strip(" |")[:60]


def make_meta(kw, label, specs, rng, prof=None):
    """Meta açıklama (50-155 karakter). {at}: "Butik'te" gibi mağaza adı + bulunma eki.
    Mağazanın sunmadığı bir hizmeti (hızlı kargo, faturalı satış...) vaat etmez."""
    prof = PR.load(prof)
    spec = f" {specs[0]}" if specs else ""
    cands = [f"{kw}{spec} {{at}}. {{marka}} {label} seçeneklerini uygun fiyatla inceleyin.",
             f"{kw}{spec} uygun fiyatla {{at}}. Ürün detaylarını inceleyip güvenle sipariş verin.",
             f"{kw}{spec}. Ürün detaylarını inceleyin, kolayca sipariş verin."]
    last = [f"{kw} {{at}}. Ürün detaylarını hemen inceleyin.", f"{kw} - ürün detayları ve fiyat bilgisi."]

    def ok(ts):   # {at} mağaza adı yoksa kullanılamaz; diğer yer tutucular profil.py'de
        at = PR.loc(prof["magaza"]) if prof["magaza"] else ""
        return [t.replace("{at}", at) for t in PR.pick(ts, prof) if at or "{at}" not in t]
    cands = ok(cands)
    rng.shuffle(cands)
    last = ok(last)
    for c in cands + last[:1]:
        if 50 <= len(c) <= 155:
            return c
    c = last[-1]
    if len(c) > 155:
        c = c[:152].rsplit(" ", 1)[0] + "..."
    return c


def make_keywords(kw, name, label, prof=None):
    prof = PR.load(prof)
    items = [kw, name] + PR.pick([f"{{marka}} {label}"], prof) + [label] + PR.pick(["{magaza}"], prof)
    seen, out = set(), []
    for i in items:
        k = tr_lower(i)
        if k not in seen:
            seen.add(k)
            out.append(i)
    return ", ".join(out)


# --------------------------------------------------------------- SEO puanı

def seo_score(name, keyword, details_html, page_title, meta_desc, method=""):
    plain = strip_tags(details_html)
    ms = [m for m in (method or "").split(",") if m in COUNT_METHODS] or ["ws_text"]
    c = count_kw(plain, keyword)
    ds = []
    for m in ms:
        wm = count_words(details_html, m)
        ds.append((wm, (c / wm * 100) if wm else 0))
    w = min(x[0] for x in ds)
    d = min(ds, key=lambda x: min(x[1] - 2.0, 3.0 - x[1]))[1]  # en riskli yöntemin yoğunluğu
    kwl = tr_lower(keyword or "")
    top = [
        (bool(keyword), "Hedef kelime tanımlı"),
        (bool(name), "Ürün adı dolu"),
        (bool(kwl) and kwl in tr_lower(name), "Hedef kelime ürün adında geçiyor"),
        (bool(plain), "Açıklama dolu"),
        (c > 0, "Hedef kelime açıklamada geçiyor"),
        (w >= 50, f"Açıklama en az 50 kelime (şu an {w})"),
        (2.0 <= d <= 3.0, f"Hedef kelime yoğunluğu %2-%3 (şu an %{d:.2f})"),
    ]
    pt, md = page_title or "", meta_desc or ""
    bottom = [
        (bool(pt), "Sayfa başlığı dolu"),
        (20 <= len(pt) <= 60, f"Sayfa başlığı 20-60 karakter (şu an {len(pt)})"),
        (bool(kwl) and kwl in tr_lower(pt), "Hedef kelime sayfa başlığında geçiyor"),
        (bool(md), "Meta açıklama dolu"),
        (50 <= len(md) <= 155, f"Meta açıklama 50-155 karakter (şu an {len(md)})"),
        (bool(kwl) and kwl in tr_lower(md), "Hedef kelime meta açıklamada geçiyor"),
    ]
    tp = round(100 * sum(ok for ok, _ in top) / len(top))
    bp = round(100 * sum(ok for ok, _ in bottom) / len(bottom))
    return {"top": tp, "bottom": bp, "words": w, "count": c, "density": round(d, 2),
            "fails": [m for ok, m in top + bottom if not ok]}
