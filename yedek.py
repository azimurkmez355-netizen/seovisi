# -*- coding: utf-8 -*-
"""Günlük yedek: data klasörünün tutarlı bir kopyası zip olarak. Yalnızca standart kütüphane.

- SQLite veritabanları (durum.db) çalışırken de tutarlı kopyalanır (sqlite3 yedekleme arayüzü; WAL dosyaları ayrıca alınmaz).
- Şifre anahtarı (anahtar.key) yedeğe GİRMEZ: yedekteki erişim anahtarları şifreli kalır, anahtar ayrı saklanmalıdır.
- En yeni `sakla` yedek tutulur, eskiler silinir.
"""
import os
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime

ALINMAZ = {"anahtar.key"}
ATLANAN_EKLER = (".db-wal", ".db-shm", ".tmp")


def yedekle(data, hedef, sakla=14):
    """data klasörünü hedef klasöre seovisi-YYYYMMDD-HHMMSS.zip olarak yedekler. Dönüş: yedek dosyasının yolu."""
    os.makedirs(hedef, exist_ok=True)
    ad = os.path.join(hedef, f"seovisi-{datetime.now():%Y%m%d-%H%M%S}.zip")
    gecici = ad + ".yaziliyor"
    with zipfile.ZipFile(gecici, "w", zipfile.ZIP_DEFLATED) as z:
        for kok, _, dosyalar in os.walk(data):
            for f in sorted(dosyalar):
                yol = os.path.join(kok, f)
                ic = os.path.relpath(yol, data).replace(os.sep, "/")
                if f in ALINMAZ or f.endswith(ATLANAN_EKLER):
                    continue
                if f.endswith(".db"):
                    fd, kopya = tempfile.mkstemp(suffix=".db")
                    os.close(fd)
                    try:
                        kaynak, hedef_db = sqlite3.connect(yol), sqlite3.connect(kopya)
                        with hedef_db:
                            kaynak.backup(hedef_db)
                        kaynak.close()
                        hedef_db.close()
                        z.write(kopya, ic)
                    finally:
                        os.remove(kopya)
                else:
                    z.write(yol, ic)
    os.replace(gecici, ad)
    eskiler = sorted(f for f in os.listdir(hedef) if f.startswith("seovisi-") and f.endswith(".zip"))
    for f in eskiler[:-sakla] if sakla else []:
        os.remove(os.path.join(hedef, f))
    return ad


def dongu(data, hedef, saat=3, sakla=14):
    """Her gün belirtilen saatte (sunucu saatiyle) yedek alır; Docker'daki yedek kabı bunu çalıştırır."""
    son = None
    while True:
        simdi = datetime.now()
        if simdi.hour == saat and son != simdi.date():
            try:
                print(f"Yedek alındı: {yedekle(data, hedef, sakla)}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"Yedek alınamadı: {e}", flush=True)
            son = simdi.date()
        time.sleep(60)
