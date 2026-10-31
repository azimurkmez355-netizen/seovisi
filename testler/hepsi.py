"""Bütün testleri çalıştırır: birim testleri (test_*.py) ve çok mağaza testi (sahte Ideasoft ile uygulamanın kendisi).

Çalıştırma: python -X utf8 testler/hepsi.py            hepsi
            python -X utf8 testler/hepsi.py --hizli    yalnızca birim testleri (commit öncesi kontrol)
Bir test bile kalırsa çıkış kodu 1 olur (GitHub'daki otomatik kontrol buna bakar)."""
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
UYGULAMA_TESTI = "test_cok_magaza.py"      # kendi başına çalışan betik; unittest ile yüklenmez


def birim():
    sys.path.insert(0, SRC)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for f in sorted(os.listdir(HERE)):
        if f.startswith("test_") and f.endswith(".py") and f != UYGULAMA_TESTI:
            suite.addTests(loader.loadTestsFromName(f"testler.{f[:-3]}"))
    return unittest.TextTestRunner(verbosity=1, buffer=True).run(suite).wasSuccessful()


def uygulama():
    print(f"\n{UYGULAMA_TESTI}", flush=True)
    return subprocess.call([sys.executable, "-X", "utf8", os.path.join(HERE, UYGULAMA_TESTI)], cwd=SRC) == 0


if __name__ == "__main__":
    os.chdir(SRC)
    t0 = time.time()
    sonuc = {"birim testleri": birim()}
    if "--hizli" not in sys.argv:
        sonuc["çok mağaza testi"] = uygulama()
    print(f"\n{'=' * 40}  ({time.time() - t0:.0f} sn)")
    for ad, ok in sonuc.items():
        print(f"  {'✓' if ok else '✗'} {ad}")
    sys.exit(0 if all(sonuc.values()) else 1)
