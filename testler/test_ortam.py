"""Railway gibi barındırma yerleri için ortam değişkenleri: sunucu ayarları, yönetici parolası, müşteri adresi başlığı.
Geçici klasörde çalışır; projenin data klasörüne dokunmaz."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seo_text as ST  # noqa: E402

_pf = ST.panel_factor
import app  # noqa: E402
import sifre  # noqa: E402
import yonetim as YN  # noqa: E402

ST.panel_factor = _pf


class Ayarlar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-ortam-")
        self.eski = (app.DATA, app.SRV)
        app.DATA = self.tmp
        sifre.KEY_PATH = os.path.join(self.tmp, "anahtar.key")
        sifre.reset()
        self.yol = os.path.join(self.tmp, "sunucu.json")
        app.SRV = app.Config(self.yol, app.SERVER_DEFAULT)

    def tearDown(self):
        app.DATA, app.SRV = self.eski
        sifre.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dolu_degiskenler_yazilir_gizli_olan_sifreli(self):
        app.SRV.update(client_id="eski", public_url="https://eski.com")
        env = {"SEOVISI_CLIENT_ID": " cid ", "SEOVISI_CLIENT_SECRET": "gizli-deger",
               "SEOVISI_PUBLIC_URL": "", "PATH": "x"}
        self.assertEqual(app.ortamdan_ayarla(env), ["client_id", "client_secret"])
        self.assertEqual((app.SRV.get("client_id"), app.SRV.get("client_secret"), app.SRV.get("public_url")),
                         ("cid", "gizli-deger", "https://eski.com"))        # boş değişken dosyadakini silmez
        with open(self.yol, encoding="utf-8") as f:
            disk = f.read()
        self.assertNotIn("gizli-deger", disk)
        self.assertTrue(json.loads(disk)["client_secret"].startswith("sifreli:v1:"))
        self.assertEqual(app.ortamdan_ayarla(env), [])                       # aynı değer yeniden yazılmaz

    def test_yonetici_parolasi(self):
        app.ortamdan_ayarla({"SEOVISI_YONETICI_PAROLA": "uzun-bir-parola"})
        k = YN.oku(self.tmp)
        self.assertTrue(YN.dogru("uzun-bir-parola", k))
        app.ortamdan_ayarla({"SEOVISI_YONETICI_PAROLA": "uzun-bir-parola"})
        self.assertEqual(YN.oku(self.tmp), k)                                 # aynı parola: oturumlar kapanmaz
        app.ortamdan_ayarla({"SEOVISI_YONETICI_PAROLA": "kisa"})              # kısa parola yazılmaz, eskisi kalır
        self.assertEqual(YN.oku(self.tmp), k)
        app.ortamdan_ayarla({})
        self.assertEqual(YN.oku(self.tmp), k)

    def test_giris_sayfasi_eksik_degiskenleri_yazar(self):
        app.ortamdan_ayarla({"SEOVISI_PUBLIC_URL": "https://ornek.up.railway.app"})
        s = app.login_page()
        self.assertIn("SEOVISI_CLIENT_ID, SEOVISI_CLIENT_SECRET.", s)
        self.assertNotIn("SEOVISI_PUBLIC_URL", s)
        app.ortamdan_ayarla({"SEOVISI_CLIENT_ID": "c", "SEOVISI_CLIENT_SECRET": "s"})
        self.assertNotIn("eksik", app.login_page())


class Istek:
    def __init__(self, ip, basliklar):
        self.client_address, self.headers = (ip, 0), basliklar


class MusteriAdresi(unittest.TestCase):
    def ip(self, ip, basliklar):
        return app.H.client_ip(Istek(ip, basliklar))

    def test_varsayilan_x_forwarded_for(self):
        b = {"X-Forwarded-For": "1.1.1.1, 203.0.113.7", "X-Real-IP": "9.9.9.9"}
        self.assertEqual(self.ip("127.0.0.1", b), "203.0.113.7")
        self.assertEqual(self.ip("198.51.100.1", b), "198.51.100.1")         # güvenilmeyen kaynağın başlığı yok sayılır

    def test_railway_x_real_ip(self):
        with mock.patch.dict(os.environ, {"SEOVISI_IP_BASLIGI": "X-Real-IP", "SEOVISI_VEKIL": "0.0.0.0/0,::/0"}):
            self.assertEqual(self.ip("100.64.0.3", {"X-Real-IP": "203.0.113.7", "X-Forwarded-For": "1.1.1.1"}),
                             "203.0.113.7")
            self.assertEqual(self.ip("100.64.0.3", {"X-Real-IP": "bozuk"}), "100.64.0.3")
            self.assertEqual(self.ip("100.64.0.3", {}), "100.64.0.3")


if __name__ == "__main__":
    unittest.main()
