"""Abonelik kaydı, paketler ve yazma izni (abonelik.py).

Testler geçici bir paket dosyasıyla çalışır; projenin paketler.json'u değişse de bozulmaz."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import abonelik as AB  # noqa: E402

YAZ = ["seo_gonder", "kategori_duzelt", "kategori_ac", "otopilot"]
PAKETLER = {"paketler": {"ucretsiz": {"ad": "Ücretsiz analiz", "urun": None, "ozellikler": []},
                         "kucuk": {"ad": "Küçük", "urun": 100, "ozellikler": YAZ},
                         "yalniz_seo": {"ad": "Yalnız SEO", "urun": None, "ozellikler": ["seo_gonder"]}},
            "yeni_magaza": {"durum": "ucretsiz", "paket": "kucuk", "gun": 0}}
BUGUN = date(2026, 10, 31)


class Ortam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-abonelik-")
        self.magaza = os.path.join(self.tmp, "magaza-com")
        self._path, AB.PAKET_PATH = AB.PAKET_PATH, os.path.join(self.tmp, "paketler.json")
        self.paket_yaz(PAKETLER)

    def tearDown(self):
        AB.PAKET_PATH = self._path
        AB._cache.update(mtime=None, data=None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def paket_yaz(self, d):
        with open(AB.PAKET_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f)
        t = time.time() + len(json.dumps(d))           # aynı saniyede yazılsa da değişiklik fark edilsin
        os.utime(AB.PAKET_PATH, (t, t))

    def gecerli(self, **kayit):
        return AB.gecerli(kayit, BUGUN)


class YeniMagaza(Ortam):
    def test_varsayilan_ucretsiz_analiz(self):
        k = AB.oku(self.magaza)
        self.assertEqual((k["paket"], k["durum"], k["kaynak"]), ("ucretsiz", "ucretsiz", "otomatik"))
        self.assertTrue(os.path.isfile(os.path.join(self.magaza, AB.FILE)))

    def test_deneme_suresi_ilk_giriste_baslar(self):
        self.paket_yaz(dict(PAKETLER, yeni_magaza={"durum": "deneme", "paket": "kucuk", "gun": 14}))
        k = AB.oku(self.magaza, bugun=BUGUN)
        self.assertEqual((k["paket"], k["durum"], k["bitis"]), ("kucuk", "deneme", "2026-11-14"))
        self.assertEqual(AB.oku(self.magaza, bugun=BUGUN + timedelta(days=5))["bitis"], "2026-11-14")   # yeniden başlamaz

    def test_bozuk_kayit_ucretsiz_sayilir_ve_uzerine_yazilmaz(self):
        os.makedirs(self.magaza)
        with open(os.path.join(self.magaza, AB.FILE), "w", encoding="utf-8") as f:
            f.write("{bozuk")
        self.assertEqual(AB.gecerli(AB.oku(self.magaza))["paket"], "ucretsiz")
        with open(os.path.join(self.magaza, AB.FILE), encoding="utf-8") as f:
            self.assertEqual(f.read(), "{bozuk")


class GecerliPaket(Ortam):
    def test_aktif_abonelik(self):
        a = self.gecerli(paket="kucuk", durum="aktif", bitis="2027-10-31")
        self.assertEqual((a["paket"], a["durum"], a["kalan_gun"], a["urun_siniri"]), ("kucuk", "aktif", 365, 100))
        self.assertEqual(a["ozellikler"], YAZ)

    def test_bitis_gunu_hala_gecerli(self):
        self.assertEqual(self.gecerli(paket="kucuk", durum="aktif", bitis="2026-10-31")["kalan_gun"], 0)

    def test_suresi_dolunca_ucretsize_duser(self):
        a = self.gecerli(paket="kucuk", durum="deneme", bitis="2026-10-30")
        self.assertEqual((a["paket"], a["durum"], a["ozellikler"], a["kayitli_paket"]),
                         ("ucretsiz", "suresi_doldu", [], "kucuk"))

    def test_bitis_tarihsiz_aktif_suresiz(self):
        self.assertEqual(self.gecerli(paket="kucuk", durum="aktif")["paket"], "kucuk")

    def test_iptal_tanınmayan_ve_okunamayan_kayit_ucretsiz(self):
        for k in ({"paket": "kucuk", "durum": "iptal"}, {"paket": "yok", "durum": "aktif"},
                  {"paket": "kucuk", "durum": "bilinmeyen"}, {"paket": "kucuk", "durum": "aktif", "bitis": "31.10.2027"}):
            self.assertEqual(self.gecerli(**k)["ozellikler"], [], k)


class YazmaIzni(Ortam):
    def test_ucretsiz_analizde_yazilamaz(self):
        m = AB.engel(self.gecerli(paket="ucretsiz", durum="ucretsiz"), "seo_gonder")
        self.assertIn("Ücretsiz analiz", m)

    def test_suresi_dolunca_tarih_ve_geri_alma_soylenir(self):
        m = AB.engel(self.gecerli(paket="kucuk", durum="aktif", bitis="2026-10-01"), "kategori_duzelt")
        self.assertIn("01.10.2026", m)
        self.assertIn("geri almaya devam", m)

    def test_iptal(self):
        self.assertIn("iptal", AB.engel(self.gecerli(paket="kucuk", durum="iptal"), "seo_gonder"))

    def test_pakette_olmayan_ozellik(self):
        a = self.gecerli(paket="yalniz_seo", durum="aktif")
        self.assertIsNone(AB.engel(a, "seo_gonder", 5000))
        self.assertEqual(AB.engel(a, "kategori_ac"), "Bu işlem Yalnız SEO paketinde yok.")

    def test_urun_siniri(self):
        a = self.gecerli(paket="kucuk", durum="aktif")
        self.assertIsNone(AB.engel(a, "seo_gonder", 100))
        m = AB.engel(a, "seo_gonder", 1250)
        self.assertIn("1.250 ürün", m)
        self.assertIn("100 ürüne kadar", m)


class PaketOnerisi(Ortam):
    def test_urun_sayisina_yeten_en_kucuk_paket(self):
        d = json.loads(json.dumps(PAKETLER))
        d["paketler"]["buyuk"] = {"ad": "Büyük", "urun": 1000, "ozellikler": YAZ}
        self.paket_yaz(d)
        self.assertEqual(AB.oneri(80), "Küçük")
        self.assertEqual(AB.oneri(100), "Küçük")
        self.assertEqual(AB.oneri(101), "Büyük")
        self.assertEqual(AB.oneri(50000), "Büyük")       # hiçbiri yetmezse en büyüğü
        self.assertIsNone(AB.oneri(0))                   # taranmadı


class KayitYazma(Ortam):
    def test_elle_kayit_ve_islem_kaydi(self):
        AB.yaz(self.magaza, paket="kucuk", bitis="2027-10-31")
        k = AB.oku(self.magaza)
        self.assertEqual((k["paket"], k["durum"], k["bitis"], k["kaynak"]), ("kucuk", "aktif", "2027-10-31", "elle"))
        with open(os.path.join(self.magaza, "islem.log"), encoding="utf-8") as f:
            self.assertIn("Abonelik: Küçük, Aktif, bitiş 2027-10-31 (elle)", f.read())

    def test_iptal_onceki_paketi_korur(self):
        AB.yaz(self.magaza, paket="kucuk", bitis="2027-10-31")
        self.assertEqual(AB.yaz(self.magaza, durum="iptal")["paket"], "kucuk")

    def test_gecersiz_degerler_yazilmaz(self):
        for kw in ({"paket": "yok"}, {"paket": "kucuk", "durum": "belki"}, {"paket": "kucuk", "bitis": "31.10.2027"},
                   {"paket": "ucretsiz", "durum": "aktif"}, {}):
            with self.assertRaises(ValueError, msg=kw):
                AB.yaz(self.magaza, **kw)
        self.assertFalse(os.path.exists(os.path.join(self.magaza, AB.FILE)))


class PaketDosyasi(Ortam):
    def test_degisiklik_yeniden_baslatmadan_okunur(self):
        self.assertEqual(AB.paketler()["paketler"]["kucuk"]["urun"], 100)
        d = json.loads(json.dumps(PAKETLER))
        d["paketler"]["kucuk"]["urun"] = 250
        self.paket_yaz(d)
        self.assertEqual(AB.paketler()["paketler"]["kucuk"]["urun"], 250)

    def test_duzenlerken_bozulursa_son_gecerli_hali_kullanilir(self):
        AB.paketler()
        with open(AB.PAKET_PATH, "w", encoding="utf-8") as f:
            f.write('{"paketler": {"kucuk": ')
        os.utime(AB.PAKET_PATH, (time.time() + 99, time.time() + 99))
        with mock.patch("builtins.print") as p:
            self.assertEqual(AB.paketler()["paketler"]["kucuk"]["urun"], 100)
        p.assert_called_once()

    def test_ucretsiz_paketi_olmayan_dosya_kabul_edilmez(self):
        self.paket_yaz({"paketler": {"kucuk": PAKETLER["paketler"]["kucuk"]}})
        AB._cache.update(mtime=None, data=None)
        with self.assertRaises(ValueError):
            AB.paketler()

    def test_projenin_paket_dosyasi_gecerli(self):
        AB.PAKET_PATH = self._path
        d = AB.paketler()
        self.assertIn(d["yeni_magaza"]["durum"], AB.DURUMLAR)
        for p in d["paketler"].values():
            self.assertFalse(set(p["ozellikler"]) - set(YAZ), p)


if __name__ == "__main__":
    unittest.main()
