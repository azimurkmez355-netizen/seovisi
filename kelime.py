# -*- coding: utf-8 -*-
"""Akıllı anahtar kelime araştırması (blog yazıları için). Yalnızca Python standart kütüphanesi.

Hedef kelime adayları ürün adından çıkarılır (ardışık 1-5 kelimelik parçalar, mevcut hedef kelime, ürün tipi, marka + tip)
ve her aday Google'ın arama önerileriyle (gerçek arama talebi: insanların yazmaya başlayınca Google'ın tamamladığı
aramalar) ve yerel ölçütlerle puanlanır:
  talep      Google önerilerinde birebir ya da başında geçiyor mu, kaç uzun kuyruklu arama onu içeriyor;
  uygunluk   ürün adında geçiyor mu, ürün tipini / markayı içeriyor mu;
  uzunluk    2-4 kelime (tek kelime çok genel ve rekabetçi, çok uzun ifade kimsenin aramadığı türden);
  özgüllük   model / seri bilgisi içeriyor mu;
  yamyamlaşma aynı hedef kelime mağazanın başka bir yazısında kullanılıyorsa büyük ceza (iki yazı aynı aramada yarışmaz).
Google'a ulaşılamazsa (ağ, sınır) puan yalnızca yerel ölçütlerle verilir ve sonuçta bu yazılır. Google istekleri
önbelleğe alınır, aralarında bekleme vardır ve art arda hata gelince bir süre kesilir.
"""
import json
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request

import seo_text as ST

GOOGLE_ONERI = "https://suggestqueries.google.com/complete/search?client=firefox&hl=tr&gl=tr&ie=utf-8&oe=utf-8&q="
EN_UZUN = 40
BEKLEME = 0.35            # iki Google isteği arasında en az (saniye)
KESINTI_DK = 30           # art arda 3 hatadan sonra Google bu kadar dakika denenmez
UA = "Mozilla/5.0 (seovisi anahtar kelime arastirmasi)"
_RISKLI = set("®™©&:;'\"()[]*+%/<>|#’“”")
_GENEL = {"set", "seti", "takım", "takımı", "adet", "model", "yeni", "orijinal", "orjinal", "professional", "profesyonel",
          "pro", "plus", "mini", "maxi", "ürün", "ürünü"}


# ---------------------------------------------------------------- Google arama önerileri

class GoogleOneri:
    """Google'ın arama önerilerini getirir; hız sınırı ve hata kesicisi süreç geneli tek nesnede."""

    def __init__(self, zaman_asimi=6):
        self.zaman_asimi = zaman_asimi
        self.kilit = threading.Lock()
        self.son = 0.0
        self.hata = 0
        self.kapali_kadar = 0.0

    def __call__(self, sorgu):
        if time.time() < self.kapali_kadar:
            return None
        with self.kilit:
            bekle = self.son + BEKLEME - time.time()
            if bekle > 0:
                time.sleep(bekle)
            self.son = time.time()
        try:
            req = urllib.request.Request(GOOGLE_ONERI + urllib.parse.quote(sorgu), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=self.zaman_asimi) as r:
                ham = r.read(200000)
                kod = r.headers.get_content_charset() or "utf-8"
            veri = json.loads(ham.decode(kod, "replace"))
            oneriler = [str(x) for x in (veri[1] if isinstance(veri, list) and len(veri) > 1 else []) if isinstance(x, str)]
            self.hata = 0
            return oneriler[:20]
        except (OSError, ValueError, TypeError):
            self.hata += 1
            if self.hata >= 3:
                self.kapali_kadar, self.hata = time.time() + KESINTI_DK * 60, 0
            return None


GOOGLE = GoogleOneri()


# ---------------------------------------------------------------- adaylar

def _temiz(ad, sku=""):
    """Ürün adından stok kodu, parantez içi ekler ve " + aksesuar" gibi kuyruklar çıkarılır."""
    t = re.sub(r"\s+", " ", ad or "").strip()
    if sku:
        t = " ".join(w for w in t.split() if ST.tr_lower(w.strip(",.;:")) != ST.tr_lower(sku))
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    t = re.split(r"\s[\+–]\s?|\s-\s|\s\+", t)[0]
    return re.sub(r"\s+", " ", t).strip(" ,-")


def _uygun(aday):
    if not aday or len(aday) > EN_UZUN or len(aday) < 3 or any(c in _RISKLI for c in aday):
        return False
    kelimeler = aday.split()
    harfli = [w for w in kelimeler if re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", w)]
    if not harfli:
        return False
    if all(ST.tr_lower(w) in _GENEL for w in harfli):
        return False
    return not (len(kelimeler) == 1 and len(re.findall(r"\d", aday)) >= 6)      # yalnızca stok kodu / barkod


def model_dizisi(ad, sku=""):
    """Ürünün model adı (müşterinin aradığı: GWS 18V-8, GDR 120-Li, GSB 13 RE): adın içindeki rakamlı / kısaltmalı
    ardışık kelimeler. Yalnızca sayı + birimden oluşan dizi (2 Ah, 750 W) model sayılmaz."""
    w = [x.strip(",.;:") for x in _temiz(ad, sku).split() if x.strip(",.;:")]
    dizi, cur = [], []
    for x in w + [""]:
        if x and (_model_mi(x) or (len(x) == 1 and x.isupper())):
            cur.append(x)
            continue
        if cur:
            dizi.append(cur)
        cur = []
    for d in dizi:
        metin = " ".join(d)
        if re.search(r"[A-Za-z]", metin) and re.search(r"\d", metin) and not (len(d) <= 2 and _BIRIM.match(metin.replace(" ", ""))):
            return metin
    return ""


def _sadece_marka(aday, marka):
    """Aday yalnızca marka ve genel kelimelerden mi oluşuyor (Bosch, Bosch Professional)? Müşteri marka değil model arar."""
    mk = {ST.tr_lower(x) for x in (marka or "").split()}
    return all(ST.tr_lower(x) in mk or ST.tr_lower(x) in _GENEL for x in aday.split())


def adaylar(ad, mevcut="", sku="", label="", marka=""):
    """Ürün adından hedef kelime adayları (sırasız, tekrarsız)."""
    t = _temiz(ad, sku)
    w = [x.strip(",.;:") for x in t.split() if x.strip(",.;:")]
    out = []
    model = model_dizisi(ad, sku)
    if model:
        out.append(model)
        if marka and ST.tr_lower(marka) not in ST.tr_lower(model):
            out.append(f"{marka} {model}")
    for n in (2, 3, 4, 5, 1):
        for i in range(0, len(w) - n + 1):
            out.append(" ".join(w[i:i + n]))
    if mevcut and ST.tr_lower(mevcut) in ST.tr_lower(ad):
        out.insert(0, mevcut.strip())
    tl = ST.tr_lower(t)
    if label and ST.tr_lower(label) in tl:
        out.append(label)
        if marka and ST.tr_lower(marka) in tl:
            out.append(f"{marka} {label}")
    gor, sonuc = set(), []
    for a in out:
        a = re.sub(r"\s+", " ", a).strip(" ,-")
        k = ST.tr_lower(a)
        if k not in gor and _uygun(a) and not _sadece_marka(a, marka):
            gor.add(k)
            sonuc.append(a)
    return sonuc


# ---------------------------------------------------------------- puanlama

_BIRIM = re.compile(r"^\d+([.,]\d+)?\s?(w|watt|v|volt|kw|hp|mm|cm|m|kg|g|gr|lt|l|ml|cl|cc|ah|mah|rpm|bar|nm|inç|inch|adet|li|lü|lu|lı)$", re.I)


def _model_mi(w):
    """Model / seri parçası: rakam içeren ya da 2-5 harfli büyük harf kısaltma (GSB, RE, 13, 600W)."""
    return bool(re.search(r"\d", w)) or (w.isupper() and 2 <= len(w) <= 5 and w.isalpha())


def _bolunmus_model(aday, ad, sku=""):
    """Aday, ürün adındaki bir model dizisini (ör. GSB 13 RE) ortasından bölüyor mu?"""
    w = [x.strip(",.;:") for x in _temiz(ad, sku).split()]
    a = [x.strip(",.;:") for x in aday.split()]
    wl, al = [ST.tr_lower(x) for x in w], [ST.tr_lower(x) for x in a]
    for i in range(len(wl) - len(al) + 1):
        if wl[i:i + len(al)] == al:
            j = i + len(al)
            bas = i > 0 and _model_mi(w[i - 1]) and _model_mi(w[i])
            son = j < len(w) and _model_mi(w[j]) and _model_mi(w[j - 1])
            return bas or son
    return False


def _sonraki_kelime(aday, ad, sku=""):
    w = [x.strip(",.;:") for x in _temiz(ad, sku).split()]
    al = [ST.tr_lower(x.strip(",.;:")) for x in aday.split()]
    wl = [ST.tr_lower(x) for x in w]
    for i in range(len(wl) - len(al) + 1):
        if wl[i:i + len(al)] == al:
            return w[i + len(al)] if i + len(al) < len(w) else ""
    return ""


def bas_isim(ad, sku=""):
    """Ürünün ne olduğunu söyleyen ana isim: adın sonundan geriye, model / sayı / birim olmayan ilk anlamlı kelime
    (Bosch Kırıcı Delici Matkap 800W → Matkap; Paslanmaz Çelik Termos 500 ml → Termos)."""
    w = [x.strip(",.;:") for x in _temiz(ad, sku).split() if x.strip(",.;:")]
    for i in range(len(w) - 1, -1, -1):
        x = w[i]
        if _model_mi(x) or _BIRIM.match(x) or _BIRIM.match("1" + x) or ST.tr_lower(x) in _GENEL or len(x) < 3:
            continue
        if re.search(r"\d", x) or not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", x):
            continue
        return x
    return ""


def _yerel(aday, ad, label, marka, sku=""):
    k = ST.tr_lower(aday)
    kel = aday.split()
    n = len(kel)
    p, neden = 0, []
    bas = ST.tr_lower(bas_isim(ad, sku))
    if bas:
        anlamli = [x for x in kel if not (_BIRIM.match(x) or _BIRIM.match("1" + x) or re.fullmatch(r"[\d.,]+", x))]
        if anlamli and ST.tr_lower(anlamli[-1]) == bas:
            p += 10
            neden.append(f"ürünün ne olduğunu söylüyor ({bas_isim(ad, sku)})")
        elif bas not in k.split() and not (model_dizisi(ad, sku) and ST.tr_lower(model_dizisi(ad, sku)) in k):
            p -= 10
            neden.append("ürünün ne olduğunu söylemiyor (yarım ifade)")
    if k in ST.tr_lower(ad):
        p += 15
        neden.append("ürün adında geçiyor")
    lab = ST.tr_lower(label or "") if ST.tr_lower(label or "") not in ("ürün", "urun") else ""
    if lab and lab in k:
        p += 15
        neden.append("ürün tipini tam içeriyor")
        if k.endswith(lab.split()[-1]):
            p += 5
    elif label and any(ST.tr_lower(x) in k for x in label.split() if len(x) > 3):
        p += 5
        neden.append("ürün tipinden bir kelime içeriyor")
    if marka and ST.tr_lower(marka) in k:
        p += 5
        neden.append("markayı içeriyor")
    if 2 <= n <= 3:
        p += 15
        neden.append(f"{n} kelime (ideal uzunluk)")
    elif n == 4:
        p += 8
        neden.append("4 kelime")
    elif n == 1:
        neden.append("tek kelime: çok genel, rekabeti yüksek")
    model = ST.tr_lower(model_dizisi(ad, sku))
    if ST.tr_lower(kel[0]) in _GENEL:
        p -= 10
        neden.append("genel bir kelimeyle başlıyor")
    if model and model in k:
        p += 20
        neden.insert(0, f"ürünün model adını içeriyor ({model_dizisi(ad, sku)}): müşterinin aradığı")
        son = ST.tr_lower(kel[-1])
        if not k.endswith(model) and son != bas and not _model_mi(kel[-1]):
            p -= 8
            neden.append("modelden sonra yarım kalıyor")
    elif any(_model_mi(x) for x in kel):
        p += 5
        neden.append("model / seri bilgisi var (daha özgül arama)")
    if _bolunmus_model(aday, ad, sku):
        p -= 25
        neden.append("model adını ortasından bölüyor")
    sonraki = _sonraki_kelime(aday, ad, sku)
    if re.fullmatch(r"\d+([.,]\d+)?", kel[-1]) and sonraki and _BIRIM.match("1" + sonraki):
        p -= 15
        neden.append("sayı ile birimi ayrılmış")
    if _BIRIM.match(kel[-1]) and not (lab and lab in k and not k.endswith(ST.tr_lower(kel[-1]))):
        p -= 10
        neden.append("teknik değerle bitiyor (doğal arama değil)")
    return p, neden


def _talep(aday, oneri):
    """Google önerilerine göre talep puanı (0-50). oneri: {sorgu: [öneriler] ya da None}."""
    k = ST.tr_lower(aday)
    liste = oneri.get(aday)
    if liste is None:
        return None, []
    tam = any(ST.tr_lower(s) == k or ST.tr_lower(s).startswith(k + " ") for s in liste)
    kuyruk = [s for s in liste if all(x in ST.tr_lower(s) for x in k.split())]
    p, neden = 0, []
    if tam:
        p += 35
        neden.append("Google'da aranıyor (öneri olarak çıkıyor)")
    if kuyruk:
        p += min(15, 3 * len(kuyruk))
        neden.append(f"{len(kuyruk)} uzun kuyruklu arama içeriyor")
    ust = " ".join(aday.split()[:2])
    if ust != aday and any(ST.tr_lower(s).startswith(k) for s in oneri.get(ust) or []):
        p = min(50, p + 10)
        neden.append("kısa aramanın en sık tamamlanan hâli")
    return p, neden


def arastir(ad, mevcut="", sku="", label="", marka="", kullanilan=(), getir=None, onbellek=None, en_cok_istek=6):
    """Hedef kelime araştırması. kullanilan: mağazanın başka yazılarındaki hedef kelimeler. getir(sorgu) -> [öneri] | None
    (None: Google'a ulaşılamadı). onbellek: get(sorgu) / set(sorgu, liste). Dönüş: {"secilen", "adaylar", "ilgili", "google"}."""
    ads = adaylar(ad, mevcut, sku, label, marka)
    if not ads:
        return {"secilen": "", "adaylar": [], "ilgili": [], "google": False}
    kullanilan = {ST.tr_lower(k) for k in kullanilan or [] if k}
    yerel = {a: _yerel(a, ad, label, marka, sku) for a in ads}
    # Google'a yalnızca yerelde en iyi görünen birkaç aday (ve kısa hâlleri) sorulur: istek sayısı sınırlı
    sirali = sorted(ads, key=lambda a: -yerel[a][0])
    sorgular = []
    for a in sirali[:4]:
        for s in (a, " ".join(a.split()[:2])):
            if s not in sorgular:
                sorgular.append(s)
    oneri, ulasildi = {}, False
    for s in sorgular[:en_cok_istek]:
        liste = onbellek.get(s) if onbellek is not None else None
        if liste is None and getir:
            liste = getir(s)
            if liste is not None and onbellek is not None:
                onbellek.set(s, liste)
        if liste is not None:
            ulasildi = True
        oneri[s] = liste
    sonuc = []
    for a in ads:
        p, neden = yerel[a]
        t, tn = _talep(a, oneri)
        if t is not None:
            p += t
            neden = tn + neden
        if ST.tr_lower(a) in kullanilan:
            p -= 40
            neden = ["başka bir yazıda hedef kelime (yamyamlaşma)"] + neden
        sonuc.append({"kelime": a, "puan": max(0, min(100, p)), "neden": neden, "talep": t})
    sonuc.sort(key=lambda x: (-x["puan"], len(x["kelime"])))
    ilgili, gor = [], {ST.tr_lower(sonuc[0]["kelime"])}
    for liste in oneri.values():
        for s in liste or []:
            if ST.tr_lower(s) not in gor and len(s) <= 60 and not any(c in _RISKLI for c in s):
                gor.add(ST.tr_lower(s))
                ilgili.append(s)
    return {"secilen": sonuc[0]["kelime"], "adaylar": sonuc[:12], "ilgili": ilgili[:10], "google": ulasildi}
