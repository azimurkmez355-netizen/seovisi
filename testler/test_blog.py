"""Blog yazarı: Ideasoft'un 13 blog kuralı, biçimler, hedef kelime, ürün kodu / barkod / mağaza adı, hariç kategoriler,
hazırlama (yazmaz), gönderim (yalnızca %100 ve kullanıcı isteğiyle), güncelleme, yayından kaldırma ve paket izni.
Bellekteki uydurma hırdavat mağazasıyla (test_otopilot.py); gerçek Ideasoft'a istek gitmez."""
import base64
import copy
import json
import os
import sys
import time
import unittest

os.environ.setdefault("SEOVISI_TEST", "1")      # Google'a istek gitmez

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_otopilot import KATEGORILER, Ortam, SahteMagaza  # noqa: E402

import app  # noqa: E402
import blog as BL  # noqa: E402
import seo_text as ST  # noqa: E402

DETAY = ("<h3>Teknik Özellikler</h3><ul><li>Güç: 750 W</li><li>Mandren: 13 mm</li></ul>"
         "<h3>Kullanım Alanları</h3><ul><li>Ahşap ve metal delme</li><li>Duvara dübel delikleri</li></ul>"
         "<h3>Paket İçeriği</h3><ul><li>Yan tutamak</li><li>Taşıma çantası</li></ul>")
JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 4000).decode()
URUN = {"id": 7, "name": "Bosch Professional GSB 13 RE Darbeli Matkap 600W", "sku": "0601217100", "barcode": "3165140371230",
        "slug": "bosch-gsb-13-re", "brand": {"name": "Bosch"}, "categories": [{"id": 11, "name": "Matkaplar"}]}


class Yazar(unittest.TestCase):
    def setUp(self):
        self._pf, ST.panel_factor = ST.panel_factor, lambda: 1.30

    def tearDown(self):
        ST.panel_factor = self._pf

    def test_her_bicim_ideasoftun_13_kuralini_tutar(self):
        for detay in (DETAY, ""):
            for b in BL.BICIMLER:
                p = BL.yaz(URUN, detay, bicim=b, prof={"magaza": "Ustapazar"}, method="panel")
                self.assertEqual(p["score"]["yuzde"], 100, (b, [k for k in p["score"]["kurallar"] if not k["ok"]]))
                self.assertEqual(p["score"]["toplam"], 13)
                self.assertGreaterEqual(p["score"]["kelime"], 300, b)       # Google için doyurucu uzunluk
                self.assertIn(ST.tr_lower(p["keyword"]), ST.tr_lower(p["title"]))
                self.assertTrue(20 <= len(p["pageTitle"]) <= 60 and 50 <= len(p["metaDescription"]) <= 155)

    def test_urun_kodu_barkod_ve_magaza_adi_gecer(self):
        p = BL.yaz(URUN, DETAY, bicim="rehber", prof={"magaza": "Ustapazar"}, method="panel")
        metin = ST.strip_tags(p["content"])
        for s in ("0601217100", "3165140371230", "Ustapazar"):
            self.assertIn(s, metin)
        self.assertIn('href="/urun/bosch-gsb-13-re"', p["content"])        # ürün sayfasına iç bağlantı
        self.assertIn("750 W", metin)                                       # teknik bilgi mevcut açıklamadan
        self.assertNotIn("<script", p["content"])

    def test_bicimler_ve_basliklar_urune_gore_degisir(self):
        bicimler = {BL.bicim_sec("karisik", pid) for pid in range(12)}
        self.assertEqual(bicimler, set(BL.BICIMLER))
        a = BL.yaz(URUN, DETAY, prof={"magaza": "Ustapazar"}, method="panel")
        b = BL.yaz(dict(URUN, id=8), DETAY, prof={"magaza": "Ustapazar"}, method="panel")
        self.assertNotEqual(a["title"], b["title"])
        self.assertNotEqual(a["content"], b["content"])

    def test_hedef_kelime_kisa_ve_adda_gecer(self):
        kw = BL.kelime_sec(URUN["name"], "", {"marka": "Bosch"})
        self.assertLessEqual(len(kw), 40)
        self.assertIn(ST.tr_lower(kw), ST.tr_lower(URUN["name"]))
        self.assertFalse(ST.tr_lower(kw).startswith("professional"))
        self.assertEqual(BL.kelime_sec(URUN["name"], "Darbeli Matkap"), "Darbeli Matkap")   # ürünün kendi kelimesi

    def test_dort_baytlik_karakter_yok(self):
        """Ideasoft blog içeriği 4 baytlık karakterleri (emoji) "????" olarak kaydediyor."""
        s = {"instagram": "https://www.instagram.com/a/", "youtube": "https://www.youtube.com/@b",
             "tiktok": "https://www.tiktok.com/@c", "facebook": "https://www.facebook.com/d"}
        for b in BL.BICIMLER:
            p = BL.yaz_tam(URUN, DETAY, bicim=b, prof={"magaza": "Ustapazar"}, method="panel", sosyal=s)
            for k in ("title", "content", "excerpt", "pageTitle", "metaDescription", "metaKeywords"):
                self.assertFalse([c for c in p[k] if ord(c) > 0xFFFF], (b, k))

    def test_ozel_karakterler_kacislidir(self):
        u = dict(URUN, name='Bosch <b>"Test"</b> & Matkap', sku="<x>")
        p = BL.yaz(u, "", bicim="sss", prof={"magaza": "A&B"}, method="panel")
        self.assertNotIn("<b>", p["content"])
        self.assertNotIn("<x>", p["content"])

    def test_gorsel_ayari_temizlenir(self):
        g = BL.gorsel_ayar({"tema": "yok", "renk": "kirmizi", "renk2": "#ABCDEF", "foto": "0", "ust_metin": "x" * 99})
        self.assertEqual((g["tema"], g["renk"], g["renk2"], g["foto"], len(g["ust_metin"])), ("lacivert_bant", "#e30613", "#abcdef", False, 40))
        self.assertEqual(len(BL.GORSEL_TEMALAR), 8)
        self.assertEqual(BL.gorsel_ayar({"tema": "gece_isik"})["tema"], "gece_isik")

    def test_urun_kodu_basligin_sonunda_hedef_kelimede_yok(self):
        u = dict(URUN, name="0603688001 Universal Humid Nem Ölçer", sku="0603688001")
        for b in BL.BICIMLER:
            p = BL.yaz_tam(u, "", bicim=b, prof={"magaza": "Ustapazar"}, method="panel")
            self.assertTrue(p["title"].endswith(" 0603688001"), p["title"])
            self.assertEqual(p["title"].count("0603688001"), 1)
            self.assertNotIn("0603688001", p["keyword"])
            self.assertNotIn("0603688001", p["gorsel_baslik"])       # görselde kod ayrıca "Ürün Kodu:" diye yazar
            self.assertEqual(p["score"]["yuzde"], 100)
        p = BL.yaz(u, "", kw="0603688001 Universal Humid", prof={"magaza": "Ustapazar"}, method="panel")   # eski kelime
        self.assertEqual(p["keyword"], "Universal Humid")

    def test_sosyal_medya_alani(self):
        s = {"instagram": "https://www.instagram.com/usta.pazar/", "youtube": "https://www.youtube.com/@UstaPazar",
             "tiktok": "javascript:alert(1)", "facebook": "https://evil.com/x"}
        self.assertEqual(set(BL.sosyal_ayar(s)), {"instagram", "youtube"})
        p = BL.yaz_tam(URUN, DETAY, prof={"magaza": "Ustapazar"}, method="panel", sosyal=s)
        self.assertIn('href="https://www.instagram.com/usta.pazar/"', p["content"])
        self.assertIn("@UstaPazar", p["content"])
        self.assertNotIn("javascript", p["content"])
        self.assertGreater(p["content"].index("Bizi takip edin"), p["content"].index("ekibi tarafından"))
        self.assertIn("linear-gradient(90deg,#4f5bd5", p["content"])      # Instagram'dan YouTube'a yatay geçiş
        self.assertIn('target="_blank"', p["content"])   # en altta
        self.assertEqual(p["score"]["yuzde"], 100)

    def test_gonderilecek_kayit(self):
        p = BL.yaz(URUN, DETAY, bicim="inceleme", prof={"magaza": "Ustapazar"}, method="panel")
        b = BL.gonderilecek(p, 5, 1, ("a.jpg", JPEG))
        for k in ("title", "excerpt", "content", "pageTitle", "metaDescription", "blockVisibility", "status", "categories"):
            self.assertIn(k, b)
        self.assertEqual((b["categories"], b["imageExtension"], b["targetKeyword"]), ([{"id": 5}], "jpg", p["keyword"]))


class BlogluMagaza(SahteMagaza):
    def __init__(self):
        super().__init__()
        self.bloglar, self.blog_kats = {}, {3: {"id": 3, "title": "Ürün Rehberleri"}}

    def call(self, method, path, params=None, body=None, tries=6):
        parts = path.strip("/").split("/")
        if parts[0] == "blogs":
            self.istekler.append((method, path))
            if method == "POST":
                bid = 500 + len(self.bloglar)
                self.bloglar[bid] = dict(copy.deepcopy(body), id=bid)
                self.bloglar[bid].pop("attachment", None)
                return copy.deepcopy(self.bloglar[bid])
            bid = int(parts[1])
            if bid not in self.bloglar:
                raise app.ApiError(404, "yok")
            if method == "DELETE":
                return self.bloglar.pop(bid) and None
            if method == "PUT":
                self.bloglar[bid].update({k: v for k, v in copy.deepcopy(body).items() if k != "attachment"})
            return copy.deepcopy(self.bloglar[bid])
        if parts[0] == "blog_categories":
            self.istekler.append((method, path))
            if method == "POST":
                k = dict(copy.deepcopy(body), id=10 + len(self.blog_kats))
                self.blog_kats[k["id"]] = k
                return k
            return list(copy.deepcopy(self.blog_kats).values())
        if parts[0] == "product_images":
            self.istekler.append((method, path))
            return []
        return super().call(method, path, params, body, tries)


class BlogEkrani(Ortam):
    def setUp(self):
        super().setUp()
        self.m = BlogluMagaza()
        self.t.api.call = self.m.call
        KATEGORILER_EK = {31: ("Bosch Aksesuar", None), 32: ("Matkap Uçları", 31)}
        app.DBI.xm("INSERT INTO cat(id, name, parent) VALUES(?,?,?)", [(i, n, u) for i, (n, u) in KATEGORILER_EK.items()])
        for pid in (1, 2):                          # iki ürün aksesuarın alt kategorisine
            self.m.urunler[pid]["categories"] = [{"id": 32}]
            app.DBI.x("UPDATE catprod SET cats=? WHERE pid=?", (json.dumps([32]), pid))
        self.m.urunler[3]["status"] = 0
        app.DBI.x("UPDATE catprod SET status=0 WHERE pid=3")
        self.m.call("POST", "product_details", body={"sku": "HR-5", "details": DETAY, "product": {"id": 5}})

    def bekle(self):
        for _ in range(400):
            if not app.BLOG.running:
                return
            time.sleep(0.05)
        self.fail("blog işi bitmedi")

    def yazmalar(self):
        return [w for w in self.m.yazmalar() if w[1] != "product_details"]

    def test_bosch_aksesuar_ve_pasif_urunler_haric(self):
        a = app.blog_ayar()
        self.assertTrue(a["haric_oto"])
        self.assertEqual(a["haric"], [31])
        pids = set(app.blog_urunler())
        self.assertFalse({1, 2, 3} & pids)
        self.assertEqual(len(pids), len(self.m.urunler) - 3)
        app.blog_ayar_yaz({"haric": []})            # kullanıcı hariç tutmayı kaldırırsa aksesuarlar da gelir
        self.assertIn(1, app.blog_urunler())

    def test_magaza_adi_yoksa_adresten(self):
        app.CFG.update(profil={"magaza": "", "marka": ""}, store="ustapazar.myideasoft.com")
        self.assertEqual(app.blog_profil()["magaza"], "Ustapazar")

    def test_hazirlama_magazaya_yazmaz(self):
        self.assertIn("hazırlanıyor", app.BLOG.start([4, 5, 6]))
        self.bekle()
        self.assertEqual(self.yazmalar(), [])
        d = app.BLOG.durum("hazir")
        self.assertEqual(d["sayilar"]["hazir"], 3)
        p = app.BLOG.plan(5)["plan"]
        self.assertEqual(p["score"]["yuzde"], 100)
        self.assertIn("HR-5", ST.strip_tags(p["content"]))
        self.assertIn("Deneme Hırdavat", ST.strip_tags(p["content"]))

    def test_gonderim_kategori_ister_ve_kayit_acar_sonra_gunceller(self):
        app.blog_hazirla(5)
        self.assertEqual(app.blog_gonder(5, JPEG)[0], "hata")              # blog kategorisi seçilmedi
        self.assertEqual(self.yazmalar(), [])
        satir = app.DBI.q("SELECT durum, mesaj FROM blog WHERE pid=5", one=True)
        self.assertEqual(satir["durum"], "hata")                             # kartta nedeni görünür
        self.assertIn("blog kategorisini", satir["mesaj"])
        app.blog_ayar_yaz({"kategori": 3})
        d, msg = app.blog_gonder(5, JPEG)
        self.assertEqual(d, "gonderildi", msg)
        self.assertEqual(len(self.m.bloglar), 1)
        b = next(iter(self.m.bloglar.values()))
        self.assertEqual((b["categories"], b["status"], b["imageExtension"]), ([{"id": 3}], 1, "jpg"))
        self.assertEqual(b["targetKeyword"], app.BLOG.plan(5)["plan"]["keyword"])
        self.assertEqual(app.DBI.q("SELECT COUNT(*) n FROM olay WHERE tur='blog'", one=True)["n"], 1)
        # yeniden yazılıp gönderilince aynı kayıt güncellenir (ikinci blog açılmaz)
        app.blog_hazirla(5, "sss", yeni=True)
        self.assertTrue(app.BLOG.plan(5)["degisti"])
        self.assertEqual(app.blog_gonder(5)[0], "gonderildi")
        self.assertEqual(len(self.m.bloglar), 1)
        self.assertIn("Soru", next(iter(self.m.bloglar.values()))["title"])           # sss biçimi
        self.assertFalse(app.BLOG.plan(5)["degisti"])
        # yayından kaldırma: pasif yapar, silmez
        self.assertEqual(app.blog_kaldir(5)[0], "kaldirildi")
        self.assertEqual(next(iter(self.m.bloglar.values()))["status"], 0)

    def test_yuzde_yuz_olmayan_yazi_gonderilmez(self):
        app.blog_ayar_yaz({"kategori": 3})
        app.blog_hazirla(6)
        plan, _ = app.blog_duzenle(6, {"pageTitle": "Kısa"})
        self.assertLess(plan["score"]["yuzde"], 100)
        d, msg = app.blog_gonder(6, JPEG)
        self.assertEqual(d, "hata")
        self.assertIn("Sayfa başlığı 20-60", msg)
        self.assertEqual(self.yazmalar(), [])
        # "Hepsini gönder" listesi: hazır ve SEO'su %100 olanlar, aramadan bağımsız
        app.blog_hazirla(5)
        self.assertEqual(app.BLOG.durum("hazir", q="bulunmayan")["hazir_tam"], [5])
        self.assertEqual(app.BLOG.durum("yazilacak")["hazir_tam"], [])

    def test_yuzde_yuz_olmayanlar_duzeltilir(self):
        app.blog_hazirla(6)
        r = app.DBI.q("SELECT plan FROM blog WHERE pid=6", one=True)
        plan = json.loads(r["plan"])
        plan["score"]["yuzde"], plan["pageTitle"] = 92, "Kısa"
        app.DBI.x("UPDATE blog SET plan=? WHERE pid=6", (json.dumps(plan),))
        self.assertEqual(app.BLOG.durum("hazir")["sayilar"]["eksik"], 1)
        self.assertIn("1 ürün", app.BLOG.start(eksik=True))
        self.bekle()
        self.assertEqual(app.BLOG.plan(6)["plan"]["score"]["yuzde"], 100)
        self.assertEqual(app.BLOG.durum("hazir")["sayilar"]["eksik"], 0)

    def test_sosyal_degisince_yazilar_yenilenir(self):
        app.blog_hazirla(6)
        self.assertEqual(app.BLOG.durum("hazir")["sayilar"]["eksik"], 0)
        app.blog_ayar_yaz({"sosyal": {"instagram": "https://www.instagram.com/usta.pazar/"}})
        self.assertEqual(app.BLOG.durum("hazir")["sayilar"]["eksik"], 1)
        app.BLOG.start(eksik=True)
        self.bekle()
        self.assertIn("instagram.com/usta.pazar", app.BLOG.plan(6)["plan"]["content"])
        self.assertEqual(app.BLOG.durum("hazir")["sayilar"]["eksik"], 0)

    def test_uzun_teknik_listeli_urun_de_yuzde_yuz(self):
        uzun = "<h3>Teknik Özellikler</h3><ul>" + "".join(f"<li>Özellik {i}: {i * 7} mm ölçü ve dayanıklı yapı</li>"
                                                          for i in range(30)) + "</ul>"
        for b in BL.BICIMLER:
            p = BL.yaz_tam(dict(URUN, name="Bosch Professional GDS 18V-1600 HC Çift Akülü 8 Ah Somun Sıkma Makinesi"), uzun,
                           bicim=b, prof={"magaza": "Ustapazar"}, method="panel")
            self.assertEqual(p["score"]["yuzde"], 100, b)

    def test_hedef_kelime_degisince_yazi_yeniden_kurulur(self):
        app.blog_hazirla(6)
        plan, msg = app.blog_duzenle(6, {"keyword": "Elektrikli Matkap"})
        self.assertIn("yeniden", msg)
        self.assertEqual(plan["keyword"], "Elektrikli Matkap")
        self.assertIn("Elektrikli Matkap", plan["title"])
        self.assertEqual(plan["score"]["yuzde"], 100)

    def test_bozuk_gorsel_gonderilmez(self):
        app.blog_ayar_yaz({"kategori": 3})
        app.blog_hazirla(6)
        for kotu in ("data:image/png;base64,AAAA", "data:image/jpeg;base64,!!!", "data:image/jpeg;base64,"
                     + base64.b64encode(b"GIF89a" * 900).decode()):
            self.assertEqual(app.blog_gonder(6, kotu)[0], "hata", kotu[:30])
        self.assertEqual(self.yazmalar(), [])

    def test_paket_izni(self):
        self.assertEqual(app.WRITE_ROUTES["/api/blog/gonder"], "blog")
        self.assertNotIn("/api/blog/kaldir", app.WRITE_ROUTES)      # geri alma her zaman açık
        self.assertNotIn("/api/blog/hazirla", app.WRITE_ROUTES)     # hazırlık yalnızca okur

    def test_izin_yoksa_anlasilir_mesaj(self):
        app.blog_ayar_yaz({"kategori": 3})
        app.blog_hazirla(6)
        gercek = self.m.call

        def izinsiz(method, path, params=None, body=None, tries=6):
            if path.startswith("blogs"):
                raise app.ApiError(403, "forbidden")
            return gercek(method, path, params, body, tries)
        self.t.api.call = izinsiz
        d, msg = app.blog_gonder(6, JPEG)
        self.assertEqual(d, "hata")
        self.assertIn("izin", msg)
        self.assertIn("izin", app.DBI.q("SELECT mesaj FROM blog WHERE pid=6", one=True)["mesaj"])

    def test_reddedilen_alan_olmadan_yeniden_denenir(self):
        app.blog_ayar_yaz({"kategori": 3, "kategori_ad": "Ürün Rehberleri"})
        app.blog_hazirla(6)
        gercek = self.m.call

        def secici(method, path, params=None, body=None, tries=6):
            if method == "POST" and path == "blogs" and "targetKeyword" in body:
                raise app.ApiError(400, '{"errorMessage":"targetKeyword: This field was not expected."}')
            return gercek(method, path, params, body, tries)
        self.t.api.call = secici
        d, msg = app.blog_gonder(6, JPEG)
        self.assertEqual(d, "gonderildi", msg)
        self.assertIn("hedef kelime", msg)                                  # panelden girilmesi söylenir
        b = next(iter(self.m.bloglar.values()))
        self.assertEqual(b["categories"], [{"id": 3, "title": "Ürün Rehberleri"}])

        def hep_red(method, path, params=None, body=None, tries=6):
            if method in ("POST", "PUT") and path.startswith("blogs"):
                raise app.ApiError(400, '{"errorMessage":"slug zaten var"}')
            return gercek(method, path, params, body, tries)
        self.t.api.call = hep_red
        app.blog_hazirla(7)
        d, msg = app.blog_gonder(7, JPEG)
        self.assertEqual(d, "hata")
        self.assertIn("slug zaten var", msg)                                # Ideasoft'un kendi nedeni görünür

    def test_blog_kategorisi_acilir(self):
        kats, hata = app.BLOG.blog_kategorileri_oku()
        self.assertIsNone(hata)
        self.assertEqual(kats, [{"id": 3, "ad": "Ürün Rehberleri"}])


if __name__ == "__main__":
    unittest.main()
