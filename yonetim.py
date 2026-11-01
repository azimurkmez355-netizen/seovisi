# -*- coding: utf-8 -*-
"""Yönetici paneli (/yonetim) yardımcıları: yönetici parolası, oturum çerezi ve mağaza kayıtlarındaki hatalar.

Parola data/yonetici.json dosyasında yalnızca karması (PBKDF2-SHA256, tuzlu) olarak durur; düz hâli hiçbir yere yazılmaz.
Dosya her girişte diskten okunur: sunucuda `python app.py --yonetici-parola` ile değiştirilen parola hemen geçerli olur
ve oturum imzası parolanın karmasını da kapsadığı için eski oturumlar kapanır.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta

FILE = "yonetici.json"
EN_KISA = 10                       # parolanın en az uzunluğu
TUR = 200_000                      # PBKDF2 tur sayısı
OTURUM_SAAT = 12


def karma(parola, tuz=None, tur=TUR):
    tuz = tuz or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", parola.encode("utf-8"), tuz.encode(), tur).hex()
    return f"pbkdf2_sha256${tur}${tuz}${h}"


def dogru(parola, kayitli):
    try:
        ad, tur, tuz, _ = (kayitli or "").split("$")
        if ad != "pbkdf2_sha256":
            return False
        return hmac.compare_digest(karma(parola or "", tuz, int(tur)), kayitli)
    except ValueError:
        return False


def oku(data):
    """Kayıtlı parola karması; parola belirlenmemişse ya da dosya bozuksa boş metin (giriş kapalı)."""
    try:
        with open(os.path.join(data, FILE), encoding="utf-8") as f:
            v = json.load(f).get("parola")
        return v if isinstance(v, str) and v.startswith("pbkdf2_sha256$") else ""
    except (OSError, ValueError, AttributeError):
        return ""


def yaz(data, parola):
    if len(parola or "") < EN_KISA:
        raise ValueError(f"Parola en az {EN_KISA} karakter olmalı.")
    path = os.path.join(data, FILE)
    os.makedirs(data, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"parola": karma(parola), "guncellendi": datetime.now().isoformat(timespec="seconds")}, f)
    os.replace(tmp, path)


def _imza(secret, bitis, kayitli):
    return hmac.new(secret.encode(), f"yonetim|{bitis}|{kayitli}".encode(), hashlib.sha256).hexdigest()


def cerez(secret, kayitli, simdi=None):
    """Oturum çerezinin değeri: bitiş zamanı ve imzası."""
    bitis = int(simdi or time.time()) + OTURUM_SAAT * 3600
    return f"{bitis}.{_imza(secret, bitis, kayitli)}"


def cerez_gecerli(secret, kayitli, deger, simdi=None):
    if not kayitli or not deger:
        return False
    bitis, _, imza = deger.partition(".")
    if not bitis.isdigit() or int(bitis) < (simdi or time.time()):
        return False
    return hmac.compare_digest(_imza(secret, int(bitis), kayitli), imza)


def _kuyruk(path, boyut=262144):
    """Kayıt dosyasının son kısmı (büyük dosyanın tamamı okunmaz)."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            n = f.tell()
            f.seek(max(0, n - boyut))
            satirlar = f.read().decode("utf-8", "replace").splitlines()
        return satirlar[1:] if n > boyut else satirlar          # ilk satır yarım olabilir
    except OSError:
        return []


def hatalar(klasor, gun=7, simdi=None):
    """islem.log içindeki son `gun` günün hataları, yeniden eskiye: [{"zaman", "mesaj"}]."""
    sinir = ((simdi or datetime.now()) - timedelta(days=gun)).strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for s in _kuyruk(os.path.join(klasor, "islem.log")):
        if s[20:26] == "[err] " and s[:19] >= sinir:
            out.append({"zaman": s[:19], "mesaj": s[26:].strip()})
    return out[::-1]


def son_islem(klasor):
    """Kayıttaki son satırın zamanı (YYYY-AA-GG SS:DD:ss) ya da None."""
    for s in reversed(_kuyruk(os.path.join(klasor, "islem.log"), 4096)):
        if len(s) > 19 and s[4] == "-" and s[13] == ":":
            return s[:19]
    return None
