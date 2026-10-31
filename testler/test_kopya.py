"""Kopya ürün tespiti (kopya.py)."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kopya as KP  # noqa: E402


def urun(pid, name=None, **kw):
    u = {"pid": pid, "sku": f"S-{pid}", "name": name or f"Ürün {pid}", "barkod": f"86900000{pid:05d}",
         "baslik": f"Başlık {pid}", "meta": f"Meta {pid}", "aktif": 1}
    u.update(kw)
    return u


def turler(urunler):
    return sorted((g["tur"], tuple(x["pid"] for x in g["urunler"])) for g in KP.hesapla(urunler))


class Kopya(unittest.TestCase):
    def test_tekil_urunlerde_kopya_yok(self):
        self.assertEqual(KP.hesapla([urun(i) for i in range(30)]), [])

    def test_ayni_stok_kodu_bosluk_ve_harf_farkiyla(self):
        self.assertEqual(turler([urun(1, sku="hr-10"), urun(2, sku=" HR-10 ")]), [("ayni_sku", (1, 2))])

    def test_ayni_barkod_yer_tutucular_sayilmaz(self):
        self.assertEqual(turler([urun(1, barkod="8690001112223"), urun(2, barkod="8690001112223")]), [("ayni_barkod", (1, 2))])
        self.assertEqual(turler([urun(1, barkod="0000000"), urun(2, barkod="0000000"), urun(3, barkod="0"), urun(4, barkod="0")]), [])

    def test_ayni_ad_harf_noktalama_ve_sira_farkiyla(self):
        g = turler([urun(1, "Bosch Darbeli Matkap 750W"), urun(2, "bosch  darbeli MATKAP, 750W"), urun(3, "Darbeli Matkap Bosch 750W")])
        self.assertEqual(g, [("ayni_ad", (1, 2, 3))])

    def test_turkce_buyuk_harf(self):
        self.assertEqual(turler([urun(1, "IŞIKLI AYNA"), urun(2, "ışıklı ayna")]), [("ayni_ad", (1, 2))])

    def test_farkli_marka_ya_da_renk_kopya_sayilmaz(self):
        self.assertEqual(turler([urun(1, "Bosch Darbeli Matkap"), urun(2, "Makita Darbeli Matkap"),
                                 urun(3, "Kadın Siyah Elbise"), urun(4, "Kadın Kırmızı Elbise")]), [])

    def test_pasif_urunlerde_ad_aranmaz_ama_stok_kodu_aranir(self):
        self.assertEqual(turler([urun(1, "Aynı Ad", aktif=0), urun(2, "Aynı Ad")]), [])
        self.assertEqual(turler([urun(1, sku="X", aktif=0), urun(2, sku="X")]), [("ayni_sku", (1, 2))])

    def test_ayni_baslik_ve_meta(self):
        self.assertEqual(turler([urun(1, baslik="Matkap | Mağaza"), urun(2, baslik="matkap |  mağaza")]), [("ayni_baslik", (1, 2))])
        self.assertEqual(turler([urun(1, meta="Hemen inceleyin."), urun(2, meta="Hemen inceleyin.")]), [("ayni_meta", (1, 2))])

    def test_ayni_kume_iki_kez_bildirilmez(self):
        # aynı ad → genellikle aynı başlık; yalnızca "aynı ad" olarak bildirilir
        g = turler([urun(1, "Termos 500 ml", baslik="Termos"), urun(2, "Termos 500 ml", baslik="Termos")])
        self.assertEqual(g, [("ayni_ad", (1, 2))])

    def test_bos_degerler_gruplanmaz(self):
        self.assertEqual(turler([urun(1, sku="", barkod=None, baslik="", meta=None), urun(2, sku="", barkod=None, baslik="", meta=None)]), [])

    def test_buyuk_grup_once_ve_mesaj(self):
        g = KP.hesapla([urun(1, "A"), urun(2, "A"), urun(3, "B"), urun(4, "B"), urun(5, "B")])
        self.assertEqual([len(x["urunler"]) for x in g], [3, 2])
        self.assertIn("3 yayındaki ürün", g[0]["mesaj"])

    def test_buyuk_magazada_hizli(self):
        t = time.time()
        KP.hesapla([urun(i, f"Ürün {i % 5000}") for i in range(20000)])
        self.assertLess(time.time() - t, 3)


if __name__ == "__main__":
    unittest.main()
