"""Açıklama şablonu (sablon.py) ve açıklama üreticisinin şablona uyması (seo_machine.py).

En önemli iki kural:
  - varsayılan şablon (sade ve Ustapazar'ın lacivert bantlı görünümü) bugüne kadarki açıklamaları birebir üretir,
  - her görünüm ve her renk, panel katsayısının ölçüldüğü görünümle aynı sayıda kelime üretir (SEO yüzdesi kaymaz)."""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sablon as TPL  # noqa: E402
import seo_machine as SM  # noqa: E402
import seo_text as ST  # noqa: E402

ESKI = ("<h2>Öne Çıkan Özellikler</h2><ul><li>Kömür fırçasız motor</li><li>LED çalışma ışığı</li></ul>"
        "<h2>Teknik Özellikler</h2><table><tr><td>Güç</td><td>750 W</td></tr><tr><td>Devir</td><td>0-3000 dev/dk</td></tr>"
        "</table><h2>Kullanım Alanları</h2><ul><li>Ahşap delme</li><li>Metal delme</li></ul>"
        "<h2>Paket İçeriği</h2><ul><li>1 adet matkap</li><li>Taşıma çantası</li></ul>")
DURUMLAR = [
    ({"name": "Bosch GSB 18V-50 Akülü Darbeli Matkap", "brand": {"name": "Bosch"}, "categories": [{"id": 1, "name": "Matkaplar"}]},
     ESKI, "HR-7", "8690001", {"magaza": "Deneme Hırdavat", "marka": ""}, 0),
    ({"name": "Kadın Çiçek Desenli Midi Elbise 36-44 Beden", "categories": [{"id": 5, "name": "Elbiseler"}]},
     "", "MD-1", "", {"magaza": "Moda Evi", "marka": ""}, 1),
    ({"name": "Organik Lavanta Yağı 50 ml", "categories": []}, "<p>Doğal ürün.</p>", "", "", {"magaza": "", "marka": "Doğa"}, 0),
    ({"name": "Paslanmaz Çelik Termos 500 ml", "categories": [{"id": 0, "name": "Termoslar"}]},
     ESKI, "ORNEK-1", "869", {"magaza": "X", "marka": ""}, 2),
]
# Şablon sistemi gelmeden önceki üreticinin çıktıları (sade, sonra bantlı; her durum için iki sayım yöntemi)
ONCEKI = ["40db16737add", "f3b30e9c921f", "8e6c29555544", "ae3e5960a4fa", "64d3eb835307", "6a0a9d905a00", "ae976f80ae16",
          "ae976f80ae16", "ea23cbedfe31", "5802f7371477", "c720229eb9d1", "a8ba37477a3b", "237734b6f7ab", "5aaad06e046d",
          "ad6493622607", "ad6493622607"]


def kur(sablon, durum=0, method="panel"):
    p, d, sku, bc, prof, v = DURUMLAR[durum]
    return SM.build_machine_seo(p, d, sku=sku, barcode=bc, method=method, prof=prof, variant=v, sablon=sablon)


class VarsayilanDegismez(unittest.TestCase):
    def test_bugunku_aciklamalar_birebir(self):
        out = [hashlib.md5(kur({"gorunum": g}, i, m)["details_html"].encode()).hexdigest()[:12]
               for g in ("sade", "bantli") for i in range(len(DURUMLAR)) for m in ("panel", "panel_lo,panel,panel_hi")]
        self.assertEqual(out, ONCEKI)

    def test_bos_sablon_sade(self):
        self.assertEqual(kur(None)["details_html"], kur({"gorunum": "sade"})["details_html"])


class SeoKaymaz(unittest.TestCase):
    RENKLER = ("#1b4f72", "#c0392b", "#ffff00", "#ffffff", "#000000", "#2f4bf0")

    def test_her_gorunum_ve_renk_ayni_sayida_kelime(self):
        for g in TPL.GORUNUMLER:
            for r in self.RENKLER:
                for m in TPL.MADDELER:
                    st = TPL.stiller(TPL.yukle({"gorunum": g, "renk": r, "madde": m}))
                    for k, v in st.items():
                        self.assertEqual(ST._ascii_split(v), TPL.STYLE_WORDS[k], (g, r, m, k, v))

    def test_ayni_icerik_her_gorunumde_ayni_panel_sayimi(self):
        for i in range(len(DURUMLAR)):
            say = {ST.count_words(kur({"gorunum": g, "renk": r, "madde": m}, i)["details_html"], "panel")
                   for g in TPL.GORUNUMLER for r in ("#e67e22",) for m in ("✔", "")}
            self.assertEqual(len(say), 1, (i, say))

    def test_bolum_ayarlari_yogunlugu_bozmaz(self):
        kapali = lambda *ks: {"bolumler": [{"k": k, "acik": False} for k in ks]}   # noqa: E731
        for t in (kapali("neden"), kapali("one_cikan", "neden"), kapali("kullanim", "paket"),
                  {"kapanis": {"acik": False}}, {"stok_kodu": False, "barkod": False}):
            for i in range(len(DURUMLAR)):
                d = kur(t, i)["densities"]["panel"]
                self.assertTrue(2.0 <= d <= 3.0, (t, i, d))


class Ayarlar(unittest.TestCase):
    def test_gecersiz_degerler_duzeltilir(self):
        t = TPL.yukle({"gorunum": "yok", "renk": "kırmızı", "madde": "<b>", "bolumler": "x", "kapanis": 5, "stok_kodu": "evet"})
        self.assertEqual((t["gorunum"], t["renk"], t["madde"]), ("sade", "#1b4f72", "✔"))
        self.assertEqual([b["k"] for b in t["bolumler"]], [k for k, _ in TPL.BOLUMLER])
        self.assertEqual(t["kapanis"], {"acik": True, "metin": ""})
        self.assertTrue(t["stok_kodu"])

    def test_renk_bicimi(self):
        self.assertEqual(TPL.renk_duzelt("#ABC"), "#aabbcc")
        self.assertEqual(TPL.renk_duzelt(" #C0392B "), "#c0392b")
        for x in ("red", "#12345", "#gggggg", None, 5, "#c0392b;x:y"):
            self.assertIsNone(TPL.renk_duzelt(x), x)

    def test_bolum_sirasi_ve_eksikler(self):
        t = TPL.yukle({"bolumler": [{"k": "paket"}, {"k": "teknik", "acik": False, "baslik": "  Ürün   Bilgileri "},
                                    {"k": "paket"}, {"k": "uydurma"}]})
        self.assertEqual([b["k"] for b in t["bolumler"]], ["paket", "teknik", "one_cikan", "kullanim", "neden"])
        self.assertEqual(t["bolumler"][1], {"k": "teknik", "acik": False, "baslik": "Ürün Bilgileri"})
        uzun = TPL.yukle({"bolumler": [{"k": "neden", "baslik": "x" * 200}]})["bolumler"][0]["baslik"]
        self.assertEqual(len(uzun), TPL.BASLIK_UZUNLUK)

    def test_kismi_degisiklik_digerlerini_korur(self):
        eski = {"gorunum": "kutulu", "renk": "#c0392b", "madde": "•"}
        self.assertEqual(TPL.birlestir(eski, {"madde": "→", "zararli": 1}), {"gorunum": "kutulu", "renk": "#c0392b", "madde": "→"})

    def test_acik_renkte_yazi_okunur(self):
        self.assertIn("color:#222", TPL.stiller(TPL.yukle({"gorunum": "bantli", "renk": "#ffff00"}))["h"])
        self.assertIn("color:#fff", TPL.stiller(TPL.yukle({"gorunum": "bantli", "renk": "#1b4f72"}))["h"])
        self.assertIn("color:#333", TPL.stiller(TPL.yukle({"gorunum": "cizgili", "renk": "#ffff99"}))["h"])


class Uretim(unittest.TestCase):
    def test_bolum_kapatma_siralama_ve_baslik(self):
        h = kur({"bolumler": [{"k": "paket", "baslik": "Kutuda Neler Var?"}, {"k": "kullanim", "acik": False},
                              {"k": "neden", "acik": False}]})["details_html"]
        self.assertNotIn("Kullanım Alanları", h)
        self.assertNotIn("Neden Tercih", h)
        self.assertLess(h.index("Kutuda Neler Var?"), h.index("Öne Çıkan Özellikler"))

    def test_basliktaki_html_zararsiz(self):
        h = kur({"bolumler": [{"k": "teknik", "baslik": "<script>alert(1)</script>"}]})["details_html"]
        self.assertNotIn("<script>", h)
        self.assertIn("&lt;script&gt;", h)

    def test_madde_isareti(self):
        self.assertIn("<li>• ", kur({"madde": "•"})["details_html"])
        h = kur({"madde": ""})["details_html"]
        self.assertNotIn("✔", h)
        self.assertIn("list-style:disc", h)

    def test_kendi_kapanis_metni(self):
        h = kur({"kapanis": {"metin": "{urun} için {magaza} ekibine <yazın>."}})["details_html"]
        kw = kur({})["keyword"]                           # hedef kelime (marka adı başta tekrarlanmaz)
        self.assertIn(f"{kw} için <strong>Deneme Hırdavat</strong> ekibine &lt;yazın&gt;.", h)

    def test_kapanis_kapali_stok_kodu_kalir(self):
        h = kur({"gorunum": "bantli", "kapanis": {"acik": False}})["details_html"]
        self.assertNotIn("border-left", h)
        self.assertIn("<p>Stok kodu: HR-7 Barkod: 8690001</p>", h)

    def test_stok_kodu_ve_barkod_gizlenir(self):
        h = ST.strip_tags(kur({"stok_kodu": False, "barkod": False})["details_html"])
        self.assertNotIn("Stok kodu", h)
        self.assertNotIn("Barkod", h)


class TemaRengi(unittest.TestCase):
    def test_theme_color_etiketi(self):
        self.assertEqual(TPL.tema_rengi('<meta name="theme-color" content="#E74C3C">'), "#e74c3c")
        self.assertEqual(TPL.tema_rengi('<meta content="#0a6" name="theme-color">'), "#00aa66")

    def test_stillerde_en_sik_canli_renk(self):
        sayfa = ("<style>a{color:#c0392b} .b{background:#c0392b} body{color:#333;background:#fff}</style>"
                 '<div style="border-color:#2980b9"></div>')
        self.assertEqual(TPL.tema_rengi(sayfa), "#c0392b")

    def test_bulunamazsa_none(self):
        self.assertIsNone(TPL.tema_rengi("<style>body{color:#000;background:#fff;border:#eee}</style>"))


if __name__ == "__main__":
    unittest.main()
