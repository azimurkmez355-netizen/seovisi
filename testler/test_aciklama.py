"""Açıklama üreticisi (seo_machine.py) ve yeni kategori SEO bilgileri (kategori.py).

Üretilen her açıklama Ideasoft'un SEO kurallarına uymalı: hedef kelime ürün adında, açıklamada,
başlıkta ve metada geçer; yoğunluk %2–3 arasında; en az 60 kelime."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kategori as KT  # noqa: E402
import seo_machine as SM  # noqa: E402
import seo_text as ST  # noqa: E402

PROF = {"magaza": "Deneme Hırdavat", "marka": ""}

URUNLER = [
    {"name": "Bosch GSB 18V-50 Akülü Darbeli Matkap", "brand": {"id": 1, "name": "Bosch"},
     "categories": [{"id": 11, "name": "Matkaplar"}]},
    {"name": "Kadın Çiçek Desenli Midi Elbise 36-44 Beden", "categories": [{"id": 5, "name": "Elbiseler"}]},
    {"name": "Porselen 6'lı Çay Bardağı Takımı", "categories": []},
    {"name": "Organik   Lavanta  Yağı 50 ml", "categories": [{"id": 9, "name": "Uçucu Yağlar"}]},
]

ESKI = """<h2>Teknik Özellikler</h2><table><tr><td>Güç</td><td>750 W</td></tr>
<tr><td>Devir</td><td>0-3000 dev/dk</td></tr></table>
<h2>Paket İçeriği</h2><ul><li>1 adet matkap</li><li>Taşıma çantası</li></ul>
<p>Deneme Hırdavat güvencesiyle.</p>"""


class Aciklama(unittest.TestCase):
    def kur(self, p, details="", **kw):
        return SM.build_machine_seo(p, details, sku="SKU-1", barcode="869000", method="panel", prof=PROF, **kw)

    def test_seo_kurallarina_uyar(self):
        for p in URUNLER:
            with self.subTest(p["name"]):
                plan = self.kur(p)
                kw = plan["keyword"]
                ad = " ".join(p["name"].split())
                self.assertIn(ST.tr_lower(kw), ST.tr_lower(ad))
                self.assertIn(ST.tr_lower(kw), ST.tr_lower(plan["pageTitle"]))
                self.assertIn(ST.tr_lower(kw), ST.tr_lower(plan["metaDescription"]))
                self.assertTrue(20 <= len(plan["pageTitle"]) <= 60, plan["pageTitle"])
                self.assertTrue(50 <= len(plan["metaDescription"]) <= 155, plan["metaDescription"])
                d = plan["densities"]["panel"]
                self.assertTrue(2.0 <= d <= 3.0, d)
                self.assertGreaterEqual(ST.count_words(plan["details_html"], "panel"), 50)

    def test_ayni_urun_ayni_aciklama(self):
        self.assertEqual(self.kur(URUNLER[0])["details_html"], self.kur(URUNLER[0])["details_html"])

    def test_farkli_varyant_farkli_aciklama(self):
        self.assertNotEqual(self.kur(URUNLER[0], variant=0)["details_html"],
                            self.kur(URUNLER[0], variant=1)["details_html"])

    def test_mevcut_aciklamadaki_bilgiler_korunur(self):
        plan = self.kur(URUNLER[0], ESKI)
        self.assertEqual(plan["found"]["spec"], 2)
        self.assertEqual(plan["found"]["pkg"], 2)
        metin = ST.strip_tags(plan["details_html"])
        for s in ("750 W", "0-3000 dev/dk", "Taşıma çantası"):
            self.assertIn(s, metin)

    def test_urun_adindaki_html_zararsiz_hale_gelir(self):
        plan = self.kur({"name": "Kupa <script>alert(1)</script> Bardak Seti", "categories": []})
        self.assertNotIn("<script", plan["details_html"])

    def test_magazaya_ozel_renk_yok(self):
        for p in URUNLER:
            h = self.kur(p)["details_html"]
            self.assertNotIn("1b4f72", h)
            self.assertNotIn("background", h)

    def test_stok_kodu_ve_barkod_eklenir(self):
        metin = ST.strip_tags(self.kur(URUNLER[1])["details_html"])
        self.assertIn("SKU-1", metin)
        self.assertIn("869000", metin)


class EskiAciklamaOkuma(unittest.TestCase):
    def test_bolumler_ayrilir(self):
        spec, pkg, use, feat = SM.read_existing(ESKI, store="Deneme Hırdavat")
        self.assertEqual([s[0] for s in spec], ["Güç: 750 W", "Devir: 0-3000 dev/dk"])
        self.assertEqual(pkg, ["1 adet matkap", "Taşıma çantası"])

    def test_bozuk_html_hata_vermez(self):
        SM.read_existing("<table><tr><td>Güç<td>750 W</h2><<<")
        SM.read_existing(None)


class OnarimVeTeshis(unittest.TestCase):
    def test_guvenli_kelime_ozel_karakter_icermez(self):
        for name in ("Philips® Sonicare: Diş Fırçası (2 Adet)", "Tefal & Moulinex Tost Makinesi"):
            kw = SM.safe_keyword(name)
            self.assertTrue(kw)
            self.assertFalse(set(kw) & set(SM.RISKY), kw)
            self.assertIn(ST.tr_lower(kw), ST.tr_lower(name))

    def test_teshis_bos_kelimeyi_bulur(self):
        self.assertEqual(SM.diagnose("Ürün", "", "", "", "", 1.3), ["Hedef kelime boş."])

    def test_teshis_bosluk_sorununu_bulur(self):
        self.assertTrue(any("boşluk" in x for x in SM.diagnose("Ürün  Adı", "Ürün Adı", "", "", "", 1.3)))


class KategoriSeo(unittest.TestCase):
    def test_yeni_kategori_tam_puan(self):
        for ad in ("Darbeli Matkaplar", "Elbise", "Çok Uzun Bir Kategori Adı Ki Başlığa Sığması Zor Olsun"):
            with self.subTest(ad):
                s = KT.category_seo(ad, "Elektrikli Aletler", ["a", "b"], {"magaza": "Deneme Hırdavat"})
                self.assertEqual(s["check"]["pct"], 100, s)

    def test_adres_turkce_karaktersiz(self):
        self.assertEqual(KT._slug("Çiğ Şöğüt Ürünleri!"), "cig-sogut-urunleri")
        self.assertEqual(KT._slug("!!!"), "kategori")


if __name__ == "__main__":
    unittest.main()
