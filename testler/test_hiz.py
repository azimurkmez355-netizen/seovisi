"""Ideasoft hız sınırı ve adil iş sırası (app.Throttle), paralel işlerde mağaza bağlamı (app.pmap).

Süreye dayalı testlerin sınırları geniş tutuldu; yavaş bir makinede de kararlı çalışmalı."""
import email.message
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seo_text as ST  # noqa: E402

_pf = ST.panel_factor
import app  # noqa: E402
import sifre  # noqa: E402

ST.panel_factor = _pf


def run_for(throttle, key, seconds, counts, threads=1, order=None):
    stop = time.monotonic() + seconds

    def loop():
        while time.monotonic() < stop:
            throttle.acquire(key)
            with lock:
                counts[key] = counts.get(key, 0) + 1
                if order is not None:
                    order.append(key)
    lock = threading.Lock()
    ts = [threading.Thread(target=loop) for _ in range(threads)]
    return ts


class Sinir(unittest.TestCase):
    def test_magaza_basina_sinir(self):
        th = app.Throttle(lambda: (600, 100000))         # mağaza başına saniyede 10, 20'lik birikim
        counts = {}
        ts = run_for(th, "a", 1.0, counts, threads=4)
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertTrue(20 <= counts["a"] <= 36, counts)

    def test_toplam_sinira_takilinca_siralama_adil(self):
        th = app.Throttle(lambda: (100000, 1200))        # toplam saniyede 20, başta 40'lık birikim
        counts, order = {}, []
        ts = run_for(th, "kalabalik", 2.0, counts, threads=8, order=order) + run_for(th, "tek", 2.0, counts, order=order)
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertTrue(55 <= len(order) <= 90, counts)
        steady = order[40:]                               # baştaki birikim bittikten sonra
        self.assertGreater(steady.count("tek") / len(steady), 0.35, counts)   # adil olmasa ~%11 olurdu

    def test_429_alan_magaza_bekler_digerleri_beklemez(self):
        th = app.Throttle(lambda: (6000, 100000))
        th.pause("yavas", 0.5)
        t0 = time.monotonic()
        th.acquire("hizli")
        self.assertLess(time.monotonic() - t0, 0.1)
        th.acquire("yavas")
        self.assertGreater(time.monotonic() - t0, 0.45)

    def test_ayardan_okunur(self):
        srv = app.SRV
        try:
            app.SRV = None
            self.assertEqual(app.rate_limits(), (300, 1200))
            app.SRV = mock.Mock(get=lambda k: {"hiz_magaza_dk": "60", "hiz_toplam_dk": None}[k])
            self.assertEqual(app.rate_limits(), (60, 1200))
        finally:
            app.SRV = srv


class Istek(unittest.TestCase):
    """Ideasoft.call her istekte iş sırasından izin alır; 429'da mağazayı bekletir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seovisi-hiz-")
        self._stores, app.STORES = app.STORES, self.tmp
        sifre.KEY_PATH = os.path.join(self.tmp, "anahtar.key")
        sifre.reset()
        self.t = app.Tenant("deneme-com")
        app._cur.t = self.t
        app.CFG.update(store="deneme.com", access_token="tok", refresh_token="r", expires_at=time.time() + 9999)
        self._th, app.THROTTLE = app.THROTTLE, mock.Mock()

    def tearDown(self):
        app.THROTTLE = self._th
        app._cur.t = None
        app.STORES = self._stores
        self.t.dbi.c.close()
        sifre.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def yanit(obj):
        r = mock.MagicMock()
        r.__enter__.return_value.read.return_value = json.dumps(obj).encode()
        return r

    @staticmethod
    def hata(code, retry=""):
        h = email.message.Message()
        if retry:
            h["Retry-After"] = retry
        return urllib.error.HTTPError("https://deneme.com/admin-api/products", code, "x", h, io.BytesIO(b"{}"))

    def test_her_istek_magaza_adiyla_izin_alir(self):
        with mock.patch.object(app.urllib.request, "urlopen", return_value=self.yanit([{"id": 1}])):
            self.assertEqual(self.t.api.call("GET", "products"), [{"id": 1}])
        app.THROTTLE.acquire.assert_called_once_with("deneme-com")

    def test_429_mağazayi_bekletir_ve_yeniden_dener(self):
        with mock.patch.object(app.urllib.request, "urlopen",
                               side_effect=[self.hata(429, "7"), self.yanit({"ok": 1})]):
            self.assertEqual(self.t.api.call("GET", "products/1"), {"ok": 1})
        app.THROTTLE.pause.assert_called_once_with("deneme-com", 7.0)
        self.assertEqual(app.THROTTLE.acquire.call_count, 2)

    def test_tarih_bicimli_retry_after_cokertmez(self):
        with mock.patch.object(app.urllib.request, "urlopen",
                               side_effect=[self.hata(429, "Wed, 21 Oct 2026 07:28:00 GMT"), self.yanit({})]):
            self.t.api.call("GET", "products/1")
        self.assertGreater(app.THROTTLE.pause.call_args[0][1], 0)


class ParalelBaglam(unittest.TestCase):
    def test_paralel_isler_magazayi_bilir(self):
        tmp = tempfile.mkdtemp(prefix="seovisi-pmap-")
        stores, app.STORES = app.STORES, tmp
        sifre.KEY_PATH = os.path.join(tmp, "anahtar.key")
        sifre.reset()
        t = app.Tenant("deneme-com")
        try:
            app._cur.t = t
            app.CFG.update(store="deneme.com")
            self.assertEqual(app.pmap(lambda _: app.CFG.get("store"), range(8), 4), ["deneme.com"] * 8)
        finally:
            app._cur.t = None
            app.STORES = stores
            t.dbi.c.close()
            sifre.reset()
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
