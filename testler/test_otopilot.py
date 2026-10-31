"""Yeni ürün otopilotu: yalnızca açıldıktan sonra eklenen ürünler, bekleme kuralı, hazırlık, onay, otomatik gönderim,
paket izni ve yazma güvenliği. Bellekteki uydurma bir hırdavat mağazasıyla; gerçek Ideasoft'a istek gitmez."""
import copy
import json
import os
import random
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seo_text as ST  # noqa: E402

_pf = ST.panel_factor
import app  # noqa: E402
import sifre  # noqa: E402

_app_pf, ST.panel_factor = ST.panel_factor, _pf

KATEGORILER = {1: ("Elektrikli El Aletleri", None), 2: ("El Aletleri", None), 11: ("Matkaplar", 1),
               12: ("Vidalama Makineleri", 1), 13: ("Taşlama Makineleri", 1), 21: ("Pense ve Kerpetenler", 2),
               22: ("Tornavidalar", 2)}
MARKALAR = ["Bosch", "Makita", "Dewalt", "Einhell", "Stanley"]
ADLAR = {11: ["Darbeli Matkap 750W", "Kırıcı Delici Matkap", "Sds Plus Matkap 800W"],
         12: ["Akülü Vidalama 12V", "Şarjlı Vidalama 18V", "Darbeli Somun Sıkma"],
         13: ["Avuç Taşlama 125mm", "Büyük Taşlama 230mm", "Spiral Taşlama 115mm"],
         21: ["Kombine Pense", "Yan Keski", "Kargaburun Pense"],
         22: ["Düz Tornavida Seti", "Yıldız Tornavida", "Lokma Tornavida Takımı"]}


class SahteMagaza:
    """products, product_details ve categories kaynaklarını bellekte tutar. bozuk=True iken PUT fiyatı da bozar."""

    def __init__(self):
        rnd = random.Random(3)
        self.urunler, pid = {}, 0
        for cid, adlar in ADLAR.items():
            for _ in range(30):
                pid += 1
                self.urunler[pid] = self._urun(pid, f"{rnd.choice(MARKALAR)} {rnd.choice(adlar)}", [cid])
        self.detaylar, self.istekler, self.bozuk = {}, [], False

    @staticmethod
    def _urun(pid, ad, cats, status=1, seo_tam=False):
        p = {"id": pid, "name": ad, "sku": f"HR-{pid}", "status": status, "price1": 100.0 + pid, "stockAmount": 5,
             "categories": [{"id": c} for c in cats], "targetKeyword": "", "pageTitle": "", "metaDescription": ""}
        if seo_tam:
            p.update(solvedCount=13, seoTotalRuleCount=13)
        return p

    def ekle(self, ad, cats, **kw):
        pid = max(self.urunler) + 1
        self.urunler[pid] = self._urun(pid, ad, cats, **kw)
        return pid

    def call(self, method, path, params=None, body=None, tries=6):
        self.istekler.append((method, path))
        params, parts = params or {}, path.strip("/").split("/")
        if method == "GET" and parts == ["products"]:
            if params.get("ids"):
                return [dict(copy.deepcopy(self.urunler[int(params["ids"])]), solvedCount=13, seoTotalRuleCount=13)]
            since = int(params.get("sinceId") or 0)
            return copy.deepcopy([p for i, p in sorted(self.urunler.items()) if i > since][:int(params.get("limit", 100))])
        if method == "GET" and parts[0] == "products" and len(parts) == 2:
            if int(parts[1]) not in self.urunler:
                raise app.ApiError(404, "yok")
            return copy.deepcopy(self.urunler[int(parts[1])])
        if method == "PUT" and parts[0] == "products":
            p = self.urunler[int(parts[1])]
            p.update(copy.deepcopy(body))
            if self.bozuk:
                self.bozuk = False
                p["price1"] = 0
            return copy.deepcopy(p)
        if method == "GET" and parts == ["categories"]:
            if int(params.get("page", 1)) > 1:
                return []
            return [{"id": i, "name": n, "parent": {"id": u} if u else None} for i, (n, u) in KATEGORILER.items()]
        if method == "GET" and parts == ["product_details"]:
            return [d for d in self.detaylar.values() if d["product"]["id"] == int(params.get("product", 0))]
        if method == "POST" and parts == ["product_details"]:
            d = dict(copy.deepcopy(body), id=1000 + body["product"]["id"])
            self.detaylar[d["id"]] = d
            self.urunler[body["product"]["id"]]["detail"] = {"id": d["id"]}
            return d
        if method == "GET" and parts[0] == "product_details":
            return copy.deepcopy(self.detaylar[int(parts[1])])
        if method == "PUT" and parts[0] == "product_details":
            self.detaylar[int(parts[1])].update(copy.deepcopy(body))
            return self.detaylar[int(parts[1])]
        raise app.ApiError(404, f"sahte: {method} {path}")

    def yazmalar(self):
        return [i for i in self.istekler if i[0] != "GET"]


def guclu_oneri(pid, cid, act="kategorisiz", eski=()):
    """Kategori analizinin bu ürün için emin olduğu bir öneri vermesini sağlar (otopilot testleri analizin kendisini değil,
    önerinin nasıl taşındığını denetler; analizin kararları kategori testlerinde)."""
    gercek = app.KT.analyze

    def analyze(cats, prods, progress=None):
        rep = gercek(cats, prods, progress)
        rep["uncat"] = [u for u in rep["uncat"] if u["pid"] != pid]
        rep["wrong"] = [w for w in rep["wrong"] if w["pid"] != pid]
        oneri = {"pid": pid, "sug": KATEGORILER[cid][0], "add": [cid], "rem": list(eski), "reason": "test önerisi"}
        if act == "kategorisiz":
            rep["uncat"].append(dict(oneri, strength="guclu"))
        else:
            rep["wrong"].append(dict(oneri, act=act))
        return rep
    return mock.patch.object(app.KT, "analyze", analyze)


class Ortam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-oto-")
        self._stores, app.STORES = app.STORES, self.tmp
        sifre.KEY_PATH = os.path.join(self.tmp, "anahtar.key")
        sifre.reset()
        self.t = app.Tenant("deneme-com")
        app._cur.t = self.t
        ST.panel_factor = _app_pf
        app.CFG.update(store="deneme.com", access_token="tok", refresh_token="r", expires_at=time.time() + 9999,
                       kw_loc={"res": "product", "path": "targetKeyword"}, profil={"magaza": "Deneme Hırdavat"})
        self.m = SahteMagaza()
        self.t.api.call = self.m.call
        self._tarandi()

    def tearDown(self):
        app._cur.t = None
        ST.panel_factor = _pf
        app.STORES = self._stores
        self.t.dbi.c.close()
        sifre.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _tarandi(self):
        """Mağaza bir kez taranmış gibi: kategori listesi ve ürünler yerel kayıtta."""
        app.DBI.xm("INSERT INTO cat(id, name, parent) VALUES(?,?,?)", [(i, n, u) for i, (n, u) in KATEGORILER.items()])
        app.DBI.xm("INSERT INTO catprod(pid, sku, name, cats, brand, status) VALUES(?,?,?,?,?,?)",
                   [(i, p["sku"], p["name"], json.dumps([c["id"] for c in p["categories"]]), "", 1)
                    for i, p in self.m.urunler.items()])

    def ac(self, **ayar):
        self.assertIsNone(app.OTO.ayarla(dict({"acik": True}, **ayar)))

    def sure_gecti(self):
        eski = (datetime.now() - timedelta(minutes=app.OTO_BEKLE_DK + 5)).strftime("%Y-%m-%d %H:%M")
        app.DBI.x("UPDATE oto SET bulundu=?", (eski,))

    def satir(self, pid):
        return dict(app.DBI.q("SELECT * FROM oto WHERE pid=?", (pid,), one=True) or {})

    def bekle(self):
        for _ in range(100):
            if not app.OTO.running:
                return
            time.sleep(0.05)
        self.fail("otopilot bitmedi")


class YeniUrunBulma(Ortam):
    def test_acilmadan_once_eklenen_urunlere_dokunulmaz(self):
        once = self.m.ekle("Bosch Darbeli Matkap 900W", [])       # tarandıktan sonra ama otopilot açılmadan önce
        self.ac()
        sonra = self.m.ekle("Makita Darbeli Matkap 650W", [])
        app.OTO.kontrol()
        self.assertEqual(self.satir(once), {})
        self.assertEqual(self.satir(sonra)["durum"], "bekliyor")
        self.assertEqual(self.m.yazmalar(), [])

    def test_kapaliyken_calismaz(self):
        self.m.ekle("Bosch Darbeli Matkap 900W", [])
        self.assertEqual(app.OTO.kontrol(), "Otopilot kapalı.")
        self.assertEqual(app.DBI.q("SELECT COUNT(*) n FROM oto", one=True)["n"], 0)

    def test_yeni_urun_beklemeden_islenmez(self):
        self.ac()
        pid = self.m.ekle("Bosch Darbeli Matkap 900W", [])
        app.OTO.kontrol()
        self.assertEqual(self.satir(pid)["seo"], None)                # süre dolmadı: hazırlanmadı
        self.sure_gecti()
        app.OTO.kontrol()
        self.assertEqual(self.satir(pid)["durum"], "onay")

    def test_pasif_urun_yayina_alinana_kadar_bekler(self):
        self.ac()
        pid = self.m.ekle("Bosch Darbeli Matkap 900W", [], status=0)
        app.OTO.kontrol()
        self.sure_gecti()
        app.OTO.kontrol()
        r = self.satir(pid)
        self.assertEqual(r["durum"], "bekliyor")
        self.assertIn("pasif", r["msg"])
        self.m.urunler[pid]["status"] = 1
        app.OTO.kontrol()
        self.assertEqual(self.satir(pid)["durum"], "onay")

    def test_uzun_sure_pasif_kalan_ve_silinen_urun_duser(self):
        self.ac()
        pasif = self.m.ekle("Bosch Darbeli Matkap 900W", [], status=0)
        silinen = self.m.ekle("Makita Yan Keski", [])
        app.OTO.kontrol()
        app.DBI.x("UPDATE oto SET bulundu=?", ((datetime.now() - timedelta(days=app.OTO_PASIF_GUN + 1)).strftime("%Y-%m-%d %H:%M"),))
        del self.m.urunler[silinen]
        app.OTO.kontrol()
        self.assertEqual(self.satir(pasif)["durum"], "yoksay")
        self.assertEqual(self.satir(silinen)["durum"], "yoksay")


class Hazirlik(Ortam):
    def test_kategorisiz_urune_oneri_ve_seo_hazirlanir_ama_yazilmaz(self):
        self.ac()
        pid = self.m.ekle("Bosch Darbeli Matkap 900W", [])
        app.OTO.kontrol()
        self.sure_gecti()
        app.OTO.kontrol()                                             # gerçek kategori analiziyle
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"], r["kat"], r["kat_act"]), ("onay", "hazir", "oneri", "kategorisiz"))
        self.assertIn("Matkaplar", r["kat_sug"])
        self.assertEqual(self.m.yazmalar(), [])                       # onaylı kipte mağazaya hiçbir şey yazılmaz

    def test_emin_olunmayan_oneri_otomatik_kipte_de_onaya_kalir(self):
        self.ac(mod="otomatik")
        pid = self.m.ekle("Bosch Darbeli Matkap 900W", [])
        app.OTO.kontrol()
        self.sure_gecti()
        app.OTO.kontrol()                                             # gerçek analiz bu ürün için "olası" diyor
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"], r["kat"], r["kat_guclu"]), ("onay", "gonderildi", "oneri", 0))
        self.assertEqual(self.m.urunler[pid]["categories"], [])

    def test_supheli_oneri_otomatik_kipte_onaya_kalir(self):
        self.ac(mod="otomatik")
        pid = self.m.ekle("Bosch Darbeli Matkap 900W", [21])
        with guclu_oneri(pid, 11, act="supheli", eski=[21]):
            app.OTO.kontrol()
            self.sure_gecti()
            app.OTO.kontrol()
        r = self.satir(pid)
        self.assertEqual((r["kat"], r["kat_act"], r["kat_guclu"], r["durum"]), ("oneri", "supheli", 0, "onay"))
        self.assertEqual([c["id"] for c in self.m.urunler[pid]["categories"]], [21])

    def test_seo_tamam_ve_kategorisi_dogru_urune_bir_sey_yapilmaz(self):
        self.ac()
        pid = self.m.ekle("Makita Darbeli Matkap 750W", [11], seo_tam=True)
        app.OTO.kontrol()
        self.sure_gecti()
        app.OTO.kontrol()
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"], r["kat"]), ("tamam", "gerekmez", "gerekmez"))


class Gonderim(Ortam):
    def hazirla(self, ad, cats, act="kategorisiz", hedef=11, **ayar):
        self.ac(**ayar)
        pid = self.m.ekle(ad, cats)
        with guclu_oneri(pid, hedef, act=act, eski=cats):
            app.OTO.kontrol()
            self.sure_gecti()
            app.OTO.kontrol()
        return pid

    def test_onay_seo_ve_kategoriyi_yazar(self):
        pid = self.hazirla("Bosch Darbeli Matkap 900W", [])
        fiyat = self.m.urunler[pid]["price1"]
        app.OTO.onayla(None)
        self.bekle()
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"], r["kat"]), ("tamam", "gonderildi", "uygulandi"), r["msg"])
        self.assertEqual([c["id"] for c in self.m.urunler[pid]["categories"]], [11])
        self.assertTrue(self.m.urunler[pid]["targetKeyword"])
        self.assertEqual(self.m.urunler[pid]["price1"], fiyat)
        self.assertEqual(app.cat_undo(pid)[0], "uygulandi")             # kategori geri alınabilir
        self.assertEqual(self.m.urunler[pid]["categories"], [])

    def test_otomatik_kip_kendiliginden_yazar(self):
        pid = self.hazirla("Bosch Darbeli Matkap 900W", [], mod="otomatik")
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"], r["kat"]), ("tamam", "gonderildi", "uygulandi"), r["msg"])

    def test_otomatik_kip_yanlis_kategoriyi_tasir(self):
        pid = self.hazirla("Bosch Darbeli Matkap 900W", [21], act="tasi", mod="otomatik")
        r = self.satir(pid)
        self.assertEqual((r["kat"], r["durum"]), ("uygulandi", "tamam"), r["msg"])
        self.assertEqual([c["id"] for c in self.m.urunler[pid]["categories"]], [11])

    def test_otomatik_kipte_kapali_isler_onaya_kalir(self):
        pid = self.hazirla("Bosch Darbeli Matkap 900W", [], mod="otomatik", kategorisiz=False)
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"], r["kat"]), ("onay", "gonderildi", "oneri"))
        self.assertEqual(self.m.urunler[pid]["categories"], [])

    def test_fiyat_bozulursa_eski_haline_yazilir(self):
        pid = self.hazirla("Bosch Darbeli Matkap 900W", [])
        fiyat = self.m.urunler[pid]["price1"]
        self.m.bozuk = True
        app.OTO.onayla([pid])
        self.bekle()
        r = self.satir(pid)
        self.assertEqual((r["durum"], r["seo"]), ("hata", "hata"))
        self.assertIn("Korunan alan", r["msg"])
        self.assertEqual(self.m.urunler[pid]["price1"], fiyat)

    def test_yok_sayilan_urun_onaylanmaz(self):
        pid = self.hazirla("Bosch Darbeli Matkap 900W", [])
        app.Otopilot._set(pid, durum="yoksay")
        app.OTO.onayla(None)
        self.bekle()
        self.assertEqual(self.m.yazmalar(), [])


class PaketVeZamanlayici(Ortam):
    def test_ucretsiz_pakette_acilmaz(self):
        with mock.patch.dict(app.SERVER, {"on": True}):
            msg = app.OTO.ayarla({"acik": True})
            self.assertIn("Ücretsiz analiz", msg)
            self.assertFalse(app.oto_ayar()["acik"])
            app.AB.yaz(self.t.dir, paket="baslangic", bitis="2099-12-31")
            self.assertIsNone(app.OTO.ayarla({"acik": True}))
            app.AB.yaz(self.t.dir, durum="iptal")                       # abonelik bitince otopilot durur
            self.m.ekle("Bosch Darbeli Matkap 900W", [])
            self.assertIn("iptal", app.OTO.kontrol())
        self.assertEqual(self.m.yazmalar(), [])

    def test_vekile_atama_yalnizca_o_magazaya_gider(self):
        baska = app.Tenant("baska-com")
        try:
            app.CATSCAN.running = True                                  # vekil üzerinden atama
            self.assertTrue(self.t.catscan.running)
            app._cur.t = baska
            self.assertFalse(app.CATSCAN.running)                       # başka mağazada geçerli değil
        finally:
            app._cur.t = self.t
            self.t.catscan.running = False
            baska.dbi.c.close()

    def test_gecersiz_ayar_duzeltilir(self):
        app.OTO.ayarla({"mod": "<script>", "seo": "evet", "fazla": 1})
        self.assertEqual(app.oto_ayar(), dict(app.OTO_VARSAYILAN))

    def test_zamanlayici_vakti_gelince_calistirir(self):
        app.LOCAL["id"] = self.t.id
        with mock.patch.dict(app._tenants, {self.t.id: self.t}):
            self.ac()
            pid = self.m.ekle("Bosch Darbeli Matkap 900W", [])
            app.oto_tur()
            self.assertEqual(self.satir(pid)["durum"], "bekliyor")
            n = len(self.m.istekler)
            app.oto_tur()                                               # aralık dolmadı: yeniden bakılmaz
            self.assertEqual(len(self.m.istekler), n)


if __name__ == "__main__":
    unittest.main()
