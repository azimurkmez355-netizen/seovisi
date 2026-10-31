"""Ürün uyarıları (uyari.py): fiyat hataları ve yayında olup satılamayan ürünler."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uyari as UY  # noqa: E402


def urun(pid, fiyat=100.0, **kw):
    u = {"pid": pid, "sku": f"S-{pid}", "name": f"Ürün {pid}", "fiyat": fiyat, "satis": fiyat, "alis": None, "indirim": 0,
         "indirim_tip": 0, "stok": 5, "aktif": 1, "secenekli": 0, "para": "TL", "kats": [1]}
    u.update(kw)
    return u


def turler(urunler):
    return {(x["pid"], x["tur"]) for x in UY.hesapla(urunler)}


class Fiyat(unittest.TestCase):
    def test_saglam_urunde_uyari_yok(self):
        self.assertEqual(UY.hesapla([urun(i, 100 + i) for i in range(20)]), [])

    def test_fiyati_sifir(self):
        self.assertEqual(turler([urun(1, 0, satis=0)]), {(1, "fiyat_yok")})

    def test_yuzde_indirim(self):
        self.assertEqual(turler([urun(1, indirim=100, indirim_tip=1, satis=0)]), {(1, "indirim")})
        self.assertIn("çok yüksek", UY.hesapla([urun(1, indirim=95, indirim_tip=1, satis=5)])[0]["mesaj"])
        self.assertEqual(turler([urun(1, indirim=30, indirim_tip=1, satis=70)]), set())

    def test_fiyat_tipi_indirim(self):
        self.assertIn("düşük değil", UY.hesapla([urun(1, 100, indirim=120)])[0]["mesaj"])
        self.assertIn("%5'i", UY.hesapla([urun(1, 100, indirim=5, satis=5)])[0]["mesaj"])
        self.assertEqual(turler([urun(1, 100, indirim=80, satis=80)]), set())

    def test_alis_fiyatinin_altinda(self):
        self.assertEqual(turler([urun(1, 100, alis=120)]), {(1, "zarar")})
        self.assertEqual(turler([urun(1, 100, alis=60)]), set())

    def test_benzerlerine_gore_asiri_fiyat(self):
        tek = [urun(i, 100 + i) for i in range(10)]
        self.assertEqual(turler(tek + [urun(50, 14990)]), {(50, "uc_fiyat")})       # 149,90 yerine 14.990
        self.assertEqual(turler(tek + [urun(51, 9.99)]), {(51, "uc_fiyat")})         # 99,90 yerine 9,99
        self.assertIn("katı", [x for x in UY.hesapla(tek + [urun(50, 14990)])][0]["mesaj"])

    def test_az_urunlu_kategoride_ve_farkli_parada_karsilastirilmaz(self):
        self.assertEqual(turler([urun(i, 100) for i in range(5)] + [urun(9, 5000)]), set())
        self.assertEqual(turler([urun(i, 100) for i in range(10)] + [urun(9, 5000, para="EUR")]), set())

    def test_en_ozel_kategoriye_gore(self):
        genel = [urun(i, 1000, kats=[1]) for i in range(20)]                     # pahalı ürünler, üst kategori
        ozel = [urun(100 + i, 10, kats=[1, 2]) for i in range(10)]                # ucuz alt kategori
        self.assertEqual(turler(genel + ozel), set())                               # alt kategorideki ortancaya göre


class Satilamaz(unittest.TestCase):
    def test_stokta_yok(self):
        self.assertEqual(turler([urun(1, stok=0)]), {(1, "stok_yok")})

    def test_secenekli_urunun_stogu_varyantlarda(self):
        self.assertEqual(turler([urun(1, stok=0, secenekli=1)]), set())

    def test_pasif_urun_denetlenmez(self):
        self.assertEqual(turler([urun(1, 0, satis=0, stok=0, aktif=0)]), set())

    def test_bilinmeyen_alan_kurali_atlatir(self):
        self.assertEqual(turler([urun(1, None, satis=None, stok=None)]), set())


class Sira(unittest.TestCase):
    def test_once_fiyat_sonra_stok(self):
        out = UY.hesapla([urun(1, stok=0), urun(2, 0, satis=0), urun(3, 100, alis=150)])
        self.assertEqual([x["tur"] for x in out], ["fiyat_yok", "zarar", "stok_yok"])

    def test_turk_lirasi_bicimi(self):
        self.assertEqual(UY.tl(14990.5, "TL"), "14.990,50 TL")


if __name__ == "__main__":
    unittest.main()
