"""Blog kalite kapısı, anahtar kelime araştırması, özgünlük (kopya meta / içerik), iç bağlantılar, ürün kartı ve periyodik
blog otomasyonu. Google'a ve gerçek Ideasoft'a istek gitmez (sahte öneri kaynağı ve bellekteki sahte mağaza)."""
import json
import os
import re
import sys
import unittest
from datetime import datetime

os.environ.setdefault("SEOVISI_TEST", "1")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_blog import DETAY, JPEG, URUN, BlogluMagaza  # noqa: E402
from test_otopilot import Ortam  # noqa: E402

import app  # noqa: E402
import blog as BL  # noqa: E402
import kalite as KA  # noqa: E402
import kelime as KE  # noqa: E402
import seo_text as ST  # noqa: E402

PROF = {"magaza": "Ustapazar"}
KAT = {"ad": "Matkaplar", "slug": "matkaplar"}


def benzer(i):
    """Birbirine çok benzeyen ürünler: aynı tip, farklı model ve teknik değer."""
    u = dict(URUN, id=100 + i, name=f"Bosch Professional GSB {10 + i} RE Darbeli Matkap {500 + 10 * i}W",
             sku=f"06012{i:05d}", slug=f"gsb-{10 + i}-re")
    return u, DETAY.replace("750 W", f"{500 + 10 * i} W").replace("13 mm", f"{10 + i % 5} mm")


class AnahtarKelime(unittest.TestCase):
    def test_model_adi_bolunmez_ve_urun_tipi_one_cikar(self):
        r = KE.arastir(URUN["name"], "", URUN["sku"], "darbeli matkap", "Bosch")
        self.assertIn("GSB 13 RE", r["secilen"])                                  # müşteri markayı değil modeli arar
        self.assertEqual(KE.model_dizisi("Bosch Professional GWS 18V-8 Akülü Avuç Taşlama 06019H9100", "06019H9100"), "GWS 18V-8")
        r2 = KE.arastir("Bosch Professional GDR 18 V-200 C (Solo) Akülü Darbeli Somun Sıkma Makinesi 06019G4104", "",
                        "06019G4104", "ürün", "Bosch")
        self.assertEqual(r2["secilen"], "GDR 18 V-200 C")
        self.assertNotIn("Bosch Professional", [a["kelime"] for a in r2["adaylar"]])         # yalnızca marka seçilmez
        kotu = {"RE Darbeli", "13 RE Darbeli"}
        self.assertFalse(kotu & {a["kelime"] for a in r["adaylar"][:2]})
        self.assertFalse(r["google"])
        for a in r["adaylar"]:
            self.assertLessEqual(len(a["kelime"]), KE.EN_UZUN)

    def test_google_talebi_secimi_belirler(self):
        oneri = {"Paslanmaz Çelik Termos": ["paslanmaz çelik termos", "paslanmaz çelik termos 1 lt"],
                 "Çelik Termos": ["çelik termos", "çelik termos fiyatları", "çelik termos 500 ml"]}
        r = KE.arastir("Paslanmaz Çelik Termos 500 ml", "", "", "termos", "", getir=lambda q: oneri.get(q, []))
        self.assertTrue(r["google"])
        self.assertIn(r["secilen"], ("Çelik Termos", "Paslanmaz Çelik Termos"))
        self.assertIn("Google'da aranıyor (öneri olarak çıkıyor)", r["adaylar"][0]["neden"])
        self.assertIn("çelik termos fiyatları", r["ilgili"])

    def test_yamyamlasma_baska_kelime_secer(self):
        ilk = KE.arastir(URUN["name"], "", URUN["sku"], "darbeli matkap", "Bosch")["secilen"]
        ikinci = KE.arastir(URUN["name"], "", URUN["sku"], "darbeli matkap", "Bosch", kullanilan=[ilk])
        self.assertNotEqual(ikinci["secilen"], ilk)
        eski = next((a for a in ikinci["adaylar"] if a["kelime"] == ilk), None)
        if eski:                                                    # listede kaldıysa nedeni yazar
            self.assertIn("yamyamlaşma", eski["neden"][0])

    def test_onbellek_tekrar_sormaz(self):
        sorulan = []

        class Bellek(dict):
            def get(self, q):
                return dict.get(self, q)

            def set(self, q, v):
                self[q] = v

        b = Bellek()
        getir = lambda q: sorulan.append(q) or ["darbeli matkap"]   # noqa: E731
        KE.arastir(URUN["name"], "", "", "darbeli matkap", "", getir=getir, onbellek=b)
        n = len(sorulan)
        KE.arastir(URUN["name"], "", "", "darbeli matkap", "", getir=getir, onbellek=b)
        self.assertGreater(n, 0)
        self.assertEqual(len(sorulan), n)

    def test_google_kesici(self):
        g = KE.GoogleOneri()
        g.kapali_kadar = 10 ** 12          # art arda hatalardan sonra kesilmiş gibi: istek gönderilmez
        self.assertIsNone(g("darbeli matkap"))


class Kalite(unittest.TestCase):
    def setUp(self):
        self._pf, ST.panel_factor = ST.panel_factor, lambda: 1.30

    def tearDown(self):
        ST.panel_factor = self._pf

    def test_atesman_okunabilirlik(self):
        kolay = "<p>Bu bir test. Kısa cümle var. Okuması çok kolay. Her şey açık.</p>"
        zor = ("<p>Uluslararası standartlaştırılmış değerlendirme yöntemlerinin karşılaştırmalı çözümlemesi sonucunda "
               "elde edilen bulguların yorumlanmasına ilişkin metodolojik yaklaşımların sistematikleştirilmesi.</p>")
        self.assertGreater(KA.okunabilirlik(kolay)["puan"], KA.okunabilirlik(zor)["puan"])
        self.assertEqual(KA.okunabilirlik("")["puan"], 0)
        self.assertIn(KA.okunabilirlik(kolay)["seviye"], ("Kolay", "Çok kolay"))

    def test_her_bicim_kalite_kapisini_gecer(self):
        for b in BL.BICIMLER:
            p = BL.yaz_tam(URUN, DETAY, bicim=b, prof=PROF, method="panel", kategori=KAT, foto="https://cdn.ornek.com/a.jpg",
                           bicim_sabit=True)
            k = p["kalite"]
            self.assertEqual(p["score"]["yuzde"], 100, b)
            self.assertTrue(k["gecti"], (b, [r["ad"] for r in k["kurallar"] if not r["ok"]]))
            self.assertGreaterEqual(k["puan"], KA.SINIRLAR["seo"])
            self.assertGreaterEqual(k["okunabilirlik"]["puan"], KA.SINIRLAR["okunabilirlik"])
            self.assertGreaterEqual(k["ic_baglanti"], 3)                          # ürün, kategori, blog
            self.assertLessEqual(k["kaplama"], 0.15)                              # anahtar kelime doldurma yok
            self.assertFalse([c for f in ("content", "metaDescription", "excerpt") for c in p[f] if ord(c) > 0xFFFF])

    def test_urun_karti_fotografli_ve_baglantili(self):
        p = BL.yaz(URUN, DETAY, bicim="rehber", prof=PROF, method="panel", foto="https://cdn.ornek.com/a.jpg", kategori=KAT,
                   ilgili=[("Darbeli matkap nasıl seçilir", "/blog/darbeli-matkap")])
        c = p["content"]
        self.assertIn('id="seovisi-urun-karti"', c)
        self.assertIn('src="https://cdn.ornek.com/a.jpg"', c)
        self.assertIn('href="/urun/bosch-gsb-13-re"', c)
        self.assertIn("Ürünü incele", c)
        self.assertIn('href="/kategori/matkaplar"', c)
        self.assertIn('href="/blog/darbeli-matkap"', c)
        self.assertGreater(c.index("seovisi-urun-karti"), c.index("seovisi-ilgili"))   # kart, bağlantılardan sonra
        self.assertNotIn("<script", c)
        # fotoğraf yoksa kart yine görünür (baş harf)
        self.assertIn('id="seovisi-urun-karti"', BL.yaz(URUN, DETAY, prof=PROF, method="panel")["content"])

    def test_benzer_urunlerde_kopya_meta_ve_icerik_yok(self):
        dz = KA.Dizin()
        planlar = []
        for i in range(12):
            u, d = benzer(i)
            p = BL.yaz_tam(u, d, bicim="inceleme", prof=PROF, method="panel", digerleri=dz, bicim_sabit=True)
            dz.ekle(u["id"], KA.iz(p))
            planlar.append(p)
        for i, a in enumerate(planlar):
            for b in planlar[i + 1:]:
                self.assertNotEqual(a["metaDescription"], b["metaDescription"])
                sim = KA.jaccard(set(KA.meta_parmak(a["metaDescription"], a["keyword"])),
                                 set(KA.meta_parmak(b["metaDescription"], b["keyword"])))
                self.assertLess(sim, KA.SINIRLAR["meta_benzerlik"], (a["metaDescription"], b["metaDescription"]))
            self.assertLess(a["kalite"]["icerik_benzerlik"], KA.SINIRLAR["icerik_benzerlik"])
        self.assertEqual(len({p["slug"] for p in planlar}), len(planlar))

    def test_dizin_kopyayi_ve_ayni_kelimeyi_bulur(self):
        p = BL.yaz(URUN, DETAY, bicim="sss", prof=PROF, method="panel")
        dz = KA.Dizin([dict(KA.iz(p), pid=1)])
        self.assertEqual(dz.icerik_benzerlik(p["imza"])[0], 1.0)
        self.assertEqual(dz.icerik_benzerlik(p["imza"], haric=1)[0], 0.0)
        self.assertEqual(dz.kelimeyi_kullanan(p["keyword"]), [1])
        k = KA.degerlendir(dict(p, urun={"id": 2}), dz)                             # aynı yazı başka üründe
        self.assertFalse(k["gecti"])
        self.assertEqual(k["yamyam"], [1])
        dz.sil(1)
        self.assertEqual(len(dz), 0)


class Baslik(unittest.TestCase):
    def test_baslikta_urun_adi_ve_kodu(self):
        ST.panel_factor = lambda: 1.30
        u = dict(URUN, name="Bosch Professional GWS 18V-8 Akülü Avuç Taşlama 06019H9100", sku="06019H9100")
        for b in BL.BICIMLER:
            p = BL.yaz_tam(u, DETAY, bicim=b, prof=PROF, method="panel", bicim_sabit=True)
            self.assertIn("GWS 18V-8 Akülü Avuç Taşlama", p["title"], b)
            self.assertTrue(p["title"].endswith("06019H9100"))
            self.assertNotIn("06019H9100", p["gorsel_baslik"])
            self.assertIn(ST.tr_lower(p["keyword"]), ST.tr_lower(p["title"]))
            self.assertFalse(p["title"].startswith("Bosch Professional"))
            self.assertEqual(p["score"]["yuzde"], 100)

    def test_html_agir_yazida_da_yuzde_yuz(self):
        """Sosyal medya, ürün kartı ve bağlantılarla HTML'i ağır yazı her sayım yönteminde Ideasoft'un 13 kuralını tutar."""
        ST.panel_factor = lambda: 1.30
        s = {"instagram": "https://www.instagram.com/a/", "youtube": "https://www.youtube.com/@b"}
        u = dict(URUN, name="Bosch Professional GDR 120-Li Çift Akülü 2 Ah Somun Sıkma Makinesi 06019F0001", sku="06019F0001")
        for m in ("panel", "asc_html", "ws_text", "panel_lo,panel,panel_hi"):
            for b in BL.BICIMLER:
                p = BL.yaz_tam(u, DETAY, bicim=b, prof=PROF, method=m, sosyal=s, foto="https://cdn.ornek.com/a.jpg",
                               kategori=KAT, ilgili=[("Bir yazı", "/blog/icerik/a")], bicim_sabit=True)
                self.assertEqual(p["score"]["yuzde"], 100, (m, b))
                self.assertTrue(p["kalite"]["gecti"], (m, b))


class BlogOtomasyon(Ortam):
    def setUp(self):
        super().setUp()
        self.m = BlogluMagaza()
        for pid, u in self.m.urunler.items():
            u["slug"] = f"urun-{pid}"                                  # gerçek ürünlerin vitrin adresi olur
        ic = self.m.call

        def call(method, path, params=None, body=None, tries=6):
            parca = path.strip("/").split("/")
            if method == "GET" and parca[0] == "categories" and len(parca) == 2:
                return {"id": int(parca[1]), "slug": f"kategori-{parca[1]}"}
            return ic(method, path, params, body, tries)
        self.t.api.call = call
        self.m.call("POST", "product_details", body={"sku": "HR-5", "details": DETAY, "product": {"id": 5}})
        app.blog_ayar_yaz({"kategori": 3})
        self._spawn, app.spawn = app.spawn, lambda fn, *a, **k: fn(*a, **k)       # arka plan işi hemen çalışsın

    def tearDown(self):
        app.spawn = self._spawn
        super().tearDown()

    def hazir(self, pid):
        plan = app.blog_hazirla(pid)
        self.assertEqual(plan["score"]["yuzde"], 100)
        self.assertTrue(plan["kalite"]["gecti"], [r["ad"] for r in plan["kalite"]["kurallar"] if not r["ok"]])
        return plan

    def test_sonraki_vakitler_secili_gun_ve_saat(self):
        a = app.blog_oto_yaz({"gunler": [0, 2], "saatler": [9, 21]})
        simdi = datetime(2026, 11, 20, 10, 30, tzinfo=app.TR_SAAT)          # Cuma
        t = app.blog_oto_sonraki(a, 4, simdi)
        self.assertEqual([x.strftime("%a %H") for x in t], ["Mon 09", "Mon 21", "Wed 09", "Wed 21"])
        self.assertEqual(set(app.BLOG_VAKITLER), {"sabah", "ogle", "aksam", "gece"})
        saatler = sorted(h for _, b, s in app.BLOG_VAKITLER.values() for h in range(b, s))
        self.assertEqual(saatler, list(range(24)))                                       # gün dört eşit vakit
        self.assertTrue(all(s - b == 6 for _, b, s in app.BLOG_VAKITLER.values()))

    def test_gorsel_hazir_degilse_yayimlamaz(self):
        self.hazir(5)
        app.blog_oto_yayinla("deneme", 1)
        self.assertEqual(self.m.bloglar, {})
        self.assertEqual(app.blog_oto_kuyruk()[0]["gorsel"], False)
        self.assertEqual(app.DBI.q("SELECT durum FROM blog_oto_log", one=True)["durum"], "bos")

    def test_secili_saatte_bir_kez_gorseliyle_yayimlar(self):
        self.hazir(5)
        self.assertIsNone(app.blog_oto_gorsel_kaydet(5, JPEG))
        self.assertTrue(app.blog_oto_kuyruk()[0]["uygun"])
        app.blog_oto_yaz({"acik": True, "gunler": [4], "saatler": [14]})
        self._mg, self._tn = app._magazalar, app.tenant
        app._magazalar, app.tenant = (lambda: ["deneme-com"]), (lambda tid: self.t)
        try:
            app.blog_oto_tur(datetime(2026, 11, 20, 13, 5, tzinfo=app.TR_SAAT))         # seçili saat değil
            self.assertEqual(self.m.bloglar, {})
            app.blog_oto_tur(datetime(2026, 11, 20, 14, 5, tzinfo=app.TR_SAAT))         # Cuma 14:05
            self.assertEqual(len(self.m.bloglar), 1)
            b = next(iter(self.m.bloglar.values()))
            self.assertEqual(b["imageExtension"], "jpg")
            app.blog_oto_tur(datetime(2026, 11, 20, 14, 40, tzinfo=app.TR_SAAT))        # aynı saat: tekrar yok
            self.assertEqual(len(self.m.bloglar), 1)
        finally:
            app._magazalar, app.tenant = self._mg, self._tn
        self.assertEqual(app.DBI.q("SELECT durum FROM blog WHERE pid=5", one=True)["durum"], "gonderildi")
        self.assertEqual(app.DBI.q("SELECT durum FROM blog_oto_log ORDER BY id DESC", one=True)["durum"], "gonderildi")

    def test_kapali_ya_da_izinsizse_yayimlamaz(self):
        self.hazir(5)
        app.blog_oto_gorsel_kaydet(5, JPEG)
        app.blog_ayar_yaz({"kategori": 0})
        app.blog_oto_yayinla("deneme", 1)
        self.assertEqual(self.m.bloglar, {})
        self.assertIn("kategorisi", app.DBI.q("SELECT mesaj FROM blog_oto_log", one=True)["mesaj"])
        self.assertEqual(app.WRITE_ROUTES["/api/blog/oto/simdi"], "blog")

    def test_kalite_kapisini_gecmeyen_yayimlanmaz(self):
        self.hazir(5)
        app.blog_oto_gorsel_kaydet(5, JPEG)
        app.blog_duzenle(5, {"metaDescription": "Kısa"})                                  # kurallar bozuldu
        self.assertFalse(app.blog_oto_kuyruk()[0]["uygun"])
        app.blog_oto_yayinla("deneme", 1)
        self.assertEqual(self.m.bloglar, {})

    def test_gorsel_ayari_degisince_gorsel_eskir(self):
        self.hazir(5)
        app.blog_oto_gorsel_kaydet(5, JPEG)
        self.assertTrue(app.blog_oto_kuyruk()[0]["gorsel"])
        app.blog_ayar_yaz({"gorsel": {"tema": "beyaz_kutu"}})
        self.assertFalse(app.blog_oto_kuyruk()[0]["gorsel"])
        self.assertEqual(app.blog_oto_durum()["kuyruk"]["gorsel_eksik"], [5])

    def test_yeni_yazi_eski_yaziya_ic_baglanti_ekler(self):
        for pid in (5, 6):
            app.DBI.x("UPDATE catprod SET cats=? WHERE pid=?", (json.dumps([11]), pid))
            self.m.urunler[pid]["categories"] = [{"id": 11}]
        self.hazir(5)
        self.assertEqual(app.blog_gonder(5, JPEG)[0], "gonderildi")
        self.hazir(6)
        self.assertIn(app.vitrin_yollari()["blog"] + json.loads(app.DBI.q("SELECT iz FROM blog WHERE pid=5", one=True)["iz"])["slug"],
                      app.BLOG.plan(6)["plan"]["content"])                                # yeni yazı eskisine bağlanır
        app.blog_oto_gorsel_kaydet(6, JPEG)
        app.blog_oto_yaz({"baglanti": True})
        app.blog_oto_yayinla("deneme", 1)
        slug6 = json.loads(app.DBI.q("SELECT iz FROM blog WHERE pid=6", one=True)["iz"])["slug"]
        eski = [b for b in self.m.bloglar.values() if b["id"] == app.DBI.q("SELECT blog_id FROM blog WHERE pid=5", one=True)["blog_id"]][0]
        self.assertIn(app.vitrin_yollari()["blog"] + slug6, eski["content"])          # eski yazı da yenisine bağlandı
        self.assertIn("baglanti", [r["durum"] for r in app.DBI.q("SELECT durum FROM blog_oto_log")])

    def test_sitede_acilmayan_baglanti_yaziya_girmez(self):
        acik = {"/urun/urun-5", "/blog"}
        app.VITRIN_GETIR = lambda url, govde=True: ((200, "text/html", "<h1>Ürün</h1>", url)
                                                     if url.split("deneme.com", 1)[1] in acik
                                                     else (404, "text/html", "Aradığınız sayfa bulunamamıştır", url))
        try:
            plan = app.blog_hazirla(5)
            hrefler = set(re.findall(r'href="(/[^"]*)"', plan["content"]))
            self.assertEqual(hrefler, acik)                                # kategori adresi açılmadığı için yok
            # gönderilmiş yazının adresi sitede açılmıyorsa ilgili yazılara eklenmez
            self.assertEqual(app.blog_ilgili(6, plan["keyword"], [11]), [])
            # gönderim öncesi son denetim: sonradan kırılan bağlantı yazıyı yeniden kurdurur
            acik.discard("/blog")
            app.DBI.x("DELETE FROM vitrin_link")
            self.assertEqual(app.blog_gonder(5, JPEG)[0], "gonderildi")
            self.assertNotIn('href="/blog"', next(iter(self.m.bloglar.values()))["content"])
        finally:
            app.VITRIN_GETIR = None

    def test_siteye_ulasilamazsa_gonderilmez(self):
        self.hazir(5)
        app.DBI.x("DELETE FROM vitrin_link")
        app.VITRIN_GETIR = lambda url, govde=True: (0, "", "", url)
        try:
            d, msg = app.blog_gonder(5, JPEG)
        finally:
            app.VITRIN_GETIR = None
        self.assertEqual(d, "hata")
        self.assertIn("ulaşılamadı", msg)
        self.assertEqual(self.m.bloglar, {})

    def test_sil(self):
        self.hazir(5)
        app.blog_oto_gorsel_kaydet(5, JPEG)
        self.assertEqual(app.blog_sil(5)[0], "silindi")
        self.assertIsNone(app.DBI.q("SELECT 1 FROM blog WHERE pid=5", one=True))
        self.assertNotIn(5, app.BLOG.dizin_al().izler)
        self.assertIn(5, [r["pid"] for r in app.BLOG.satirlar() if r["sekme"] == "yazilacak"])
        # gönderilmiş yazı: onay olmadan silinmez; onayla Ideasoft'taki de silinir
        self.hazir(5)
        app.blog_gonder(5, JPEG)
        self.assertEqual(app.blog_sil(5)[0], "hata")
        self.assertEqual(len(self.m.bloglar), 1)
        self.assertEqual(app.blog_sil(5, True)[0], "silindi")
        self.assertEqual(self.m.bloglar, {})

    def test_yayimlanan_yazinin_adresi_degismez(self):
        self.hazir(5)
        app.blog_gonder(5, JPEG)
        slug = app.BLOG.plan(5)["plan"]["slug"]
        app.blog_hazirla(5, "sss", yeni=True)
        self.assertEqual(app.BLOG.plan(5)["plan"]["slug"], slug)


if __name__ == "__main__":
    unittest.main()
