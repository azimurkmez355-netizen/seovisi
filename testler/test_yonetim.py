"""Yönetici paneli yardımcıları (yonetim.py): parola karması, oturum çerezi, kayıtlardaki hatalar."""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yonetim as YN  # noqa: E402


class Parola(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="seovisi-yonetim-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_karma_dogrulanir_ve_tuzludur(self):
        k = YN.karma("cok-gizli-parola", tur=1000)
        self.assertTrue(YN.dogru("cok-gizli-parola", k))
        self.assertFalse(YN.dogru("cok-gizli-parolA", k))
        self.assertNotEqual(k, YN.karma("cok-gizli-parola", tur=1000))
        self.assertNotIn("cok-gizli-parola", k)

    def test_bozuk_karma_kabul_edilmez(self):
        for k in ("", "duz-metin", "md5$1$a$b", "pbkdf2_sha256$x$a$b", None):
            self.assertFalse(YN.dogru("x", k))

    def test_parola_dosyasi(self):
        self.assertEqual(YN.oku(self.d), "")                  # belirlenmemiş: giriş kapalı
        with self.assertRaises(ValueError):
            YN.yaz(self.d, "kisa")
        YN.yaz(self.d, "uzun-bir-parola")
        self.assertTrue(YN.dogru("uzun-bir-parola", YN.oku(self.d)))
        with open(os.path.join(self.d, YN.FILE), "w", encoding="utf-8") as f:
            f.write("{bozuk")
        self.assertEqual(YN.oku(self.d), "")


class Cerez(unittest.TestCase):
    def test_gecerli_suresi_dolan_ve_parola_degisen(self):
        k = YN.karma("parola-bir-iki", tur=1000)
        c = YN.cerez("sir", k, simdi=1000)
        self.assertTrue(YN.cerez_gecerli("sir", k, c, simdi=1001))
        self.assertFalse(YN.cerez_gecerli("sir", k, c, simdi=1000 + YN.OTURUM_SAAT * 3600 + 1))
        self.assertFalse(YN.cerez_gecerli("baska", k, c, simdi=1001))
        self.assertFalse(YN.cerez_gecerli("sir", YN.karma("parola-uc-dort", tur=1000), c, simdi=1001))
        self.assertFalse(YN.cerez_gecerli("sir", "", c, simdi=1001))
        bitis, imza = c.split(".")
        self.assertFalse(YN.cerez_gecerli("sir", k, f"{int(bitis) + 9999}.{imza}", simdi=1001))
        self.assertFalse(YN.cerez_gecerli("sir", k, "", simdi=1001))


class Hatalar(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="seovisi-yonetim-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def yaz(self, satirlar):
        with open(os.path.join(self.d, "islem.log"), "w", encoding="utf-8") as f:
            f.write("".join(s + "\n" for s in satirlar))

    def test_son_gunlerin_hatalari_yeniden_eskiye(self):
        simdi = datetime(2026, 11, 1, 12, 0)
        z = lambda g: (simdi - timedelta(days=g)).strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
        self.yaz([f"{z(10)} [err] eski", f"{z(3)} [err] birinci", f"{z(2)} [info] bilgi", f"{z(1)} [warn] uyarı",
                  f"{z(0)} [err] ikinci [err] içinde", "bozuk satır"])
        self.assertEqual([h["mesaj"] for h in YN.hatalar(self.d, 7, simdi)], ["ikinci [err] içinde", "birinci"])
        self.assertEqual(YN.hatalar(self.d, 7, simdi)[0]["zaman"], z(0))
        self.assertEqual(YN.son_islem(self.d), z(0))

    def test_kayit_yoksa_bos(self):
        self.assertEqual(YN.hatalar(self.d), [])
        self.assertIsNone(YN.son_islem(self.d))

    def test_buyuk_kayitta_yalnizca_son_kisim(self):
        simdi = datetime.now()
        s = f"{simdi:%Y-%m-%d %H:%M:%S} [err] " + "x" * 200
        self.yaz([s] * 3000)                               # ~700 KB; yarım ilk satır hata sayılmaz
        h = YN.hatalar(self.d)
        self.assertTrue(0 < len(h) < 3000)
        self.assertTrue(all(x["mesaj"] == "x" * 200 for x in h))


if __name__ == "__main__":
    unittest.main()
