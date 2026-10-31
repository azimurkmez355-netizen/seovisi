"""Aylık rapor (rapor.py), olay kaydı, durum fotoğrafı ve haftalık otomatik tarama (app)."""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rapor as RP  # noqa: E402
from testler.test_otopilot import Ortam, app  # noqa: E402


def foto(**kw):
    d = {"taranan": 100, "seo_tamam": 40, "seo_eksik": 60, "kategori_sorun": 10, "gorselsiz": 5, "fiyat_uyari": 3,
         "stok_uyari": 8, "kopya": 2, "kirik": 4}
    d.update(kw)
    return d


class Hesap(unittest.TestCase):
    def test_ay_basi_ve_sonu_karsilastirilir(self):
        an = [("2026-10-20 10:00", foto()), ("2026-11-08 10:00", foto(seo_tamam=70, seo_eksik=30)),
              ("2026-11-29 10:00", foto(seo_tamam=90, seo_eksik=10, kirik=6)), ("2026-12-02 10:00", foto(seo_tamam=99))]
        r = RP.hesapla("2026-11", an, [])
        self.assertEqual((r["once_zaman"], r["sonra_zaman"], r["tarama_sayisi"]), ("2026-10-20 10:00", "2026-11-29 10:00", 2))
        m = {x["k"]: x for x in r["metrikler"]}
        self.assertEqual((m["seo_tamam"]["once"], m["seo_tamam"]["sonra"], m["seo_tamam"]["fark"], m["seo_tamam"]["iyi"]), (40, 90, 50, True))
        self.assertEqual((m["seo_eksik"]["fark"], m["seo_eksik"]["iyi"]), (-50, True))       # azalması iyi
        self.assertEqual((m["kirik"]["fark"], m["kirik"]["iyi"]), (2, False))
        self.assertIsNone(m["kopya"]["iyi"])                                                 # değişmedi
        self.assertEqual(r["seo_yuzde"], [40, 90])
        self.assertEqual(r["ay_adi"], "Kasım 2026")

    def test_onceki_fotograf_yoksa_ayin_ilki(self):
        r = RP.hesapla("2026-11", [("2026-11-03 09:00", foto()), ("2026-11-20 09:00", foto(kopya=0))], [])
        self.assertEqual((r["once_zaman"], r["sonra_zaman"]), ("2026-11-03 09:00", "2026-11-20 09:00"))

    def test_olaylar_yalnizca_o_ay(self):
        ol = [("2026-10-31 23:59", "seo"), ("2026-11-01 00:00", "seo"), ("2026-11-15 12:00", "seo"), ("2026-11-15 12:00", "kategori"),
              ("2026-12-01 00:00", "seo")]
        n = {x["tur"]: x["n"] for x in RP.hesapla("2026-11", [], ol)["olaylar"]}
        self.assertEqual((n["seo"], n["kategori"], n["geri"]), (2, 1, 0))

    def test_aralik_ve_bos(self):
        self.assertEqual(RP.ay_araligi("2026-12"), ("2026-12-01", "2027-01-01"))
        r = RP.hesapla("2026-12", [], [])
        self.assertIsNone(r["sonra_zaman"])
        self.assertEqual(r["seo_yuzde"], [None, None])
        self.assertEqual(RP.aylar(["2026-11-02 10:00", "2026-10-05 10:00", "2026-11-30 10:00", ""]), ["2026-11", "2026-10"])


class Kayit(Ortam):
    def test_yapilanlar_olay_olarak_kaydedilir(self):
        app.DBI.x("INSERT INTO seo(pid, sku, name) VALUES(1, 'HR-1', ?)", (self.m.urunler[1]["name"],))
        app.prepare_plan(1)
        self.assertEqual(app.send_plan(1)[0], "gonderildi")
        self.assertEqual(app.cat_fix(2, [12], [11])[0], "uygulandi")
        self.assertEqual(app.cat_undo(2)[0], "uygulandi")
        self.assertEqual(app.seo_geri_al(1)[0], "uygulandi")
        turler = [r["tur"] for r in app.DBI.q("SELECT tur FROM olay ORDER BY id")]
        self.assertEqual(turler, ["seo", "kategori", "geri", "geri"])
        r = app.rapor_al()["rapor"]
        n = {x["tur"]: x["n"] for x in r["olaylar"]}
        self.assertEqual((n["seo"], n["kategori"], n["geri"]), (1, 1, 2))

    def test_durum_fotografi(self):
        v = app.anlik_al()
        self.assertEqual(set(v), {"taranan", "seo_tamam", "seo_eksik", "kategori_sorun", "gorselsiz", "fiyat_uyari", "stok_uyari", "kopya", "kirik"})
        r = app.rapor_al()
        self.assertEqual(r["rapor"]["tarama_sayisi"], 1)
        self.assertEqual(r["aylar"][0]["ay"], datetime.now().strftime("%Y-%m"))


class Haftalik(Ortam):
    def setUp(self):
        super().setUp()
        app.LOCAL["id"] = self.t.id
        self._p = mock.patch.dict(app._tenants, {self.t.id: self.t})
        self._p.start()
        for x in (self.t.seoscan, self.t.catscan, self.t.links):
            x.start = mock.Mock(return_value="başladı")

    def tearDown(self):
        self._p.stop()
        super().tearDown()

    def test_haftada_bir_baslar(self):
        app.haftalik_tur()
        for x in (self.t.seoscan, self.t.catscan, self.t.links):
            x.start.assert_called_once()
        app.haftalik_tur()                                             # 7 gün dolmadı
        self.t.seoscan.start.assert_called_once()
        eski = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d %H:%M")
        app.DBI.x("UPDATE kv SET v=? WHERE k='haftalik_son'", (eski,))
        app.haftalik_tur()
        self.assertEqual(self.t.seoscan.start.call_count, 2)

    def test_baska_is_surerken_baslamaz(self):
        self.t.seojobs.running = True
        app.haftalik_tur()
        self.t.seoscan.start.assert_not_called()

    def test_ucretsiz_pakette_ve_baglanti_yokken_baslamaz(self):
        with mock.patch.dict(app.SERVER, {"on": True}), mock.patch.object(app, "_magazalar", return_value=[self.t.id]):
            app.haftalik_tur()                                         # ücretsiz analiz
        self.t.seoscan.start.assert_not_called()
        app.CFG.update(access_token="", refresh_token="")
        app.haftalik_tur()
        self.t.seoscan.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
