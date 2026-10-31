"""Diskteki gizli bilgilerin şifrelenmesi (sifre.py) ve ayar dosyalarına uygulanması (app.Config).

Anahtar geçici bir klasörde üretilir; projenin data klasörüne dokunulmaz."""
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

ST.panel_factor = _pf


class Ortam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-sifre-")
        self.key = os.path.join(self.tmp, "anahtar.key")
        self._env = mock.patch.dict(os.environ, {sifre.ENV: ""})
        self._env.start()
        sifre.KEY_PATH = self.key
        sifre.reset()

    def tearDown(self):
        self._env.stop()
        sifre.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def yeni_anahtar(self):
        os.remove(self.key)
        sifre.reset()


class Sifreleme(Ortam):
    def test_gidip_gelir(self):
        for t in ("tok-abc123", "Şifre: çğıöşü İ €", "x" * 5000, ""):
            self.assertEqual(sifre.decrypt(sifre.encrypt(t)), t)

    def test_sifreli_metinde_duz_metin_gorunmez(self):
        v = sifre.encrypt("gizli-erisim-anahtari")
        self.assertTrue(v.startswith(sifre.PREFIX))
        self.assertNotIn("gizli", v)

    def test_ayni_metin_her_seferinde_farkli_sifrelenir(self):
        self.assertNotEqual(sifre.encrypt("aynı"), sifre.encrypt("aynı"))

    def test_degistirilmis_deger_acilmaz(self):
        v = sifre.encrypt("tok-abc123")
        body = v[len(sifre.PREFIX):]
        bozuk = sifre.PREFIX + body[:-6] + ("A" if body[-6] != "A" else "B") + body[-5:]
        for x in (bozuk, sifre.PREFIX + "kısa", sifre.PREFIX + "!!!", "duz-metin"):
            with self.assertRaises(sifre.SifreHatasi):
                sifre.decrypt(x)

    def test_baska_anahtarla_acilmaz(self):
        v = sifre.encrypt("tok-abc123")
        self.yeni_anahtar()
        with self.assertRaises(sifre.SifreHatasi):
            sifre.decrypt(v)

    def test_anahtar_dosyasi_bir_kez_uretilir(self):
        def oku():
            with open(self.key, "rb") as f:
                return f.read()
        v = sifre.encrypt("tok")
        once = oku()
        sifre.reset()
        self.assertEqual(sifre.decrypt(v), "tok")
        self.assertEqual(oku(), once)

    def test_ortam_degiskeni_once_gelir(self):
        with mock.patch.dict(os.environ, {sifre.ENV: "sunucu-anahtari"}):
            sifre.reset()
            v = sifre.encrypt("tok")
        self.assertFalse(os.path.exists(self.key))
        sifre.reset()
        with self.assertRaises(sifre.SifreHatasi):
            sifre.decrypt(v)                     # dosya anahtarıyla açılmaz
        with mock.patch.dict(os.environ, {sifre.ENV: "sunucu-anahtari"}):
            sifre.reset()
            self.assertEqual(sifre.decrypt(v), "tok")


class AyarDosyasi(Ortam):
    def dosya(self):
        with open(os.path.join(self.tmp, "ayarlar.json"), encoding="utf-8") as f:
            return f.read()

    def yaz(self, d):
        with open(os.path.join(self.tmp, "ayarlar.json"), "w", encoding="utf-8") as f:
            json.dump(d, f)

    def ayar(self):
        return app.Config(os.path.join(self.tmp, "ayarlar.json"))

    def test_anahtarlar_diskte_sifreli_programda_duz(self):
        c = self.ayar()
        c.update(access_token="tok-gizli-1", refresh_token="ref-gizli-2", client_secret="sec-gizli-3", store="a.com")
        disk = self.dosya()
        for s in ("tok-gizli-1", "ref-gizli-2", "sec-gizli-3"):
            self.assertNotIn(s, disk)
        self.assertIn('"store": "a.com"', disk)       # gizli olmayan ayarlar okunabilir kalır
        c2 = self.ayar()
        self.assertEqual((c2.get("access_token"), c2.get("refresh_token"), c2.get("client_secret")),
                         ("tok-gizli-1", "ref-gizli-2", "sec-gizli-3"))

    def test_eski_duz_metin_dosya_ilk_acilista_sifrelenir(self):
        self.yaz({"store": "a.com", "access_token": "tok-eski", "refresh_token": "ref-eski", "expires_at": 5})
        c = self.ayar()
        self.assertEqual(c.get("access_token"), "tok-eski")
        self.assertNotIn("tok-eski", self.dosya())
        self.assertNotIn("ref-eski", self.dosya())

    def test_bos_anahtar_bos_kalir(self):
        self.ayar().update(access_token="")
        self.assertEqual(json.loads(self.dosya())["access_token"], "")

    def test_acilamayan_deger_silinmez(self):
        self.ayar().update(access_token="tok-1", refresh_token="ref-1")
        self.yeni_anahtar()
        with mock.patch("builtins.print"):
            c = self.ayar()
        self.assertEqual(c.get("access_token"), "")    # program bağlantı yok sanar, çökmez
        self.assertFalse(c.public()["connected"])
        c.update(store="b.com")                         # başka bir ayarın kaydı şifreli değeri silmemeli
        d = json.loads(self.dosya())
        self.assertTrue(sifre.is_encrypted(d["access_token"]) and sifre.is_encrypted(d["refresh_token"]))
        c.update(access_token="tok-yeni")               # yeniden bağlanınca yenisi yazılır
        with mock.patch("builtins.print"):              # refresh_token hâlâ eski anahtarla şifreli
            self.assertEqual(self.ayar().get("access_token"), "tok-yeni")

    def test_panele_giden_ayarlarda_anahtar_yok(self):
        c = self.ayar()
        c.update(access_token="tok", refresh_token="ref", client_secret="sec")
        p = c.public()
        self.assertFalse({"access_token", "refresh_token", "client_secret"} & set(p))
        self.assertTrue(p["connected"] and p["has_secret"])

    def test_sunucu_oturum_anahtari_da_sifrelenir(self):
        s = app.Config(os.path.join(self.tmp, "sunucu.json"), app.SERVER_DEFAULT)
        s.update(secret="oturum-anahtari", client_secret="ortak-sec")
        with open(os.path.join(self.tmp, "sunucu.json"), encoding="utf-8") as f:
            disk = f.read()
        self.assertNotIn("oturum-anahtari", disk)
        self.assertNotIn("ortak-sec", disk)


if __name__ == "__main__":
    unittest.main()
