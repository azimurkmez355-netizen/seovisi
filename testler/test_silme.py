"""Uygulama kaldırılınca veri silme: anahtar reddi → "kaldırıldı", yeniden bağlanınca iptal, süre dolunca klasörün silinmesi.
Geçici klasörde çalışır; projenin data klasörüne dokunmaz."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seo_text as ST  # noqa: E402

_pf = ST.panel_factor
import app  # noqa: E402
import sifre  # noqa: E402

ST.panel_factor = _pf


def oku(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Silme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-silme-")
        self.eski = (app.STORES, app.DATA, app.SRV, app.SERVER["on"], app.token_request)
        app.DATA = self.tmp
        app.STORES = os.path.join(self.tmp, "magazalar")
        os.makedirs(app.STORES)
        sifre.KEY_PATH = os.path.join(self.tmp, "anahtar.key")
        sifre.reset()
        app.SRV = app.Config(os.path.join(self.tmp, "sunucu.json"), app.SERVER_DEFAULT)
        app.SERVER["on"] = True
        self.cevap = None
        app.token_request = self._token

    def tearDown(self):
        app._cur.t = None
        with app._tenants_lock:
            for t in app._tenants.values():
                t.dbi.c.close()
            app._tenants.clear()
        app.STORES, app.DATA, app.SRV, app.SERVER["on"], app.token_request = self.eski
        sifre.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _token(self, host, data):
        if isinstance(self.cevap, Exception):
            raise self.cevap
        return {"access_token": "yeni", "refresh_token": "r2", "expires_in": 3600}

    def magaza(self, tid="a-com"):
        t = app.tenant(tid)
        app._cur.t = t
        app.CFG.update(store=tid.replace("-", "."), access_token="eski", refresh_token="r", expires_at=0)
        app.log("Mağazaya bağlanıldı.", "ok")
        return t

    def test_anahtar_reddi_kaldirildi_isaretler(self):
        self.magaza()
        self.cevap = app.ApiError(400, '{"error":"invalid_grant"}', "token")
        with self.assertRaises(app.ApiError) as c:
            app.API.refresh()
        self.assertEqual(c.exception.status, 401)
        self.assertTrue(app.CFG.get("kaldirildi"))
        self.assertEqual((app.CFG.get("access_token"), app.CFG.get("refresh_token")), ("", ""))
        self.assertIn("silinecek", oku(app.current().path("islem.log")))

    def test_gecici_hata_isaretlemez(self):
        self.magaza()
        for e in (app.ApiError(0, "Ağ hatası", "token"), app.ApiError(503, "bakım", "token")):
            self.cevap = e
            with self.assertRaises(app.ApiError):
                app.API.refresh()
            self.assertFalse(app.CFG.get("kaldirildi"))
            self.assertEqual(app.CFG.get("refresh_token"), "r")

    def test_yerel_kipte_hic_isaretlenmez(self):
        self.magaza()
        app.SERVER["on"] = False
        self.cevap = app.ApiError(401, "reddedildi", "token")
        with self.assertRaises(app.ApiError):
            app.API.refresh()
        self.assertFalse(app.CFG.get("kaldirildi"))

    def test_yeniden_baglaninca_iptal(self):
        self.magaza()
        app.uygulama_kaldirildi("deneme")
        self.assertTrue(app.CFG.get("kaldirildi"))
        app.API.save_token({"access_token": "t", "refresh_token": "r", "expires_in": 3600})
        self.assertFalse(app.CFG.get("kaldirildi"))

    def kaldirilali(self, gun, tid="a-com"):
        t = self.magaza(tid)
        app.uygulama_kaldirildi("deneme")
        app.CFG.update(kaldirildi=(datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d %H:%M"))
        app._cur.t = None
        return t

    def test_sure_dolunca_silinir_dolmadan_silinmez(self):
        self.kaldirilali(31, "a-com")
        self.kaldirilali(29, "b-com")
        self.magaza("c-com")                          # bağlı, hiç dokunulmaz
        app._cur.t = None
        app.silme_turu(simdi=datetime.now())
        self.assertEqual(sorted(os.listdir(app.STORES)), ["b-com", "c-com"])
        self.assertNotIn("a-com", app._tenants)
        kayit = oku(os.path.join(self.tmp, "silme.log"))
        self.assertIn("a-com silindi", kayit)
        self.assertNotIn("b-com", kayit)

    def test_sure_ayardan(self):
        app.SRV.update(silme_gun=60)
        self.kaldirilali(31)
        app.silme_turu(simdi=datetime.now())
        self.assertEqual(os.listdir(app.STORES), ["a-com"])
        self.assertEqual(app.silinecegi_gun("2026-01-01 10:00"), "2026-03-02")

    def test_suren_is_varken_silinmez(self):
        t = self.kaldirilali(40)
        t.seoscan.running = True
        app.silme_turu(simdi=datetime.now())
        self.assertEqual(os.listdir(app.STORES), ["a-com"])
        t.seoscan.running = False
        app.silme_turu(simdi=datetime.now())
        self.assertEqual(os.listdir(app.STORES), [])

    def test_yerel_kipte_silme_turu_calismaz(self):
        self.kaldirilali(40)
        app.SERVER["on"] = False
        app.silme_turu(simdi=datetime.now())
        self.assertEqual(os.listdir(app.STORES), ["a-com"])

    def test_gecersiz_klasor_adi_silinmez(self):
        os.makedirs(os.path.join(self.tmp, "baska"))
        self.assertFalse(app.magaza_sil("../baska", "deneme"))
        self.assertFalse(app.magaza_sil("", "deneme"))
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "baska")))

    def test_saatte_bir_bakar(self):
        self.kaldirilali(40)
        app._SILME["son"] = time.time()
        app.silme_turu()                              # zamanlayıcıdan: bir saat dolmadı
        self.assertEqual(os.listdir(app.STORES), ["a-com"])


if __name__ == "__main__":
    unittest.main()
