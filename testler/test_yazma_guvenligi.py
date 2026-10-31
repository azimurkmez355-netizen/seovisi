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

    def test_klasor_adi_temiz(self):
        self.assertEqual(app.tenant_id(app.store_host("https://Magaza.MyIdeasoft.com/")), "magaza-myideasoft-com")
        self.assertEqual(app.tenant_id("mağaza.com"), "ma-aza-com")
        self.assertFalse(app.known_tenant("../../data"))
        self.assertFalse(app.known_tenant(""))

    def test_ic_ag_adresi_kabul_edilmez(self):
        for h in ("localhost", "127.0.0.1", "10.0.0.5", "metadata.google.internal", ""):
            self.assertFalse(app.public_host(h), h)

    def test_magaza_adresi_temizlenir(self):
        self.assertEqual(app.store_host("https://A-Magaza.com/panel/"), "a-magaza.com")


if __name__ == "__main__":
    unittest.main()
