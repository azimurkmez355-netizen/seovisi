"""Metin üreticileri: hedef kelime, başlık, meta açıklama, SEO puanı, mağaza profili ve Türkçe ekler.

Çalıştırma: python -X utf8 testler/hepsi.py   (ya da yalnızca bu dosya: python -X utf8 -m unittest testler.test_seo_metin)"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import profil as PR  # noqa: E402
import seo_text as ST  # noqa: E402

PROF = {"magaza": "Deneme Hırdavat", "marka": "Bosch"}


class Yardimcilar(unittest.TestCase):
    def test_turkce_kucuk_harf(self):
        self.assertEqual(ST.tr_lower("IŞIK İĞNE"), "ışık iğne")

    def test_etiketler_ve_kodlar_temizlenir(self):
        h = "<p>Merhaba&nbsp;<b>dünya</b></p><script>x()</script><li>Bir</li>"
        self.assertEqual(ST.strip_tags(h), "Merhaba dünya Bir")

    def test_hedef_kelime_sayimi_buyuk_kucuk_harf_duyarsiz(self):
        self.assertEqual(ST.count_kw("Midi Elbise güzel. MİDİ ELBİSE uygun.", "midi elbise"), 2)
        self.assertEqual(ST.count_kw("bir şey", ""), 0)

    def test_yogunluk(self):
        self.assertAlmostEqual(ST.density("a b c d kelime", "kelime"), 20.0)
        self.assertEqual(ST.density("", "x"), 0.0)


class HedefKelime(unittest.TestCase):
    def test_olcu_bilgisinden_once_kesilir(self):
        self.assertEqual(ST.extract_keyword("Kadın Çiçek Desenli Midi Elbise 36-44 Beden"),
                         "Kadın Çiçek Desenli Midi Elbise")

    def test_her_zaman_urun_adinda_gecer(self):
        for name in ("Bosch GSB 18V-50 Akülü Darbeli Matkap", "Philips (2 Adet) Ampul", "X", "Çay Bardağı 6'lı Set",
                     "Samsung 55\" QLED TV", "  Boşluklu   Ürün   Adı  "):
            kw = ST.extract_keyword(name)
            self.assertIn(ST.tr_lower(kw), ST.tr_lower(" ".join(name.split())), name)

    def test_bos_ad(self):
        self.assertEqual(ST.extract_keyword(""), "")


class BaslikVeMeta(unittest.TestCase):
    def test_baslik_20_60_karakter(self):
        for name in ("Kısa Ad", "Bosch Darbeli Matkap 750W Profesyonel",
                     "Çok Uzun Bir Ürün Adı Ki Altmış Karakteri Rahatlıkla Geçer Ve Kesilmesi Gerekir"):
            kw = ST.extract_keyword(name)
            t = ST.make_title(name, kw, PROF)
            self.assertTrue(20 <= len(t) <= 60, (name, t))

    def test_meta_50_155_karakter_ve_hedef_kelimeyi_icerir(self):
        for kw in ("Darbeli Matkap", "Kadın Çiçek Desenli Midi Elbise"):
            m = ST.make_meta(kw, "matkap", [], random.Random(1), PROF)
            self.assertTrue(50 <= len(m) <= 155, m)
            self.assertIn(kw, m)

    def test_magaza_adi_yoksa_bos_yer_tutucu_kalmaz(self):
        m = ST.make_meta("Darbeli Matkap", "matkap", [], random.Random(1), {})
        self.assertNotIn("{", m)
        self.assertNotIn("  ", m)

    def test_anahtar_kelimelerde_tekrar_yok(self):
        k = ST.make_keywords("Darbeli Matkap", "darbeli matkap", "matkap", PROF).split(", ")
        self.assertEqual(len(k), len({ST.tr_lower(x) for x in k}))


class Puan(unittest.TestCase):
    def test_eksiksiz_urun_tam_puan(self):
        kw = "Darbeli Matkap"
        body = "<p>" + " ".join([kw] + ["kelime"] * 38 + [kw] + ["söz"] * 38) + "</p>"
        s = ST.seo_score("Bosch Darbeli Matkap 750W", kw, body, "Bosch Darbeli Matkap 750W | Deneme",
                         f"{kw} modelleri uygun fiyatla Deneme Hırdavat'ta. Hemen inceleyin.")
        self.assertEqual((s["top"], s["bottom"]), (100, 100), s["fails"])

    def test_bos_urun_dusuk_puan_ve_sebepler(self):
        s = ST.seo_score("Ürün", "", "", "", "")
        self.assertLess(s["top"], 50)
        self.assertEqual(s["bottom"], 0)
        self.assertIn("Hedef kelime tanımlı", s["fails"])


class Profil(unittest.TestCase):
    def test_bulunma_eki(self):
        for ad, ek in (("Butik", "Butik'te"), ("Pazar", "Pazar'da"), ("Moda Evi", "Moda Evi'nde"),
                       ("Güzellik Dünyası", "Güzellik Dünyası'nda"), ("Kitap", "Kitap'ta")):
            self.assertEqual(PR.loc(ad), ek)

    def test_iyelik_eki(self):
        for ad, ek in (("Philips", "Philips'in"), ("Koton", "Koton'un"), ("Mavi", "Mavi'nin"), ("Bosch", "Bosch'un")):
            self.assertEqual(PR.gen(ad), ek)

    def test_eksik_profil_tamamlanir(self):
        self.assertEqual(PR.load({"magaza": "  A  ", "fazla": 1}), {"magaza": "A", "marka": ""})

    def test_urunun_kendi_markasi_once_gelir(self):
        self.assertEqual(PR.with_brand(PROF, {"brand": {"id": 3, "name": "Makita"}})["marka"], "Makita")
        self.assertEqual(PR.with_brand(PROF, {"brand": None})["marka"], "Bosch")

    def test_karsiligi_olmayan_sablon_secilmez(self):
        self.assertEqual(PR.pick(["{marka} ürünü", "{magaza} mağazası"], {"magaza": "A", "marka": ""}), ["A mağazası"])

    def test_suslu_parantezli_ad_bozulmaz(self):
        self.assertEqual(PR.fill("Set {x} {magaza}", {"magaza": "A", "marka": ""}), "Set {x} A")


if __name__ == "__main__":
    unittest.main()
