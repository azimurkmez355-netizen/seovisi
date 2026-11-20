# -*- coding: utf-8 -*-
"""seovisi kalite kapısı: blog yazısının kendi SEO puanı, okunabilirliği ve özgünlüğü. Yalnızca hesaplar.

Ideasoft'un 13 blog kuralı (blog.puan) zorunlu tabandır; bu modül onun üstüne Google'ın "yararlı içerik" ve sayfa içi SEO
ölçütlerinden türetilen kendi kurallarımızı koyar:
  - hedef kelime ilk paragrafta, en az bir ara başlıkta ve sayfa başlığının başında;
  - doyurucu uzunluk, ara başlık yapısı, liste / tablo / sık sorulan sorular;
  - iç bağlantılar (ürün sayfası, kategori, ilgili yazılar) ve ürün kartı;
  - özgünlük: meta açıklama, içerik ve hedef kelime mağazanın diğer yazılarıyla karşılaştırılır (kopya meta, kopya
    içerik ve aynı hedef kelimeyle yarışan iki yazı / "yamyamlaşma" olmaz);
  - okunabilirlik: Türkçe için Ateşman formülü, ortalama ve uzun cümle oranı, doğal anahtar kelime kullanımı.
Yazı SINIRLAR'ı geçmezse yazar (blog.yaz_tam) yazıyı başka anlatım ve biçimle baştan yazar.
"""
import hashlib
import html
import re
import threading
from collections import defaultdict

import seo_text as ST

# kalite kapısı: bu sınırların altındaki yazı yeniden yazılır, otomasyon onu yayımlamaz
SINIRLAR = {"seo": 94, "okunabilirlik": 50, "meta_benzerlik": 0.5, "icerik_benzerlik": 0.7}
TAM_OZGUN = 0.5           # içerik benzerliği bunun altındaysa özgünlük kuralının tam puanı

_SESLI = set("aeıioöuüâîû")
_KELIME = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+(?:['’][A-Za-zçğıöşü]+)?")
_BLOK = re.compile(r"(?is)<(p|li|blockquote|td)\b[^>]*>(.*?)</\1>")
_DOLGU_KELIMELER = {"ve", "ile", "bir", "bu", "için", "da", "de", "ki", "mi", "çok", "daha", "en", "gibi", "olarak", "her",
                    "ya", "veya", "ama", "ne", "o", "şu", "hem", "kadar"}


# ---------------------------------------------------------------- okunabilirlik

def _hece(kelime):
    n = sum(1 for c in ST.tr_lower(kelime) if c in _SESLI)
    return max(1, n)


def _bloklar(icerik):
    """Okunan metin blokları (paragraf, liste maddesi, alıntı, tablo hücresi); başlıklar ve düğmeler sayılmaz."""
    out = []
    for _, govde in _BLOK.findall(icerik or ""):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", govde))).strip()
        if len(_KELIME.findall(t)) >= 3:
            out.append(t)
    return out


def cumleler(icerik):
    out = []
    for b in _bloklar(icerik):
        for c in re.split(r"(?<=[.!?…])\s+(?=[A-ZÇĞİÖŞÜ0-9\"“])", b):
            if _KELIME.findall(c):
                out.append(c)
    return out


def okunabilirlik(icerik):
    """Ateşman (1997) Türkçe okunabilirlik: 198,825 − 40,175 × (hece / kelime) − 2,610 × (kelime / cümle).
    90-100 çok kolay, 70-89 kolay, 50-69 orta, 30-49 zor, 0-29 çok zor."""
    cs = cumleler(icerik)
    kelimeler = [w for c in cs for w in _KELIME.findall(c)]
    if not cs or not kelimeler:
        return {"puan": 0, "seviye": "Ölçülemedi", "ort_cumle": 0, "uzun_cumle": 0, "cumle": 0, "kelime": 0}
    hece = sum(_hece(w) for w in kelimeler)
    kpc = len(kelimeler) / len(cs)
    puan = 198.825 - 40.175 * (hece / len(kelimeler)) - 2.610 * kpc
    puan = max(0, min(100, round(puan)))
    uzun = sum(1 for c in cs if len(_KELIME.findall(c)) > 25)
    seviye = ("Çok kolay" if puan >= 90 else "Kolay" if puan >= 70 else "Orta" if puan >= 50 else "Zor" if puan >= 30
              else "Çok zor")
    return {"puan": puan, "seviye": seviye, "ort_cumle": round(kpc, 1), "uzun_cumle": round(100 * uzun / len(cs)),
            "cumle": len(cs), "kelime": len(kelimeler)}


# ---------------------------------------------------------------- özgünlük (kopya meta, kopya içerik)

def _normal(metin, kw=""):
    """Karşılaştırma için: küçük harf, hedef kelime ve sayılar çıkarılmış kelimeler (ürün adı değişse de şablon görünsün)."""
    t = ST.tr_lower(html.unescape(metin or ""))
    for k in {ST.tr_lower(kw or "")} | set(ST.tr_lower(kw or "").split()):
        if len(k) > 2:
            t = t.replace(k, " ")
    return [w for w in _KELIME.findall(t) if not w.isdigit()]


def _shingle(kelimeler, n):
    return {" ".join(kelimeler[i:i + n]) for i in range(max(0, len(kelimeler) - n + 1))} or set(kelimeler)


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def meta_parmak(meta, kw=""):
    """Meta açıklamanın karşılaştırma izi: hedef kelime çıkarılmış kelime ikilileri ve anlamlı tekil kelimeler."""
    k = _normal(meta, kw)
    return sorted(_shingle(k, 2) | {w for w in k if w not in _DOLGU_KELIMELER})


def meta_benzerlik(meta, kw, digerleri, haric=None):
    """En benzeyen diğer metanın benzerliği (0-1) ve o yazının numarası. digerleri: Dizin ya da [{"pid", "meta_iz"}]."""
    return dizin(digerleri).meta_benzerlik(meta, kw, haric)


_MASKE = [int(hashlib.md5(f"seovisi-minhash-{i}".encode()).hexdigest()[:16], 16) for i in range(64)]


def icerik_imzasi(icerik, kw=""):
    """İçeriğin MinHash imzası (64 sayı): 5 kelimelik parçalar; iki imzanın aynı sıradaki eşitlik oranı benzerliktir."""
    parcalar = _shingle(_normal(ST.strip_tags(icerik or ""), kw), 5)
    if not parcalar:
        return []
    hs = [int(hashlib.md5(p.encode()).hexdigest()[:16], 16) for p in parcalar]
    return [min(h ^ m for h in hs) for m in _MASKE]


def imza_benzerlik(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def icerik_benzerlik(imza, digerleri, haric=None):
    return dizin(digerleri).icerik_benzerlik(imza, haric)


class Dizin:
    """Mağazanın bütün yazılarının izleri için hızlı arama: içerik için MinHash bantları (16 bant x 4), meta için ters
    dizin, hedef kelimeler için sözlük. Binlerce yazıda her yeni yazı yalnızca adaylarla karşılaştırılır."""
    BANT = 4

    def __init__(self, izler=()):
        self.kilit = threading.Lock()
        self.izler = {}
        self.bant = defaultdict(set)
        self.meta = defaultdict(set)
        self.kw = defaultdict(set)
        for d in izler or []:
            self.ekle(d.get("pid"), d)

    def ekle(self, pid, d):
        with self.kilit:
            self._sil(pid)
            d = {"pid": pid, "keyword": d.get("keyword") or "", "meta_iz": list(d.get("meta_iz") or []),
                 "imza": list(d.get("imza") or [])}
            self.izler[pid] = d
            for i in range(0, len(d["imza"]), self.BANT):
                self.bant[(i, tuple(d["imza"][i:i + self.BANT]))].add(pid)
            for t in d["meta_iz"]:
                self.meta[t].add(pid)
            if d["keyword"]:
                self.kw[ST.tr_lower(d["keyword"])].add(pid)

    def sil(self, pid):
        with self.kilit:
            self._sil(pid)

    def _sil(self, pid):
        d = self.izler.pop(pid, None)
        if not d:
            return
        for i in range(0, len(d["imza"]), self.BANT):
            self.bant[(i, tuple(d["imza"][i:i + self.BANT]))].discard(pid)
        for t in d["meta_iz"]:
            self.meta[t].discard(pid)
        self.kw[ST.tr_lower(d["keyword"])].discard(pid)

    def __len__(self):
        return len(self.izler)

    def meta_benzerlik(self, meta, kw, haric=None):
        iz = set(meta_parmak(meta, kw))
        with self.kilit:
            adaylar = set().union(*(self.meta.get(t, ()) for t in iz)) if iz else set()
            adaylar.discard(haric)
            en, kim = 0.0, None
            for pid in adaylar:
                s = jaccard(iz, set(self.izler[pid]["meta_iz"]))
                if s > en:
                    en, kim = s, pid
        return round(en, 2), kim

    def icerik_benzerlik(self, imza, haric=None):
        if not imza:
            return 0.0, None
        with self.kilit:
            adaylar = set()
            for i in range(0, len(imza), self.BANT):
                adaylar |= self.bant.get((i, tuple(imza[i:i + self.BANT])), set())
            adaylar.discard(haric)
            en, kim = 0.0, None
            for pid in adaylar:
                s = imza_benzerlik(imza, self.izler[pid]["imza"])
                if s > en:
                    en, kim = s, pid
        return round(en, 2), kim

    def kelimeyi_kullanan(self, kw, haric=None):
        with self.kilit:
            return sorted(p for p in self.kw.get(ST.tr_lower(kw or ""), ()) if p != haric)


def dizin(d):
    return d if isinstance(d, Dizin) else Dizin(d or [])


# ---------------------------------------------------------------- seovisi SEO puanı

def _ilk_paragraf(icerik):
    m = re.search(r"(?is)<p\b[^>]*>(.*?)</p>", icerik or "")
    return ST.strip_tags(m.group(1)) if m else ""


def _ic_baglantilar(icerik):
    return [h for h in re.findall(r'href="([^"]+)"', icerik or "") if h.startswith("/")]


def degerlendir(plan, digerleri=(), ideasoft=None, haric=None):
    """Yazının seovisi kalite raporu. plan: blog planı; digerleri: mağazanın diğer yazılarının izleri
    [{"pid", "keyword", "meta_iz", "imza"}]; ideasoft: blog.puan sonucu (verilmezse plan["score"])."""
    ideasoft = ideasoft or plan.get("score") or {"yuzde": 0}
    kw, icerik = plan.get("keyword") or "", plan.get("content") or ""
    kwl = ST.tr_lower(kw)
    duz = ST.strip_tags(icerik)
    kelime = ST.word_count(duz)
    oku = okunabilirlik(icerik)
    h2 = re.findall(r"(?is)<h2\b[^>]*>(.*?)</h2>", icerik)
    basliklar = [ST.strip_tags(x) for x in h2 + re.findall(r"(?is)<h3\b[^>]*>(.*?)</h3>", icerik)]
    linkler = _ic_baglantilar(icerik)
    dz = dizin(digerleri)
    haric = haric if haric is not None else (plan.get("urun") or {}).get("id")
    meta_s, meta_kim = dz.meta_benzerlik(plan.get("metaDescription") or "", kw, haric)
    imza = plan.get("imza") or icerik_imzasi(icerik, kw)
    ic_s, ic_kim = dz.icerik_benzerlik(imza, haric)
    yamyam = dz.kelimeyi_kullanan(kw, haric) if kwl else []
    doldurma = [c for c in cumleler(icerik) if ST.count_kw(c, kw) >= 2]
    kaplama = (ST.count_kw(duz, kw) * len(kw.split()) / kelime) if kelime and kw else 0
    pt, ex, sl = plan.get("pageTitle") or "", plan.get("excerpt") or "", plan.get("slug") or ""

    def kademe(deger, tam, yarim):
        return 1.0 if deger >= tam else 0.5 if deger >= yarim else 0.0

    S = SINIRLAR
    kurallar = [
        # (ağırlık, kazanılan 0-1, grup, ad)
        (25, ideasoft.get("yuzde", 0) / 100, "Temel", "Ideasoft'un 13 blog kuralı"),
        (5, float(bool(kwl) and kwl in ST.tr_lower(_ilk_paragraf(icerik))), "Anahtar kelime", "Hedef kelime ilk paragrafta"),
        (5, float(any(kwl in ST.tr_lower(b) for b in basliklar)), "Anahtar kelime", "Hedef kelime bir ara başlıkta"),
        (4, float(bool(kwl) and ST.tr_lower(pt).startswith(kwl)), "Anahtar kelime", "Sayfa başlığı hedef kelimeyle başlıyor"),
        (6, float(not yamyam), "Anahtar kelime", "Hedef kelime başka bir yazıda kullanılmıyor"),
        (8, kademe(kelime, 500, 350), "İçerik", f"Doyurucu uzunluk: en az 500 kelime ({kelime})"),
        (5, kademe(len(h2), 3, 2), "İçerik", f"En az 3 ara başlık ({len(h2)})"),
        (4, float(bool(re.search(r"<(ul|ol)\b", icerik)) and bool(re.search(r"<table\b|<h3\b", icerik))),
         "İçerik", "Liste ve tablo / soru-cevap yapısı"),
        (8, kademe(len(set(linkler)), 3, 2), "Bağlantı", f"En az 3 iç bağlantı ({len(set(linkler))})"),
        (5, float('id="seovisi-urun-karti"' in icerik), "Bağlantı", "Ürün kartı"),
        (8, 1.0 if meta_s < S["meta_benzerlik"] else 0.0, "Özgünlük", f"Meta açıklama özgün (en yakın benzerlik %{round(meta_s * 100)})"),
        (10, 1.0 if ic_s < TAM_OZGUN else 0.5 if ic_s < S["icerik_benzerlik"] else 0.0,
         "Özgünlük", f"İçerik özgün (en yakın benzerlik %{round(ic_s * 100)})"),
        (8, kademe(oku["puan"], 60, S["okunabilirlik"]), "Okunabilirlik", f"Okunabilirlik (Ateşman {oku['puan']}, {oku['seviye'].lower()})"),
        (3, float(0 < oku["ort_cumle"] <= 18), "Okunabilirlik", f"Ortalama cümle en çok 18 kelime ({oku['ort_cumle']})"),
        (3, float(oku["uzun_cumle"] <= 10), "Okunabilirlik", f"Uzun cümle oranı en çok %10 (%{oku['uzun_cumle']})"),
        (3, float(not doldurma), "Okunabilirlik", "Doğal kullanım: hiçbir cümlede hedef kelime iki kez geçmiyor"),
        (4, float(kaplama <= 0.12), "Okunabilirlik", f"Anahtar kelime doldurma yok: hedef kelime metnin en çok %12'si (%{round(kaplama * 100)})"),
        (2, float(bool(sl) and len(sl) <= 80), "Teknik", f"Kısa adres (slug) ({len(sl)} karakter)"),
        (2, float(80 <= len(ex) <= 320 and kwl in ST.tr_lower(ex)), "Teknik", "Özet 80-320 karakter ve hedef kelimeyi içeriyor"),
    ]
    toplam = sum(w for w, _, _, _ in kurallar)
    puan = round(100 * sum(w * k for w, k, _, _ in kurallar) / toplam)
    gecti = (puan >= S["seo"] and oku["puan"] >= S["okunabilirlik"] and ideasoft.get("yuzde", 0) == 100 and kaplama <= 0.15
             and meta_s < S["meta_benzerlik"] and ic_s < S["icerik_benzerlik"] and not yamyam)
    return {"puan": puan, "okunabilirlik": oku, "gecti": gecti, "sinir": dict(S),
            "meta_benzerlik": meta_s, "meta_benzer_pid": meta_kim, "icerik_benzerlik": ic_s, "icerik_benzer_pid": ic_kim,
            "yamyam": yamyam[:5], "ic_baglanti": len(set(linkler)), "kelime": kelime, "kaplama": round(kaplama, 3),
            "kurallar": [{"ad": ad, "grup": g, "agirlik": w, "ok": k >= 1.0, "kismi": 0 < k < 1}
                         for w, k, g, ad in kurallar]}


def iz(plan):
    """Diğer yazılarla karşılaştırma için bu yazının izi (veritabanındaki planla birlikte saklanır)."""
    return {"keyword": plan.get("keyword") or "", "meta_iz": meta_parmak(plan.get("metaDescription") or "", plan.get("keyword")),
            "imza": plan.get("imza") or icerik_imzasi(plan.get("content") or "", plan.get("keyword"))}
