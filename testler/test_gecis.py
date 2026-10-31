"""Toplu şablon geçişi ve SEO geri alma: içerik aynı kalır, yalnızca şablon değişir; sonradan elle değiştirilen ürünlere
dokunulmaz; her geçiş ve her gönderim geri alınabilir. Bellekteki sahte mağazayla (test_otopilot.SahteMagaza)."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testler.test_otopilot import Ortam, app  # noqa: E402

ST = app.ST


class Gecis(Ortam):
    def gonder(self, pid):
        app.DBI.x("INSERT OR IGNORE INTO seo(pid, sku, name) VALUES(?,?,?)", (pid, f"HR-{pid}", self.m.urunler[pid]["name"]))
        app.prepare_plan(pid)
        self.assertEqual(app.send_plan(pid)[0], "gonderildi")
        return self.aciklama(pid)

    def aciklama(self, pid):
        return self.m.detaylar[self.m.urunler[pid]["detail"]["id"]]["details"]

    def calistir(self, kind="gecir"):
        app.GECIS.start(kind)
        for _ in range(200):
            if not app.GECIS.running:
                return app.GECIS.state()
            time.sleep(0.02)
        self.fail("geçiş bitmedi")

    def satir(self, pid):
        return dict(app.DBI.q("SELECT gecis, pmsg, onceki, pstate, backup FROM seo WHERE pid=?", (pid,), one=True))

    def test_icerik_ayni_kalir_yalnizca_sablon_degisir(self):
        eski = self.gonder(1)
        p = dict(self.m.urunler[1])
        self.assertIn("1b4f72", eski)                                 # bilgisayar kurulumu: bantlı
        app.CFG.update(sablon={"gorunum": "cizgili", "renk": "#c0392b"})
        st = self.calistir()
        yeni = self.aciklama(1)
        self.assertEqual(self.satir(1)["gecis"], "gecti", self.satir(1)["pmsg"])
        self.assertIn("c0392b", yeni)
        self.assertNotIn("1b4f72", yeni)
        self.assertEqual(ST.strip_tags(yeni), ST.strip_tags(eski))  # aynı cümleler
        for k in ("pageTitle", "metaDescription", "targetKeyword", "price1", "name"):
            self.assertEqual(self.m.urunler[1][k], p[k], k)
        self.assertEqual(st["sayilar"], {"gecti": 1})

    def test_gecis_geri_alinir(self):
        eski = self.gonder(1)
        app.CFG.update(sablon={"gorunum": "kutulu"})
        self.calistir()
        self.calistir("geri")
        self.assertEqual(self.aciklama(1), eski)
        r = self.satir(1)
        self.assertEqual((r["gecis"], r["onceki"]), ("geri", None))

    def test_sonradan_elle_degistirilen_urune_dokunulmaz(self):
        self.gonder(1)
        self.gonder(2)
        d = self.m.urunler[1]["detail"]["id"]
        self.m.detaylar[d]["details"] = "<p>Mağaza sahibinin yeni metni.</p>"
        self.m.urunler[2]["pageTitle"] = "Elle yazılmış başlık"
        app.CFG.update(sablon={"gorunum": "cizgili"})
        once = len(self.m.yazmalar())
        self.calistir()
        for pid in (1, 2):
            r = self.satir(pid)
            self.assertEqual(r["gecis"], "atlandi")
            self.assertIn("panelde değiştirilmiş", r["pmsg"])
        self.assertEqual(len(self.m.yazmalar()), once)
        self.assertEqual(self.m.detaylar[d]["details"], "<p>Mağaza sahibinin yeni metni.</p>")

    def test_zaten_bu_sablondaysa_yazilmaz(self):
        self.gonder(1)
        once = len(self.m.yazmalar())
        self.calistir()                                                # şablon değişmedi
        self.assertEqual(self.satir(1)["gecis"], "atlandi")
        self.assertIn("zaten bu şablonda", self.satir(1)["pmsg"])
        self.assertEqual(len(self.m.yazmalar()), once)

    def test_gonderilmemis_urune_dokunulmaz(self):
        self.gonder(1)
        app.DBI.x("INSERT INTO seo(pid, sku, name) VALUES(2, 'HR-2', 'x')")
        app.prepare_plan(2)                                            # hazır ama gönderilmedi
        app.CFG.update(sablon={"gorunum": "cizgili"})
        st = self.calistir()
        self.assertEqual(st["sayilar"], {"gecti": 1})
        self.assertIsNone(self.satir(2)["gecis"])

    def test_fiyat_bozulursa_eski_haline_yazilir_ve_durur(self):
        self.gonder(1)
        self.gonder(2)
        fiyat = self.m.urunler[1]["price1"]
        app.CFG.update(sablon={"gorunum": "cizgili"})
        self.m.bozuk = True
        st = self.calistir()
        self.assertEqual(self.m.urunler[1]["price1"], fiyat)
        self.assertEqual(self.satir(1)["gecis"], "hata")
        self.assertIn("Korunan alan", self.satir(1)["pmsg"])
        self.assertLess(st["sayilar"].get("gecti", 0), 2)              # toplu işlem durdu

    def test_ayni_anda_iki_toplu_islem_baslamaz(self):
        self.gonder(1)
        app.SEOJOBS.running = True
        try:
            self.assertIn("Başka bir işlem", app.GECIS.start("gecir"))
        finally:
            app.SEOJOBS.running = False


class SeoGeriAlma(Ortam):
    def test_gonderim_ozgun_haline_doner(self):
        p0 = dict(self.m.urunler[1], targetKeyword="eski kelime", pageTitle="Eski başlık", metaDescription="Eski meta")
        self.m.urunler[1].update(p0)
        app.DBI.x("INSERT INTO seo(pid, sku, name) VALUES(1, 'HR-1', ?)", (p0["name"],))
        app.prepare_plan(1)
        self.assertEqual(app.send_plan(1)[0], "gonderildi")
        self.assertNotEqual(self.m.urunler[1]["pageTitle"], "Eski başlık")
        state, msg = app.seo_geri_al(1)
        self.assertEqual(state, "uygulandi", msg)
        u = self.m.urunler[1]
        self.assertEqual((u["pageTitle"], u["metaDescription"], u["targetKeyword"]), ("Eski başlık", "Eski meta", "eski kelime"))
        self.assertEqual(self.m.detaylar[u["detail"]["id"]]["details"], "")      # önce açıklaması yoktu
        r = dict(app.DBI.q("SELECT pstate, backup, plan FROM seo WHERE pid=1", one=True))
        self.assertEqual((r["pstate"], r["backup"], r["plan"]), ("geri", None, None))
        self.assertEqual(app.seo_geri_al(1)[0], "hata")                          # ikinci kez geri alınacak bir şey yok

    def test_yedegi_olmayan_urun(self):
        self.assertEqual(app.seo_geri_al(99)[0], "hata")


if __name__ == "__main__":
    unittest.main()
