"""Günlük yedek (yedek.py): çalışan veritabanının tutarlı kopyası, anahtarın yedeğe girmemesi, eski yedeklerin silinmesi."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yedek as YD  # noqa: E402


class Yedek(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-yedek-")
        self.data = os.path.join(self.tmp, "data")
        m = os.path.join(self.data, "magazalar", "a-com")
        os.makedirs(m)
        for ad, icerik in (("anahtar.key", "GIZLI"), ("sunucu.json", "{}"), ("magazalar/a-com/ayarlar.json", '{"store": "a.com"}'),
                           ("magazalar/a-com/islem.log", "kayıt")):
            with open(os.path.join(self.data, ad), "w", encoding="utf-8") as f:
                f.write(icerik)
        self.db = sqlite3.connect(os.path.join(m, "durum.db"))         # açık kalır: çalışan uygulama gibi
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE seo(pid INTEGER)")
        self.db.executemany("INSERT INTO seo VALUES(?)", [(i,) for i in range(500)])
        self.db.commit()
        self.hedef = os.path.join(self.tmp, "yedekler")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_yedek_icerigi(self):
        yol = YD.yedekle(self.data, self.hedef)
        with zipfile.ZipFile(yol) as z:
            adlar = set(z.namelist())
            self.assertEqual(adlar, {"sunucu.json", "magazalar/a-com/ayarlar.json", "magazalar/a-com/islem.log",
                                     "magazalar/a-com/durum.db"})
            z.extract("magazalar/a-com/durum.db", self.tmp)
        kopya = sqlite3.connect(os.path.join(self.tmp, "magazalar", "a-com", "durum.db"))
        self.assertEqual(kopya.execute("SELECT COUNT(*) FROM seo").fetchone()[0], 500)
        kopya.close()

    def test_anahtar_yedege_girmez(self):
        with zipfile.ZipFile(YD.yedekle(self.data, self.hedef)) as z:
            self.assertFalse(any("anahtar" in n for n in z.namelist()))
            self.assertFalse(any(b"GIZLI" in z.read(n) for n in z.namelist()))

    def test_eski_yedekler_silinir(self):
        os.makedirs(self.hedef)
        for i in range(5):
            open(os.path.join(self.hedef, f"seovisi-2026010{i}-000000.zip"), "w").close()
        YD.yedekle(self.data, self.hedef, sakla=3)
        kalan = sorted(os.listdir(self.hedef))
        self.assertEqual(len(kalan), 3)
        self.assertNotIn("seovisi-20260100-000000.zip", kalan)


if __name__ == "__main__":
    unittest.main()
