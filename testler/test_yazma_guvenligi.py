"""Mağazaya yazma güvenliği (CLAUDE.md: "Bu kurallar hiçbir zaman gevşetilmemeli").

Bellekteki uydurma bir Ideasoft ile: yazmadan önce yeniden okuma, korunan alan (fiyat, stok, ad…) değişirse
ürünün eski hâline yazılması, yedek ve geri alma. Gerçek Ideasoft'a hiç istek gitmez; projenin data klasörüne dokunmaz."""
import copy
import json
import os
import re
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

_app_pf, ST.panel_factor = ST.panel_factor, _pf    # app, katsayıyı mağaza ayarından okur; yalnızca bu testlerde
_KEYDIR = tempfile.mkdtemp(prefix="seovisi-anahtar-")


def setUpModule():
    # şifreleme anahtarı projenin data klasöründe değil, geçici klasörde üretilir
    sifre.KEY_PATH = os.path.join(_KEYDIR, "anahtar.key")
    sifre.reset()


def tearDownModule():
    sifre.reset()
    shutil.rmtree(_KEYDIR, ignore_errors=True)

URUN = {"id": 7, "name": "Bosch Darbeli Matkap 750W", "sku": "HR-7", "barcode": "8690001", "price1": 1499.9,
        "stockAmount": 12, "status": 1, "currency": {"id": 1}, "brand": {"id": 3, "name": "Bosch"},
        "categories": [{"id": 11, "name": "Matkaplar"}], "detail": {"id": 70}, "targetKeyword": "",
        "pageTitle": "", "metaDescription": "", "metaKeywords": "", "updatedAt": "2026-10-01"}
DETAY = {"id": 70, "sku": "HR-7", "details": "<p>Eski açıklama</p>", "product": {"id": 7}}


class SahteIdeasoft:
    """products, product_details ve product_to_categories kaynaklarını bellekte tutar.
    bozuk=True iken ilk PUT products isteği fiyatı da değiştirir (Ideasoft'un beklenmedik davranışı)."""

    def __init__(self):
        self.urun = copy.deepcopy(URUN)
        self.detay = copy.deepcopy(DETAY)
        self.istekler = []
        self.bozuk = False
        self.put_kabul = True

    def call(self, method, path, params=None, body=None, tries=6):
        self.istekler.append((method, path))
        parts = path.strip("/").split("/")
        if method == "GET" and parts == ["products", "7"]:
            return copy.deepcopy(self.urun)
        if method == "GET" and parts == ["products"]:
            return [dict(copy.deepcopy(self.urun), solvedCount=13, seoTotalRuleCount=13)]
        if method == "PUT" and parts == ["products", "7"]:
            if not self.put_kabul:
                raise app.ApiError(400, "kabul edilmedi")
            for k in app.READONLY:
                assert k not in body, f"salt okunur alan gönderildi: {k}"
            self.urun.update(copy.deepcopy(body))
            if self.bozuk:
                self.bozuk = False
                self.urun["price1"] = 0
            return copy.deepcopy(self.urun)
        if method == "GET" and parts == ["product_details", "70"]:
            return copy.deepcopy(self.detay)
        if method == "PUT" and parts == ["product_details", "70"]:
            self.detay.update(copy.deepcopy(body))
            return copy.deepcopy(self.detay)
        if method == "POST" and parts == ["product_to_categories"]:
            self.urun["categories"].append({"id": body["category"]["id"]})
            return {"id": 1}
        raise app.ApiError(404, f"sahte api: {method} {path}")

    def yazmalar(self):
        return [i for i in self.istekler if i[0] != "GET"]


class Ortam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-yazma-")
        self._stores, app.STORES = app.STORES, self.tmp
        self.t = app.Tenant("deneme-com")
        app._cur.t = self.t
        ST.panel_factor = _app_pf
        app.CFG.update(store="deneme.com", kw_loc={"res": "product", "path": "targetKeyword"})
        self.api = SahteIdeasoft()
        self.t.api.call = self.api.call

    def tearDown(self):
        app._cur.t = None
        ST.panel_factor = _pf
        app.STORES = self._stores
        self.t.dbi.c.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def korunanlar(self):
        return {k: self.api.urun.get(k) for k in ("name", "sku", "price1", "stockAmount", "status")}


class KategoriYazma(Ortam):
    def test_kategori_eklenir_diger_alanlar_degismez(self):
        once = self.korunanlar()
        durum, msg, onceki, sonraki = app.apply_categories(7, [12], [])
        self.assertEqual(durum, "uygulandi", msg)
        self.assertEqual(sorted(sonraki), [11, 12])
        self.assertEqual(self.korunanlar(), once)

    def test_fiyat_bozulursa_eski_haline_yazilir(self):
        self.api.bozuk = True
        durum, msg, _, _ = app.apply_categories(7, [12], [11])
        self.assertEqual(durum, "koruma", msg)
        self.assertIn("price1", msg)
        self.assertEqual(self.api.urun["price1"], 1499.9)

    def test_analizden_sonra_degisen_urune_dokunulmaz(self):
        durum, _, _, _ = app.apply_categories(7, [12], [11], expect=[99])
        self.assertEqual(durum, "degisti")
        self.assertEqual(self.api.yazmalar(), [])

    def test_urun_kategorisiz_birakilmaz(self):
        durum, _, _, _ = app.apply_categories(7, [], [11])
        self.assertEqual(durum, "hata")
        self.assertEqual(self.api.yazmalar(), [])

    def test_put_reddedilirse_baglanti_yontemi_denenir(self):
        self.api.put_kabul = False
        durum, msg, _, sonraki = app.apply_categories(7, [12], [])
        self.assertEqual(durum, "uygulandi", msg)
        self.assertIn(("POST", "product_to_categories"), self.api.istekler)
        self.assertEqual(app.CFG.get("cat_write_mode"), "link")

    def test_duzeltme_geri_alinir(self):
        self.assertEqual(app.cat_fix(7, [12], [11])[0], "uygulandi")
        self.api.put_kabul = True
        self.assertEqual(app.cat_undo(7)[0], "uygulandi")
        self.assertEqual([c["id"] for c in self.api.urun["categories"]], [11])
        self.assertEqual(app.cat_undo(7)[0], "hata")     # ikinci kez geri alınacak bir şey yok


class AciklamaGonderme(Ortam):
    def hazirla(self):
        app.DBI.x("INSERT INTO seo(pid, sku, name) VALUES(7, 'HR-7', ?)", (URUN["name"],))
        return app.prepare_plan(7)

    def test_hazirlama_magazaya_yazmaz(self):
        plan = self.hazirla()
        self.assertTrue(plan["details_html"])
        self.assertEqual(self.api.yazmalar(), [])

    def test_gorunum_kurulum_turune_gore(self):
        self.assertIn("1b4f72", self.hazirla()["details_html"])        # bilgisayardaki kurulum: Ustapazar görünümü
        with mock.patch.dict(app.SERVER, {"on": True}):
            sade = app.prepare_plan(7)["details_html"]                   # sunucuda satılan sürüm: sade
        self.assertNotIn("1b4f72", sade)
        self.assertIn(app.TPL.stiller(app.TPL.yukle({}))["h"], sade)

    def test_sablon_hazirlanan_aciklamaya_uygulanir(self):
        app.CFG.update(sablon={"gorunum": "kutulu", "renk": "#c0392b", "madde": "•", "barkod": False,
                               "bolumler": [{"k": "teknik", "baslik": "Ürün Bilgileri"}]})
        h = self.hazirla()["details_html"]
        self.assertIn("border:1px solid #c0392b", h)
        self.assertIn("Ürün Bilgileri", h)
        self.assertNotIn("Barkod", h)
        self.assertNotIn("✔", h)

    def test_gonderim_aciklamayi_yazar_ve_yedek_alir(self):
        plan = self.hazirla()
        once = self.korunanlar()
        durum, msg = app.send_plan(7)
        self.assertEqual(durum, "gonderildi", msg)
        self.assertEqual(self.api.detay["details"], plan["details_html"])
        self.assertEqual(self.api.urun["targetKeyword"], plan["keyword"])
        self.assertEqual(self.korunanlar(), once)
        yedek = json.loads(app.DBI.q("SELECT backup FROM seo WHERE pid=7", one=True)["backup"])
        self.assertEqual(yedek["detail"]["details"], "<p>Eski açıklama</p>")

    def test_fiyat_bozulursa_eski_haline_yazilir_ve_toplu_is_durur(self):
        self.hazirla()
        self.api.bozuk = True
        durum, msg = app.send_plan(7)
        self.assertEqual(durum, "hata")
        self.assertIn("Korunan alan", msg)
        self.assertEqual(self.api.urun["price1"], 1499.9)

    def test_kullanici_duzenlemesi_gonderilir(self):
        self.hazirla()
        app.send_plan(7, {"pageTitle": "Bosch Darbeli Matkap 750W | Deneme"})
        self.assertEqual(self.api.urun["pageTitle"], "Bosch Darbeli Matkap 750W | Deneme")

    def test_hazirlik_yoksa_gonderilmez(self):
        durum, _ = app.send_plan(7)
        self.assertEqual(durum, "hata")
        self.assertEqual(self.api.yazmalar(), [])


class Kurulum(Ortam):
    """Kurulum sihirbazının ihtiyaçları: hedef kelime yerinin varsayılanı, mağaza başına görünüm, sihirbazın kime çıkacağı."""

    def srv(self, **d):
        return mock.patch.object(app, "SRV", mock.Mock(get=lambda k, default=None: d.get(k, default)))

    def test_hedef_kelime_yeri_sunucu_varsayilanindan(self):
        app.CFG.update(kw_loc={})
        with self.srv(kw_loc={"res": "seo_settings", "path": "keyword"}):
            self.assertEqual(app.kw_loc(), {"res": "seo_settings", "path": "keyword"})
            app.CFG.update(kw_loc={"res": "product", "path": "targetKeyword"})       # mağazanın kendi keşfi önce gelir
            self.assertEqual(app.kw_loc()["res"], "product")
        with self.srv(kw_loc={"res": "bilinmeyen", "path": "x"}):
            app.CFG.update(kw_loc={})
            self.assertEqual(app.kw_loc(), {})                                         # bozuk varsayılan kullanılmaz

    def test_varsayilan_yerle_gonderim_calisir(self):
        app.CFG.update(kw_loc={})
        with self.srv(kw_loc={"res": "product", "path": "targetKeyword"}):
            app.DBI.x("INSERT INTO seo(pid, sku, name) VALUES(7, 'HR-7', ?)", (URUN["name"],))
            plan = app.prepare_plan(7)
            self.assertEqual(app.send_plan(7)[0], "gonderildi")
        self.assertEqual(self.api.urun["targetKeyword"], plan["keyword"])

    def test_sablon_varsayilani_kurulum_turune_gore(self):
        self.assertEqual(app.sablon()["gorunum"], "bantli")                   # bilgisayar kurulumu (Ustapazar)
        with mock.patch.dict(app.SERVER, {"on": True}):
            self.assertEqual(app.sablon()["gorunum"], "sade")                 # sunucu
            app.CFG.update(sablon={"gorunum": "cizgili"})
            self.assertEqual(app.sablon()["gorunum"], "cizgili")              # mağazanın seçimi

    def test_onizleme_seo_puani_ve_tum_bolumler(self):
        o = app.sablon_onizleme(app.TPL.yukle({"gorunum": "bantli"}))
        self.assertEqual(o["puan"], 100, o["eksikler"])
        self.assertTrue(2.0 <= o["yogunluk"] <= 3.0, o["yogunluk"])
        for b in ("Öne Çıkan Özellikler", "Teknik Özellikler", "Kullanım Alanları", "Paket İçeriği"):
            self.assertIn(b, o["html"])

    def test_tema_rengi_ic_aga_istek_gondermez(self):
        app.CFG.update(store="magaza.com")
        with mock.patch.object(app, "public_host", return_value=False), \
                mock.patch.object(app.urllib.request.OpenerDirector, "open") as op:
            self.assertIsNone(app.tema_rengi_oner())
        op.assert_not_called()
        h = app._PublicRedirects()
        with mock.patch.object(app, "public_host", return_value=False):
            with self.assertRaises(app.urllib.error.URLError):
                h.redirect_request(None, None, 302, "", {}, "http://169.254.169.254/")

    def test_sihirbaz_yalnizca_yeni_magazaya(self):
        self.assertFalse(app.kurulum_gerekli())                                 # bilgisayar kurulumunda yok
        with mock.patch.dict(app.SERVER, {"on": True}):
            self.assertTrue(app.kurulum_gerekli())                              # yeni, taranmamış mağaza
            app.DBI.x("INSERT INTO seo(pid, sku, name) VALUES(7, 'HR-7', 'x')")
            self.assertTrue(app.kurulum_gerekli())                              # sihirbaz sırasında tarandı: sürer
            app.CFG.update(kurulum_bitti=None)                                  # bu ayardan önce kurulmuş, taranmış mağaza
            self.assertFalse(app.kurulum_gerekli())
            self.assertIs(app.CFG.get("kurulum_bitti"), True)


class Oturum(unittest.TestCase):
    def setUp(self):
        self._srv = app.SRV
        app.SRV = app.Config(os.path.join(tempfile.mkdtemp(prefix="seovisi-oturum-"), "sunucu.json"),
                             app.SERVER_DEFAULT)
        app.SRV.update(secret="test-anahtari")

    def tearDown(self):
        shutil.rmtree(os.path.dirname(app.SRV.path), ignore_errors=True)
        app.SRV = self._srv

    def test_cerez_imzali_ve_suresi_var(self):
        c = app.session_cookie("deneme-com")
        self.assertRegex(c, r"^sv=deneme-com\.\d+\.[0-9a-f]{64}; Path=/; HttpOnly")

    def test_https_cerezi_cercevede_calisir(self):
        app.SRV.update(public_url="https://app.seovisi.com.tr")
        c, f = app.session_cookie("deneme-com"), app.session_cookie("deneme-com", framed=True)
        self.assertIn("SameSite=None; Secure", c)
        self.assertNotIn("Partitioned", c)
        self.assertIn("SameSite=None; Secure; Partitioned", f)
        self.assertEqual([("Partitioned" in x, "Max-Age=0" in x) for x in app.clear_cookies()], [(False, True), (True, True)])
        app.SRV.update(public_url="http://localhost:8770")
        self.assertIn("SameSite=Lax", app.session_cookie("deneme-com"))
        self.assertNotIn("Secure", app.session_cookie("deneme-com"))

    def test_ideasoft_acilis_bilgisine_henuz_guvenilmez(self):
        self.assertIsNone(app.ideasoft_launch({"store": "magaza.com", "sig": "x", "shop": "magaza.com"}))

    def test_klasor_adi_temiz(self):
        self.assertEqual(app.tenant_id(app.store_host("https://Magaza.MyIdeasoft.com/")), "magaza-myideasoft-com")
        self.assertEqual(app.tenant_id("mağaza.com"), "ma-aza-com")
        self.assertFalse(app.known_tenant("../../data"))
        self.assertFalse(app.known_tenant(""))

    def test_ic_ag_adresi_kabul_edilmez(self):
        for h in ("localhost", "127.0.0.1", "10.0.0.5", "metadata.google.internal", ""):
            self.assertFalse(app.public_host(h), h)

    def test_cerceve_adresleri_baslik_icine_kod_sokamaz(self):
        app.SRV.update(frame_hosts=["panel.ornek.com", "kotu.com; script-src *", "https://x.com\r\nSet-Cookie: a=b"])
        fa = app.frame_ancestors("magaza.com")
        self.assertEqual(fa, "'self' https://magaza.com https://*.myideasoft.com https://*.ideasoft.com.tr "
                             "https://panel.ornek.com")
        self.assertEqual(app.frame_ancestors("kotu.com; script-src *"),
                         "'self' https://*.myideasoft.com https://*.ideasoft.com.tr https://panel.ornek.com")

    def test_guvenilir_vekil(self):
        self.assertTrue(app.guvenilir_vekil("127.0.0.1"))
        self.assertFalse(app.guvenilir_vekil("172.18.0.5"))                       # ayar yokken Docker ağı güvenilmez
        with mock.patch.dict(os.environ, {"SEOVISI_VEKIL": "172.16.0.0/12, 10.1.0.0/16"}):
            self.assertTrue(app.guvenilir_vekil("172.18.0.5"))
            self.assertTrue(app.guvenilir_vekil("10.1.2.3"))
            self.assertFalse(app.guvenilir_vekil("203.0.113.9"))                  # internetten gelen başlığa güvenilmez
            self.assertFalse(app.guvenilir_vekil("bozuk"))

    def test_deneme_siniri(self):
        rl = app.RateLimit(3, 60)
        self.assertEqual([rl.hit("1.1.1.1") for _ in range(3)], [0, 0, 0])
        self.assertGreater(rl.hit("1.1.1.1"), 0)
        self.assertEqual(rl.hit("2.2.2.2"), 0)
        rl.hits["1.1.1.1"] = app.deque(t - 61 for t in rl.hits["1.1.1.1"])   # süre doldu
        self.assertEqual(rl.hit("1.1.1.1"), 0)

    def test_magaza_adresi_temizlenir(self):
        self.assertEqual(app.store_host("https://A-Magaza.com/panel/"), "a-magaza.com")


if __name__ == "__main__":
    unittest.main()
