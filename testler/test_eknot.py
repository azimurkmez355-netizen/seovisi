"""Ek not: notun üretimi, tanınması ve kaldırılması; kategori grubu, SEO koruması, ekleme / güncelleme / kaldırma ve
yazma güvenliği. Bellekteki uydurma hırdavat mağazasıyla (test_otopilot.py); gerçek Ideasoft'a istek gitmez."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_otopilot import Ortam  # noqa: E402

import app  # noqa: E402
import eknot as EN  # noqa: E402
import seo_machine as SM  # noqa: E402
import seo_text as ST  # noqa: E402

AYAR = {"simge": "🛡️", "baslik": "+1 yıl ek garanti", "metin": "{urun} ürününü üreticinin sitesinden kaydettirerek ek garanti kazanın.",
        "link_yazi": "Ürününüzü kaydedin", "link_url": "https://www.ornek-uretici.com/kayit"}


class NotMetni(unittest.TestCase):
    def test_ayar_temizlenir(self):
        a = EN.yukle({"acik": "evet", "simge": "💣", "metin": "  çok   boşluk  ", "link_url": "www.ornek.com/kayit",
                      "kategoriler": ["3", 3, -1, "x", 5]})
        self.assertEqual((a["acik"], a["simge"], a["metin"], a["kategoriler"]), (False, "🛡️", "çok boşluk", [3, 5]))
        self.assertEqual(a["link_url"], "https://www.ornek.com/kayit")
        for kotu in ("javascript:alert(1)", 'https://a.com/"onmouseover=x', "ftp://a.com", "kayit"):
            self.assertEqual(EN.url_duzelt(kotu), "", kotu)
        self.assertEqual(len(EN.yukle({"metin": "x" * 999})["metin"]), EN.METIN_UZUNLUK)
        self.assertEqual(EN.eksik(EN.yukle({})), "Not metnini yazın.")
        self.assertEqual(EN.eksik(EN.yukle({"metin": "a"})), "En az bir kategori seçin.")

    def test_html_kacislidir_ve_isaretlidir(self):
        h = EN.uret(EN.yukle(dict(AYAR, metin="<script>x</script> {urun}")), "#123456", "Darbeli Matkap")
        self.assertNotIn("<script>", h)
        self.assertIn("Darbeli Matkap", h)
        self.assertIn(f'id="{EN.ISARET}"', h)
        self.assertIn('rel="nofollow noopener"', h)
        self.assertNotIn("<h", h.replace("href", ""))              # başlık etiketi yok
        self.assertNotIn("<a", EN.uret(EN.yukle(dict(AYAR, link_url="")), "#123456"))

    def test_ekle_cikar(self):
        a = EN.yukle(AYAR)
        n1, n2 = EN.uret(a, "#111111", "X"), EN.uret(dict(a, metin="yeni metin"), "#111111", "X")
        d = "<p>Ürün açıklaması</p><div style='x'>kutu</div>"
        bir = EN.ekle(d, n1)
        self.assertEqual(EN.ekle(bir, n1), bir)                     # iki kez eklenmez
        iki = EN.ekle(bir, n2)
        self.assertEqual(iki.count(EN.ISARET), 1)
        self.assertIn("yeni metin", iki)
        self.assertEqual(EN.cikar(iki), (d, True))                  # açıklamanın geri kalanı ve başka kutular aynen
        self.assertEqual(EN.cikar(d), (d, False))
        # düzenleyici işareti silse de bilinen metinle tanınır
        isaretsiz = bir.replace(f' id="{EN.ISARET}"', "")
        self.assertFalse(EN.var_mi(isaretsiz))
        self.assertEqual(EN.cikar(isaretsiz, [n1]), (d, True))

    def test_aciklama_uretici_notu_hesaba_katar(self):
        a = EN.yukle(AYAR)
        prod = {"name": "Bosch Darbeli Matkap 750W", "categories": [{"id": 11, "name": "Matkaplar"}]}
        notsuz = SM.build_machine_seo(prod, "", sku="HR-1", method="panel")
        notlu = SM.build_machine_seo(prod, "", sku="HR-1", method="panel", ek_not=lambda kw: EN.uret(a, "#111111", kw))
        self.assertTrue(notlu["details_html"].endswith("</div>") and EN.var_mi(notlu["details_html"]))
        sc = ST.seo_score(prod["name"], notlu["keyword"], notlu["details_html"], "", "", "panel")
        self.assertTrue(2.0 <= sc["density"] <= 3.0, sc)
        # mevcut açıklamadaki eski not içerik olarak okunmaz
        eski = EN.ekle(notsuz["details_html"], EN.uret(a, "#111111", "X")).replace(f' id="{EN.ISARET}"', "")
        tekrar = SM.build_machine_seo(prod, eski, sku="HR-1", method="panel", ek_not_bilinen=[EN.uret(a, "#111111", "X")])
        self.assertEqual(tekrar["details_html"], SM.build_machine_seo(prod, notsuz["details_html"], sku="HR-1", method="panel")["details_html"])


class EkNotMagaza(Ortam):
    def setUp(self):
        super().setUp()
        app.CFG.update(ek_not=dict(AYAR, acik=True, kategoriler=[1]))     # Elektrikli El Aletleri ve alt kategorileri

    def aciklama(self, pid, html):
        self.m.call("POST", "product_details", body={"sku": f"HR-{pid}", "details": html, "product": {"id": pid}})

    def detay(self, pid):
        return self.m.detaylar[self.m.urunler[pid]["detail"]["id"]]["details"]

    def satir(self, pid):
        return dict(app.DBI.q("SELECT * FROM eknot WHERE pid=?", (pid,), one=True) or {})

    def sekmeler(self):
        return {r["pid"]: r for r in app.EKNOT.satirlar()}

    def bekle(self):
        for _ in range(200):
            if not app.EKNOT.running:
                return
            time.sleep(0.05)
        self.fail("ek not işi bitmedi")

    def test_grup_alt_kategorileri_kapsar(self):
        s = self.sekmeler()
        self.assertEqual({c for pid in s for c in json.loads(app.DBI.q("SELECT cats FROM catprod WHERE pid=?", (pid,), one=True)["cats"])},
                         {11, 12, 13})
        self.assertEqual(len(s), 90)
        self.assertTrue(all(r["sekme"] == "eklenecek" for r in s.values()))

    def test_kontrol_yazmaz(self):
        self.aciklama(1, "<p>Kısa açıklama</p>")
        self.assertIn("kontrol ediliyor", app.EKNOT.start("kontrol", [1, 2]))
        self.bekle()
        self.assertEqual([w for w in self.m.yazmalar() if w[1] != "product_details"], [])
        self.assertEqual(self.m.yazmalar(), [("POST", "product_details")])   # yalnızca testin kendi açıklaması
        self.assertEqual(self.satir(1)["mesaj"], "Not eklenebilir; SEO puanı değişmez.")

    def test_ekle_guncelle_kaldir(self):
        once = "<p>Darbeli matkap, sağlam gövde.</p>"
        self.aciklama(1, once)
        fiyat = self.m.urunler[1]["price1"]
        self.assertEqual(app.eknot_yaz(1, "ekle")[0], "eklendi")
        d = self.detay(1)
        self.assertTrue(d.startswith(once) and EN.var_mi(d))
        self.assertEqual(self.m.urunler[1]["price1"], fiyat)
        r = self.satir(1)
        self.assertEqual((r["durum"], r["yedek"]), ("eklendi", once))
        self.assertEqual(app.DBI.q("SELECT COUNT(*) n FROM olay WHERE tur='ek_not'", one=True)["n"], 1)
        self.assertEqual(app.eknot_yaz(1, "ekle"), ("eklendi", "Not zaten güncel."))
        # metin değişti: ürün "eski not" olur, güncellenince tek ve yeni not
        app.CFG.update(ek_not=dict(app.CFG.get("ek_not"), metin="Yeni not metni."))
        self.assertTrue(self.sekmeler()[1]["eski"])
        self.assertIn("güncelleniyor", app.EKNOT.start("guncelle"))
        self.bekle()
        d = self.detay(1)
        self.assertEqual((d.count(EN.ISARET), "Yeni not metni." in d, "kaydettirerek" in d), (1, True, False))
        self.assertFalse(self.sekmeler()[1]["eski"])
        # kaldırma: açıklamanın geri kalanı aynen
        self.assertEqual(app.eknot_yaz(1, "kaldir")[0], "kaldirildi")
        self.assertEqual(self.detay(1), once)
        self.assertEqual(self.sekmeler()[1]["sekme"], "eklenecek")

    def test_isaret_silinse_de_kaldirilir(self):
        self.aciklama(2, "<p>Açıklama</p>")
        app.eknot_yaz(2, "ekle")
        did = self.m.urunler[2]["detail"]["id"]
        self.m.detaylar[did]["details"] = self.detay(2).replace(f' id="{EN.ISARET}"', "")    # düzenleyici işareti sildi
        self.assertEqual(app.eknot_yaz(2, "kaldir")[0], "kaldirildi")
        self.assertEqual(self.detay(2), "<p>Açıklama</p>")

    def test_seo_orani_dusecekse_eklenmez(self):
        kw = "Darbeli Matkap"
        # metinde {urun} yok: not hedef kelimeyi tekrarlamaz, yalnızca açıklamayı uzatır
        app.CFG.update(ek_not=dict(app.CFG.get("ek_not"), metin="Ürününüzü üreticinin sitesinden kaydettirerek ek garanti kazanın."))
        self.m.urunler[3].update(name=f"Bosch {kw} 750W", targetKeyword=kw)
        for n in range(30, 400):                     # yoğunluğu %2'nin hemen üstünde bir açıklama
            html = f"<p>{kw} " + "kelime " * n + f"{kw}</p>"
            e = EN.etki(f"Bosch {kw} 750W", kw, html, EN.ekle(html, app.eknot_html(app.eknot_ayar(), kw)), app.SAFE_METHODS)
            if e["bozar"]:
                break
        else:
            self.fail("uygun açıklama bulunamadı")
        self.aciklama(3, html)
        yaz = len(self.m.yazmalar())
        self.assertEqual(app.eknot_yaz(3, "ekle")[0], "atlandi")
        self.assertEqual(len(self.m.yazmalar()), yaz)
        self.assertEqual(self.detay(3), html)
        self.assertEqual(self.sekmeler()[3]["sekme"], "atlandi")
        # toplu eklemede atlanan yeniden denenmez; seçilince denenir
        self.assertNotIn(3, [r["pid"] for r in app.EKNOT.satirlar() if r["sekme"] == "eklenecek"])

    def test_korunan_alan_degisirse_geri_yazilir(self):
        self.aciklama(4, "<p>Açıklama</p>")
        fiyat = self.m.urunler[4]["price1"]
        self.m.bozuk = True                                         # Ideasoft yazarken fiyatı bozuyor
        d, msg = app.eknot_yaz(4, "ekle")
        self.assertEqual(d, "hata")
        self.assertIn("Korunan alan", msg)
        self.assertEqual(self.m.urunler[4]["price1"], fiyat)

    def test_hedef_kelimeye_dokunulmaz(self):
        self.m.urunler[5]["targetKeyword"] = "Darbeli Matkap"
        self.aciklama(5, "<p>Açıklama</p>")
        app.eknot_yaz(5, "ekle")
        self.assertEqual(self.m.urunler[5]["targetKeyword"], "Darbeli Matkap")

    def test_haric_ve_yeni_urun(self):
        app.EKNOT.haric(6, True)
        s = self.sekmeler()
        self.assertEqual((s[6]["sekme"], s[6]["haric"]), ("atlandi", True))
        self.assertIn("eklenecek", app.EKNOT.durum()["items"][0]["sekme"])
        app.EKNOT.haric(6, False)
        self.assertEqual(self.sekmeler()[6]["sekme"], "eklenecek")
        # yeni ürün kategoriye girince "eklenecek"e düşer; başka kategorideki girmez
        yeni = self.m.ekle("Bosch Darbeli Matkap 900W", [11])
        baska = self.m.ekle("Stanley Yan Keski", [21])
        for pid in (yeni, baska):
            p = self.m.urunler[pid]
            app.DBI.x("INSERT INTO catprod(pid, sku, name, cats, brand, status) VALUES(?,?,?,?,?,?)",
                      (pid, p["sku"], p["name"], json.dumps([c["id"] for c in p["categories"]]), "", 1))
        s = self.sekmeler()
        self.assertEqual(s[yeni]["sekme"], "eklenecek")
        self.assertNotIn(baska, s)
        self.assertEqual(app.EKNOT.bekleyen(), 91)

    def test_kapaliyken_eklenmez(self):
        app.CFG.update(ek_not=dict(app.CFG.get("ek_not"), acik=False))
        self.assertEqual(app.EKNOT.start("ekle"), "Önce notu açın (sayfanın üstündeki düğme).")
        self.assertEqual(app.EKNOT.bekleyen(), 0)

    def test_notla_seo_hazirlama_ve_gonderim(self):
        p = self.m.urunler[7]
        app.DBI.x("INSERT INTO seo(pid, sku, name, ok) VALUES(?,?,?,0)", (7, p["sku"], p["name"]))
        self.aciklama(7, "<p>Eski açıklama</p>")
        plan = app.prepare_plan(7, ek_not_zorla=True)
        self.assertTrue(plan["ek_not"] and EN.var_mi(plan["details_html"]))
        self.assertTrue(2.0 <= plan["score"]["density"] <= 3.0)
        self.assertEqual(app.send_plan(7)[0], "gonderildi")
        self.assertEqual(self.satir(7)["durum"], "eklendi")
        # notu olan ürünün açıklaması yeniden hazırlanınca not kalır; olmayanınki notsuz
        self.assertTrue(EN.var_mi(app.prepare_plan(7)["details_html"]))
        app.DBI.x("INSERT INTO seo(pid, sku, name, ok) VALUES(8, 'HR-8', 'x', 0)")
        self.assertFalse(EN.var_mi(app.prepare_plan(8)["details_html"]))
        # SEO özgün hâline dönünce not kaydı da düşer
        self.assertEqual(app.seo_geri_al(7)[0], "uygulandi")
        self.assertEqual(self.satir(7)["durum"], "")

    def test_paket_kurali(self):
        self.assertEqual(app.WRITE_ROUTES["/api/eknot/yaz"], "ek_not")
        for yol in ("/api/eknot/kaldir", "/api/eknot/geri_al", "/api/eknot/baslat"):     # kaldırmak geri almadır
            self.assertNotIn(yol, app.WRITE_ROUTES)


if __name__ == "__main__":
    unittest.main()
