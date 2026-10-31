# -*- coding: utf-8 -*-
"""Abonelik kaydı, paketler (paketler.json) ve mağazaya yazma izni.

Her mağazanın tek bir abonelik kaydı vardır: mağaza klasöründeki abonelik.json (paket, durum, bitiş tarihi, kaynak).
Kaydı bugün `python app.py --abonelik` komutu, ileride Ideasoft bildirimi, API sorgusu ya da yönetici paneli besler;
hepsi yaz() ile yazar. Program yalnızca bu kayda bakar. Kayıt her seferinde diskten okunur: dışarıdan yapılan bir
değişiklik çalışan sunucuda hemen geçerli olur.

Analiz ve geri alma her durumda açıktır; abonelik yalnızca mağazaya yeni değişiklik yazmayı sınırlar.
"""
import json
import os
import threading
from datetime import date, datetime, timedelta

PAKET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paketler.json")
FILE = "abonelik.json"
FREE = "ucretsiz"
DURUMLAR = ("deneme", "aktif", "ucretsiz", "iptal")      # süresi geçen deneme / aktif kayıt "suresi_doldu" sayılır
DURUM_ADI = {"deneme": "Deneme", "aktif": "Aktif", "ucretsiz": "Ücretsiz analiz", "iptal": "İptal edildi",
             "suresi_doldu": "Süresi doldu"}
_lock = threading.Lock()
_cache, _cache_lock = {"mtime": None, "data": None}, threading.Lock()


def _load():
    with open(PAKET_PATH, encoding="utf-8") as f:
        d = json.load(f)
    P = d.get("paketler") if isinstance(d, dict) else None
    if not isinstance(P, dict) or FREE not in P or \
            not all(isinstance(p, dict) and "ad" in p and "ozellikler" in p for p in P.values()):
        raise ValueError(f"'paketler' içinde '{FREE}' ve her pakette 'ad', 'ozellikler' olmalı")
    return d


def paketler():
    """paketler.json; dosya değişince yeniden okunur. Düzenlerken bozulursa son geçerli hâli kullanılır."""
    try:
        m = os.path.getmtime(PAKET_PATH)
    except OSError:
        m = None
    with _cache_lock:
        if _cache["data"] is None or m != _cache["mtime"]:
            _cache["mtime"] = m
            try:
                _cache["data"] = _load()
            except (OSError, ValueError) as e:
                if _cache["data"] is None:
                    raise
                print(f"Uyarı: {PAKET_PATH} okunamadı ({e}); önceki paketler kullanılıyor.")
        return _cache["data"]


def _write(path, kayit):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(kayit, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def oku(klasor, bugun=None):
    """Mağazanın kaydı. Yoksa paketler.json'daki yeni_magaza ayarıyla oluşturulur (deneme süresi o an başlar).
    Bozuk kayıt üzerine yazılmaz (elle düzeltilebilsin); düzelene kadar ücretsiz analiz sayılır."""
    path = os.path.join(klasor, FILE)
    with _lock:
        try:
            with open(path, encoding="utf-8") as f:
                kayit = json.load(f)
            return kayit if isinstance(kayit, dict) else {"paket": FREE, "durum": FREE, "kaynak": "bozuk kayıt"}
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            return {"paket": FREE, "durum": FREE, "kaynak": "bozuk kayıt"}
        yeni = paketler().get("yeni_magaza") or {}
        gun = int(yeni.get("gun") or 0)
        if yeni.get("durum") == "deneme" and gun > 0:
            kayit = {"paket": yeni.get("paket"), "durum": "deneme",
                     "bitis": ((bugun or date.today()) + timedelta(days=gun)).isoformat()}
        else:
            kayit = {"paket": FREE, "durum": FREE, "bitis": None}
        kayit.update(kaynak="otomatik", guncellendi=_now())
        os.makedirs(klasor, exist_ok=True)
        _write(path, kayit)
        return kayit


def yaz(klasor, paket=None, durum="aktif", bitis=None, kaynak="elle"):
    """Kaydı değiştirir. Bütün kaynaklar (komut satırı, Ideasoft bildirimi, yönetici paneli) buradan yazar.
    Geçersiz değerde ValueError (Türkçe mesajla)."""
    P = paketler()["paketler"]
    if durum not in DURUMLAR:
        raise ValueError(f"Durum şunlardan biri olmalı: {', '.join(DURUMLAR)}")
    if durum == FREE:
        paket = FREE
    elif durum == "iptal":
        paket = paket or (oku(klasor).get("paket") if os.path.isfile(os.path.join(klasor, FILE)) else FREE)
    if paket not in P:
        raise ValueError(f"Paket şunlardan biri olmalı: {', '.join(P)}")
    if durum in ("aktif", "deneme") and paket == FREE:
        raise ValueError("Aktif ya da deneme kaydı için ücretli bir paket seçin.")
    if bitis:
        try:
            bitis = date.fromisoformat(bitis).isoformat()
        except ValueError:
            raise ValueError("Bitiş tarihi YYYY-AA-GG biçiminde olmalı, örn. 2027-10-31.")
    kayit = {"paket": paket, "durum": durum, "bitis": bitis or None, "kaynak": kaynak, "guncellendi": _now()}
    with _lock:
        os.makedirs(klasor, exist_ok=True)
        _write(os.path.join(klasor, FILE), kayit)
    try:
        with open(os.path.join(klasor, "islem.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [info] Abonelik: {P[paket]['ad']}, {DURUM_ADI[durum]}"
                    f"{', bitiş ' + bitis if bitis else ''} ({kaynak}).\n")
    except OSError:
        pass
    return kayit


def gecerli(kayit, bugun=None):
    """Kayda göre bugün geçerli olan paket. Süresi geçmiş, iptal edilmiş ya da tanınmayan kayıt ücretsiz analize düşer."""
    bugun = bugun or date.today()
    P = paketler()["paketler"]
    durum = kayit.get("durum") if kayit.get("durum") in DURUMLAR else FREE
    bitis = kayit.get("bitis")
    kalan = None
    if durum in ("aktif", "deneme") and bitis:
        try:
            kalan = (date.fromisoformat(bitis) - bugun).days
        except (TypeError, ValueError):
            kalan = -1                                   # okunamayan tarih: süresi dolmuş sayılır
        if kalan < 0:
            durum, kalan = "suresi_doldu", None
    key = kayit.get("paket") if durum in ("aktif", "deneme") and kayit.get("paket") in P else FREE
    p = P[key]
    return {"paket": key, "ad": p["ad"], "durum": durum, "durum_adi": DURUM_ADI[durum], "bitis": bitis,
            "kalan_gun": kalan, "urun_siniri": p.get("urun"), "ozellikler": list(p.get("ozellikler") or []),
            "kayitli_paket": kayit.get("paket")}


def oneri(urun_sayisi):
    """Ürün sayısına yeten en küçük ücretli paketin adı (ürün sınırı olmayan iç paketler önerilmez)."""
    P = [p for p in paketler()["paketler"].values() if p.get("urun") and p.get("ozellikler")]
    if not P or not urun_sayisi:
        return None
    yeten = [p for p in P if p["urun"] >= urun_sayisi]
    return (min(yeten, key=lambda p: p["urun"]) if yeten else max(P, key=lambda p: p["urun"]))["ad"]


def _sayi(n):
    return f"{n:,}".replace(",", ".")


def _tarih(iso):
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(iso)


SONRA = " Mağazanızı analiz etmeye ve yapılan değişiklikleri geri almaya devam edebilirsiniz."


def engel(a, ozellik, urun_sayisi=0):
    """Mağazaya yazan bir işten önce: izin yoksa kullanıcıya gösterilecek mesaj, varsa None."""
    if ozellik not in a["ozellikler"]:
        if a["durum"] == "suresi_doldu":
            return (f"Aboneliğinizin süresi {_tarih(a['bitis'])} tarihinde doldu; mağazaya düzeltme gönderilemiyor. "
                    "Ideasoft App Store'dan yenileyebilirsiniz." + SONRA)
        if a["durum"] == "iptal":
            return "Aboneliğiniz iptal edildi; mağazaya düzeltme gönderilemiyor." + SONRA
        if a["paket"] == FREE:
            return ("Ücretsiz analiz kullanıyorsunuz: sorunları görebilirsiniz, düzeltmeleri mağazaya göndermek için "
                    "Ideasoft App Store'daki seovisi sayfasından bir paket seçin.")
        return f"Bu işlem {a['ad']} paketinde yok."
    lim = a["urun_siniri"]
    if lim and urun_sayisi > lim:
        return (f"Mağazanızda {_sayi(urun_sayisi)} ürün var; {a['ad']} paketi {_sayi(lim)} ürüne kadar. "
                "Düzeltme göndermek için bir üst pakete geçin." + SONRA)
    return None
