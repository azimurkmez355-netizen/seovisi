"""Platform adaptörü sınırı: Ideasoft'a özgü adresler ve istekler yalnızca platformlar/ideasoft.py içinde."""
import inspect
import os
import re
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import platformlar as PL  # noqa: E402
from platformlar.ideasoft import Ideasoft  # noqa: E402


class Ortam:
    class cfg:
        @staticmethod
        def get(k, default=None):
            return {"store": "Magaza.com"}.get(k, default)

    @staticmethod
    def creds():
        return "cid", "sec"

    @staticmethod
    def redirect_uri():
        return "https://app.seovisi.com.tr/callback"


class Sinir(unittest.TestCase):
    def test_app_ideasofta_dogrudan_istek_gondermez(self):
        with open(os.path.join(KOK, "app.py"), encoding="utf-8") as f:
            app = f.read()
        for yasak in (r"API\.call\(", r"admin-api", r"/panel/products", r"/panel/categories", r"oauth/v2", r"urlopen\(req, context=self"):
            self.assertIsNone(re.search(yasak, app), yasak)

    def test_ideasoft_kayitli_ve_arayuzu_tamamlar(self):
        self.assertIs(PL.PLATFORMLAR["ideasoft"], Ideasoft)
        eksik = [ad for ad, v in vars(PL.Platform).items()
                 if not ad.startswith("_") and callable(getattr(PL.Platform, ad))
                 and getattr(Ideasoft, ad) is getattr(PL.Platform, ad)]
        self.assertEqual(eksik, [])
        self.assertTrue(Ideasoft.PROTECTED and Ideasoft.READONLY)

    def test_adresler(self):
        p = Ideasoft(Ortam())
        self.assertEqual(p.base(), "https://magaza.com")
        self.assertEqual(p.panel_adresleri(), {"urun": "https://magaza.com/panel/products/edit/",
                                               "kategori": "https://magaza.com/panel/categories/edit/"})
        self.assertEqual(p.mutlak_url("//cdn.x.com/a.jpg"), "https://cdn.x.com/a.jpg")
        self.assertEqual(p.mutlak_url("/a.jpg"), "https://magaza.com/a.jpg")
        self.assertTrue(p.auth_url("st").startswith("https://magaza.com/panel/auth?client_id=cid&"))
        self.assertIn("redirect_uri=https%3A%2F%2Fapp.seovisi.com.tr%2Fcallback", p.auth_url("st"))

    def test_korunan_alan_ozeti(self):
        a = {"name": "X", "price1": 10, "categories": [{"id": 3}, {"id": 1}], "images": [1, 2], "brand": {"id": 7}}
        fp = Ideasoft.fingerprint(a)
        self.assertEqual((fp["categories"], fp["images"], fp["brand"]), ([1, 3], 2, 7))
        self.assertNotEqual(fp, Ideasoft.fingerprint(dict(a, price1=11)))

    def test_yazilacak_kayit_salt_okunurlari_atar(self):
        p = Ideasoft(Ortam())
        k = {"id": 1, "name": "X", "updatedAt": "t", "children": [1]}
        self.assertEqual(p.yazilacak(k), {"id": 1, "name": "X"})
        self.assertIn("children", k)

    def test_ortam_arayuzu_belgelenmis(self):
        # adaptörün programdan aldığı her şey platformlar/__init__.py başındaki listede yazılı
        doc = inspect.getdoc(PL)
        with open(os.path.join(KOK, "platformlar", "ideasoft.py"), encoding="utf-8") as f:
            kullanilan = set(re.findall(r"self\.o\.(\w+)", f.read()))
        self.assertEqual(sorted(a for a in kullanilan if f"ortam.{a}" not in doc), [])


if __name__ == "__main__":
    unittest.main()
