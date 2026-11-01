# -*- coding: utf-8 -*-
"""Ideasoft Admin API adaptörü: OAuth girişi, erişim anahtarı, istek gönderme (hız sınırı, 401'de yenileme, 429 / 5xx'te
bekleyip yeniden deneme) ve programın kullandığı kaynaklar (products, product_details, categories, category_images,
product_images, product_to_categories, seo_settings, metafields, product_extra_fields).

Mağazaya yazma güvenliğinin kuralları (önce yeniden okuma, korunan alanların karşılaştırılması, geri yazma) app.py'dedir;
burası yalnızca Ideasoft'a nasıl okunup yazılacağını bilir.
"""
import copy
import json
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

from . import ApiError, Platform, kaydet, store_host


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ref_id(v):
    """Ideasoft ilişki alanı: {'id': 5, ...} ya da 5 -> 5"""
    if isinstance(v, dict):
        v = v.get("id")
    try:
        return int(v) if v not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


def _cat_ids(prod):
    return [i for i in (_ref_id(c) for c in (prod.get("categories") or [])) if i]


@kaydet
class Ideasoft(Platform):
    AD = "ideasoft"
    PROTECTED = ("name", "sku", "barcode", "price1", "stockAmount", "status", "discount", "discountType",
                 "taxIncluded", "tax", "slug", "hasOption", "buyingPrice", "warranty")
    # Ideasoft kaydında yazılamayan alanlar
    READONLY = ("children", "comments", "next", "prev", "updatedAt", "createdAt", "seoSetting",
                "solvedCount", "seoTotalRuleCount")

    def __init__(self, ortam):
        super().__init__(ortam)
        self.ctx = ssl.create_default_context()
        self.tok_lock = threading.Lock()
        self.req_times = deque(maxlen=2000)

    # ---- giriş
    @staticmethod
    def auth_link(host, state, client_id, redirect_uri):
        q = urllib.parse.urlencode({"client_id": client_id, "response_type": "code", "state": state,
                                    "redirect_uri": redirect_uri})
        return f"https://{host}/panel/auth?{q}"

    @staticmethod
    def token_request(host, data):
        """Ideasoft'tan erişim anahtarı ister; mağaza bağlamı gerektirmez (girişte mağaza henüz yoktur)."""
        req = urllib.request.Request(f"https://{host}/oauth/v2/token", data=urllib.parse.urlencode(data).encode(),
                                     method="POST", headers={"Content-Type": "application/x-www-form-urlencoded",
                                                             "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=40) as r:
                tok = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, e.read().decode("utf-8", "replace"), "token")
        if not tok.get("access_token"):
            raise ApiError(0, json.dumps(tok), "token")
        return tok

    # ---- adresler
    def host(self):
        return store_host(self.o.cfg.get("store"))

    def base(self):
        return f"https://{self.host()}"

    def auth_url(self, state):
        return self.auth_link(self.host(), state, self.o.creds()[0], self.o.redirect_uri())

    def panel_adresleri(self):
        return {"urun": f"{self.base()}/panel/products/edit/", "kategori": f"{self.base()}/panel/categories/edit/"}

    def mutlak_url(self, u):
        """Kayıttaki görsel adresini tam adrese çevirir (//… ve /… biçimleri)."""
        return "https:" + u if u.startswith("//") else (self.base() + u if u.startswith("/") else u)

    # ---- erişim anahtarı
    def save_token(self, tok):
        cfg = self.o.cfg
        cfg.update(access_token=tok["access_token"],
                   refresh_token=tok.get("refresh_token") or cfg.get("refresh_token"),
                   expires_at=time.time() + int(tok.get("expires_in") or 3600))
        if cfg.get("kaldirildi"):             # yeniden bağlandı: silme iptal
            cfg.update(kaldirildi="", kaldirma_nedeni="")
            self.o.log("Mağaza yeniden bağlandı; verilerin silinmesi iptal edildi.", "ok")

    def _token_req(self, data):
        cid, sec = self.o.creds()
        tok = self.o.token_request(self.host(), dict(data, client_id=cid, client_secret=sec))
        self.save_token(tok)
        return tok

    def exchange(self, code):
        return self._token_req({"grant_type": "authorization_code", "code": code, "redirect_uri": self.o.redirect_uri()})

    def refresh(self):
        cfg = self.o.cfg
        with self.tok_lock:
            if cfg.get("expires_at", 0) - time.time() > 120 and cfg.get("access_token"):
                return
            if not cfg.get("refresh_token"):
                raise ApiError(401, "Bağlantı yok. Ayarlar sayfasından mağazaya bağlanın.")
            try:
                self._token_req({"grant_type": "refresh_token", "refresh_token": cfg.get("refresh_token")})
            except ApiError as e:
                if e.status in (400, 401):     # Ideasoft anahtarı reddetti: uygulama kaldırıldı ya da izin geri alındı
                    self.o.kaldirildi("Ideasoft erişim anahtarını reddetti")
                    raise ApiError(401, "Mağazanın Ideasoft bağlantısı sona erdi; yeniden giriş yapın.")
                raise
            self.o.log("Erişim anahtarı yenilendi.")

    # ---- istek
    def call(self, method, path, params=None, body=None, tries=6):
        cfg = self.o.cfg
        url = f"{self.base()}/admin-api/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        refreshed = False
        for attempt in range(tries):
            if cfg.get("expires_at", 0) - time.time() < 120:
                self.refresh()
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {cfg.get('access_token')}",
                "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"})
            self.o.izin()
            self.req_times.append(time.time())
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=60) as r:
                    raw = r.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else None
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")
                if e.code == 401 and not refreshed:
                    refreshed = True
                    cfg.update(expires_at=0)
                    self.refresh()
                    continue
                if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                    wait = min(120, _num(e.headers.get("Retry-After")) or 0) or min(30, 1.5 * 2 ** attempt)
                    if e.code == 429:              # mağazanın bütün işleri birlikte bekler, sıra diğerlerine geçer
                        self.o.yavasla(wait)
                    else:
                        time.sleep(wait)
                    continue
                raise ApiError(e.code, txt, url)
            except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
                if attempt < tries - 1:
                    time.sleep(min(30, 2 * 2 ** attempt))
                    continue
                raise ApiError(0, f"Ağ hatası: {e}", url)

    def rpm(self):
        now = time.time()
        return sum(1 for t in self.req_times if now - t < 60)

    # ---- genel kaynaklar (hedef kelime yeri, SEO kuralları: seo_settings, metafields, product_extra_fields)
    def liste(self, res, params=None):
        return self.call("GET", res, params) or []

    def kayit_yaz(self, res, rid, body):
        return self.call("PUT", f"{res}/{rid}", body=body)

    def kayit_ekle(self, res, body):
        return self.call("POST", res, body=body)

    # ---- ürünler
    def urun_sayisi(self):
        """Mağazadaki ürün sayısı; okunamazsa 0."""
        try:
            r = self.call("GET", "products/count")
            if isinstance(r, dict):
                for v in r.values():
                    if isinstance(v, (int, float)):
                        return int(v)
            if isinstance(r, (int, float)):
                return int(r)
            if isinstance(r, str) and r.strip().isdigit():
                return int(r)
        except ApiError:
            pass
        return 0

    def urunler_sonra(self, son_id, limit=100):
        """Numara sırasıyla son_id'den sonraki ürünler (Ideasoft'un yanıtı olduğu gibi; sinceId en az 1 olmalı)."""
        prm = {"limit": limit, "sort": "id"}
        if son_id:
            prm["sinceId"] = son_id
        return self.call("GET", "products", prm) or []

    def urun_sayfasi(self, sayfa, limit=100):
        """sinceId çalışmayan mağazalarda sayfa numarasıyla okuma."""
        return self.call("GET", "products", {"limit": limit, "page": sayfa, "sort": "id"}) or []

    def urun_liste_kaydi(self, pid):
        """Ürünün liste yanıtındaki kaydı (Ideasoft'un SEO yüzdesi yalnızca burada olabilir)."""
        return next((x for x in self.call("GET", "products", {"ids": str(pid), "limit": 1}) or [] if x.get("id") == pid),
                    None)

    def get_product(self, pid):
        return self.call("GET", f"products/{pid}")

    def urun_yaz(self, pid, kayit):
        return self.call("PUT", f"products/{pid}", body=kayit)

    def urun_geri_yaz(self, pid, prod):
        """Ürünü yazmadan önceki kaydıyla geri yazar (korunan alan değiştiyse)."""
        return self.urun_yaz(pid, {k: v for k, v in prod.items() if k not in self.READONLY})

    def yazilacak(self, kayit):
        """Kaydın geri yazılabilir kopyası."""
        return {k: v for k, v in copy.deepcopy(kayit).items() if k not in self.READONLY}

    # ---- ürün arama (stok koduyla)
    def detect_lookup(self):
        cfg = self.o.cfg
        probe = "ZZ-YOK-" + secrets.token_hex(4)
        for mode, params in (("sku", {"sku": probe}), ("qsku", {"q[sku]": probe}), ("s", {"s": probe})):
            try:
                r = self.call("GET", "products", dict(params, limit=5))
                if isinstance(r, list) and len(r) == 0:
                    cfg.update(lookup_mode=mode)
                    self.o.log(f"Ürün arama yöntemi: {mode}")
                    return mode
            except ApiError:
                continue
        cfg.update(lookup_mode="index")
        self.o.log("Stok kodu filtresi desteklenmiyor; mağaza ürün listesi indekslenecek.", "warn")
        return "index"

    def build_index(self, progress=None):
        db = self.o.db
        db.x("DELETE FROM idx")
        since, total = 0, 0
        while True:
            r = self.urunler_sonra(since)
            if not r:
                break
            db.xm("INSERT OR REPLACE INTO idx(sku, pid, name) VALUES(?,?,?)",
                  [((p.get("sku") or "").strip().upper(), p["id"], p.get("name")) for p in r if p.get("sku")])
            total += len(r)
            since = max(p["id"] for p in r)
            if progress:
                progress(total)
            if len(r) < 100:
                break
        self.o.log(f"Mağaza indeksi hazır: {total} ürün.")
        return total

    def find(self, sku):
        """Stok koduna göre ürünü bulur. Dönüş: ürün dict | None."""
        mode = self.o.cfg.get("lookup_mode") or self.detect_lookup()
        key = sku.strip().upper()
        if mode == "index":
            r = self.o.db.q("SELECT pid FROM idx WHERE sku=?", (key,), one=True)
            return self.get_product(r["pid"]) if r else None
        params = {"sku": sku} if mode == "sku" else {"q[sku]": sku} if mode == "qsku" else {"s": sku}
        res = self.call("GET", "products", dict(params, limit=50)) or []
        for p in res:
            if (p.get("sku") or "").strip().upper() == key:
                return p
        return None

    # ---- açıklama
    def get_detail(self, product):
        d = product.get("detail")
        if isinstance(d, dict) and d.get("id"):
            try:
                return self.call("GET", f"product_details/{d['id']}")
            except ApiError:
                return d
        r = self.call("GET", "product_details", {"product": product["id"], "limit": 5}) or []
        return r[0] if r else None

    def aciklama_yaz(self, pid, prod, detail, html):
        """Ürün açıklamasını yazar: kaydı varsa günceller, yoksa açar."""
        if detail and detail.get("id"):
            d = {k: v for k, v in detail.items() if k != "product"}
            d.update(details=html, product={"id": pid}, sku=detail.get("sku") or prod.get("sku"))
            self.call("PUT", f"product_details/{detail['id']}", body=d)
        else:
            self.call("POST", "product_details", body={"sku": prod.get("sku"), "details": html,
                                                       "extraDetails": "", "product": {"id": pid}})

    # ---- görseller
    def gorseller(self, pid, limit=20):
        """Ürünün görsel kayıtları (başka ürüne ait dönenler ayıklanır)."""
        r = self.call("GET", "product_images", {"product": pid, "limit": limit}) or []
        return [x for x in r if str((x.get("product") or {}).get("id", pid)) == str(pid)]

    # ---- kategoriler
    def kategori(self, cid):
        return self.call("GET", f"categories/{cid}") or {}

    def kategori_ekle(self, body):
        return self.call("POST", "categories", body=body) or {}

    def kategori_yaz(self, cid, body):
        return self.call("PUT", f"categories/{cid}", body=body)

    def kategori_gorseli_ekle(self, cid, ad, uzanti, veri):
        """Bazı sürümlerde kategori resmi ayrı bir kaynaktan yüklenir."""
        return self.call("POST", "category_images", body={"category": {"id": cid}, "filename": ad, "extension": uzanti,
                                                          "attachment": veri})

    def kategorileri_yaz(self, pid, prod, target, mode):
        """Ürünün kategorilerini target yapar. mode "put": ürün kaydıyla; "link": ürün-kategori bağlantıları tek tek."""
        if mode == "put":
            keep = {_ref_id(c): c for c in prod.get("categories") or []}
            payload = self.yazilacak(prod)
            payload["categories"] = [keep.get(c) or {"id": c} for c in target]
            self.urun_yaz(pid, payload)
            return
        cur = _cat_ids(self.get_product(pid))
        for a in target:
            if a not in cur:
                self.call("POST", "product_to_categories", body={"product": {"id": pid}, "category": {"id": a}})
        rm = [c for c in cur if c not in target]
        if rm:
            for link in self.call("GET", "product_to_categories", {"product": pid, "limit": 100}) or []:
                if _ref_id(link.get("product")) == pid and _ref_id(link.get("category")) in rm and link.get("id"):
                    self.call("DELETE", f"product_to_categories/{link['id']}")

    # ---- yazma güvenliği
    @classmethod
    def fingerprint(cls, p):
        fp = {k: p.get(k) for k in cls.PROTECTED}
        fp["currency"] = (p.get("currency") or {}).get("id") if isinstance(p.get("currency"), dict) else p.get("currency")
        fp["brand"] = (p.get("brand") or {}).get("id") if isinstance(p.get("brand"), dict) else p.get("brand")
        fp["categories"] = sorted((c or {}).get("id") for c in (p.get("categories") or []) if isinstance(c, dict))
        fp["images"] = len(p.get("images") or [])
        fp["prices"] = len(p.get("prices") or [])
        return fp
