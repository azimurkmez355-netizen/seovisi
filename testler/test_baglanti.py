"""Kırık bağlantı taraması (baglanti.py): bellekteki uydurma bir siteyle, ağsız."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import baglanti as BG  # noqa: E402

K = "https://magaza.com"


class Site:
    """{adres: (durum, içerik türü, metin)}; olmayan adres 404. İstekler kaydedilir."""

    def __init__(self, sayfalar):
        self.sayfalar, self.istekler = sayfalar, []

    def getir(self, url, govde=True):
        self.istekler.append((url, govde))
        st, ct, txt = self.sayfalar.get(url, (404, "text/html", "yok"))
        return st, ct, txt if govde else "", url


def html(*govde):
    return (200, "text/html; charset=utf-8", "<html><body>" + "".join(govde) + "</body></html>")


def tara(site, **kw):
    return BG.tara(K, site.getir, bekle=0, **kw)


def kiriklar(sonuc):
    return {(k["url"], k["tur"]) for k in sonuc["kirik"]}


class Tarama(unittest.TestCase):
    def test_kirik_sayfa_gorsel_ve_dis_baglanti(self):
        s = Site({K + "/": html('<a href="/urun-1">Ürün 1</a> <a href="/yok">Eski kampanya</a>',
                                '<img src="/resim/var.jpg"><img src="/resim/yok.jpg" alt="x">',
                                '<a href="https://disari.com/yok">Tedarikçi</a> <a href="https://disari.com/var">Ok</a>'),
                  K + "/urun-1": html("<p>ürün</p>"), K + "/resim/var.jpg": (200, "image/jpeg", ""),
                  "https://disari.com/var": (200, "text/html", "")})
        r = tara(s)
        self.assertEqual(kiriklar(r), {(K + "/yok", "sayfa"), (K + "/resim/yok.jpg", "gorsel"), ("https://disari.com/yok", "dis")})
        yok = next(k for k in r["kirik"] if k["url"] == K + "/yok")
        self.assertEqual((yok["durum"], yok["kaynaklar"]), (404, [{"sayfa": K + "/", "metin": "Eski kampanya"}]))
        self.assertEqual(r["sayfa"], 3)                                 # ana sayfa, ürün, kırık sayfa

    def test_site_haritasindaki_kirik_sayfa_isaretlenir(self):
        s = Site({K + "/": html("<p>ana</p>"),
                  K + "/sitemap.xml": (200, "application/xml", "<sitemapindex><sitemap><loc>https://magaza.com/s1.xml</loc></sitemap></sitemapindex>"),
                  K + "/s1.xml": (200, "application/xml", "<urlset><url><loc>https://magaza.com/a</loc></url><url><loc>https://magaza.com/silinmis</loc></url></urlset>"),
                  K + "/a": html("<p>a</p>")})
        r = tara(s)
        self.assertEqual(kiriklar(r), {(K + "/silinmis", "sayfa")})
        self.assertTrue(r["kirik"][0]["site_haritasi"])

    def test_robots_izin_vermeyen_adrese_gidilmez(self):
        s = Site({K + "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /hesabim"),
                  K + "/": html('<a href="/hesabim/siparisler">Siparişlerim</a><a href="/b">B</a>'), K + "/b": html("")})
        r = tara(s)
        self.assertNotIn(K + "/hesabim/siparisler", [u for u, _ in s.istekler])
        self.assertEqual(r["kirik"], [])

    def test_sorgulu_adresler_ve_baska_siteler_gezilmez(self):
        s = Site({K + "/": html('<a href="/kategori?sirala=fiyat">Sırala</a><a href="https://baska.com/sayfa">Dış</a>')})
        tara(s, dis=False)
        gidilen = [u for u, _ in s.istekler]
        self.assertNotIn(K + "/kategori?sirala=fiyat", gidilen)
        self.assertNotIn("https://baska.com/sayfa", gidilen)

    def test_dis_baglanti_yalnizca_durum_icin_istenir_gezilmez(self):
        s = Site({K + "/": html('<a href="https://baska.com/a">Dış</a>'),
                  "https://baska.com/a": html('<a href="https://baska.com/b">B</a>')})
        tara(s)
        self.assertIn(("https://baska.com/a", False), s.istekler)          # gövdesiz, yalnızca durum
        self.assertNotIn("https://baska.com/b", [u for u, _ in s.istekler])

    def test_sayfa_siniri(self):
        s = Site({K + "/": html(*[f'<a href="/u{i}">u</a>' for i in range(50)]), **{f"{K}/u{i}": html("") for i in range(50)}})
        r = tara(s, sinir=10)
        self.assertLessEqual(r["sayfa"], 10)
        self.assertTrue(r["sinira_ulasti"])

    def test_durdurulabilir(self):
        s = Site({K + "/": html(*[f'<a href="/u{i}">u</a>' for i in range(20)])})
        n = [0]

        def dur():
            n[0] += 1
            return n[0] > 3
        r = tara(s, dur=dur)
        self.assertTrue(r["durduruldu"])
        self.assertLess(r["sayfa"], 5)

    def test_ulasilamayan_adres_kirik_sayilir(self):
        s = Site({K + "/": html('<a href="/zaman-asimi">x</a>'), K + "/zaman-asimi": (0, "", "")})
        self.assertEqual(kiriklar(tara(s)), {(K + "/zaman-asimi", "sayfa")})

    def test_www_ayni_site_sayilir(self):
        s = Site({K + "/": html('<a href="https://www.magaza.com/x">x</a>'), "https://www.magaza.com/x": html("")})
        tara(s)
        self.assertIn(("https://www.magaza.com/x", True), s.istekler)          # gezildi (gövdeyle)


class Guvenlik(unittest.TestCase):
    def test_ic_ag_adresine_istek_gonderilmez(self):
        from unittest import mock
        import app
        with mock.patch.object(app, "public_host", return_value=False), \
                mock.patch.object(app.urllib.request.OpenerDirector, "open") as op:
            getir = app.site_getirici()
            for u in ("http://169.254.169.254/latest/meta-data/", "http://localhost:8765/api/state", "https://10.0.0.5/"):
                self.assertEqual(getir(u), (0, "", "", u))
        op.assert_not_called()

    def test_alan_adi_denetimi_tarama_boyunca_bir_kez(self):
        from unittest import mock
        import app
        with mock.patch.object(app, "public_host", return_value=False) as ph:
            getir = app.site_getirici()
            for i in range(5):
                getir(f"https://magaza.com/u{i}")
        self.assertEqual(ph.call_count, 1)


class Linkler(unittest.TestCase):
    def test_goreli_adres_base_ve_parca(self):
        out = BG.linkler('<base href="https://magaza.com/kategori/"><a href="urun#yorum">Ürün</a>'
                         '<a href="mailto:a@b.c">m</a><a href="tel:1">t</a><a href="javascript:void(0)">j</a><a href="#ust">ü</a>',
                         K + "/")
        self.assertEqual(out, [("a", "https://magaza.com/kategori/urun", "Ürün")])

    def test_bozuk_html_hata_vermez(self):
        BG.linkler("<a href='/x'>yarım <img src=", K + "/")
        BG.linkler(None, K + "/")


if __name__ == "__main__":
    unittest.main()
