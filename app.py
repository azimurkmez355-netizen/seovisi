# -*- coding: utf-8 -*-
"""seovisi — Ideasoft mağazaları için SEO ve kategori düzenleme aracı (Ideasoft Admin API).

Sadece Python standart kütüphanesi kullanılır (kurulum gerekmez).
Panel: http://localhost:8765
"""
import copy
import hashlib
import hmac
import html
import http.cookies
import ipaddress
import json
import os
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections import Counter, deque
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_text as ST  # noqa: E402
import seo_machine as SM  # noqa: E402
import kategori as KT  # noqa: E402
import profil as PR  # noqa: E402
import sifre  # noqa: E402
import abonelik as AB  # noqa: E402
import sablon as TPL  # noqa: E402
import uyari as UY  # noqa: E402
import kopya as KP  # noqa: E402
import baglanti as BG  # noqa: E402
import rapor as RP  # noqa: E402
import yedek as YD  # noqa: E402
import yonetim as YN  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sifre.KEY_PATH = os.path.join(DATA, "anahtar.key")
STORES = os.path.join(DATA, "magazalar")       # her mağazanın ayarları, veritabanı ve kaydı kendi klasöründe
SERVER_PATH = os.path.join(DATA, "sunucu.json")
UI = os.path.join(BASE, "ui", "index.html")
MARKA = os.path.join(BASE, "ui", "marka")   # logo ve simgeler
PORT = 8765

DEFAULT_CFG = {
    "store": "",
    "client_id": "", "client_secret": "",
    "redirect_uri": f"http://localhost:{PORT}/callback",
    "target_density": 2.5,
    "kw_loc": {},                 # keşifle bulunur — hedef kelimenin Ideasoft'ta saklandığı yer
    "kw_needle": "",              # örnek üründe panelde yazan hedef kelime
    "count_method": "",           # paneldeki kelime sayımıyla eşleştirilen yöntem ("" = hepsine göre güvenli)
    "sample_sku": "",
    "lookup_mode": "",
    "profil": {},                 # mağaza profili (profil.py): mağaza adı, varsayılan marka
    "sablon": {},                 # açıklama şablonu (sablon.py); boşsa sunucuda sade, bilgisayarda bantlı
    "kurulum_bitti": None,        # kurulum sihirbazı (sunucu); None: bu ayardan önce kurulmuş mağaza
    "otopilot": {},               # yeni ürün otopilotu ayarları (oto_ayar)
    "seo_prepare": True,
    "eur_rate": 55,
    "panel_factor": 1.30,         # Ideasoft oranı / ham HTML oranı (gönderilmiş ürünlerden ölçüldü)
    "access_token": "", "refresh_token": "", "expires_at": 0,
}

SERVER_DEFAULT = {
    "secret": "",                 # oturum çerezlerini imzalar; ilk açılışta üretilir
    "client_id": "", "client_secret": "",   # sunucu kipinde Ideasoft uygulamasının ortak anahtarları
    "public_url": "",             # sunucu kipinde dışarıdan açılan adres, örn. https://app.seovisi.com.tr
    "yerel": "",                  # yerel kipte açılan mağaza klasörü
    "frame_hosts": [],            # panelin çerçevede açılabileceği ek adresler (FRAME_HOSTS'a ek)
    "kw_loc": {},                 # hedef kelime yerinin varsayılanı (Ustapazar'da bulunan); mağaza keşif yaparsa onunki geçerli
    "hiz_magaza_dk": 300,        # Ideasoft'a mağaza başına dakikada en çok istek (tahmin; Ideasoft'un cevabıyla kesinleşir)
    "otopilot_dk": 60,            # otopilotun her mağazada yeni ürünlere bakma aralığı (dakika)
    "link_sinir": 10000,          # kırık bağlantı taramasında bir mağazada gezilen en çok sayfa
    "hiz_toplam_dk": 1200,        # bütün mağazalar toplamı (uygulama başına sınır varsa)
}
SERVER = {"on": False}            # main() --sunucu ile açar

# ============================================================ mağaza bağlamı
# Kodun geri kalanı tek mağaza varmış gibi CFG, DBI, API… adlarını kullanır. Bu adlar o anki iş parçacığının
# mağazasına yönlenir: istek işleyicisi oturumdaki mağazayı, arka plan işleri kendilerini başlatan mağazayı ayarlar.

_cur = threading.local()


def current():
    t = getattr(_cur, "t", None)
    if t is None:
        raise RuntimeError("Mağaza seçilmedi.")
    return t


class _Ref:
    def __init__(self, attr):
        self._attr = attr

    def __getattr__(self, k):
        return getattr(getattr(current(), self._attr), k)

    def __setattr__(self, k, v):
        # atama da o anki mağazanın nesnesine gider; vekilin üstünde kalsaydı bütün mağazalarda geçerli olurdu
        if k == "_attr":
            object.__setattr__(self, k, v)
        else:
            setattr(getattr(current(), self._attr), k, v)


def spawn(target, *args):
    """Arka plan işini, onu başlatan mağazanın bağlamında çalıştırır."""
    t = getattr(_cur, "t", None)

    def run():
        _cur.t = t
        target(*args)
    threading.Thread(target=run, daemon=True).start()


def pmap(fn, items, workers):
    """Paralel map; iş parçacıkları başlatan mağazanın bağlamını taşır. **ThreadPoolExecutor'ı doğrudan kullanma.**"""
    from concurrent.futures import ThreadPoolExecutor
    t = getattr(_cur, "t", None)

    def run(x):
        _cur.t = t
        try:
            return fn(x)
        finally:
            _cur.t = None
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(run, items))


# ================================================================= yardımcılar

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    t = getattr(_cur, "t", None)
    if t is not None:
        with t.log_lock:
            t.logs.append({"t": ts, "l": level, "m": msg})
            try:
                with open(t.path("islem.log"), "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now():%Y-%m-%d} {ts} [{level}] {msg}\n")
            except OSError:
                pass
    print(f"{ts} {f'[{t.id}] ' if t is not None and SERVER['on'] else ''}{msg}", flush=True)


class Config:
    # diskte şifreli tutulur (sifre.py); bellekte ve programın geri kalanında düz metin
    SECRET = ("access_token", "refresh_token", "client_secret", "secret")

    def __init__(self, path, defaults=DEFAULT_CFG):
        self.path = path
        self.lock = threading.Lock()
        self.d = dict(defaults)
        self.locked = {}          # açılamayan şifreli değerler: silinmesin diye olduğu gibi geri yazılır
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.d.update(json.load(f))
            except (OSError, ValueError):
                pass
        for k in self.SECRET:
            if sifre.is_encrypted(self.d.get(k)):
                try:
                    self.d[k] = sifre.decrypt(self.d[k])
                except sifre.SifreHatasi as e:
                    self.locked[k], self.d[k] = self.d[k], ""
                    print(f"Uyarı: {path} içindeki {k} açılamadı: {e}")
        self.save()               # eski kurulumdaki düz metin anahtarlar burada şifrelenir

    def get(self, k, default=None):
        with self.lock:
            v = self.d.get(k)
        return default if v is None else v

    def update(self, **kw):
        with self.lock:
            self.d.update(kw)
            for k in kw:
                self.locked.pop(k, None)
        self.save()

    def save(self):
        with self.lock:
            disk = dict(self.d)
            for k in self.SECRET:
                if k in self.locked:
                    disk[k] = self.locked[k]
                elif disk.get(k):
                    disk[k] = sifre.encrypt(str(disk[k]))
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(disk, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def public(self):
        with self.lock:
            p = {k: v for k, v in self.d.items() if k not in ("access_token", "refresh_token", "client_secret")}
            p["has_secret"] = bool(self.d.get("client_secret"))
            p["connected"] = bool(self.d.get("refresh_token") or self.d.get("access_token"))
            return p


CFG = _Ref("cfg")
SRV = None                        # sunucu ayarları (sunucu.json); main() açar


def PROFILE():
    """Mağaza profili; metin üreticileri ve görsel kopyalama buna göre çalışır."""
    return PR.load(CFG.get("profil"))


# ================================================================== veritabanı

class DB:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.execute("CREATE TABLE IF NOT EXISTS idx(sku TEXT PRIMARY KEY, pid INTEGER, name TEXT)")
        self.c.commit()

    def q(self, sql, args=(), one=False):
        with self.lock:
            cur = self.c.execute(sql, args)
            r = cur.fetchall()
        return (r[0] if r else None) if one else r

    def x(self, sql, args=()):
        with self.lock:
            self.c.execute(sql, args)
            self.c.commit()

    def xm(self, sql, rows):
        with self.lock:
            self.c.executemany(sql, rows)
            self.c.commit()



DBI = _Ref("dbi")


# ================================================================ Ideasoft API

class ApiError(Exception):
    def __init__(self, status, body, url=""):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status, self.body, self.url = status, body, url


def store_host(s):
    """Kullanıcının yazdığı mağaza adresinden yalın alan adı: https://Magaza.com/ → magaza.com"""
    s = (s or "").strip().lower()
    s = re.sub(r"^[a-z]+://", "", s)
    return s.split("/")[0].split("?")[0].strip(".")


def client_creds():
    """Mağazanın kendi API anahtarı (yerel kurulum) yoksa sunucunun ortak Ideasoft uygulaması."""
    if CFG.get("client_id"):
        return CFG.get("client_id"), CFG.get("client_secret")
    return SRV.get("client_id"), SRV.get("client_secret")


def redirect_uri():
    if SERVER["on"]:
        return SRV.get("public_url").rstrip("/") + "/callback"
    return CFG.get("redirect_uri")


def auth_link(host, state):
    cid = client_creds()[0] if getattr(_cur, "t", None) else SRV.get("client_id")
    q = urllib.parse.urlencode({"client_id": cid, "response_type": "code", "state": state,
                                "redirect_uri": redirect_uri()})
    return f"https://{host}/panel/auth?{q}"


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


# ============================================================ Ideasoft hız sınırı

# Dakikadaki istek sınırları sunucu.json'dan okunur ("hiz_magaza_dk", "hiz_toplam_dk"). Ideasoft'un gerçek sınırı
# öğrenilene kadar varsayılanlar tahmindir; değişince yalnızca ayar değişir.
RATE_DEFAULTS = {"hiz_magaza_dk": 300, "hiz_toplam_dk": 1200}


class Throttle:
    """Ideasoft'a giden her istek buradan izin alır: mağaza başına ve toplamda dakikada en çok N istek.
    Toplam sınıra takılınca bekleyen mağazalar sırayla (en uzun süredir istek gönderemeyen önce) izin alır;
    çok sayıda iş parçacığı açan bir mağaza diğerlerini bekletmez. 429 alan mağaza bir süre bekletilir."""

    def __init__(self, limits=None):
        self.limits = limits or (lambda: (RATE_DEFAULTS["hiz_magaza_dk"], RATE_DEFAULTS["hiz_toplam_dk"]))
        self.cv = threading.Condition()
        self.stores = {}          # mağaza -> {"tok", "at", "until", "served"}
        self.total = None         # [jeton, son dolum]
        self.waiting = {}         # mağaza -> sıradaki istekler (FIFO)
        self.gunluk = {}          # mağaza -> [gün, bugünkü istek sayısı] (yönetici paneli)

    @staticmethod
    def _fill(b, rate, now):
        cap = max(1.0, rate / 30.0)          # en çok 2 saniyelik birikim
        b[0] = min(cap, b[0] + (now - b[1]) * rate / 60.0)
        b[1] = now

    def _store(self, key, rate, now):
        s = self.stores.get(key)
        if s is None:
            s = self.stores[key] = {"b": [max(1.0, rate / 30.0), now], "until": 0.0, "served": 0.0}
        self._fill(s["b"], rate, now)
        return s

    def acquire(self, key):
        ticket = object()
        with self.cv:
            q = self.waiting.setdefault(key, deque())
            q.append(ticket)
            try:
                while True:
                    per, total = (max(1, int(x)) for x in self.limits())
                    now = time.monotonic()
                    if self.total is None:
                        self.total = [max(1.0, total / 30.0), now]
                    self._fill(self.total, total, now)
                    ready = []
                    for k in self.waiting:
                        s = self._store(k, per, now)
                        if s["b"][0] >= 1 and s["until"] <= now:
                            ready.append(k)
                    if self.total[0] >= 1 and ready:
                        pick = min(ready, key=lambda k: self.stores[k]["served"])
                        if pick == key and q[0] is ticket:
                            s = self.stores[key]
                            s["b"][0] -= 1
                            self.total[0] -= 1
                            s["served"] = now
                            gun = time.strftime("%Y-%m-%d")
                            g = self.gunluk.get(key)
                            self.gunluk[key] = [gun, (g[1] if g and g[0] == gun else 0) + 1]
                            q.popleft()
                            self.cv.notify_all()
                            return
                    # bir sonraki jetonun gelmesine kalan süre kadar (ya da başkası izin alınca) bekle
                    waits = [(1 - self.total[0]) * 60.0 / total] if self.total[0] < 1 else []
                    for k in self.waiting:
                        s = self.stores[k]
                        waits.append(max(s["until"] - now, (1 - s["b"][0]) * 60.0 / per if s["b"][0] < 1 else 0))
                    self.cv.wait(min(0.5, max(0.002, min([w for w in waits if w > 0] or [0.05]))))
            finally:
                if ticket in q:
                    q.remove(ticket)
                if not q and self.waiting.get(key) is q:
                    del self.waiting[key]
                    self.cv.notify_all()

    def bugun(self, key):
        """Mağazanın bugün Ideasoft'a gönderdiği istek sayısı."""
        with self.cv:
            g = self.gunluk.get(key)
        return g[1] if g and g[0] == time.strftime("%Y-%m-%d") else 0

    def pause(self, key, seconds):
        """Ideasoft "yavaşla" (429) dediğinde mağazanın isteklerini bir süre durdurur."""
        with self.cv:
            s = self._store(key, max(1, int(self.limits()[0])), time.monotonic())
            s["until"] = max(s["until"], time.monotonic() + seconds)
            self.cv.notify_all()


def rate_limits():
    get = SRV.get if SRV else RATE_DEFAULTS.get
    return tuple(_num(get(k)) or RATE_DEFAULTS[k] for k in ("hiz_magaza_dk", "hiz_toplam_dk"))


THROTTLE = Throttle(rate_limits)


class Ideasoft:
    PROTECTED =("name", "sku", "barcode", "price1", "stockAmount", "status", "discount", "discountType",
                 "taxIncluded", "tax", "slug", "hasOption", "buyingPrice", "warranty")

    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.tok_lock = threading.Lock()
        self.req_times = deque(maxlen=2000)

    # ---- temel
    def base(self):
        return f"https://{store_host(CFG.get('store'))}"

    def auth_url(self, state):
        return auth_link(store_host(CFG.get("store")), state)

    def save_token(self, tok):
        CFG.update(access_token=tok["access_token"],
                   refresh_token=tok.get("refresh_token") or CFG.get("refresh_token"),
                   expires_at=time.time() + int(tok.get("expires_in") or 3600))

    def _token_req(self, data):
        cid, sec = client_creds()
        tok = token_request(store_host(CFG.get("store")), dict(data, client_id=cid, client_secret=sec))
        self.save_token(tok)
        return tok

    def exchange(self, code):
        return self._token_req({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()})

    def refresh(self):
        with self.tok_lock:
            if CFG.get("expires_at", 0) - time.time() > 120 and CFG.get("access_token"):
                return
            if not CFG.get("refresh_token"):
                raise ApiError(401, "Bağlantı yok. Ayarlar sayfasından mağazaya bağlanın.")
            self._token_req({"grant_type": "refresh_token", "refresh_token": CFG.get("refresh_token")})
            log("Erişim anahtarı yenilendi.")

    def call(self, method, path, params=None, body=None, tries=6):
        url = f"{self.base()}/admin-api/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        refreshed = False
        for attempt in range(tries):
            if CFG.get("expires_at", 0) - time.time() < 120:
                self.refresh()
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {CFG.get('access_token')}",
                "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"})
            THROTTLE.acquire(current().id)
            self.req_times.append(time.time())
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=60) as r:
                    raw = r.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else None
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")
                if e.code == 401 and not refreshed:
                    refreshed = True
                    CFG.update(expires_at=0)
                    self.refresh()
                    continue
                if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                    wait = min(120, _num(e.headers.get("Retry-After")) or 0) or min(30, 1.5 * 2 ** attempt)
                    if e.code == 429:              # mağazanın bütün işleri birlikte bekler, sıra diğerlerine geçer
                        THROTTLE.pause(current().id, wait)
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

    # ---- ürün bulma
    def detect_lookup(self):
        probe = "ZZ-YOK-" + secrets.token_hex(4)
        for mode, params in (("sku", {"sku": probe}), ("qsku", {"q[sku]": probe}), ("s", {"s": probe})):
            try:
                r = self.call("GET", "products", dict(params, limit=5))
                if isinstance(r, list) and len(r) == 0:
                    CFG.update(lookup_mode=mode)
                    log(f"Ürün arama yöntemi: {mode}")
                    return mode
            except ApiError:
                continue
        CFG.update(lookup_mode="index")
        log("Stok kodu filtresi desteklenmiyor; mağaza ürün listesi indekslenecek.", "warn")
        return "index"

    def build_index(self, progress=None):
        DBI.x("DELETE FROM idx")
        since, total = 0, 0
        while True:
            prm = {"limit": 100, "sort": "id"}
            if since:
                prm["sinceId"] = since
            r = self.call("GET", "products", prm)
            if not r:
                break
            DBI.xm("INSERT OR REPLACE INTO idx(sku, pid, name) VALUES(?,?,?)",
                   [((p.get("sku") or "").strip().upper(), p["id"], p.get("name")) for p in r if p.get("sku")])
            total += len(r)
            since = max(p["id"] for p in r)
            if progress:
                progress(total)
            if len(r) < 100:
                break
        log(f"Mağaza indeksi hazır: {total} ürün.")
        return total

    def find(self, sku):
        """Stok koduna göre ürünü bulur. Dönüş: ürün dict | None."""
        mode = CFG.get("lookup_mode") or self.detect_lookup()
        key = sku.strip().upper()
        if mode == "index":
            r = DBI.q("SELECT pid FROM idx WHERE sku=?", (key,), one=True)
            return self.call("GET", f"products/{r['pid']}") if r else None
        params = {"sku": sku} if mode == "sku" else {"q[sku]": sku} if mode == "qsku" else {"s": sku}
        res = self.call("GET", "products", dict(params, limit=50)) or []
        for p in res:
            if (p.get("sku") or "").strip().upper() == key:
                return p
        return None

    def get_product(self, pid):
        return self.call("GET", f"products/{pid}")

    def get_detail(self, product):
        d = product.get("detail")
        if isinstance(d, dict) and d.get("id"):
            try:
                return self.call("GET", f"product_details/{d['id']}")
            except ApiError:
                return d
        r = self.call("GET", "product_details", {"product": product["id"], "limit": 5}) or []
        return r[0] if r else None

    @staticmethod
    def fingerprint(p):
        fp = {k: p.get(k) for k in Ideasoft.PROTECTED}
        fp["currency"] = (p.get("currency") or {}).get("id") if isinstance(p.get("currency"), dict) else p.get("currency")
        fp["brand"] = (p.get("brand") or {}).get("id") if isinstance(p.get("brand"), dict) else p.get("brand")
        fp["categories"] = sorted((c or {}).get("id") for c in (p.get("categories") or []) if isinstance(c, dict))
        fp["images"] = len(p.get("images") or [])
        fp["prices"] = len(p.get("prices") or [])
        return fp


API = _Ref("api")


# ============================================================ hedef kelime yeri
#
# Ideasoft hedef kelimeyi belgelenmiş bir alanda tutmuyor. Keşif, örnek üründe panelde yazan
# hedef kelimeyi ürünün kendisinde, SEO ayarlarında (seo_settings), metafield'larda ve ürün ek
# alanlarında arar; bulduğu yeri CFG["kw_loc"] olarak kaydeder. Yazma ve okuma bu yere göre yapılır.

RECORD_RES = ("seo_settings", "metafields", "product_extra_fields")


def _parse_jsonish(v):
    if isinstance(v, str) and v.strip()[:1] in ("{", "["):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def jget(obj, path):
    for k in [x for x in (path or "").split(".") if x]:
        obj = _parse_jsonish(obj)
        if isinstance(obj, list):
            try:
                obj = obj[int(k)]
            except (ValueError, IndexError):
                return None
        elif isinstance(obj, dict):
            obj = obj.get(k)
        else:
            return None
    return obj


def jset(obj, path, val):
    """path boyunca değeri yazar; JSON metin olarak saklanan ara alanları da korur."""
    ks = [x for x in path.split(".") if x]
    k0 = ks[0]
    if len(ks) == 1:
        obj[k0] = val
        return
    cur = obj.get(k0) if isinstance(obj, dict) else obj[int(k0)]
    was_str = isinstance(cur, str)
    inner = _parse_jsonish(cur) if was_str else cur
    if not isinstance(inner, (dict, list)):
        inner = {}
    jset(inner, ".".join(ks[1:]), val)
    new = json.dumps(inner, ensure_ascii=False) if was_str else inner
    if isinstance(obj, dict):
        obj[k0] = new
    else:
        obj[int(k0)] = new


def deep_find(obj, needle, path=""):
    out = []
    obj = _parse_jsonish(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += deep_find(v, needle, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += deep_find(v, needle, f"{path}.{i}" if path else str(i))
    elif isinstance(obj, str) and ST.tr_lower(obj.strip()) == needle:
        out.append(path)
    return out


_scan_cache = {}


def _fill(q, pid):
    return {k: (pid if v == "{pid}" else v) for k, v in q.items()}


def find_record(res, pid, loc):
    """Ürünün hedef kelime kaydını getirir (yoksa None)."""
    if loc.get("query"):
        recs = API.call("GET", res, dict(_fill(loc["query"], pid), limit=100)) or []
    else:
        if res not in _scan_cache:
            allr, page = [], 1
            while page <= 500:
                r = API.call("GET", res, {"limit": 100, "page": page}) or []
                allr += r
                if len(r) < 100:
                    break
                page += 1
            _scan_cache[res] = allr
        recs = _scan_cache[res]
    out = []
    for r in recs:
        owner = r.get("contextItemId") if res != "product_extra_fields" else (r.get("product") or {}).get("id")
        if str(owner) != str(pid):
            continue
        if loc.get("context") and r.get("context") != loc["context"]:
            continue
        if loc.get("varKey") and r.get("varKey") != loc["varKey"]:
            continue
        out.append(r)
    return out[0] if out else None


def kw_loc():
    """Hedef kelimenin Ideasoft'ta saklandığı yer: mağazada keşfedilen, yoksa sunucu.json'daki varsayılan
    (Ustapazar'da bulunan yer; Ideasoft'ta her mağazada aynı olduğu varsayılır, mağaza sahibi keşif yapmaz)."""
    for loc in (CFG.get("kw_loc"), SRV.get("kw_loc") if SRV else None):
        if isinstance(loc, dict) and loc.get("res") in ("product",) + RECORD_RES and loc.get("path"):
            return loc
    return {}


def kw_read(prod):
    loc = kw_loc()
    if not loc:
        return "", None
    if loc["res"] == "product":
        return jget(prod, loc["path"]) or "", None
    rec = find_record(loc["res"], prod["id"], loc)
    return (jget(rec, loc["path"]) or "") if rec else "", rec


def kw_write(pid, value, rec):
    """Ürün dışındaki kayıtlara hedef kelimeyi yazar (ürün içindeyse ürün PUT'unda yazılır)."""
    loc = kw_loc()
    res = loc.get("res")
    if res == "product":
        return
    if rec and rec.get("id"):
        body = {k: v for k, v in copy.deepcopy(rec).items() if k not in ("createdAt", "updatedAt")}
        if res == "product_extra_fields":
            body["product"] = {"id": pid}
        jset(body, loc["path"], value)
        API.call("PUT", f"{res}/{rec['id']}", body=body)
        return
    body = {}
    if res == "product_extra_fields":
        body = {"product": {"id": pid}, "varKey": loc.get("varKey"), "varValue": ""}
    else:
        body = {"context": loc.get("context") or "product", "contextItemId": pid}
        if res == "metafields":
            body.update(type=loc.get("type") or "string", varKey=loc.get("varKey"), varValue="")
        else:
            body["jsonValue"] = {}
    jset(body, loc["path"], value)
    created = API.call("POST", res, body=body)
    if res in _scan_cache and isinstance(created, dict):
        _scan_cache[res].append(created)


def discover(sku=None, needle=None):
    """Örnek üründe panelde yazan hedef kelimeyi arayarak saklandığı yeri öğrenir."""
    sku = (sku or CFG.get("sample_sku") or "").strip()
    needle_raw = (needle or CFG.get("kw_needle") or "").strip()
    if not needle_raw:
        return {"ok": False, "msg": "Örnek üründe panelde yazan hedef kelimeyi kutuya yazın."}
    CFG.update(sample_sku=sku, kw_needle=needle_raw)
    nd = ST.tr_lower(needle_raw)
    found = API.find(sku)
    if not found:
        return {"ok": False, "msg": f"{sku} stok kodlu ürün mağazada bulunamadı."}
    pid = found["id"]
    prod = API.get_product(pid)
    checked, hits = [], []

    for path in deep_find(prod, nd):
        m = re.match(r"productExtraFields\.(\d+)\.(.+)", path)
        if m:
            rec = prod["productExtraFields"][int(m.group(1))]
            hits.append({"res": "product_extra_fields", "path": m.group(2), "varKey": rec.get("varKey"),
                         "query": {"product": "{pid}"}})
        elif path not in ("name", "fullName", "pageTitle", "metaKeywords", "metaDescription", "searchKeywords"):
            hits.append({"res": "product", "path": path})
    checked.append(f"ürün kaydı ({len(prod)} alan)")

    queries = {"seo_settings": [{"contextItemId": "{pid}"}, {"q[contextItemId]": "{pid}"},
                                {"context": "product", "contextItemId": "{pid}"}],
               "metafields": [{"contextItemId": "{pid}"}, {"q[contextItemId]": "{pid}"},
                              {"context": "product", "contextItemId": "{pid}"}],
               "product_extra_fields": [{"product": "{pid}"}, {"q[product]": "{pid}"}]}
    samples = {}
    for res, qs in queries.items():
        for qv in qs:
            if hits:
                break
            try:
                recs = API.call("GET", res, dict(_fill(qv, pid), limit=100)) or []
            except ApiError as e:
                checked.append(f"{res} {qv}: HTTP {e.status}")
                continue
            checked.append(f"{res} {list(qv)}: {len(recs)} kayıt")
            for r in recs:
                owner = r.get("contextItemId") if res != "product_extra_fields" else (r.get("product") or {}).get("id")
                if str(owner) != str(pid):
                    continue
                samples.setdefault(res, []).append(r)
                for path in deep_find(r, nd):
                    hits.append({"res": res, "path": path, "context": r.get("context"),
                                 "varKey": r.get("varKey"), "type": r.get("type"), "query": qv})
    if not hits:  # filtre çalışmıyorsa tüm kayıtları tara
        for res in ("seo_settings", "metafields"):
            page = 1
            while page <= 300 and not hits:
                try:
                    recs = API.call("GET", res, {"limit": 100, "page": page}) or []
                except ApiError as e:
                    checked.append(f"{res} tarama: HTTP {e.status}")
                    break
                for r in recs:
                    if str(r.get("contextItemId")) == str(pid):
                        samples.setdefault(res, []).append(r)
                        for path in deep_find(r, nd):
                            hits.append({"res": res, "path": path, "context": r.get("context"),
                                         "varKey": r.get("varKey"), "type": r.get("type"), "query": None})
                if len(recs) < 100:
                    break
                page += 1
            checked.append(f"{res} tam tarama: {page} sayfa")
            if hits:
                break

    prod_view = {k: v for k, v in prod.items() if k not in ("images", "children", "comments", "categories", "prices")}
    res = {"ok": bool(hits), "product": {"id": pid, "name": prod.get("name"), "sku": prod.get("sku")},
           "checked": checked, "records": samples, "raw_product": prod_view}
    if hits:
        loc = hits[0]
        CFG.update(kw_loc=loc)
        _scan_cache.clear()
        where = {"product": "ürün kaydı", "seo_settings": "SEO ayarları", "metafields": "metafield",
                 "product_extra_fields": "ürün ek alanı"}[loc["res"]]
        res["msg"] = f"Bulundu: {where} › {loc['path']}" + (f" ({loc['varKey']})" if loc.get("varKey") else "")
        res["loc"] = loc
        log("Hedef kelime yeri: " + res["msg"], "ok")
    else:
        res["msg"] = ("Hedef kelime API'de bulunamadı. Aşağıdaki ham veriyi ve Ideasoft panelinde F12 > Ağ (Network) "
                      "sekmesi açıkken hedef kelimeyi kaydettiğinizde giden isteği gönderin.")
        log(res["msg"], "warn")
    return res


def calibrate(panel_count, sku=None):
    """Paneldeki 'Kelime Sayısı' ile örnek ürünün açıklamasını karşılaştırıp sayım yöntemini seçer."""
    sku = (sku or CFG.get("sample_sku") or "").strip()
    found = API.find(sku)
    if not found:
        return {"ok": False, "msg": f"{sku} bulunamadı."}
    prod = API.get_product(found["id"])
    det = API.get_detail(prod)
    h = (det or {}).get("details") or ""
    counts = {m: ST.count_words(h, m) for m in ST.COUNT_METHODS}
    match = [m for m, c in counts.items() if c == int(panel_count)]
    out = {"counts": counts, "panel": int(panel_count), "html": h[:3000]}
    if match:
        CFG.update(count_method=",".join(match))
        names = " / ".join(ST.COUNT_METHODS[m][0] for m in match)
        out.update(ok=True, method=",".join(match), msg=f"Eşleşti: {names}. Açıklamalar buna göre ayarlanacak.")
        log(out["msg"], "ok")
    else:
        CFG.update(count_method="")
        out.update(ok=False, msg="Hiçbir yöntem birebir tutmadı; tüm yöntemlerde güvenli aralık hedeflenecek. "
                                 "Bu ekranın görüntüsünü gönderirseniz yöntemi ekleyebilirim.")
    return out


# ======================================================== Ideasoft kaydında yazılamayan alanlar

READONLY = ("children", "comments", "next", "prev", "updatedAt", "createdAt", "seoSetting",
            "solvedCount", "seoTotalRuleCount")


# ============================================================ görsel kontrolü
#
# Mağazadaki TÜM ürünleri id sırasıyla tarar ve görseli olmayanları bulur. Mağazada hiçbir şey değiştirmez.

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
IMG_EXT = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"GIF8": "gif"}


def slugify(s):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").translate(tr)).strip("-").lower()
    return s[:60] or "urun"


def image_count(pid):
    r = API.call("GET", "product_images", {"product": pid, "limit": 20}) or []
    return len([x for x in r if str((x.get("product") or {}).get("id", pid)) == str(pid)])


class ImgScanner:
    def __init__(self):
        self.running = False
        self.paused = False
        self.stop_flag = False
        self.pause_ev = threading.Event()
        self.pause_ev.set()
        self.total = 0
        self.note = ""
        self.phase = ""
        self.started_at = None
        self.done_session = 0
        DBI.x("""CREATE TABLE IF NOT EXISTS img(pid INTEGER PRIMARY KEY, sku TEXT, name TEXT,
                 has INTEGER, cnt INTEGER, checked TEXT)""")
        DBI.x("CREATE INDEX IF NOT EXISTS i_img_has ON img(has)")
        DBI.x("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
        r = DBI.q("SELECT v FROM kv WHERE k='img_total'", one=True)
        self.total = int(r["v"]) if r else 0

    def start(self):
        if self.running:
            if self.paused:
                self.resume()
            return "Zaten çalışıyor."
        if not CFG.get("access_token") and not CFG.get("refresh_token"):
            return "Önce mağazaya bağlanın (Ayarlar)."
        self.running, self.paused, self.stop_flag, self.note = True, False, False, ""
        self.pause_ev.set()
        self.started_at, self.done_session = time.time(), 0
        spawn(self._run)
        return "Görsel kontrolü başladı."

    def pause(self):
        self.paused = True
        self.pause_ev.clear()
        log("Görsel kontrolü duraklatıldı.")

    def resume(self):
        self.paused = False
        self.pause_ev.set()
        log("Görsel kontrolü devam ediyor.")

    def stop(self):
        self.stop_flag = True
        self.pause_ev.set()

    def reset(self):
        if self.running:
            return "Önce durdurun."
        DBI.x("DELETE FROM img")
        return "Sonuçlar silindi; Başlat ile baştan taranır."

    def _count(self):
        try:
            r = API.call("GET", "products/count")
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

    def _run(self):
        try:
            n = self._count()
            if n:
                self.total = n
                DBI.x("INSERT OR REPLACE INTO kv(k, v) VALUES('img_total', ?)", (str(n),))
            last = DBI.q("SELECT MAX(pid) m FROM img", one=True)["m"] or 0
            self.phase = "taranıyor"
            log(f"Görsel kontrolü: {self.total or '?'} ürün, {last and 'kaldığı yerden' or 'baştan'} taranıyor.", "ok")
            page_mode, pno = False, 0
            while not self.stop_flag:
                self.pause_ev.wait()
                if self.stop_flag:
                    break
                if page_mode:
                    pno += 1
                    page = API.call("GET", "products", {"limit": 100, "page": pno, "sort": "id"}) or []
                    page = [p for p in page if isinstance(p, dict) and p.get("id")]
                else:
                    prm = {"limit": 100, "sort": "id"}
                    if last:  # Ideasoft sinceId için en az 1 istiyor
                        prm["sinceId"] = last
                    try:
                        raw = API.call("GET", "products", prm) or []
                    except ApiError as e:
                        if e.status != 400:
                            raise
                        raw, page_mode, pno = None, True, max(0, img_counts()["taranan"] // 100 - 1)
                    if raw is None:
                        continue
                    page = [p for p in raw if isinstance(p, dict) and p.get("id", 0) > last]
                    if raw and not page:
                        page_mode, pno = True, max(0, img_counts()["taranan"] // 100 - 1)
                        continue
                if not page:
                    break
                rows, missing = [], []
                for p in page:
                    imgs = p.get("images")
                    if isinstance(imgs, list):
                        rows.append((p["id"], p.get("sku"), p.get("name"), 1 if imgs else 0, len(imgs)))
                    else:
                        missing.append(p)
                if missing:
                    cnts = pmap(lambda q: image_count(q["id"]), missing, 4)
                    rows += [(p["id"], p.get("sku"), p.get("name"), 1 if c else 0, c) for p, c in zip(missing, cnts)]
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                DBI.xm("""INSERT INTO img(pid, sku, name, has, cnt, checked) VALUES(?,?,?,?,?,?)
                          ON CONFLICT(pid) DO UPDATE SET sku=excluded.sku, name=excluded.name,
                          has=excluded.has, cnt=excluded.cnt, checked=excluded.checked""",
                       [r + (now,) for r in rows])
                self.done_session += len(rows)
                last = max(p["id"] for p in page)
                if page_mode and len(page) < 100:
                    break
            c = img_counts()
            if not self.stop_flag:
                log(f"Görsel kontrolü bitti: {c['var']} görselli, {c['yok']} görselsiz ürün.", "ok")
            else:
                log("Görsel kontrolü durduruldu.")
        except Exception as e:  # noqa: BLE001
            self.note = f"Görsel kontrolü hata ile durdu: {e}"
            log(self.note, "err")
            traceback.print_exc()
        finally:
            self.running = False
            self.paused = False
            self.phase = ""

    def state(self):
        el = time.time() - self.started_at if self.started_at and self.running else 0
        rate = self.done_session / el * 60 if el > 3 else 0
        c = img_counts()
        left = max(0, self.total - c["taranan"]) if self.total else None
        return {"running": self.running, "paused": self.paused, "note": self.note, "total": self.total,
                "phase": self.phase, "rate": round(rate),
                "eta_min": (round(left / rate) if rate and left else None), "counts": c}


def img_counts():
    r = DBI.q("SELECT SUM(has=1) v, SUM(has=0) y, COUNT(*) n FROM img", one=True)
    return {"var": r["v"] or 0, "yok": r["y"] or 0, "taranan": r["n"] or 0}


IMG = _Ref("img")

# ============================================================ SEO analizi
#
# Mağazadaki TÜM ürünlerin SEO durumunu sadece okuyarak hesaplar; hiçbir şey yazmaz.
# Hızlı olması için hedef kelimeler, açıklamalar ve ürünler 100'erli sayfalar hâlinde toplu çekilir.

FAIL_CODES = [("Hedef kelime tanımlı", "kw_yok", "Hedef kelime yok"),
              ("Ürün adı dolu", "ad_yok", "Ürün adı yok"),
              ("Hedef kelime ürün adında", "kw_ad", "Hedef kelime adda geçmiyor"),
              ("Açıklama dolu", "aciklama_yok", "Açıklama boş"),
              ("Hedef kelime açıklamada", "kw_aciklama", "Hedef kelime açıklamada yok"),
              ("Açıklama en az 50", "kisa", "Açıklama 50 kelimeden kısa"),
              ("Hedef kelime yoğunluğu", "yogunluk", "Yoğunluk %2-%3 dışında"),
              ("Sayfa başlığı", "baslik", "Etiket başlığı sorunlu"),
              ("Hedef kelime sayfa başlığında", "baslik", "Etiket başlığı sorunlu"),
              ("Meta açıklama", "meta", "Meta açıklama sorunlu"),
              ("Hedef kelime meta", "meta", "Meta açıklama sorunlu")]
FAIL_LABELS = {}
for _p, _c, _l in FAIL_CODES:
    FAIL_LABELS.setdefault(_c, _l)


def fail_codes(fails):
    out = []
    for f in fails:
        for prefix, code, _ in FAIL_CODES:
            if f.startswith(prefix):
                if code not in out:
                    out.append(code)
                break
    return out


class SeoScanner:
    def __init__(self):
        self.running = self.paused = self.stop_flag = False
        self.pause_ev = threading.Event()
        self.pause_ev.set()
        self.note = self.phase = ""
        self.total = 0
        self.started_at = None
        self.done_session = 0
        DBI.x("""CREATE TABLE IF NOT EXISTS seo(pid INTEGER PRIMARY KEY, sku TEXT, name TEXT, kw TEXT,
                 top INTEGER, bottom INTEGER, ok INTEGER, codes TEXT, fails TEXT, words INTEGER,
                 density REAL, checked TEXT)""")
        DBI.x("CREATE INDEX IF NOT EXISTS i_seo_ok ON seo(ok)")
        # uyarılar için fiyat ve stok bilgileri (uyari.py); SEO taramasında aynı ürün kayıtlarından, ek istek olmadan
        DBI.x("""CREATE TABLE IF NOT EXISTS urunbilgi(pid INTEGER PRIMARY KEY, sku TEXT, name TEXT, fiyat REAL, satis REAL,
                 alis REAL, indirim REAL, indirim_tip INTEGER, stok REAL, aktif INTEGER, secenekli INTEGER, para TEXT,
                 kats TEXT, guncellendi TEXT)""")
        for col in ("barkod TEXT", "baslik TEXT", "meta TEXT"):      # kopya ürün tespiti (kopya.py)
            try:
                DBI.x(f"ALTER TABLE urunbilgi ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        for col in ("gecis TEXT", "onceki TEXT",       # şablon geçişi: durum ve bir önceki gönderilen açıklama
                    "pscore TEXT", "src TEXT", "plan TEXT", "pstate TEXT", "pmsg TEXT", "backup TEXT",
                    "price REAL", "cur TEXT"):
            try:
                DBI.x(f"ALTER TABLE seo ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        self.score_src = ""
        # eski sürümle hazırlanmış (gönderilmemiş) açıklamaları yeniden üretilecek şekilde işaretle
        # eski sürümle hazırlanmış ya da gönderildiği hâlde hâlâ eksik olan ürünler yeniden hazırlanır
        DBI.x("""UPDATE seo SET pstate='', plan=NULL, pmsg=NULL WHERE ok=0
                 AND (plan IS NULL OR plan NOT LIKE '%"v": 6%')""")
        r = DBI.q("SELECT v FROM kv WHERE k='img_total'", one=True)
        self.total = int(r["v"]) if r else 0

    def start(self):
        if self.running:
            if self.paused:
                self.resume()
            return "Zaten çalışıyor."
        if not CFG.get("access_token") and not CFG.get("refresh_token"):
            return "Önce mağazaya bağlanın (Ayarlar)."
        self.running, self.paused, self.stop_flag, self.note = True, False, False, ""
        self.pause_ev.set()
        self.started_at, self.done_session = time.time(), 0
        spawn(self._run)
        return "SEO analizi başladı."

    def pause(self):
        self.paused = True
        self.pause_ev.clear()

    def resume(self):
        self.paused = False
        self.pause_ev.set()

    def stop(self):
        self.stop_flag = True
        self.pause_ev.set()

    def _pages(self, res, params=None, label=""):
        """res kaynağının tüm kayıtlarını 100'erli sayfalarla getirir (duraklat/durdur destekli)."""
        page, seen = 1, set()
        while not self.stop_flag:
            self.pause_ev.wait()
            if self.stop_flag:
                return
            self.phase = f"{label} okunuyor (sayfa {page})"
            r = API.call("GET", res, dict(params or {}, limit=100, page=page)) or []
            new = [x for x in r if x.get("id") not in seen]
            if not new:  # sayfa parametresi desteklenmiyorsa aynı kayıtlar döner: dur
                return
            seen.update(x.get("id") for x in new)
            yield from new
            if len(r) < 100:
                return
            page += 1

    def _run(self):
        """Sadece Ideasoft'un ürün kaydındaki SEO kural sayılarını okur; açıklama ya da içerik taramaz."""
        try:
            n = IMG._count() if IMG else 0
            if n:
                self.total = n
            scan_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last, warned = 0, False
            # Liste yanıtında tamamlanan kural sayısı yoksa tek ürün kaydında olup olmadığına bak
            self.single = False
            first = API.call("GET", "products", {"limit": 1, "sort": "id"}) or []
            if first and panel_pct(seo_fields(first[0])) is None:
                full = API.call("GET", f"products/{first[0]['id']}") or {}
                if panel_pct(seo_fields(full)) is not None:
                    self.single = True
                    log("SEO yüzdesi tek tek ürün kayıtlarından okunacak (biraz daha uzun sürer).")
            while not self.stop_flag:
                self.pause_ev.wait()
                if self.stop_flag:
                    break
                self.phase = "ürünler okunuyor"
                prm = {"limit": 100, "sort": "id"}
                if last:
                    prm["sinceId"] = last
                page = [p for p in (API.call("GET", "products", prm) or []) if p.get("id", 0) > last]
                if not page:
                    break
                rows, bilgi, now = [], [], datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if self.single:
                    page = pmap(lambda q: API.call("GET", f"products/{q['id']}") or q, page, 4)
                for p in page:
                    fields = seo_fields(p)
                    pct = panel_pct(fields)
                    if pct is None and not warned:
                        warned = True
                        log("Ürün kaydında tamamlanan kural sayısı bulunamadı. Bulunan SEO alanları: "
                            + (", ".join(f"{k}={v}" for k, v in fields.items()) or "yok"), "warn")
                    ok = None if pct is None else (1 if pct >= 100 else 0)
                    info = ", ".join(f"{k}={v}" for k, v in fields.items())
                    price, cur = sale_price(p)
                    rows.append((p["id"], p.get("sku"), p.get("name"), "", None, None,
                                 -1 if ok is None else ok, "", "[]", None, None, now,
                                 None if pct is None else str(pct), info, price, cur))
                    bilgi.append((p["id"], p.get("sku"), p.get("name"), _num(p.get("price1")), price,
                                  _num(p.get("buyingPrice")), _num(p.get("discount")), int(_num(p.get("discountType")) or 0),
                                  _num(p.get("stockAmount")), None if p.get("status") is None else (0 if _pasif(p) else 1),
                                  1 if p.get("hasOption") else 0, cur, json.dumps(_cat_ids(p)), now,
                                  p.get("barcode"), p.get("pageTitle"), p.get("metaDescription")))
                DBI.xm("""INSERT INTO seo(pid, sku, name, kw, top, bottom, ok, codes, fails, words,
                          density, checked, pscore, src, price, cur) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                          ON CONFLICT(pid) DO UPDATE SET sku=excluded.sku, name=excluded.name, ok=excluded.ok,
                          checked=excluded.checked, pscore=excluded.pscore, src=excluded.src,
                          price=excluded.price, cur=excluded.cur""", rows)
                DBI.xm("""INSERT OR REPLACE INTO urunbilgi(pid, sku, name, fiyat, satis, alis, indirim, indirim_tip, stok, aktif,
                          secenekli, para, kats, guncellendi, barkod, baslik, meta) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", bilgi)
                self.done_session += len(rows)
                last = max(p["id"] for p in page)
                if CFG.get("seo_prepare", True):
                    todo = [r["pid"] for r in DBI.q(
                        f"SELECT pid FROM seo WHERE ok=0 AND (pstate IS NULL OR pstate='') AND pid IN "
                        f"({','.join(str(x[0]) for x in rows)})")]
                    if todo:
                        self.phase = f"{len(todo)} eksik ürün için açıklama hazırlanıyor"

                        def prep(pid):
                            try:
                                prepare_plan(pid)
                            except Exception as e:  # noqa: BLE001
                                DBI.x("UPDATE seo SET pstate='hata', pmsg=? WHERE pid=?", (f"Hazırlanamadı: {str(e)[:200]}", pid))
                        pmap(prep, todo, 3)
            if not self.stop_flag:
                DBI.x("DELETE FROM seo WHERE checked < ?", (scan_start,))  # mağazadan silinmiş ürünler
                DBI.x("DELETE FROM urunbilgi WHERE guncellendi < ?", (scan_start,))
            c = seo_counts()
            if not self.stop_flag:
                anlik_al()                                      # aylık rapor için durum fotoğrafı
            log(f"SEO analizi {'durduruldu' if self.stop_flag else 'bitti'}: {c['ok']} ürün %100, "
                f"{c['eksik']} ürün eksik" + (f", {c['bilinmiyor']} ürünün puanı okunamadı" if c['bilinmiyor'] else "") + ".",
                "ok")
        except Exception as e:  # noqa: BLE001
            self.note = f"SEO analizi hata ile durdu: {e}"
            log(self.note, "err")
            traceback.print_exc()
        finally:
            self.running = self.paused = False
            self.phase = ""

    def _panel_scores(self, loc, kws):
        """Metafield ve SEO ayarlarında SEO puanı gibi görünen bir alan arar. Dönüş: {pid: ham değer, '__src__': ad}"""
        name_rx = re.compile(r"seo|score|puan|rate|oran|percent|yuzde|yüzde", re.I)
        try:
            by_key = {}
            for r in self._pages("metafields", {"context": "product"}, "SEO puanı aranıyor"):
                k, v, pid = r.get("varKey") or "", r.get("varValue"), r.get("contextItemId")
                if pid and name_rx.search(k) and score_pct(v) is not None:
                    by_key.setdefault(k, {})[int(pid)] = v
            if by_key:
                k = max(by_key, key=lambda x: len(by_key[x]))
                out = dict(by_key[k])
                out["__src__"] = f"metafield › {k}"
                log(f"Panel SEO puanı bulundu: metafield › {k} ({len(by_key[k])} ürün).", "ok")
                return out
            by_key = {}
            for r in self._pages("seo_settings", {"context": "product"}, "SEO puanı aranıyor"):
                pid = r.get("contextItemId")
                val = _parse_jsonish(r.get("jsonValue"))
                for k, v in (val.items() if isinstance(val, dict) else []):
                    if pid and name_rx.search(k) and score_pct(v) is not None:
                        by_key.setdefault(k, {})[int(pid)] = v
            if by_key:
                k = max(by_key, key=lambda x: len(by_key[x]))
                out = dict(by_key[k])
                out["__src__"] = f"SEO ayarları › {k}"
                log(f"Panel SEO puanı bulundu: SEO ayarları › {k}.", "ok")
                return out
        except ApiError as e:
            log(f"SEO puanı aranırken: {e}", "warn")
        return {}

    def state(self):
        el = time.time() - self.started_at if self.started_at and self.running else 0
        rate = self.done_session / el * 60 if el > 3 else 0
        c = seo_counts()
        left = max(0, self.total - c["taranan"]) if self.total else None
        return {"running": self.running, "paused": self.paused, "note": self.note, "phase": self.phase,
                "total": self.total, "rate": round(rate),
                "eta_min": (round(left / rate) if rate and left else None), "counts": c,
                "has_loc": bool(kw_loc())}


def score_pct(v):
    """'92', 92, '%92', '12/13', 0.92 gibi değerleri yüzdeye çevirir; sayı değilse None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
    else:
        t = str(v).strip().replace("%", "").replace(",", ".")
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", t)
        if m:
            return round(100 * float(m.group(1)) / float(m.group(2))) if float(m.group(2)) else None
        try:
            x = float(t)
        except ValueError:
            return None
    if 0 < x <= 1 and not float(x).is_integer():
        x *= 100
    return round(x) if 0 <= x <= 100 else None


def sale_price(p):
    """Ürünün indirimli (satış) fiyatı ve para birimi.
    Ideasoft: discountType 1 = yüzde indirim ("Oran"), 0 = panelde "Fiyat" seçili; bu durumda
    indirim kutusundaki değer indirimli fiyatın kendisidir (ör. 440 -> 326.7)."""
    try:
        price = float(p.get("price1") or 0)
        d = float(p.get("discount") or 0)
    except (TypeError, ValueError):
        return None, None
    cur = p.get("currency") or {}
    cur = (cur.get("abbr") or cur.get("label") or cur.get("code") or "") if isinstance(cur, dict) else str(cur)
    if d > 0:
        if int(p.get("discountType") or 0) == 1:
            price = price * (1 - d / 100)
        elif d < price:
            price = d
    return round(price, 2), cur.upper()


def seo_fields(p):
    """Ürün kaydındaki SEO ile ilgili basit alanlar (iç içe olanlar dahil, en fazla 2 seviye)."""
    out = {}

    def walk(o, pre, depth):
        for k, v in o.items():
            path = f"{pre}{k}"
            if isinstance(v, dict) and depth < 2 and k not in ("seoSetting", "detail"):
                walk(v, path + ".", depth + 1)
            elif not isinstance(v, (dict, list)) and re.search(r"seo|rule|solved", path, re.I):
                out[path] = v
    walk(p, "", 0)
    return out


def _num(v):
    try:
        return float(str(v).replace("%", "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def panel_pct(fields):
    """Ideasoft'un ürün listesindeki SEO yüzdesi: tamamlanan kural / toplam kural (ya da hazır puan)."""
    total = done = score = None
    for k, v in fields.items():
        x = _num(v)
        if x is None:
            continue
        low = k.lower()
        if "rule" in low and "total" in low:
            total = x
        elif "solved" in low or "rule" in low:  # Ideasoft: solvedCount = tamamlanan kural sayısı
            done = x if done is None else done
        elif re.search(r"score|percent|rate|puan|point|oran", low) and 0 <= x <= 100:
            score = x
    if total and done is not None:
        return round(done / total * 100)
    if score is not None:
        return round(score)
    return None


def seo_counts():
    r = DBI.q("SELECT SUM(ok=1) o, SUM(ok=0) e, SUM(ok=-1) b, COUNT(*) n FROM seo", one=True)
    groups = {}
    for g in DBI.q("SELECT pscore, COUNT(*) n FROM seo WHERE ok=0 GROUP BY pscore ORDER BY CAST(pscore AS INTEGER) DESC"):
        groups[f"p{g['pscore']}"] = {"label": f"%{g['pscore']}", "n": g["n"]}
    return {"ok": r["o"] or 0, "eksik": r["e"] or 0, "bilinmiyor": r["b"] or 0, "taranan": r["n"] or 0,
            "reasons": groups}


SEOSCAN = _Ref("seoscan")

# ============================================================ kategori analizi (sadece okur)

def _ref_id(v):
    """Ideasoft ilişki alanı: {'id': 5, ...} ya da 5 -> 5"""
    if isinstance(v, dict):
        v = v.get("id")
    try:
        return int(v) if v not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


class CatScanner:
    """Kategorileri ve ürünlerin kategorilerini okur, kategori.py ile analiz eder. Mağazaya hiçbir şey yazmaz."""

    def __init__(self):
        self.running = self.stop_flag = False
        self.note = self.phase = ""
        DBI.x("CREATE TABLE IF NOT EXISTS cat(id INTEGER PRIMARY KEY, name TEXT, parent INTEGER)")
        DBI.x("CREATE TABLE IF NOT EXISTS catprod(pid INTEGER PRIMARY KEY, sku TEXT, name TEXT, cats TEXT)")
        try:
            DBI.x("ALTER TABLE catprod ADD COLUMN brand TEXT")   # yeni kategori SEO'sunda ürünlerin markası
        except sqlite3.OperationalError:
            pass
        try:
            DBI.x("ALTER TABLE catprod ADD COLUMN status INTEGER")   # 0 = pasif (sitede görünmez); boş = bilinmiyor
        except sqlite3.OperationalError:
            pass
        DBI.x("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
        # uygulanan kategori değişiklikleri: önceki ve sonraki kategoriler (geri almak için)
        DBI.x("""CREATE TABLE IF NOT EXISTS catfix(pid INTEGER PRIMARY KEY, sug TEXT, before TEXT, after TEXT,
                 state TEXT, msg TEXT, at TEXT)""")
        # açılan yeni kategori önerileri (aynı öneri iki kez açılmasın)
        DBI.x("CREATE TABLE IF NOT EXISTS catnew(key TEXT PRIMARY KEY, cid INTEGER, name TEXT, at TEXT)")
        r = DBI.q("SELECT v FROM kv WHERE k='cat_report'", one=True)
        self.report = json.loads(r["v"]) if r else None
        if self.report and self.report.get("v") != 4:  # eski sürümün raporu: "Yeniden hesapla" ile yenilenir
            self.report = None

    def start(self, fetch=True):
        if self.running:
            return "Zaten çalışıyor."
        if fetch and not CFG.get("access_token") and not CFG.get("refresh_token"):
            return "Önce mağazaya bağlanın (Ayarlar)."
        if not fetch and not DBI.q("SELECT 1 FROM catprod LIMIT 1"):
            return "Önce mağazadan ürünleri okuyun (Analizi başlat)."
        self.running, self.stop_flag, self.note = True, False, ""
        spawn(self._run, fetch)
        return "Kategori analizi başladı." if fetch else "Analiz kayıtlı verilerle yeniden hesaplanıyor."

    def stop(self):
        self.stop_flag = True

    def _pages(self, res, label, params=None):
        page, seen = 1, set()
        while not self.stop_flag:
            self.phase = f"{label} okunuyor (sayfa {page})"
            r = API.call("GET", res, dict(params or {}, limit=100, page=page)) or []
            new = [x for x in r if x.get("id") not in seen]
            if not new:
                return
            seen.update(x.get("id") for x in new)
            yield from new
            if len(r) < 100:
                return
            page += 1

    def _fetch(self):
        cats = [(c["id"], (c.get("name") or "").strip(), _ref_id(c.get("parent")))
                for c in self._pages("categories", "Kategoriler") if c.get("id")]
        if self.stop_flag:
            return False
        log(f"Kategori analizi: {len(cats)} kategori okundu.")
        prods, last, has_key = {}, 0, False
        while not self.stop_flag:
            self.phase = f"ürünler okunuyor ({len(prods):,} ürün)".replace(",", ".")
            prm = {"limit": 100, "sort": "id"}
            if last:
                prm["sinceId"] = last
            page = [p for p in (API.call("GET", "products", prm) or []) if p.get("id", 0) > last]
            if not page:
                break
            for p in page:
                has_key = has_key or "categories" in p
                ids = [_ref_id(c) for c in (p.get("categories") or [])]
                st = p.get("status")
                prods[p["id"]] = [p.get("sku") or "", p.get("name") or "", [i for i in ids if i], PR.product_brand(p),
                                  None if st is None else (0 if str(st) in ("0", "False", "false") else 1)]
            last = max(p["id"] for p in page)
        if self.stop_flag:
            return False
        if prods and not has_key:
            # ürün listesinde kategori yoksa ürün-kategori bağlantıları ayrıca okunur
            log("Ürün listesinde kategori bilgisi yok; ürün-kategori bağlantıları ayrıca okunuyor.", "warn")
            for r in self._pages("product_to_categories", "Ürün-kategori bağlantıları"):
                pid, cid = _ref_id(r.get("product")), _ref_id(r.get("category"))
                if pid in prods and cid and cid not in prods[pid][2]:
                    prods[pid][2].append(cid)
            if self.stop_flag:
                return False
        with DBI.lock:
            DBI.c.execute("DELETE FROM cat")
            DBI.c.executemany("INSERT INTO cat(id, name, parent) VALUES(?,?,?)", cats)
            DBI.c.execute("DELETE FROM catprod")
            DBI.c.executemany("INSERT INTO catprod(pid, sku, name, cats, brand, status) VALUES(?,?,?,?,?,?)",
                              [(pid, s, n, json.dumps(c), b, st) for pid, (s, n, c, b, st) in prods.items()])
            DBI.c.commit()
        log(f"Kategori analizi: {len(prods)} ürün okundu.")
        return True

    def _run(self, fetch):
        try:
            if fetch and not self._fetch():
                self.note = "Durduruldu; önceki analiz sonuçları korunuyor."
                return
            self.phase = "analiz ediliyor"
            cats = {r["id"]: {"name": r["name"], "parent": r["parent"]} for r in DBI.q("SELECT * FROM cat")}
            prods = [{"pid": r["pid"], "sku": r["sku"], "name": r["name"], "cats": json.loads(r["cats"] or "[]"),
                      "active": r["status"] != 0}
                     for r in DBI.q("SELECT * FROM catprod ORDER BY pid")]

            def prog(i, n):
                self.phase = f"analiz ediliyor ({i * 100 // max(n, 1)}%)"
            rep = KT.analyze(cats, prods, prog)
            rep["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            DBI.x("INSERT OR REPLACE INTO kv(k, v) VALUES('cat_report', ?)", (json.dumps(rep, ensure_ascii=False),))
            self.report = rep
            s = rep["summary"]
            log(f"Kategori analizi bitti: {s['tasi']} ürün taşınmalı, {s['supheli']} ürün şüpheli, {s['ekle']} ürün başka bir "
                f"kategoriye de eklenebilir, {s['kategorisiz']} ürün kategorisiz, {s['oneri']} yeni kategori önerisi.", "ok")
        except Exception as e:  # noqa: BLE001
            self.note = f"Kategori analizi hata ile durdu: {e}"
            log(self.note, "err")
            traceback.print_exc()
        finally:
            self.running = False
            self.phase = ""

    def state(self):
        rep = self.report or {}
        n = DBI.q("SELECT COUNT(*) n FROM catprod", one=True)["n"]
        fx = DBI.q("SELECT SUM(state='uygulandi') u, SUM(state='hata') h FROM catfix", one=True)
        return {"running": self.running, "phase": self.phase, "note": self.note, "stored": n,
                "summary": rep.get("summary"), "generated": rep.get("generated"),
                "panel": API.base() if CFG.get("store") else "", "jobs": CATJOBS.state(),
                "applied": fx["u"] or 0, "failed": fx["h"] or 0,
                "connected": bool(CFG.get("access_token") or CFG.get("refresh_token"))}

    def rows(self, kind, q="", conf="", min_score=0, pending=False):
        rep = self.report or {}
        items = rep.get(kind) or []
        if kind in ("wrong", "uncat"):
            fix = {r["pid"]: r for r in DBI.q("SELECT pid, state, msg FROM catfix")}
            items = [dict(it, fix=fix[it["pid"]]["state"], fixmsg=fix[it["pid"]]["msg"]) if it["pid"] in fix else it
                     for it in items]
            if min_score:
                items = [it for it in items if it.get("score", 0) >= min_score]
            if pending:
                items = [it for it in items if it.get("fix") not in ("uygulandi", "geri")]
        if kind == "newcats":
            made = {r["key"]: {"cid": r["cid"], "name": r["name"]} for r in DBI.q("SELECT key, cid, name FROM catnew")}
            items = [dict(it, i=i, created=made.get(newcat_key(it))) for i, it in enumerate(items)]
            if conf in ("alt", "genel"):
                items = [it for it in items if it["kind"] == conf]
            if pending:
                items = [it for it in items if not it["created"]]
        if kind == "wrong" and conf in ("tasi", "ekle", "supheli"):
            items = [it for it in items if it["act"] == conf]
        if kind == "uncat" and conf in ("guclu", "yok"):   # önerisi olan / olmayan
            items = [it for it in items if bool(it.get("sug")) == (conf == "guclu")]
        if kind == "categories" and conf == "az":
            items = [it for it in items if it["total"] <= 2 and not it["children"]]
        if q:
            ql = ST.tr_lower(q)
            items = [it for it in items if ql in ST.tr_lower(" ".join(
                str(it.get(k) or "") for k in ("pid", "sku", "name", "sug", "label", "parent", "path")) + " "
                + " ".join(it.get("cur") or []))]
        return items

    def tasks(self, kind, q="", conf="", min_score=0, pids=None):
        """Uygulanacak işler: listedeki (filtreye uyan, henüz uygulanmamış) ya da seçilen ürünler."""
        items = self.rows(kind, q, conf, min_score, pending=True)
        if pids is not None:
            want = set(pids)
            items = [it for it in items if it["pid"] in want]
        return [{"pid": it["pid"], "add": it["add"], "rem": it["rem"], "sug": it["sug"]}
                for it in items if it.get("add") or it.get("rem")]

    def item(self, kind, pid):
        return next((it for it in self.rows(kind) if it["pid"] == pid), None)

    def group(self, i):
        rep = self.report or {}
        items = rep.get("newcats") or []
        if not 0 <= i < len(items):
            return None
        g = dict(items[i])
        pids = g.pop("pids")
        names = {r["id"]: r["name"] for r in DBI.q("SELECT id, name FROM cat")}
        rows = []
        for k in range(0, len(pids), 500):
            chunk = pids[k:k + 500]
            rows += DBI.q(f"SELECT pid, sku, name, cats FROM catprod WHERE pid IN ({','.join('?' * len(chunk))})", chunk)
        g["products"] = [{"pid": r["pid"], "sku": r["sku"], "name": r["name"],
                          "cats": ", ".join(names.get(c, f"#{c}") for c in json.loads(r["cats"] or "[]")) or "Kategorisiz"}
                         for r in rows]
        return g

    def csv(self, kind):
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        items = self.rows(kind)
        if kind == "wrong":
            acts = {"tasi": "Taşınmalı", "ekle": "Eklenebilir", "supheli": "Şüpheli"}
            w.writerow(["Ürün no", "Stok kodu", "Ürün adı", "Öneri", "Güven", "Şu anki kategori", "Uymayan kategori",
                        "Önerilen kategori", "Neden", "Durum"])
            for it in items:
                w.writerow([it["pid"], it["sku"], it["name"], acts[it["act"]], it["score"], " | ".join(it["cur"]),
                            " | ".join(it["bad"]), it["sug"], it["reason"], it.get("fixmsg") or ""])
        elif kind == "uncat":
            w.writerow(["Ürün no", "Stok kodu", "Ürün adı", "Önerilen kategori", "Güven", "Neden", "Durum"])
            for it in items:
                w.writerow([it["pid"], it["sku"], it["name"], it["sug"], it["score"], it["reason"], it.get("fixmsg") or ""])
        elif kind == "newcats":
            w.writerow(["Tür", "Üst kategori", "Önerilen kategori", "Ürün sayısı", "Ürün nolar"])
            for it in items:
                w.writerow(["Alt kategori" if it["kind"] == "alt" else "Yeni kategori", it["parent"] or "–",
                            it["label"], it["count"], " ".join(map(str, it["pids"]))])
        else:
            w.writerow(["Kategori no", "Kategori", "Doğrudan ürün", "Alt kategorilerle", "Alt kategori sayısı", "Uyum %"])
            for it in items:
                w.writerow([it["id"], it["path"], it["direct"], it["total"], it["children"],
                            "" if it["uyum"] is None else it["uyum"]])
        return "﻿" + buf.getvalue()  # Excel Türkçe karakterleri doğru açsın


CATSCAN = _Ref("catscan")

# ============================================================ kategori önerilerini uygulama (kullanıcı onaylı)
#
# Sadece ürünün kategorileri değişir. Yazmadan önce ürün yeniden okunur; kategorileri analizden sonra
# değişmişse dokunulmaz. Yazdıktan sonra ürün tekrar okunur: kategoriler beklendiği gibi mi, fiyat/stok gibi
# korunan alanlar aynı mı kontrol edilir. Korunan alan değişirse ürün eski hâline yazılır ve toplu işlem durur.

def _cat_ids(prod):
    return [i for i in (_ref_id(c) for c in (prod.get("categories") or [])) if i]


def _write_cats(pid, prod, target, mode):
    if mode == "put":
        keep = {_ref_id(c): c for c in prod.get("categories") or []}
        payload = {k: v for k, v in copy.deepcopy(prod).items() if k not in READONLY}
        payload["categories"] = [keep.get(c) or {"id": c} for c in target]
        API.call("PUT", f"products/{pid}", body=payload)
        return
    # ürün-kategori bağlantıları tek tek eklenir / silinir
    cur = _cat_ids(API.get_product(pid))
    for a in target:
        if a not in cur:
            API.call("POST", "product_to_categories", body={"product": {"id": pid}, "category": {"id": a}})
    rm = [c for c in cur if c not in target]
    if rm:
        for link in API.call("GET", "product_to_categories", {"product": pid, "limit": 100}) or []:
            if _ref_id(link.get("product")) == pid and _ref_id(link.get("category")) in rm and link.get("id"):
                API.call("DELETE", f"product_to_categories/{link['id']}")


def apply_categories(pid, add, rem, expect=None, bos_olabilir=False):
    """Ürüne add kategorilerini ekler, rem kategorilerini çıkarır. Dönüş: (durum, mesaj, önceki, sonraki)
    bos_olabilir: yalnızca geri alma; ürün düzeltmeden önce kategorisizdiyse yine kategorisiz kalabilir."""
    prod = API.get_product(pid)
    before = _cat_ids(prod)
    if expect is not None and set(before) != set(expect):
        return "degisti", "Ürünün kategorileri analizden sonra değişmiş; dokunulmadı. Yeniden hesaplayıp tekrar deneyin.", before, before
    target = [c for c in before if c not in rem] + [a for a in dict.fromkeys(add) if a not in before]
    if set(target) == set(before):
        return "uygulandi", "Ürün zaten istenen kategorilerde.", before, before
    if not target and not bos_olabilir:
        return "hata", "Ürün hiçbir kategoride kalmayacaktı; uygulanmadı.", before, before
    fp_before = Ideasoft.fingerprint(prod)
    fp_before.pop("categories", None)
    first = CFG.get("cat_write_mode") or "put"
    last = ""
    for mode in [first] + [m for m in ("put", "link") if m != first]:
        try:
            _write_cats(pid, prod, target, mode)
        except ApiError as e:
            last = str(e)[:200]
        after = API.get_product(pid)
        fp = Ideasoft.fingerprint(after)
        fp.pop("categories", None)
        if fp != fp_before:
            diff = [k for k, v in fp_before.items() if fp.get(k) != v]
            try:
                API.call("PUT", f"products/{pid}", body={k: v for k, v in prod.items() if k not in READONLY})
            except ApiError:
                pass
            back = Ideasoft.fingerprint(API.get_product(pid))
            back.pop("categories", None)
            still = [k for k, v in fp_before.items() if back.get(k) != v]
            if still:
                return ("koruma", f"Korunan alan değişti ({', '.join(diff)}) ve geri yazılamadı: {', '.join(still)} "
                                  f"alanlarını Ideasoft panelinden kontrol edin.", before, before)
            return "koruma", f"Korunan alan değişti ({', '.join(diff)}); ürün eski hâline geri yazıldı.", before, before
        now = _cat_ids(after)
        if set(now) == set(target):
            if mode != CFG.get("cat_write_mode"):
                CFG.update(cat_write_mode=mode)
            return "uygulandi", "Kategoriler Ideasoft'a yazıldı.", before, now
        last = last or f"{mode} yöntemiyle kategoriler kaydedilmedi"
    return "hata", f"Ideasoft kategori değişikliğini kabul etmedi ({last}).", before, _cat_ids(API.get_product(pid))


def cat_fix(pid, add, rem, sug="", undo=False):
    """Bir ürüne öneriyi uygular (ya da geri alır), sonucu kaydeder. Dönüş: (durum, mesaj)"""
    row = DBI.q("SELECT cats FROM catprod WHERE pid=?", (pid,), one=True)
    expect = json.loads(row["cats"]) if row else None
    state, msg, before, after = apply_categories(pid, add, rem, expect, bos_olabilir=undo)
    if state == "uygulandi":
        olay("geri" if undo else "kategori", pid)
        DBI.x("UPDATE catprod SET cats=? WHERE pid=?", (json.dumps(after), pid))
        if undo:
            DBI.x("UPDATE catfix SET state='geri', msg=?, at=? WHERE pid=?",
                  ("Geri alındı; eski kategoriler yazıldı.", datetime.now().strftime("%Y-%m-%d %H:%M"), pid))
        else:
            DBI.x("INSERT OR REPLACE INTO catfix(pid, sug, before, after, state, msg, at) VALUES(?,?,?,?,?,?,?)",
                  (pid, sug, json.dumps(before), json.dumps(after), "uygulandi", msg, datetime.now().strftime("%Y-%m-%d %H:%M")))
    elif not undo:
        DBI.x("INSERT OR REPLACE INTO catfix(pid, sug, before, after, state, msg, at) VALUES(?,?,?,?,?,?,?)",
              (pid, sug, json.dumps(before), json.dumps(after), "hata", msg, datetime.now().strftime("%Y-%m-%d %H:%M")))
    log(f"Kategori {'geri alma' if undo else 'düzeltme'} ürün {pid}: {msg}",
        "ok" if state == "uygulandi" else ("err" if state == "koruma" else "warn"))
    return state, msg


def cat_undo(pid):
    r = DBI.q("SELECT before, after FROM catfix WHERE pid=? AND state='uygulandi'", (pid,), one=True)
    if not r:
        return "hata", "Bu ürün için geri alınacak bir değişiklik yok."
    before, after = json.loads(r["before"]), json.loads(r["after"])
    return cat_fix(pid, [c for c in before if c not in after], [c for c in after if c not in before], undo=True)


class CatJobs:
    """Toplu işçi: kategori düzeltmeleri ve yeni kategori açma. Ürünler sırayla (tek tek) yazılır;
    korunan alan değişirse durur. Görevler: {"pid", "add", "rem"} ya da {"type": "create", "group", "name"}."""

    def __init__(self):
        self.running, self.stop_flag, self.label, self.current = False, False, "", ""
        self.done = self.todo = self.ok = self.err = 0
        self.results = []   # açılan kategoriler: {"name", "cid", "notes"} ya da {"name", "error"}

    def start(self, tasks, label):
        if self.running:
            return "Başka bir uygulama sürüyor."
        if not CFG.get("access_token") and not CFG.get("refresh_token"):
            return "Önce mağazaya bağlanın (Ayarlar)."
        if not tasks:
            return "Uygulanacak ürün yok."
        self.running, self.stop_flag, self.label, self.current = True, False, label, ""
        self.done, self.ok, self.err, self.results = 0, 0, 0, []
        self.todo = sum(1 + len(t["group"]["pids"]) if t.get("type") == "create" else 1 for t in tasks)
        spawn(self._run, list(tasks))
        cats = sum(1 for t in tasks if t.get("type") == "create")
        prods = self.todo - cats
        return (f"{cats} kategori açılıyor ve {prods} ürün taşınıyor." if cats else f"{prods} ürün için {label} başladı.")

    def stop(self):
        self.stop_flag = True

    def _create(self, t, queue):
        g, name = t["group"], t["name"]
        self.current = f"“{name}” kategorisi açılıyor"
        try:
            seo = t.get("seo")
            if seo is None:
                rows = DBI.q(f"SELECT name, brand FROM catprod WHERE pid IN ({','.join('?' * len(g['pids']))})", g["pids"])
                seo = KT.category_seo(name, g["parent"], [r["name"] for r in rows], PROFILE(), [r["brand"] for r in rows])
            img = t.get("image")
            if img is None:
                cands = category_image_candidates(g["pids"], limit=1)
                img = cands[0]["url"] if cands else ""
            cid, notes = create_category(name, g["parent_id"], seo, img)
        except Exception as e:  # noqa: BLE001
            self.err += 1
            self.todo -= len(g["pids"])   # ürünleri taşınmayacak
            self.results.append({"name": name, "error": str(e)[:200]})
            log(f"Kategori açılamadı ({name}): {e}", "err")
            return
        self.ok += 1
        DBI.x("INSERT OR REPLACE INTO catnew(key, cid, name, at) VALUES(?,?,?,?)",
              (newcat_key(g), cid, name, datetime.now().strftime("%Y-%m-%d %H:%M")))
        olay("kategori_ac", cid)
        self.results.append({"name": name, "cid": cid, "notes": notes})
        move = (CATSCAN.report or {}).get("with_parents") is False
        pids = g["pids"]
        if move:  # aynı ürün iki öneride olabilir: önceki öneriyle üst kategoriden çıkarılmış ürüne dokunulmaz
            cur = {r["pid"]: json.loads(r["cats"] or "[]") for r in DBI.q(
                f"SELECT pid, cats FROM catprod WHERE pid IN ({','.join('?' * len(pids))})", pids)}
            keep = [p for p in pids if g["parent_id"] in cur.get(p, [])]
            self.todo -= len(pids) - len(keep)
            pids = keep
        queue[0:0] = [{"pid": pid, "add": [cid], "rem": [g["parent_id"]] if move else [], "sug": name} for pid in pids]

    def _run(self, queue):
        try:
            while queue and not self.stop_flag:
                t = queue.pop(0)
                if t.get("type") == "create":
                    self._create(t, queue)
                    self.done += 1
                    continue
                row = DBI.q("SELECT name FROM catprod WHERE pid=?", (t["pid"],), one=True)
                self.current = (f"{t['sug']}: " if t.get("sug") else "") + ((row and row["name"]) or f"ürün {t['pid']}")
                try:
                    state, _ = cat_fix(t["pid"], t["add"], t["rem"], t.get("sug", ""))
                except Exception as e:  # noqa: BLE001
                    state = "hata"
                    log(f"Kategori düzeltme ürün {t['pid']}: {e}", "err")
                self.done += 1
                if state == "uygulandi":
                    self.ok += 1
                else:
                    self.err += 1
                if state == "koruma":
                    log("Korunan bir alan değiştiği için toplu işlem durduruldu.", "err")
                    break
        finally:
            log(f"{self.label[:1].upper() + self.label[1:]} {'durduruldu' if self.stop_flag else 'bitti'}: "
                f"{self.ok} işlem başarılı, {self.err} işlem başarısız.", "ok")
            self.running, self.current = False, ""

    def state(self):
        return {"running": self.running, "label": self.label, "done": self.done, "todo": self.todo,
                "ok": self.ok, "err": self.err, "current": self.current, "results": self.results[-40:]}


def jobs_state():
    """Süren arka plan işleri (her sayfada sol menüde gösterilir) ve menüdeki bekleyen iş sayıları."""
    pct = lambda a, b: round(100 * a / b) if b else None  # noqa: E731
    out = []
    s = SEOSCAN.state()
    if s["running"]:
        out.append({"t": "SEO analizi", "v": "seo", "d": s["phase"], "pct": pct(s["counts"]["taranan"], s["total"]), "paused": s["paused"]})
    j = SEOJOBS.state()
    if j["running"]:
        t = {"send": "SEO toplu gönderim", "repair": "Eksik ürünler inceleniyor", "prepare": "Açıklamalar hazırlanıyor"}.get(j["kind"], "SEO işlemi")
        out.append({"t": t, "v": "seo", "d": f"{j['done']} / {j['todo']} ürün", "pct": pct(j["done"], j["todo"])})
    i = IMG.state()
    if i["running"]:
        out.append({"t": "Görsel taraması", "v": "gorsel", "d": i["phase"], "pct": pct(img_counts()["taranan"], i["total"]), "paused": i["paused"]})
    if CATSCAN.running:
        out.append({"t": "Kategori analizi", "v": "kategori", "d": CATSCAN.phase, "pct": None})
    c = CATJOBS.state()
    if c["running"]:
        out.append({"t": c["label"][:1].upper() + c["label"][1:], "v": "kategori", "d": f"{c['done']} / {c['todo']} işlem",
                    "pct": pct(c["done"], c["todo"])})
    summ = (CATSCAN.report or {}).get("summary") or {}
    return {"jobs": out, "badges": {
        "seo": DBI.q("SELECT COUNT(*) n FROM seo WHERE ok=0", one=True)["n"],
        "gorsel": DBI.q("SELECT COUNT(*) n FROM img WHERE has=0", one=True)["n"],
        "kategori": (summ.get("tasi") or 0) + (summ.get("kategorisiz") or 0)}}


def overview():
    """Genel bakış: her ürün için SEO, görsel ve kategori durumu (aynı sırada) ve yapılacaklar sayıları.
    Durum harfleri: v = tamam, y = eksik, u = taranmadı; kategoride t = taşınmalı, s = şüpheli,
    e = eklenebilir, k = kategorisiz."""
    seo = {r["pid"]: r["ok"] for r in DBI.q("SELECT pid, ok FROM seo")}
    img = {r["pid"]: r["has"] for r in DBI.q("SELECT pid, has FROM img")}
    inst = {r["pid"]: bool(json.loads(r["cats"] or "[]")) for r in DBI.q("SELECT pid, cats FROM catprod")}
    rep = CATSCAN.report or {}
    done = {r["pid"] for r in DBI.q("SELECT pid FROM catfix WHERE state='uygulandi'")}
    act = {w["pid"]: {"tasi": "t", "supheli": "s", "ekle": "e"}[w["act"]] for w in rep.get("wrong") or []
           if w["pid"] not in done}
    pids = sorted(set(seo) | set(img) | set(inst))

    uncat = {w["pid"] for w in rep.get("uncat") or [] if w["pid"] not in done}

    def cat_code(p):
        if p not in inst or not rep:
            return "u"
        if p in act:
            return act[p]
        if p in uncat:
            return "k"
        return "v" if inst[p] or p in done else "u"   # kategorisiz ama pasif ürün: analiz dışı
    maps = {"seo": "".join({1: "v", 0: "y"}.get(seo.get(p), "u") for p in pids),
            "img": "".join({1: "v", 0: "y"}.get(img.get(p), "u") for p in pids),
            "cat": "".join(cat_code(p) for p in pids)}
    made = {r["key"] for r in DBI.q("SELECT key FROM catnew")}
    jobs = SEOJOBS.state()
    uy = Counter(u["grup"] for u in uyarilar()[0])
    uy["kopya"] = len(kopyalar())
    uy["kirik"] = DBI.q("SELECT COUNT(*) n FROM kirik", one=True)["n"]
    return {
        "pids": pids, "maps": maps,
        "counts": {"seo_eksik": maps["seo"].count("y"), "seo_hazir": jobs["hazir"],
                   "seo_taranan": len(seo), "img_yok": maps["img"].count("y"), "img_taranan": len(img),
                   "tasi": maps["cat"].count("t"), "supheli": maps["cat"].count("s"), "ekle": maps["cat"].count("e"),
                   "kategorisiz": maps["cat"].count("k"), "uyari_fiyat": uy["fiyat"], "uyari_satilamaz": uy["satilamaz"], "kopya": uy["kopya"], "kirik": uy["kirik"],
                   "yeni_kategori": sum(1 for g in rep.get("newcats") or [] if g["kind"] == "alt" and newcat_key(g) not in made)},
        "scans": {"seo": SEOSCAN.running, "cat": CATSCAN.running, "img": IMG.running,
                  "phase": SEOSCAN.phase or CATSCAN.phase or IMG.phase or "",
                  "note": SEOSCAN.note or CATSCAN.note or ""},     # son taramanın hata / durum notu
        "cat_ready": bool(rep), "connected": bool(CFG.get("access_token") or CFG.get("refresh_token")),
        "profil": PROFILE(),
    }


def uyarilar():
    """Taranan ürünlerin uyarıları (uyari.py); her istekte kayıtlı bilgilerden hesaplanır."""
    rows = DBI.q("SELECT * FROM urunbilgi")
    return UY.hesapla([dict(r, kats=json.loads(r["kats"] or "[]")) for r in rows]), len(rows)


def kopyalar():
    """Kopya ürün grupları (kopya.py); taramada kaydedilen bilgilerden her istekte hesaplanır."""
    return KP.hesapla([dict(r) for r in DBI.q("SELECT pid, sku, name, barkod, baslik, meta, aktif FROM urunbilgi")])


def category_paths():
    """Kategori no -> "Üst › Alt" yolu (yerel kategori listesinden)."""
    rows = {r["id"]: (r["name"], r["parent"]) for r in DBI.q("SELECT id, name, parent FROM cat")}
    out = {}
    for cid in rows:
        names, cur, seen = [], cid, set()
        while cur in rows and cur not in seen:
            seen.add(cur)
            names.append(rows[cur][0] or f"#{cur}")
            cur = rows[cur][1]
        out[cid] = " › ".join(reversed(names))
    return out


def newcat_key(g):
    """Bir yeni kategori önerisinin kalıcı anahtarı (analiz yeniden hesaplanınca sıra numarası değişebilir)."""
    return f"{g.get('parent_id')}|{ST.tr_lower(g.get('label') or '')}"


CATJOBS = _Ref("catjobs")


def _fetch_image(url):
    """Ürün görselini indirir. Dönüş: (bayt, uzantı) ya da (None, None)"""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = API.base() + url
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=40) as r:
        data = r.read()
    ext = next((e for sig, e in IMG_EXT.items() if data.startswith(sig)), None)
    if not ext and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = "webp"
    return (data, ext) if ext and len(data) > 2000 else (None, None)


def _image_url(rec):
    """Ideasoft görsel kaydındaki (alan adları ne olursa olsun) en büyük görselin adresi."""
    urls = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, k)
        elif isinstance(o, str) and re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", o, re.I) and o.startswith(("http", "//", "/")):
            urls.append((0 if re.search(r"original|big|large|full", key, re.I) else
                         2 if re.search(r"thumb|small|mini", key, re.I) else 1, o))
    walk(rec)
    return sorted(urls)[0][1] if urls else ""


def category_image_candidates(pids, limit=6):
    """Kategoriye taşınacak ürünlerin ana görselleri (ilk birkaç üründen)."""
    out = []
    for pid in pids[:15]:
        try:
            recs = API.call("GET", "product_images", {"product": pid, "limit": 5}) or []
        except ApiError:
            continue
        recs = [r for r in recs if str((r.get("product") or {}).get("id", pid)) == str(pid)]
        recs.sort(key=lambda r: r.get("sortOrder") or 0)
        u = _image_url(recs[0]) if recs else ""
        if u:
            out.append({"pid": pid, "url": "https:" + u if u.startswith("//") else (API.base() + u if u.startswith("/") else u)})
        if len(out) >= limit:
            break
    return out


def _category_schema():
    """Mağazadaki kategori kayıtlarının alan adları (alan adları sürüme göre değişebilir)."""
    try:
        sample = API.call("GET", "categories", {"limit": 50}) or []
    except ApiError:
        sample = []
    keys = set()
    for c in sample:
        keys.update(c)

    def pick(*rxs, avoid=r"^$"):
        for rx in rxs:
            for k in sorted(keys):
                if re.search(rx, k, re.I) and not re.search(avoid, k, re.I):
                    return k
        return None
    s = {
        "title": pick(r"^pageTitle$", r"^metaTitle$", r"seoTitle") or "pageTitle",
        "desc": pick(r"^metaDescription$", r"description$", avoid=r"content") or "metaDescription",
        "keys": pick(r"^metaKeywords$", r"keywords$", avoid=r"search") or "metaKeywords",
        "percent": "percent" if "percent" in keys or not keys else None,
        "image": pick(r"^imageFile$", r"^image$", avoid=r"url"),
    }
    return s


def create_category(name, parent_id, seo=None, image_url=""):
    """Ideasoft'ta yeni kategori açar; SEO bilgilerini ve resmi yazar (hedef kelime kategori adının kendisidir),
    sonra kategoriyi tekrar okuyup hangi alanların kaydedildiğini doğrular. Dönüş: (kategori no, [notlar])"""
    seo = seo or {}
    sch = _category_schema()
    body = {"name": name, "slug": seo.get("slug") or slugify(name), "status": 1, "sortOrder": 999}
    if sch["percent"]:
        body[sch["percent"]] = 1
    if parent_id:
        body["parent"] = {"id": parent_id}
    want = {sch["title"]: seo.get("pageTitle"), sch["desc"]: seo.get("metaDescription"), sch["keys"]: seo.get("metaKeywords")}
    want = {k: v for k, v in want.items() if v}
    body.update(want)
    r = API.call("POST", "categories", body=body) or {}
    cid = _ref_id(r.get("id"))
    if not cid:
        raise ApiError(0, f"Kategori oluşturuldu ama numarası okunamadı: {json.dumps(r)[:200]}")
    got = API.call("GET", f"categories/{cid}") or {}
    notes = []
    if parent_id and _ref_id(got.get("parent")) != parent_id:
        notes.append("Kategori istenen üst kategorinin altında görünmüyor.")
    labels = {sch["title"]: "sayfa başlığı", sch["desc"]: "meta açıklama", sch["keys"]: "anahtar kelimeler"}
    missing = [labels[k] for k, v in want.items() if not str(got.get(k) or "").strip()]
    notes.append("Ideasoft şu alanları kaydetmedi: " + ", ".join(missing) + "." if missing
                 else "SEO bilgileri kaydedildi." if want else "")
    DBI.x("INSERT OR REPLACE INTO cat(id, name, parent) VALUES(?,?,?)", (cid, got.get("name") or name, parent_id))
    log(f"Yeni kategori açıldı: {name} (no {cid}).", "ok")

    if image_url:
        notes.append(_category_image(cid, got, image_url, body["slug"], sch))
    pct = panel_pct(seo_fields(API.call("GET", f"categories/{cid}") or {}))
    if pct is not None:
        notes.insert(0, f"Ideasoft SEO puanı: %{pct}.")
    notes = [n for n in notes if n]
    for n in notes:
        log(f"Kategori {cid}: {n}", "warn" if re.search(r"kaydetmedi|yüklenemedi|yazılamadı|indirilemedi", n) else "info")
    return cid, notes


def _category_image(cid, got, url, slug, sch):
    try:
        data, ext = _fetch_image(url)
    except (urllib.error.URLError, socket.timeout, ConnectionError, ValueError) as e:
        return f"Resim indirilemedi: {str(e)[:120]}"
    if not data:
        return "Resim indirilemedi (geçerli bir görsel değil)."
    mime = "jpeg" if ext == "jpg" else ext
    att = f"data:image/{mime};base64," + __import__("base64").b64encode(data).decode()

    def has_image():
        c = API.call("GET", f"categories/{cid}") or {}
        return any(v for k, v in c.items() if re.search(r"image", k, re.I) and v and not isinstance(v, bool))
    body = {k: v for k, v in got.items() if k not in READONLY}
    body["attachment"] = att
    if sch.get("image"):
        body[sch["image"]] = f"{slug}.{ext}"
    errs = []
    try:
        API.call("PUT", f"categories/{cid}", body=body)
        if has_image():
            return "Resim yüklendi."
    except ApiError as e:
        errs.append(str(e)[:120])
    try:  # bazı sürümlerde kategori resmi ayrı bir kaynaktan yüklenir
        API.call("POST", "category_images", body={"category": {"id": cid}, "filename": slug, "extension": ext,
                                                  "attachment": att})
        if has_image():
            return "Resim yüklendi."
    except ApiError as e:
        errs.append(str(e)[:120])
    return "Resim yüklenemedi; Ideasoft panelinden ekleyebilirsiniz." + (f" ({'; '.join(errs)})" if errs else "")


# ============================================================ eksik SEO'ları tamamlama (elle onaylı)
#
# SEO analizinde kırmızı çıkan ürünlere açıklama HAZIRLANIR ama Ideasoft'a kendiliğinden
# GÖNDERİLMEZ. Kullanıcı ürünü açıp kontrol eder ve "Ideasoft'a gönder"e basar ya da
# "Toplu gönder" ile hazırlananların hepsini onaylayarak gönderir.

# Ideasoft'un kelime sayımı HTML etiketlerini de sayıyor; stil özelliklerini sayıp saymadığı kesin değil.
# Gönderilen ürünlerde panelin gösterdiği oranlar (%3,07 / %3,20) bu üç sayımın arasında kaldı; açıklama
# üçünde birden %2-%3 aralığına girecek şekilde kurulur.
SAFE_METHODS = "panel"
PLAN_VERSION = 6   # açıklama üreticisi değiştikçe artar; eski hazırlıklar yeniden üretilir


def sablon():
    """Mağazanın açıklama şablonu (sablon.py). Kaydedilmediyse bilgisayardaki kurulum (Ustapazar) sitedeki eski
    açıklamalarla aynı lacivert bantlı, sunucuda satılan sürüm sade görünümle başlar."""
    return TPL.yukle(CFG.get("sablon"), "sade" if SERVER["on"] else "bantli")


# Önizleme ürünü: mevcut açıklaması her bölümü içerir, böylece önizlemede bütün bölümler görünür
ORNEK_URUN = {"name": "Paslanmaz Çelik Termos 500 ml", "categories": [{"id": 0, "name": "Termoslar"}]}
ORNEK_ACIKLAMA = ("<h2>Öne Çıkan Özellikler</h2><ul><li>Çift cidarlı vakum yalıtım</li><li>Sızdırmaz kapak</li></ul>"
                  "<h2>Teknik Özellikler</h2><table><tr><td>Hacim</td><td>500 ml</td></tr>"
                  "<tr><td>Malzeme</td><td>18/8 paslanmaz çelik</td></tr></table>"
                  "<h2>Kullanım Alanları</h2><ul><li>Ofis</li><li>Kamp ve yürüyüş</li></ul>"
                  "<h2>Paket İçeriği</h2><ul><li>1 adet termos</li><li>Kullanım kılavuzu</li></ul>")


def sablon_onizleme(t):
    """Şablon önizlemesi: mağaza adıyla uydurma bir ürünün açıklaması ve Ideasoft SEO puanı tahmini."""
    method = CFG.get("count_method") or SAFE_METHODS
    plan = SM.build_machine_seo(ORNEK_URUN, ORNEK_ACIKLAMA, sku="ORNEK-1", barcode="8690000000001", method=method,
                                prof=PROFILE(), sablon=t)
    sc = ST.seo_score(ORNEK_URUN["name"], plan["keyword"], plan["details_html"], plan["pageTitle"],
                      plan["metaDescription"], method)
    kurallar = 13                                      # seo_score: 7 açıklama + 6 başlık / meta kuralı
    return {"html": plan["details_html"], "puan": round(100 * (kurallar - len(sc["fails"])) / kurallar),
            "yogunluk": sc["density"], "kelime": sc["words"], "eksikler": sc["fails"]}


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Yönlendirme yalnızca internetteki bir adrese olabilir (sunucunun iç ağına istek gönderilmesin)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not public_host(urllib.parse.urlparse(newurl).hostname or ""):
            raise urllib.error.URLError("iç ağa yönlendirme reddedildi")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def tema_rengi_oner():
    """Mağazanın ana sayfasından tema rengi önerisi; bulunamazsa None."""
    host = store_host(CFG.get("store"))
    if not host or not public_host(host):
        return None
    opener = urllib.request.build_opener(_PublicRedirects, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req = urllib.request.Request(f"https://{host}/", headers={"User-Agent": "Mozilla/5.0 (seovisi)"})
    try:
        with opener.open(req, timeout=8) as r:
            return TPL.tema_rengi(r.read(400_000).decode("utf-8", "replace"))
    except (urllib.error.URLError, socket.timeout, ConnectionError, ValueError):
        return None


def kurulum_gerekli():
    """Kurulum sihirbazı gösterilsin mi (yalnızca sunucuda). Bu ayardan önce kurulup taranmış mağazaya gösterilmez."""
    if not SERVER["on"]:
        return False
    done = CFG.get("kurulum_bitti")
    if done is None:
        done = urun_sayisi() > 0
        CFG.update(kurulum_bitti=done)
    return not done


def prepare_plan(pid, variant=0):
    """Ürünü okuyup açıklama ve SEO alanlarını hazırlar; mağazaya hiçbir şey yazmaz."""
    prod = API.get_product(pid)
    detail = API.get_detail(prod)
    cur_kw, _ = kw_read(prod) if kw_loc() else (prod.get("targetKeyword") or "", None)
    method = CFG.get("count_method") or SAFE_METHODS
    raw_name = prod.get("name") or ""
    fixed_name = clean_name(raw_name)
    plan = SM.build_machine_seo(dict(prod, name=fixed_name), (detail or {}).get("details") or "",
                                cur_kw or prod.get("targetKeyword") or "",
                                sku=prod.get("sku") or "", barcode=prod.get("barcode") or "", method=method,
                                target=float(CFG.get("target_density") or 2.5), variant=variant, prof=PROFILE(),
                                sablon=sablon())
    kw = plan["keyword"]
    kwl = ST.tr_lower(kw)
    old_t, old_m = (prod.get("pageTitle") or "").strip(), (prod.get("metaDescription") or "").strip()
    if 20 <= len(old_t) <= 60 and kwl in ST.tr_lower(old_t):
        plan["pageTitle"] = old_t          # mevcut etiket başlığı kurallara uyuyorsa dokunma
    if 50 <= len(old_m) <= 155 and kwl in ST.tr_lower(old_m):
        plan["metaDescription"] = old_m
    if (prod.get("metaKeywords") or "").strip():
        plan["metaKeywords"] = prod["metaKeywords"]
    plan["score"] = ST.seo_score(fixed_name, kw, plan["details_html"], plan["pageTitle"],
                                 plan["metaDescription"], method)
    # Ürün adındaki fazla/görünmez boşluk yüzünden "hedef kelime ürün adında geçmiyor" hatası çıkıyorsa
    # sadece boşluklar düzeltilir; adın başka hiçbir karakterine dokunulmaz.
    plan["name_fix"] = fixed_name if fixed_name != raw_name else None
    plan["old"] = {"keyword": cur_kw, "pageTitle": old_t, "metaDescription": old_m,
                   "details_html": (detail or {}).get("details") or ""}
    plan["variant"] = variant
    plan["v"] = PLAN_VERSION
    DBI.x("UPDATE seo SET plan=?, pstate='hazir', pmsg=? WHERE pid=?",
          (json.dumps(plan, ensure_ascii=False), "Açıklama hazır; kontrol edip gönderin.", pid))
    return plan


def repair_plan(pid):
    """İnatçı eksik ürünler için: önce olası sebepleri teşhis eder, sonra güvenli bir hedef kelimeyle
    (özel karakter içermeyen), yoğunluğu panel katsayısının olası her değerinde %2-%3 içinde kalacak
    şekilde yeni içerik hazırlar. Mağazaya yazmaz; gönderimi kullanıcı yapar."""
    prod = API.get_product(pid)
    detail = API.get_detail(prod)
    cur_kw, _ = kw_read(prod) if kw_loc() else (prod.get("targetKeyword") or "", None)
    raw_name = prod.get("name") or ""
    fixed_name = clean_name(raw_name)
    details = (detail or {}).get("details") or ""
    issues = SM.diagnose(raw_name, cur_kw, details, prod.get("pageTitle"), prod.get("metaDescription"),
                         ST.panel_factor())
    kw = cur_kw if (cur_kw and not any(c in SM.RISKY for c in cur_kw) and len(cur_kw) <= 55
                    and ST.tr_lower(cur_kw) in ST.tr_lower(fixed_name)) else SM.safe_keyword(fixed_name)
    if not kw:
        kw = SM.machine_keyword(fixed_name, "", PROFILE())
    method = "panel_lo,panel,panel_hi"
    prof = PR.with_brand(PROFILE(), prod)
    plan = SM.build_machine_seo(dict(prod, name=fixed_name), details, kw, sku=prod.get("sku") or "",
                                barcode=prod.get("barcode") or "", method=method, target=2.5, prof=prof,
                                sablon=sablon())
    kw = plan["keyword"]
    # etiket başlığında da özel karakter olmasın: hedef kelime + mağaza adı
    titles = [f"{kw} | {{magaza}}", f"{kw} - {{marka}} | {{magaza}}"]
    for t in PR.pick(titles, prof) + [kw]:
        if 20 <= len(t) <= 60:
            plan["pageTitle"] = t
            break
    else:
        plan["pageTitle"] = ST.make_title(fixed_name, kw, prof)
    at = PR.loc(prof["magaza"]) if prof["magaza"] else ""
    # meta açıklamada özel karakter yok: hedef kelime ve sabit cümleler
    meta = f"{kw} {at}. Ürün detaylarını inceleyin, kolayca sipariş verin." if at else \
        f"{kw}. Ürün detaylarını inceleyin, kolayca sipariş verin."
    if len(meta) > 155:
        meta = f"{kw} {at}." if at else f"{kw}."
    plan["metaDescription"] = meta if len(meta) >= 50 else meta + " Güvenli ödeme seçenekleriyle."
    if (prod.get("metaKeywords") or "").strip():
        plan["metaKeywords"] = prod["metaKeywords"]
    plan["score"] = ST.seo_score(fixed_name, kw, plan["details_html"], plan["pageTitle"], plan["metaDescription"],
                                 method)
    plan["name_fix"] = fixed_name if fixed_name != raw_name else None
    plan["old"] = {"keyword": cur_kw, "pageTitle": prod.get("pageTitle") or "",
                   "metaDescription": prod.get("metaDescription") or "", "details_html": details}
    plan["diag"] = issues
    plan["repair"] = True
    plan["v"] = PLAN_VERSION
    plan["variant"] = 0
    DBI.x("UPDATE seo SET plan=?, pstate='hazir', pmsg=? WHERE pid=?",
          (json.dumps(plan, ensure_ascii=False), "Onarım planı hazır; teşhisi ve içeriği kontrol edip gönderin.", pid))
    return plan


def clean_name(name):
    """Ürün adındaki çift / görünmez (nbsp, sekme) boşlukları tek boşluğa indirir, baş-sondaki boşlukları atar."""
    return re.sub(r"[\s\u00a0\u200b]+", " ", name or "").strip()


def _seo_yaz(pid, prod, detail, kw_rec, alanlar, yeni_ad=None):
    """Ürünün SEO alanlarını ve açıklamasını yazar (gönderim, şablon geçişi ve geri almanın ortak yolu).
    alanlar: pageTitle, metaDescription, metaKeywords, details_html, keyword. prod / detail / kw_rec yazmadan hemen önce
    okunmuş olmalı. Yazdıktan sonra korunan alanlar karşılaştırılır; biri değiştiyse ürün eski hâline yazılır ve toplu
    işler durur. Dönüş: (yazmadan sonraki ürün, None) ya da (None, hata mesajı)."""
    loc = kw_loc()
    fp_before = Ideasoft.fingerprint(prod)
    payload = {k: v for k, v in copy.deepcopy(prod).items() if k not in READONLY}
    if yeni_ad:
        payload["name"] = yeni_ad
        fp_before = dict(fp_before, name=yeni_ad)        # beklenen tek değişiklik
    payload.update(pageTitle=alanlar["pageTitle"], metaDescription=alanlar["metaDescription"],
                   metaKeywords=alanlar["metaKeywords"])
    if isinstance(payload.get("detail"), dict) and detail:
        payload["detail"] = dict(payload["detail"], details=alanlar["details_html"])
    if loc["res"] == "product":
        jset(payload, loc["path"], alanlar["keyword"])
    API.call("PUT", f"products/{pid}", body=payload)
    if detail and detail.get("id"):
        d = {k: v for k, v in detail.items() if k != "product"}
        d.update(details=alanlar["details_html"], product={"id": pid}, sku=detail.get("sku") or prod.get("sku"))
        API.call("PUT", f"product_details/{detail['id']}", body=d)
    else:
        API.call("POST", "product_details", body={"sku": prod.get("sku"), "details": alanlar["details_html"],
                                                  "extraDetails": "", "product": {"id": pid}})
    kw_write(pid, alanlar["keyword"], kw_rec)
    after = API.get_product(pid)
    if Ideasoft.fingerprint(after) != fp_before:
        diff = [k for k, v in fp_before.items() if Ideasoft.fingerprint(after).get(k) != v]
        try:
            API.call("PUT", f"products/{pid}", body={k: v for k, v in prod.items() if k not in READONLY})
        except ApiError:
            pass
        SEOJOBS.stop()
        GECIS.stop()
        msg = f"Korunan alan değişti ({', '.join(diff)}); eski hâline geri yazıldı, toplu işlem durduruldu."
        log(f"Ürün {pid}: {msg}", "err")
        return None, msg
    return after, None


def seo_geri_al(pid):
    """Gönderilen SEO'yu ürünün seovisi'den önceki (özgün) hâline döndürür: açıklama, sayfa başlığı, meta açıklama,
    anahtar kelimeler ve hedef kelime. Abonelikten bağımsız her zaman yapılabilir. Dönüş: (durum, mesaj)"""
    r = DBI.q("SELECT backup FROM seo WHERE pid=?", (pid,), one=True)
    if not r or not r["backup"]:
        return "hata", "Bu ürün için özgün hâlin yedeği yok."
    if not kw_loc():
        return "hata", "Hedef kelimenin yeri bilinmiyor (Ayarlar > Keşfet)."
    b = json.loads(r["backup"])
    prod = API.get_product(pid)
    detail = API.get_detail(prod)
    _, kw_rec = kw_read(prod)
    _, msg = _seo_yaz(pid, prod, detail, kw_rec, {
        "pageTitle": b.get("pageTitle") or "", "metaDescription": b.get("metaDescription") or "",
        "metaKeywords": b.get("metaKeywords") or "", "details_html": (b.get("detail") or {}).get("details") or "",
        "keyword": b.get("kw") or ""})
    if msg:
        return "hata", msg
    DBI.x("UPDATE seo SET pstate='geri', pmsg=?, plan=NULL, backup=NULL, onceki=NULL, gecis=NULL, ok=-1 WHERE pid=?",
          ("Özgün hâline döndürüldü.", pid))
    olay("geri", pid)
    log(f"SEO geri alındı, ürün {pid}: özgün hâline döndürüldü.", "ok")
    return "uygulandi", "Ürünün SEO'su ve açıklaması seovisi'den önceki hâline döndü."


def send_plan(pid, edited=None):
    """Hazırlanan (ya da kullanıcının düzenlediği) içeriği Ideasoft'a gönderir ve sonucu doğrular."""
    r = DBI.q("SELECT plan, backup FROM seo WHERE pid=?", (pid,), one=True)
    if not r or not r["plan"]:
        return "hata", "Bu ürün için hazırlanmış açıklama yok."
    if not kw_loc():
        return "hata", "Hedef kelimenin yeri bilinmiyor (Ayarlar > Keşfet)."
    plan = json.loads(r["plan"])
    for k in ("keyword", "details_html", "pageTitle", "metaDescription"):
        if edited and isinstance(edited.get(k), str) and edited[k].strip():
            plan[k] = edited[k].strip()
    prod = API.get_product(pid)
    detail = API.get_detail(prod)
    _, kw_rec = kw_read(prod)
    if not r["backup"]:
        DBI.x("UPDATE seo SET backup=? WHERE pid=?", (json.dumps({
            "pageTitle": prod.get("pageTitle"), "metaDescription": prod.get("metaDescription"),
            "metaKeywords": prod.get("metaKeywords"), "detail": detail, "kw_rec": kw_rec,
            "kw": kw_read(prod)[0], "time": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), pid))
    ad = plan.get("name_fix") if plan.get("name_fix") and clean_name(prod.get("name") or "") == plan["name_fix"] != prod.get("name") else None
    after, msg = _seo_yaz(pid, prod, detail, kw_rec, {
        "pageTitle": plan["pageTitle"], "metaDescription": plan["metaDescription"],
        "metaKeywords": plan.get("metaKeywords") or prod.get("metaKeywords"), "details_html": plan["details_html"],
        "keyword": plan["keyword"]}, yeni_ad=ad)
    if msg:
        DBI.x("UPDATE seo SET pstate='hata', pmsg=? WHERE pid=?", (msg, pid))
        return "hata", msg
    problems = []
    if ST.strip_tags((API.get_detail(after) or {}).get("details")) != ST.strip_tags(plan["details_html"]):
        problems.append("açıklama kaydedilmedi")
    if (kw_read(after)[0] or "").strip() != plan["keyword"].strip():
        problems.append("hedef kelime kaydedilmedi")
    # Ideasoft'un hesapladığı yüzde (liste kaydında)
    pct = None
    for _ in range(2):
        lst = API.call("GET", "products", {"ids": str(pid), "limit": 1}) or []
        lst = [x for x in lst if x.get("id") == pid]
        if lst:
            pct = panel_pct(seo_fields(lst[0]))
        if pct == 100:
            break
        time.sleep(1.5)
    plan.update({k: plan[k] for k in ("keyword", "details_html", "pageTitle", "metaDescription")})
    if problems:
        msg = "Gönderildi ama " + ", ".join(problems) + "."
        state = "hata"
    else:
        state = "gonderildi"
        msg = "Ideasoft'a gönderildi." + (f" Ideasoft SEO yüzdesi: %{pct}." if pct is not None else
                                          " Yüzde bir sonraki analizde güncellenir.")
    ok = 1 if pct == 100 else 0
    DBI.x("UPDATE seo SET pstate=?, pmsg=?, plan=?, ok=CASE WHEN ? IS NULL THEN ok ELSE ? END, "
          "pscore=COALESCE(?, pscore) WHERE pid=?",
          (state, msg, json.dumps(plan, ensure_ascii=False), pct, ok, None if pct is None else str(pct), pid))
    if state == "gonderildi":
        olay("seo", pid)
    log(f"SEO gönderimi ürün {pid}: {msg}", "ok" if state == "gonderildi" else "warn")
    return state, msg


class SeoJobs:
    """Toplu hazırlama ve (kullanıcı onaylı) toplu gönderim işçisi."""

    def __init__(self):
        self.running, self.kind, self.done, self.todo, self.stop_flag = False, "", 0, 0, False

    def start(self, kind):
        if self.running:
            return "Başka bir işlem sürüyor."
        if kind == "send":
            pids = [r["pid"] for r in DBI.q("SELECT pid FROM seo WHERE ok=0 AND pstate='hazir' ORDER BY pid")]
        elif kind == "repair":
            pids = [r["pid"] for r in DBI.q("SELECT pid FROM seo WHERE ok=0 ORDER BY pid")]
        else:
            pids = [r["pid"] for r in DBI.q(
                "SELECT pid FROM seo WHERE ok=0 AND (pstate IS NULL OR pstate='') ORDER BY pid")]
        if not pids:
            return "İşlenecek ürün yok."
        self.running, self.kind, self.done, self.todo, self.stop_flag = True, kind, 0, len(pids), False
        spawn(self._run, kind, pids)
        return f"{len(pids)} ürün " + {"send": "gönderiliyor.", "repair": "inceleniyor ve onarım planı hazırlanıyor.",
                                       "prepare": "için açıklama hazırlanıyor."}[kind]

    def stop(self):
        self.stop_flag = True

    def _run(self, kind, pids):
        def one(pid):
            if self.stop_flag:
                return
            try:
                if kind == "send":
                    send_plan(pid)
                elif kind == "repair":
                    repair_plan(pid)
                else:
                    prepare_plan(pid)
            except Exception as e:  # noqa: BLE001
                DBI.x("UPDATE seo SET pstate='hata', pmsg=? WHERE pid=?", (f"Hata: {str(e)[:200]}", pid))
                log(f"Ürün {pid}: {e}", "err")
            self.done += 1

        try:
            pmap(one, pids, 2 if kind == "send" else 3)
        finally:
            log(f"{'Toplu gönderim' if kind == 'send' else 'Açıklama hazırlama'} "
                f"{'durduruldu' if self.stop_flag else 'bitti'}: {self.done}/{self.todo}.", "ok")
            self.running = False

    def state(self):
        c = DBI.q("""SELECT SUM(ok=0 AND pstate='hazir') h, SUM(pstate='gonderildi') g, SUM(pstate='hata') e,
                     SUM(ok=0 AND (pstate IS NULL OR pstate='')) b FROM seo""", one=True)
        eksik = DBI.q("SELECT COUNT(*) n FROM seo WHERE ok=0", one=True)["n"]
        return {"running": self.running, "kind": self.kind, "done": self.done, "todo": self.todo, "eksik": eksik,
                "hazir": c["h"] or 0, "gonderildi": c["g"] or 0, "hata": c["e"] or 0, "bekleyen": c["b"] or 0}


SEOJOBS = _Ref("seojobs")


# ============================================================ toplu şablon geçişi
#
# seovisi'nin daha önce gönderdiği açıklamaları mağazanın bugünkü şablonuyla yeniden yazar. İçerik aynı kalır: açıklama
# ürünün özgün (seovisi'den önceki) açıklamasından, aynı hedef kelime ve aynı varyantla yeniden kurulur; yalnızca görünüm,
# renk ve bölümler değişir. Sayfa başlığı, meta açıklama ve hedef kelimeye dokunulmaz.
# Atlananlar: gönderildikten sonra panelde elle değiştirilen (açıklama, başlık, meta ya da hedef kelime), zaten bu şablonda
# olan ve yeni hâli SEO kurallarını tutmayacak olan ürünler. Her ürünün bir önceki açıklaması `onceki`de saklanır;
# geçiş ürün ürün ya da toplu geri alınabilir. gecis: gecti | atlandi | hata | geri.

class SablonGecisi:
    def __init__(self):
        self.running, self.kind, self.done, self.todo, self.stop_flag = False, "", 0, 0, False
        self.phase = ""

    def adaylar(self):
        return [r["pid"] for r in DBI.q("""SELECT pid FROM seo WHERE pstate='gonderildi' AND plan IS NOT NULL
                                           AND backup IS NOT NULL ORDER BY pid""")]

    def start(self, kind="gecir"):
        if self.running or SEOJOBS.running:
            return "Başka bir işlem sürüyor; bitmesini bekleyin."
        pids = self.adaylar() if kind == "gecir" else [r["pid"] for r in DBI.q("SELECT pid FROM seo WHERE gecis='gecti' ORDER BY pid")]
        if not pids:
            return "Geçirilecek açıklama yok." if kind == "gecir" else "Geri alınacak geçiş yok."
        self.running, self.kind, self.done, self.todo, self.stop_flag = True, kind, 0, len(pids), False
        spawn(self._run, kind, pids)
        return (f"{len(pids)} açıklama yeni şablona geçiriliyor." if kind == "gecir"
                else f"{len(pids)} açıklama önceki şablona döndürülüyor.")

    def stop(self):
        self.stop_flag = True

    def _run(self, kind, pids):
        def one(pid):
            if self.stop_flag:
                return
            try:
                gecir(pid) if kind == "gecir" else gecis_geri(pid)
            except Exception as e:  # noqa: BLE001
                DBI.x("UPDATE seo SET gecis='hata', pmsg=? WHERE pid=?", (f"Şablon geçişi: {str(e)[:200]}", pid))
                log(f"Ürün {pid}: {e}", "err")
            self.done += 1
        try:
            pmap(one, pids, 2)
        finally:
            say = {r["gecis"]: r["n"] for r in DBI.q("SELECT gecis, COUNT(*) n FROM seo WHERE gecis IS NOT NULL GROUP BY gecis")}
            log(("Şablon geçişi" if kind == "gecir" else "Şablon geçişini geri alma") + f" {'durduruldu' if self.stop_flag else 'bitti'}: "
                f"{say.get('gecti', 0)} geçti, {say.get('atlandi', 0)} atlandı, {say.get('hata', 0)} hata.", "ok")
            self.running = False

    def state(self):
        say = {r["gecis"]: r["n"] for r in DBI.q("SELECT gecis, COUNT(*) n FROM seo WHERE gecis IS NOT NULL GROUP BY gecis")}
        return {"running": self.running, "kind": self.kind, "done": self.done, "todo": self.todo,
                "aday": len(self.adaylar()), "sayilar": say,
                "atlananlar": [dict(r) for r in DBI.q("SELECT pid, sku, name, pmsg FROM seo WHERE gecis IN ('atlandi', 'hata') "
                                                      "ORDER BY pid LIMIT 100")]}


def gecir(pid):
    """Bir ürünün gönderilmiş açıklamasını bugünkü şablona geçirir. Dönüş: gecis durumu."""
    r = DBI.q("SELECT plan, backup FROM seo WHERE pid=?", (pid,), one=True)
    plan, b = json.loads(r["plan"]), json.loads(r["backup"])

    def atla(neden):
        DBI.x("UPDATE seo SET gecis='atlandi', pmsg=? WHERE pid=?", (f"Şablon geçişi atlandı: {neden}", pid))
        return "atlandi"
    prod = API.get_product(pid)
    detail = API.get_detail(prod)
    kw_now, kw_rec = kw_read(prod)
    simdi = (detail or {}).get("details") or ""
    if (ST.strip_tags(simdi) != ST.strip_tags(plan["details_html"]) or (prod.get("pageTitle") or "").strip() != plan["pageTitle"].strip()
            or (prod.get("metaDescription") or "").strip() != plan["metaDescription"].strip()
            or (kw_now or "").strip() != plan["keyword"].strip()):
        return atla("gönderildikten sonra panelde değiştirilmiş; dokunulmadı.")
    method = CFG.get("count_method") or SAFE_METHODS
    yeni = SM.build_machine_seo(dict(prod, name=clean_name(prod.get("name") or "")), (b.get("detail") or {}).get("details") or "",
                                plan["keyword"], sku=prod.get("sku") or "", barcode=prod.get("barcode") or "", method=method,
                                target=float(CFG.get("target_density") or 2.5), variant=int(plan.get("variant") or 0),
                                prof=PROFILE(), sablon=sablon())
    if yeni["keyword"].strip() != plan["keyword"].strip():
        return atla("hedef kelime değişecekti.")
    if yeni["details_html"] == simdi:
        return atla("zaten bu şablonda.")
    sc = ST.seo_score(clean_name(prod.get("name") or ""), plan["keyword"], yeni["details_html"], plan["pageTitle"],
                      plan["metaDescription"], method)
    if sc["top"] < 100:
        return atla("yeni hâli SEO kurallarını tutmuyor (" + "; ".join(sc["fails"][:2]) + ").")
    DBI.x("UPDATE seo SET onceki=? WHERE pid=?", (json.dumps({"details": simdi, "zaman": datetime.now().isoformat(timespec="seconds")},
                                                             ensure_ascii=False), pid))
    _, msg = _seo_yaz(pid, prod, detail, kw_rec, {
        "pageTitle": plan["pageTitle"], "metaDescription": plan["metaDescription"],
        "metaKeywords": prod.get("metaKeywords") or "", "details_html": yeni["details_html"], "keyword": plan["keyword"]})
    if msg:
        DBI.x("UPDATE seo SET gecis='hata', pmsg=? WHERE pid=?", (msg, pid))
        return "hata"
    plan["details_html"] = yeni["details_html"]
    olay("gecis", pid)
    DBI.x("UPDATE seo SET gecis='gecti', plan=?, pmsg=? WHERE pid=?",
          (json.dumps(plan, ensure_ascii=False), "Açıklama yeni şablona geçirildi.", pid))
    return "gecti"


def gecis_geri(pid):
    """Şablon geçişini geri alır: açıklama bir önceki (geçişten önceki) hâline döner. Dönüş: gecis durumu."""
    r = DBI.q("SELECT plan, onceki FROM seo WHERE pid=? AND gecis='gecti'", (pid,), one=True)
    if not r or not r["onceki"]:
        return "hata"
    plan, onceki = json.loads(r["plan"]), json.loads(r["onceki"])
    prod = API.get_product(pid)
    detail = API.get_detail(prod)
    kw_now, kw_rec = kw_read(prod)
    _, msg = _seo_yaz(pid, prod, detail, kw_rec, {
        "pageTitle": prod.get("pageTitle") or "", "metaDescription": prod.get("metaDescription") or "",
        "metaKeywords": prod.get("metaKeywords") or "", "details_html": onceki["details"], "keyword": kw_now or plan["keyword"]})
    if msg:
        DBI.x("UPDATE seo SET pmsg=? WHERE pid=?", (msg, pid))
        return "hata"
    plan["details_html"] = onceki["details"]
    olay("geri", pid)
    DBI.x("UPDATE seo SET gecis='geri', onceki=NULL, plan=?, pmsg=? WHERE pid=?",
          (json.dumps(plan, ensure_ascii=False), "Şablon geçişi geri alındı; önceki açıklama yazıldı.", pid))
    return "geri"


GECIS = _Ref("gecis")


# ============================================================ kırık bağlantı taraması

SITE_SINIR = 2_000_000                # bir sayfadan en çok okunan bayt


def site_getirici():
    """Mağazanın herkese açık sitesinden adres getiren işlev (baglanti.py için). Yalnızca internetteki adreslere ve
    yönlendirmelere gider: sitedeki bir bağlantı sunucunun iç ağını gösterse de istek gönderilmez. Alan adı denetimi
    tarama boyunca bellekte tutulur. Dönüş: (durum, içerik türü, metin, son adres); ulaşılamazsa durum 0."""
    genel = {}
    opener = urllib.request.build_opener(_PublicRedirects, urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def getir(url, govde=True):
        host = urllib.parse.urlsplit(url).hostname or ""
        if host not in genel:
            genel[host] = public_host(host)
        if not genel[host]:
            return 0, "", "", url
        for m in (["GET"] if govde else ["HEAD", "GET"]):
            req = urllib.request.Request(url, method=m, headers={"User-Agent": "Mozilla/5.0 (compatible; seovisi-baglanti/1.0)"})
            try:
                with opener.open(req, timeout=15) as r:
                    metin = r.read(SITE_SINIR).decode(r.headers.get_content_charset() or "utf-8", "replace") if govde else ""
                    return r.status, r.headers.get("Content-Type", ""), metin, r.geturl()
            except urllib.error.HTTPError as e:
                if m == "HEAD" and e.code in (403, 405, 501):
                    continue                    # HEAD'i kabul etmeyen sunucu: GET ile denenir
                return e.code, "", "", url
            except (urllib.error.URLError, socket.timeout, ConnectionError, ValueError, OSError):
                return 0, "", "", url
        return 0, "", "", url
    return getir


class LinkScanner:
    """Mağazanın herkese açık sitesindeki kırık bağlantıları bulur (baglanti.py). Mağazaya hiçbir şey yazmaz.
    Durdurulan taramada önceki sonuçlar korunur."""

    def __init__(self):
        self.running = self.stop_flag = False
        self.phase = self.note = ""
        DBI.x("CREATE TABLE IF NOT EXISTS kirik(url TEXT PRIMARY KEY, durum INTEGER, tur TEXT, kaynaklar TEXT, harita INTEGER)")
        DBI.x("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")

    def start(self):
        if self.running:
            return "Bağlantı taraması zaten sürüyor."
        host = store_host(CFG.get("store"))
        if not host:
            return "Önce mağaza adresini girin (Ayarlar)."
        self.running, self.stop_flag, self.note, self.phase = True, False, "", "başlıyor"
        spawn(self._run, host)
        return "Bağlantı taraması başladı; sitenizin büyüklüğüne göre birkaç dakika ile bir saat sürebilir."

    def stop(self):
        self.stop_flag = True

    def _run(self, host):
        try:
            def ilerleme(n, toplam):
                self.phase = f"{n:,} / {toplam:,} sayfa".replace(",", ".")
            sinir = int(_num(SRV.get("link_sinir")) or 10000) if SRV else 10000
            r = BG.tara(f"https://{host}", site_getirici(), sinir=sinir, bekle=LINK_BEKLE, dur=lambda: self.stop_flag,
                        ilerleme=ilerleme)
            if r["durduruldu"]:
                self.note = "Durduruldu; önceki sonuçlar korunuyor."
                return
            with DBI.lock:
                DBI.c.execute("DELETE FROM kirik")
                DBI.c.executemany("INSERT INTO kirik(url, durum, tur, kaynaklar, harita) VALUES(?,?,?,?,?)",
                                  [(k["url"], k["durum"], k["tur"], json.dumps(k["kaynaklar"], ensure_ascii=False),
                                    1 if k["site_haritasi"] else 0) for k in r["kirik"]])
                DBI.c.commit()
            DBI.x("INSERT OR REPLACE INTO kv(k, v) VALUES('link_tarama', ?)", (json.dumps({
                "zaman": datetime.now().strftime("%Y-%m-%d %H:%M"), "sayfa": r["sayfa"], "sinir": r["sinira_ulasti"]}),))
            log(f"Bağlantı taraması bitti: {r['sayfa']} sayfa gezildi, {len(r['kirik'])} kırık bağlantı"
                + (" (sayfa sınırına ulaşıldı)." if r["sinira_ulasti"] else "."), "ok")
        except Exception as e:  # noqa: BLE001
            self.note = f"Bağlantı taraması hata ile durdu: {e}"
            log(self.note, "err")
            traceback.print_exc()
        finally:
            self.running, self.phase = False, ""

    def state(self):
        r = DBI.q("SELECT v FROM kv WHERE k='link_tarama'", one=True)
        return {"running": self.running, "phase": self.phase, "note": self.note, "son": json.loads(r["v"]) if r else None}


# ============================================================ aylık rapor: olaylar ve durum fotoğrafları

class Raporlar:
    """olay: seovisi'nin mağazada yaptığı her iş (rapor.OLAYLAR); anlik: tam taramaların sonundaki durum fotoğrafı."""

    def __init__(self):
        DBI.x("CREATE TABLE IF NOT EXISTS olay(id INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT, tur TEXT, pid INTEGER)")
        DBI.x("CREATE TABLE IF NOT EXISTS anlik(zaman TEXT PRIMARY KEY, veri TEXT)")


def olay(tur, pid=None):
    DBI.x("INSERT INTO olay(zaman, tur, pid) VALUES(?,?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), tur, pid))


def anlik_al():
    """Mağazanın bugünkü durumunu rapor için kaydeder (tam SEO taramasının sonunda)."""
    c, sc = overview()["counts"], seo_counts()
    veri = {"taranan": sc["taranan"], "seo_tamam": sc["ok"], "seo_eksik": sc["eksik"],
            "kategori_sorun": c["tasi"] + c["supheli"] + c["kategorisiz"], "gorselsiz": c["img_yok"],
            "fiyat_uyari": c["uyari_fiyat"], "stok_uyari": c["uyari_satilamaz"], "kopya": c["kopya"], "kirik": c["kirik"]}
    DBI.x("INSERT OR REPLACE INTO anlik(zaman, veri) VALUES(?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(veri)))
    return veri


def rapor_al(ay=None):
    an = [(r["zaman"], json.loads(r["veri"])) for r in DBI.q("SELECT zaman, veri FROM anlik ORDER BY zaman")]
    ol = [(r["zaman"], r["tur"]) for r in DBI.q("SELECT zaman, tur FROM olay")]
    aylar = RP.aylar([z for z, _ in an] + [z for z, _ in ol]) or [datetime.now().strftime("%Y-%m")]
    ay = ay if ay in aylar else aylar[0]
    return {"aylar": [{"ay": a, "ad": RP.ay_adi(a)} for a in aylar], "rapor": RP.hesapla(ay, an, ol)}


LINK_BEKLE = 0.25                     # istekler arası bekleme (sn): mağazanın sitesini yormamak için
LINKS = _Ref("links")


# ============================================================ yeni ürün otopilotu
#
# Otopilot açıldıktan SONRA mağazaya eklenen ürünleri bulur; SEO açıklamasını ve kategori önerisini hazırlar. Onaylı kipte
# mağaza sahibinin onayını bekler, otomatik kipte seçilen işleri kendisi yazar; şüpheli kategori önerileri her durumda onaya
# kalır. Mağazaya yazma bugünkü güvenlik kurallarıyla (send_plan, cat_fix) yapılır; eski ürünlere hiç dokunulmaz.
# Yeni ürün, sitede yayına alındıktan (aktif) ve OTO_BEKLE_DK geçtikten sonra işlenir: mağaza sahibi ürünü hâlâ düzenlerken
# üstüne yazılmasın. Bugün oto_zamanlayici() belirli aralıklarla kontrol() çağırır; Ideasoft yeni ürün bildirimi (webhook)
# verirse bildirim de kontrol()'ü çağırabilir.
#
# oto tablosunda durum: bekliyor (yayına alınmadı ya da süre dolmadı), onay (onay bekliyor), tamam, hata, yoksay.
# seo: gerekmez | hazir | gonderildi | hata.  kat: gerekmez | oneri | sec (öneri yok, elle seçilmeli) | uygulandi | hata.

OTO_BEKLE_DK = 30
OTO_PASIF_GUN = 30
OTO_VARSAYILAN = {"acik": False, "mod": "onay", "seo": True, "kategorisiz": True, "tasi": True}


def oto_ayar():
    d = CFG.get("otopilot") or {}
    a = dict(OTO_VARSAYILAN, **{k: v for k, v in d.items() if k in OTO_VARSAYILAN})
    a["mod"] = a["mod"] if a["mod"] in ("onay", "otomatik") else "onay"
    for k in ("acik", "seo", "kategorisiz", "tasi"):
        a[k] = a[k] if isinstance(a[k], bool) else OTO_VARSAYILAN[k]
    return a


def _pasif(p):
    return str(p.get("status")) in ("0", "False", "false")


class Otopilot:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.phase = self.note = ""
        DBI.x("""CREATE TABLE IF NOT EXISTS oto(pid INTEGER PRIMARY KEY, sku TEXT, name TEXT, bulundu TEXT, durum TEXT,
                 seo TEXT, kat TEXT, kat_act TEXT, kat_sug TEXT, kat_add TEXT, kat_rem TEXT, kat_guclu INTEGER,
                 msg TEXT, guncellendi TEXT)""")
        DBI.x("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")

    @staticmethod
    def _kv(k):
        r = DBI.q("SELECT v FROM kv WHERE k=?", (k,), one=True)
        return r["v"] if r else None

    @staticmethod
    def _kv_set(k, v):
        DBI.x("INSERT OR REPLACE INTO kv(k, v) VALUES(?, ?)", (k, str(v)))

    @staticmethod
    def _set(pid, **f):
        f["guncellendi"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        DBI.x(f"UPDATE oto SET {', '.join(k + '=?' for k in f)} WHERE pid=?", list(f.values()) + [pid])

    @staticmethod
    def _yeni_urunler(since):
        """Numarası since'ten büyük bütün ürünler (Ideasoft ürün numaraları artarak verilir)."""
        out, last = [], since
        while True:
            prm = {"limit": 100, "sort": "id"}
            if last:
                prm["sinceId"] = last
            page = [p for p in (API.call("GET", "products", prm) or []) if p.get("id", 0) > last]
            if not page:
                return out
            out += page
            last = max(p["id"] for p in page)

    def izin(self):
        """Otopilot bu mağazada çalışabilir mi: None ya da sebep."""
        a = abonelik_durumu()
        msg = AB.engel(a, "otopilot", a["urun_sayisi"]) if a else None    # pakette var mı, ürün sınırı aşıldı mı
        if msg:
            return msg
        if not (CFG.get("access_token") or CFG.get("refresh_token")):
            return "Mağaza bağlı değil."
        return None

    def ayarla(self, d):
        """Ayarları kaydeder. İlk kez açılırken o ana kadarki son ürün numarası kaydedilir: daha eski ürünlere dokunulmaz."""
        eski = oto_ayar()
        CFG.update(otopilot=dict(eski, **{k: d[k] for k in OTO_VARSAYILAN if k in d}))
        a = oto_ayar()                                    # geçersiz değerler düzeltilmiş hâli
        if a["acik"] and not eski["acik"]:
            msg = self.izin()
            if msg:
                CFG.update(otopilot=eski)
                return msg
            if self._kv("oto_son_id") is None:
                known = max([0] + [DBI.q(f"SELECT MAX(pid) m FROM {t}", one=True)["m"] or 0 for t in ("seo", "catprod", "idx")])
                yeni = self._yeni_urunler(known)
                self._kv_set("oto_son_id", max([known] + [p["id"] for p in yeni]))
            log("Otopilot açıldı: bundan sonra eklenen ürünler " + ("onayınıza sunulacak." if a["mod"] == "onay"
                                                                   else "kendiliğinden düzenlenecek."), "ok")
        elif eski["acik"] and not a["acik"]:
            log("Otopilot kapatıldı.")
        CFG.update(otopilot=a)
        return None

    def kontrol(self):
        """Yeni ürünleri bulur, bekleme süresi dolan ve yayındaki ürünleri işler. Aynı anda tek kez çalışır."""
        if not self.lock.acquire(blocking=False):
            return "Otopilot zaten çalışıyor."
        self.running, self.note = True, ""
        try:
            if not oto_ayar()["acik"]:
                return "Otopilot kapalı."
            msg = self.izin()
            if msg:
                self.note = msg
                return msg
            self.phase = "yeni ürünler aranıyor"
            yeni = self._yeni_urunler(int(self._kv("oto_son_id") or 0))
            now = datetime.now()
            if yeni:
                ts = now.strftime("%Y-%m-%d %H:%M")
                DBI.xm("INSERT OR IGNORE INTO oto(pid, sku, name, bulundu, durum, msg, guncellendi) VALUES(?,?,?,?,?,?,?)",
                       [(p["id"], p.get("sku"), p.get("name"), ts, "bekliyor", "Yayına alınması ve kısa bir süre geçmesi bekleniyor.", ts)
                        for p in yeni])
                self._kv_set("oto_son_id", max(p["id"] for p in yeni))
                log(f"Otopilot: {len(yeni)} yeni ürün bulundu.")
            sinir = (now - timedelta(minutes=OTO_BEKLE_DK)).strftime("%Y-%m-%d %H:%M")
            sira = [r["pid"] for r in DBI.q("SELECT pid FROM oto WHERE durum='bekliyor' AND bulundu<=? ORDER BY pid", (sinir,))]
            if sira:
                if CATSCAN.running or CATJOBS.running or SEOJOBS.running:
                    self.note = "Başka bir işlem sürüyor; yeni ürünler bir sonraki kontrolde işlenecek."
                else:
                    self._isle(sira)
            self._kv_set("oto_son_kontrol", now.strftime("%Y-%m-%d %H:%M"))
            return "Kontrol edildi."
        except Exception as e:  # noqa: BLE001
            self.note = f"Otopilot hata ile durdu: {e}"
            log(self.note, "err")
            traceback.print_exc()
            return self.note
        finally:
            self.running, self.phase = False, ""
            self.lock.release()

    def _isle(self, pids):
        prods, eski = {}, (datetime.now() - timedelta(days=OTO_PASIF_GUN)).strftime("%Y-%m-%d %H:%M")
        for pid in pids:
            try:
                p = API.get_product(pid)
            except ApiError as e:
                if e.status == 404:
                    self._set(pid, durum="yoksay", msg="Ürün mağazadan silinmiş.")
                    continue
                raise
            if _pasif(p):
                r = DBI.q("SELECT bulundu FROM oto WHERE pid=?", (pid,), one=True)
                if r and r["bulundu"] < eski:
                    self._set(pid, durum="yoksay", msg=f"{OTO_PASIF_GUN} gün içinde yayına alınmadı; listeden çıkarıldı.")
                else:
                    self._set(pid, msg="Ürün henüz yayında değil (pasif); yayına alınınca işlenecek.")
                continue
            prods[pid] = p
        if not prods:
            return
        self.phase = f"{len(prods)} yeni ürün için SEO hazırlanıyor"
        for pid, p in prods.items():
            pct = panel_pct(seo_fields(p))
            price, cur = sale_price(p)
            DBI.x("""INSERT INTO seo(pid, sku, name, kw, ok, codes, fails, checked, pscore, price, cur) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(pid) DO UPDATE SET sku=excluded.sku, name=excluded.name, ok=excluded.ok,
                     checked=excluded.checked, pscore=excluded.pscore, price=excluded.price, cur=excluded.cur""",
                  (pid, p.get("sku"), p.get("name"), "", -1 if pct is None else (1 if pct >= 100 else 0), "", "[]",
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"), None if pct is None else str(pct), price, cur))
            if pct is not None and pct >= 100:
                self._set(pid, seo="gerekmez")
                continue
            try:
                prepare_plan(pid)
                self._set(pid, seo="hazir")
            except Exception as e:  # noqa: BLE001
                self._set(pid, seo="hata", msg=f"Açıklama hazırlanamadı: {str(e)[:200]}")
        self.phase = "kategoriler öneriliyor"
        self._kategori(prods)
        for pid in prods:
            self._karar(pid)
        if oto_ayar()["mod"] == "otomatik":
            self._uygula(list(prods), otomatik=True)

    def _kategori(self, prods):
        """Yeni ürünler yerel kayda eklenir, kategori listesi tazelenir, analiz kayıtlı verilerle yeniden yapılır."""
        cats = [(c["id"], (c.get("name") or "").strip(), _ref_id(c.get("parent")))
                for c in CATSCAN._pages("categories", "Kategoriler") if c.get("id")]
        with DBI.lock:
            DBI.c.execute("DELETE FROM cat")
            DBI.c.executemany("INSERT INTO cat(id, name, parent) VALUES(?,?,?)", cats)
            DBI.c.executemany("INSERT OR REPLACE INTO catprod(pid, sku, name, cats, brand, status) VALUES(?,?,?,?,?,?)",
                              [(pid, p.get("sku") or "", p.get("name") or "", json.dumps(_cat_ids(p)), PR.product_brand(p), 1)
                               for pid, p in prods.items()])
            DBI.c.commit()
        CATSCAN.running = True                    # analiz sürerken panelden ikinci bir analiz başlatılmasın
        CATSCAN._run(False)
        rep = CATSCAN.report or {}
        wrong = {w["pid"]: w for w in rep.get("wrong") or []}
        uncat = {u["pid"]: u for u in rep.get("uncat") or []}
        for pid in prods:
            it = uncat.get(pid) or wrong.get(pid)
            if not it:
                self._set(pid, kat="gerekmez")
            elif pid in uncat and not (it.get("add") and it.get("strength") in ("guclu", "olasi")):
                self._set(pid, kat="sec", kat_act="kategorisiz", kat_sug="", msg=it.get("reason") or "")
            else:
                act = "kategorisiz" if pid in uncat else it["act"]
                guclu = it.get("strength") == "guclu" if pid in uncat else it["act"] == "tasi"
                self._set(pid, kat="oneri", kat_act=act, kat_sug=it.get("sug") or "", kat_add=json.dumps(it.get("add") or []),
                          kat_rem=json.dumps(it.get("rem") or []), kat_guclu=1 if guclu else 0, msg=it.get("reason") or "")

    def _karar(self, pid):
        r = DBI.q("SELECT seo, kat FROM oto WHERE pid=?", (pid,), one=True)
        if r["seo"] == "hata" or r["kat"] == "hata":
            self._set(pid, durum="hata")
        elif r["seo"] == "hazir" or r["kat"] in ("oneri", "sec"):
            self._set(pid, durum="onay")
        else:
            self._set(pid, durum="tamam", msg="SEO'su ve kategorisi uygun; yapılacak bir şey yok.")

    def _uygula(self, pids, otomatik=False):
        """Hazırlanan SEO'yu gönderir, kategori önerisini uygular. Otomatik kipte yalnızca seçilen işler ve emin olunan
        kategori önerileri; onayda hepsi. Paket izni her yazmadan önce denetlenir."""
        a = oto_ayar()
        for pid in pids:
            r = DBI.q("SELECT * FROM oto WHERE pid=?", (pid,), one=True)
            if not r or (not otomatik and r["durum"] not in ("onay", "hata")):
                continue
            msgs = []
            if r["seo"] == "hazir" and (not otomatik or a["seo"]):
                engel = yazma_engeli("seo_gonder")
                if engel:
                    msgs.append(engel)
                else:
                    self.phase = f"ürün {pid}: SEO gönderiliyor"
                    state, msg = send_plan(pid)
                    self._set(pid, seo="gonderildi" if state == "gonderildi" else "hata")
                    msgs.append(msg)
            auto_kat = r["kat_guclu"] and ((r["kat_act"] == "kategorisiz" and a["kategorisiz"]) or (r["kat_act"] == "tasi" and a["tasi"]))
            if r["kat"] == "oneri" and (not otomatik or auto_kat):
                engel = yazma_engeli("kategori_duzelt")
                if engel:
                    msgs.append(engel)
                else:
                    self.phase = f"ürün {pid}: kategori yazılıyor"
                    state, msg = cat_fix(pid, json.loads(r["kat_add"] or "[]"), json.loads(r["kat_rem"] or "[]"), r["kat_sug"] or "")
                    self._set(pid, kat="uygulandi" if state == "uygulandi" else "hata")
                    msgs.append(msg)
            if msgs:
                self._set(pid, msg=" ".join(msgs))
            self._karar(pid)
            if otomatik and msgs:
                log(f"Otopilot ürün {pid}: {' '.join(msgs)}")

    def onayla(self, pids):
        """Mağaza sahibinin onayı: seçilen (ya da onay bekleyen bütün) ürünlerde hazırlananlar yazılır."""
        if not self.lock.acquire(blocking=False):
            return "Otopilot çalışıyor; birazdan yeniden deneyin."
        self.running = True

        def run():
            try:
                todo = pids or [r["pid"] for r in DBI.q("SELECT pid FROM oto WHERE durum='onay' ORDER BY pid")]
                self._uygula(todo)
                log(f"Otopilot: {len(todo)} ürün onaylandı.", "ok")
            except Exception as e:  # noqa: BLE001
                self.note = f"Onay işlenirken hata: {e}"
                log(self.note, "err")
            finally:
                self.running, self.phase = False, ""
                self.lock.release()
        spawn(run)
        return "Onaylananlar mağazaya yazılıyor."

    def state(self):
        rows = [dict(r) for r in DBI.q("""SELECT pid, sku, name, bulundu, durum, seo, kat, kat_act, kat_sug, kat_guclu, msg,
                                           guncellendi FROM oto ORDER BY CASE durum WHEN 'onay' THEN 0 WHEN 'hata' THEN 1
                                           WHEN 'bekliyor' THEN 2 ELSE 3 END, pid DESC LIMIT 300""")]
        say = {r["durum"]: r["n"] for r in DBI.q("SELECT durum, COUNT(*) n FROM oto GROUP BY durum")}
        return {"ayar": oto_ayar(), "running": self.running, "phase": self.phase, "note": self.note,
                "izin": self.izin(), "son_kontrol": self._kv("oto_son_kontrol"), "aralik_dk": oto_aralik(),
                "bekle_dk": OTO_BEKLE_DK, "sayilar": say, "items": rows}


OTO = _Ref("oto")


def oto_aralik():
    return max(5, int(_num(SRV.get("otopilot_dk")) or 60)) if SRV else 60


def oto_zamanlayici():
    """Açık otopilotları sırayla çalıştırır; her mağaza en çok otopilot_dk dakikada bir (sunucu.json, varsayılan 60).
    Her mağaza kendi bağlamında çalışır (spawn gibi); bir mağazanın hatası diğerlerini durdurmaz."""
    while True:
        time.sleep(60)
        oto_tur()
        haftalik_tur()


def _magazalar():
    return sorted(d for d in os.listdir(STORES) if known_tenant(d)) if SERVER["on"] else [LOCAL["id"]]


HAFTALIK_GUN = 7


def haftalik_tur():
    """Haftalık otomatik tarama (yalnızca okur): bağlı ve ücretli paketteki her mağazada 7 günde bir SEO, kategori ve kırık
    bağlantı taraması başlatır; SEO taramasının sonunda rapor için durum fotoğrafı alınır. Başka bir iş sürüyorsa sonraki tura kalır."""
    prev = getattr(_cur, "t", None)
    for tid in _magazalar():
        try:
            _cur.t = tenant(tid)
            if not (CFG.get("access_token") or CFG.get("refresh_token")):
                continue
            a = abonelik_durumu()
            if a and not a["ozellikler"]:
                continue                                       # ücretsiz analizde otomatik tarama yok
            r = DBI.q("SELECT v FROM kv WHERE k='haftalik_son'", one=True)
            if r and r["v"] > (datetime.now() - timedelta(days=HAFTALIK_GUN)).strftime("%Y-%m-%d %H:%M"):
                continue
            if any(x.running for x in (SEOSCAN, CATSCAN, LINKS, SEOJOBS, CATJOBS, GECIS, OTO)):
                continue
            DBI.x("INSERT OR REPLACE INTO kv(k, v) VALUES('haftalik_son', ?)", (datetime.now().strftime("%Y-%m-%d %H:%M"),))
            log("Haftalık otomatik tarama başladı (yalnızca okur).")
            SEOSCAN.start()
            CATSCAN.start()
            LINKS.start()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        finally:
            _cur.t = prev


def oto_tur():
    """Zamanlayıcının bir turu: vakti gelen her açık otopilotu çalıştırır."""
    tids = _magazalar()
    prev = getattr(_cur, "t", None)
    for tid in tids:
        try:
            _cur.t = tenant(tid)
            son = OTO._kv("oto_son_kontrol")
            vakit = not son or son <= (datetime.now() - timedelta(minutes=oto_aralik())).strftime("%Y-%m-%d %H:%M")
            if oto_ayar()["acik"] and vakit and not OTO.running:
                OTO.kontrol()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        finally:
            _cur.t = prev


# ================================================================== mağazalar

class Tenant:
    """Bir mağazanın her şeyi: ayarları, veritabanı, Ideasoft bağlantısı, arka plan işleri ve kaydı."""

    def __init__(self, tid):
        self.id = tid
        self.dir = os.path.join(STORES, tid)
        os.makedirs(self.dir, exist_ok=True)
        self.logs = deque(maxlen=400)
        self.log_lock = threading.Lock()
        prev, _cur.t = getattr(_cur, "t", None), self
        try:
            self.cfg = Config(self.path("ayarlar.json"))
            self.dbi = DB(self.path("durum.db"))
            self.api = Ideasoft()
            self.img = ImgScanner()
            self.seoscan = SeoScanner()
            self.seojobs = SeoJobs()
            self.catscan = CatScanner()
            self.catjobs = CatJobs()
            self.oto = Otopilot()
            self.links = LinkScanner()
            self.gecis = SablonGecisi()
            self.rapor = Raporlar()
        finally:
            _cur.t = prev

    def path(self, name):
        return os.path.join(self.dir, name)


_tenants, _tenants_lock = {}, threading.Lock()
LOCAL = {"id": ""}                # yerel kipte açılan mağaza


def tenant(tid):
    with _tenants_lock:
        t = _tenants.get(tid)
        if t is None:
            t = _tenants[tid] = Tenant(tid)
        return t


def tenant_id(host):
    """Mağaza alan adından klasör adı: magaza.myideasoft.com → magaza-myideasoft-com"""
    return re.sub(r"[^a-z0-9]+", "-", host).strip("-")[:80] or "yerel"


def known_tenant(tid):
    return bool(re.fullmatch(r"[a-z0-9-]{1,80}", tid or "")) and os.path.isfile(os.path.join(STORES, tid, "ayarlar.json"))


# ================================================================== abonelik

def urun_sayisi():
    """Taramalarda görülen ürün sayısı (henüz taranmadıysa 0)."""
    return max(DBI.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in ("seo", "catprod", "img"))


def abonelik_durumu():
    """Mağazanın bugün geçerli aboneliği ve ürün sayısı. Yerel kipte (satılmayan, Ustapazar sürümü) None: sınır yok."""
    if not SERVER["on"]:
        return None
    a = AB.gecerli(AB.oku(current().dir))
    a["urun_sayisi"] = urun_sayisi()
    a["oneri"] = AB.oneri(a["urun_sayisi"])
    return a


def yazma_engeli(ozellik):
    """Mağazaya yazan istekten önce: paket izin vermiyorsa kullanıcıya gösterilecek mesaj, veriyorsa None."""
    a = abonelik_durumu()
    return AB.engel(a, ozellik, a["urun_sayisi"]) if a else None


# Mağazaya yazan istekler ve gerektirdikleri paket özelliği (paketler.json). Yeni bir yazma yolu buraya eklenmeli.
# Geri alma (/api/cat/undo) bilerek yok: abonelik bitse de yapılan değişiklikler geri alınabilir.
WRITE_ROUTES = {
    "/api/seo/send": "seo_gonder", "/api/seo/send_all": "seo_gonder",
    "/api/cat/apply": "kategori_duzelt", "/api/cat/apply_many": "kategori_duzelt", "/api/cat/assign": "kategori_duzelt",
    "/api/cat/create": "kategori_ac", "/api/cat/create_many": "kategori_ac",
    "/api/otopilot/onayla": "otopilot",
    "/api/sablon/gecis/start": "seo_gonder",       # içindeki SEO ve kategori yazımları ayrıca seo_gonder / kategori_duzelt ister
}


# metin üreticisinin panel katsayısı o anki mağazanın ayarından gelir
ST.panel_factor = lambda: float(CFG.get("panel_factor") or 1.30)


def public_host(host):
    """Girişte yazılan adres internette bir alan adı mı? (sunucunun iç ağına istek gönderilmesini engeller)"""
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}", host or ""):
        return False
    try:
        infos = socket.getaddrinfo(host, 443)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)


# ============================================================ istek güvenliği

MAX_BODY = 5 * 1024 * 1024        # en büyük istek gövdesi (toplu iş listeleri, düzenlenmiş açıklama bunun çok altında)
MAX_PENDING = 10000               # aynı anda açık bekleyen Ideasoft izin isteği
# Panel bu adreslerin içinde (çerçevede) açılabilir; giriş yapmış mağazanın kendi adresi ayrıca eklenir.
# Ideasoft'un cevabına göre sunucu.json'daki "frame_hosts" listesiyle genişletilir.
FRAME_HOSTS = ("https://*.myideasoft.com", "https://*.ideasoft.com.tr")
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
       "img-src 'self' https: http: data:; connect-src 'self'; form-action 'self' https:; base-uri 'self'; "
       "object-src 'none'; frame-ancestors {}")
_HOST_RX = re.compile(r"(https://)?(\*\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(:\d{1,5})?")


def guvenilir_vekil(ip):
    """X-Forwarded-For başlığına güvenilen ters vekil mi: aynı makine ya da SEOVISI_VEKIL ortam değişkenindeki ağlar
    (virgülle, ör. Docker ağı "172.16.0.0/12")."""
    try:
        a = ipaddress.ip_address(ip)
        if a.is_loopback:
            return True
        return any(a in ipaddress.ip_network(n.strip(), strict=False)
                   for n in os.environ.get("SEOVISI_VEKIL", "").split(",") if n.strip())
    except ValueError:
        return False


class TooLarge(Exception):
    pass


class RateLimit:
    """Aynı adresten belirli sürede en çok n deneme."""

    def __init__(self, n, per):
        self.n, self.per = n, per
        self.hits, self.lock = {}, threading.Lock()

    def hit(self, key):
        """Denemeyi sayar. Sınır aşıldıysa beklenmesi gereken saniyeyi, aşılmadıysa 0 döndürür."""
        now = time.time()
        with self.lock:
            if len(self.hits) > 10000:
                self.hits = {k: q for k, q in self.hits.items() if q and now - q[-1] < self.per}
            q = self.hits.setdefault(key, deque())
            while q and now - q[0] >= self.per:
                q.popleft()
            if len(q) >= self.n:
                return int(self.per - (now - q[0])) + 1
            q.append(now)
            return 0


LOGIN_TRIES = RateLimit(20, 600)  # giriş: aynı adresten 10 dakikada en çok 20 deneme


def frame_ancestors(store=""):
    """Panelin hangi sayfaların içinde açılabileceği. Mağaza bilinmiyorsa (giriş sayfası) her HTTPS sayfası:
    giriş sayfasında tıklatılarak yaptırılabilecek zararlı bir iş yok."""
    if not store:
        return "'self' https:"
    extra = SRV.get("frame_hosts") if SRV else []
    hosts = [f"https://{store}"] + list(FRAME_HOSTS) + [h for h in extra or [] if isinstance(h, str)]
    return " ".join(["'self'"] + [h if h.startswith("https://") else f"https://{h}"
                                  for h in dict.fromkeys(hosts) if _HOST_RX.fullmatch(h)])


# Ideasoft izin sayfasına giden her istek bir "state" taşır; dönüşte hangi mağaza ya da giriş olduğu buradan bulunur
_pending, _pending_lock = {}, threading.Lock()


def new_state(info):
    st = secrets.token_urlsafe(24)
    with _pending_lock:
        now = time.time()
        for k in [k for k, v in _pending.items() if now - v["at"] > 900]:
            del _pending[k]
        if len(_pending) >= MAX_PENDING:          # bellek sınırı: en eskisi düşer
            del _pending[min(_pending, key=lambda k: _pending[k]["at"])]
        _pending[st] = dict(info, at=now)
    return st


def take_state(st):
    with _pending_lock:
        v = _pending.pop(st or "", None)
    return v if v and time.time() - v["at"] <= 900 else None


SESSION_DAYS = 30


def _sign(v):
    return hmac.new(SRV.get("secret").encode(), v.encode(), hashlib.sha256).hexdigest()


def session_cookie(tid, clear=False, framed=False):
    """HTTPS'te SameSite=None: panel Ideasoft'un içinde (başka sitenin çerçevesinde) açılırken de çerez gider.
    framed: çerçevenin içinde verilen çerez; Partitioned olduğu için yalnızca o üst sitenin içinde geçerli (CHIPS)
    ve üçüncü taraf çerezleri kapatan tarayıcılarda da çalışır. Başka sitelerden gelen sahte istekleri X-Seovisi başlığı keser."""
    if clear:
        val, age = "", 0
    else:
        v = f"{tid}.{int(time.time()) + SESSION_DAYS * 86400}"
        val, age = f"{v}.{_sign(v)}", SESSION_DAYS * 86400
    if SRV.get("public_url", "").startswith("https://"):
        site = "SameSite=None; Secure" + ("; Partitioned" if framed else "")
    else:
        site = "SameSite=Lax"
    return f"sv={val}; Path=/; HttpOnly; {site}; Max-Age={age}"


def clear_cookies():
    """Çıkış: hem normal hem çerçeve içi (Partitioned) çerez silinir."""
    return [session_cookie("", clear=True), session_cookie("", clear=True, framed=True)]


# ============================================================ giriş kapısı
#
# Panel üç yoldan oturum açar:
#   1. Ideasoft paneli uygulamayı açarken mağazayı imzalı bir bilgiyle bildirirse: ideasoft_launch() (Ideasoft'un cevabı bekleniyor).
#   2. Çerçeve içinden giriş: Ideasoft'un izin sayfası çerçevede açılmadığı için giriş yeni sekmede yapılır. Çerçevedeki sayfa
#      rastgele bir kapı kodu üretip girişe ekler; giriş bitince aynı kodla /kapi/al'dan kendi (Partitioned) çerezini alır.
#      Kod tek kullanımlıktır, 5 dakika geçerlidir ve yalnızca girişi başlatan internet adresine verilir: başkasına
#      gönderilen bir giriş bağlantısıyla oturum çalınamaz.
#   3. Tam ekran: uygulama kendi sekmesinde normal çerezle çalışır.

KAPI_SECONDS = 300
_KAPI_RX = re.compile(r"[A-Za-z0-9_-]{22,64}")
_kapi, _kapi_lock = {}, threading.Lock()


def kapi_open(code, ip):
    if not _KAPI_RX.fullmatch(code or ""):
        return None
    with _kapi_lock:
        now = time.time()
        for k in [k for k, v in _kapi.items() if now - v["at"] > KAPI_SECONDS]:
            del _kapi[k]
        if len(_kapi) >= MAX_PENDING:
            del _kapi[min(_kapi, key=lambda k: _kapi[k]["at"])]
        if code in _kapi:                 # aynı kod ikinci kez kullanılamaz
            return None
        _kapi[code] = {"ip": ip, "at": now, "tid": None}
    return code


def kapi_done(code, tid):
    with _kapi_lock:
        if code in _kapi:
            _kapi[code]["tid"] = tid


def kapi_take(code, ip):
    """Dönüş: mağaza klasörü (giriş tamam), "bekle" (giriş sürüyor) ya da None (geçersiz)."""
    with _kapi_lock:
        v = _kapi.get(code or "")
        if not v or v.get("used") or v["ip"] != ip or time.time() - v["at"] > KAPI_SECONDS:
            return None
        if not v["tid"]:
            return "bekle"
        v["used"] = True                  # süresi dolana kadar hatırlanır; aynı kod yeniden açılamaz
        return v["tid"]


def ideasoft_launch(q):
    """Kapı 1: Ideasoft paneli uygulamayı açarken hangi mağazanın açtığını imzalı bir bilgiyle bildiriyorsa (Ideasoft'a
    sorulan 1. soru) burada doğrulanıp mağaza klasörü döndürülür. Cevap gelene kadar kapalı: hiçbir parametreye güvenilmez."""
    return None


def session_tenant(cookie_header):
    c = http.cookies.SimpleCookie()
    try:
        c.load(cookie_header or "")
    except http.cookies.CookieError:
        return None
    raw = c["sv"].value if "sv" in c else ""
    parts = raw.rsplit(".", 2)
    if len(parts) != 3 or not hmac.compare_digest(_sign(f"{parts[0]}.{parts[1]}"), parts[2]):
        return None
    if not parts[1].isdigit() or int(parts[1]) < time.time() or not known_tenant(parts[0]):
        return None
    return parts[0]


# ============================================================ yönetici paneli
#
# /yonetim: yalnızca sunucu kipinde, mağaza oturumundan tamamen ayrı. Parola data/yonetici.json'da karma olarak durur
# (python app.py --yonetici-parola). Çerez "svy" yalnızca /yonetim yolunda geçerli, SameSite=Strict, 12 saat; sayfa
# hiçbir çerçevede açılmaz. Girişten başka her POST gibi buradakiler de X-Seovisi başlığı ister.

ADMIN_TRIES = RateLimit(10, 900)  # yönetici girişi: aynı adresten 15 dakikada en çok 10 deneme
UI_YONETIM = os.path.join(BASE, "ui", "yonetim.html")
_IS_ADI = (("seoscan", "SEO taraması"), ("catscan", "Kategori analizi"), ("img", "Görsel taraması"),
           ("links", "Kırık bağlantı taraması"), ("seojobs", "SEO gönderimi"), ("catjobs", "Kategori düzeltme"),
           ("gecis", "Şablon geçişi"), ("oto", "Otopilot"))


def yonetici_cerezi(deger="", clear=False):
    site = "; Secure" if SRV.get("public_url", "").startswith("https://") else ""
    age = 0 if clear else YN.OTURUM_SAAT * 3600
    return f"svy={'' if clear else deger}; Path=/yonetim; HttpOnly; SameSite=Strict{site}; Max-Age={age}"


def yonetici_oturumu(cookie_header):
    c = http.cookies.SimpleCookie()
    try:
        c.load(cookie_header or "")
    except http.cookies.CookieError:
        return False
    return "svy" in c and YN.cerez_gecerli(SRV.get("secret"), YN.oku(DATA), c["svy"].value)


def yonetim_satiri(tid):
    """Bir mağazanın özeti. Hiç giriş yapmamış (yalnızca aboneliği açılmış) mağazanın klasörüne ayar yazılmaz."""
    d = os.path.join(STORES, tid)
    kayit = AB.oku(d) if os.path.isfile(os.path.join(d, AB.FILE)) else {}   # okumak, kaydı olmayana kayıt açardı
    a = AB.gecerli(kayit)
    row = {"id": tid, "magaza": "", "ad": "", "bagli": False, "giris": known_tenant(tid), "abonelik": a,
           "kaynak": kayit.get("kaynak"), "urun": 0, "otopilot": False, "isler": [], "istek_bugun": THROTTLE.bugun(tid),
           "son_islem": YN.son_islem(d), "hata_7g": len(YN.hatalar(d))}
    if row["giris"]:
        prev = getattr(_cur, "t", None)
        try:
            _cur.t = t = tenant(tid)
            row.update(magaza=CFG.get("store") or "", ad=PROFILE().get("magaza") or "",
                       bagli=bool(CFG.get("access_token") or CFG.get("refresh_token")), urun=urun_sayisi(),
                       otopilot=oto_ayar()["acik"], isler=[ad for k, ad in _IS_ADI if getattr(t, k).running])
        finally:
            _cur.t = prev
    return row


def yonetim_durum():
    tids = sorted(d for d in os.listdir(STORES) if re.fullmatch(r"[a-z0-9-]{1,80}", d)
                  and (known_tenant(d) or os.path.isfile(os.path.join(STORES, d, AB.FILE))))
    rows = [yonetim_satiri(t) for t in tids]
    durum = Counter(r["abonelik"]["durum"] for r in rows)
    ozet = {"toplam": len(rows), "bagli": sum(r["bagli"] for r in rows), "aktif": durum["aktif"], "deneme": durum["deneme"],
            "ucretsiz": durum["ucretsiz"] + durum["suresi_doldu"] + durum["iptal"],
            "yakinda": sum(1 for r in rows if r["abonelik"]["kalan_gun"] is not None and r["abonelik"]["kalan_gun"] <= 30),
            "hata_7g": sum(r["hata_7g"] for r in rows), "istek_bugun": sum(r["istek_bugun"] for r in rows),
            "otopilot": sum(r["otopilot"] for r in rows)}
    P = AB.paketler()["paketler"]
    return {"ozet": ozet, "magazalar": rows, "paketler": [{"id": k, "ad": v["ad"], "urun": v.get("urun")} for k, v in P.items()],
            "durumlar": [{"id": k, "ad": AB.DURUM_ADI[k]} for k in AB.DURUMLAR]}


def yonetim_hatalar(gun=7):
    out = []
    for tid in sorted(os.listdir(STORES)):
        d = os.path.join(STORES, tid)
        if re.fullmatch(r"[a-z0-9-]{1,80}", tid) and os.path.isdir(d):
            out += [dict(h, id=tid) for h in YN.hatalar(d, gun)]
    return sorted(out, key=lambda h: h["zaman"], reverse=True)[:300]


def yonetim_abonelik(form):
    """Yönetici panelinden abonelik açma / uzatma. Mağaza klasör adıyla ya da alan adıyla verilir; henüz giriş yapmamış
    mağazanın kaydı ilk girişte geçerli olur (komut satırındaki --abonelik gibi)."""
    m = str(form.get("magaza") or "").strip().lower()
    if re.fullmatch(r"[a-z0-9-]{1,80}", m) and os.path.isdir(os.path.join(STORES, m)):
        tid = m
    else:
        host = store_host(m)
        if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host):
            raise ValueError("Mağaza adresini yazın, örn. magaza.myideasoft.com")
        tid = tenant_id(host)
    AB.yaz(os.path.join(STORES, tid), paket=form.get("paket") or None, durum=form.get("durum") or "aktif",
           bitis=form.get("bitis") or None, kaynak="yonetici")
    print(f"Yönetici paneli: {tid} aboneliği değişti.", flush=True)
    return yonetim_satiri(tid)


def local_store():
    """Yerel kipte açılacak mağaza: en son kullanılan, yoksa ilk bulunan, hiç yoksa yeni bir 'yerel' klasörü."""
    tid = SRV.get("yerel")
    if not known_tenant(tid):
        found = sorted(d for d in os.listdir(STORES) if known_tenant(d))
        tid = found[0] if found else "yerel"
        SRV.update(yerel=tid)
    return tid


def migrate_legacy():
    """Eski kurulumda ayarlar ve veritabanı doğrudan data klasöründeydi; bunları mağaza klasörüne taşır."""
    names = [n for n in ("ayarlar.json", "durum.db", "durum.db-wal", "durum.db-shm", "islem.log")
             if os.path.isfile(os.path.join(DATA, n))]
    if not {"ayarlar.json", "durum.db"} & set(names):
        return
    store = ""
    try:
        with open(os.path.join(DATA, "ayarlar.json"), encoding="utf-8") as f:
            store = store_host(json.load(f).get("store"))
    except (OSError, ValueError, AttributeError):
        pass
    tid = tenant_id(store) if store else "yerel"
    dest = os.path.join(STORES, tid)
    if os.path.exists(os.path.join(dest, "ayarlar.json")) or os.path.exists(os.path.join(dest, "durum.db")):
        print(f"Uyarı: data klasöründe eski kurulum dosyaları var ama {dest} dolu; dosyalara dokunulmadı.")
        return
    os.makedirs(dest, exist_ok=True)
    for n in names:
        os.replace(os.path.join(DATA, n), os.path.join(dest, n))
    SRV.update(yerel=tid)
    print(f"Eski kurulum {dest} klasörüne taşındı.")


def login_page(msg=""):
    ready = all(SRV.get(k) for k in ("client_id", "client_secret", "public_url"))
    err = f'<p class="err">{html.escape(msg)}</p>' if msg else ""
    if not ready:
        err += ('<p class="err">Sunucu ayarları eksik: data/sunucu.json dosyasına Ideasoft uygulama anahtarlarını '
                've public_url adresini girin.</p>')
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>seovisi — giriş</title><link rel="icon" href="/favicon.ico">
<style>
:root{{--ink:#15161a;--muted:#5d6270;--line:#e3e5ea;--blue:#2f4bf0;--bg:#f5f6f8;--card:#fff;--err:#c0392b}}
@media (prefers-color-scheme:dark){{:root{{--ink:#eef0f4;--muted:#a0a5b1;--line:#2c2f37;--bg:#111216;--card:#1a1c21;--err:#ff7b6b}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);
font-family:"Segoe UI",system-ui,sans-serif;padding:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:36px 32px;width:100%;max-width:420px}}
img{{height:34px;margin-bottom:22px}}h1{{font-size:22px;margin:0 0 6px}}p{{color:var(--muted);line-height:1.5;margin:0 0 20px}}
label{{display:block;font-weight:600;font-size:14px;margin-bottom:6px}}
input{{width:100%;font:inherit;padding:11px 12px;border:1px solid var(--line);border-radius:9px;background:transparent;color:var(--ink)}}
button{{width:100%;margin-top:14px;font:inherit;font-weight:600;padding:12px;border:0;border-radius:9px;background:var(--blue);color:#fff;cursor:pointer}}
.err{{color:var(--err);margin:0 0 16px}}.frame{{margin:16px 0 0;color:var(--ink)}}.frame a{{color:var(--blue)}}small{{display:block;color:var(--muted);margin-top:16px;line-height:1.5}}
</style>
<div class="card"><img src="/marka/seovisi-logo.svg" alt="seovisi">
<h1>Mağazanızla giriş yapın</h1><p>Ideasoft mağazanızın adresini yazın. Ideasoft'un izin sayfasında onay verdiğinizde panel açılır.</p>
{err}<form method="post" action="/giris" id="f"><label for="m">Mağaza adresi</label>
<input id="m" name="store" placeholder="magazaniz.myideasoft.com" autocomplete="url" required autofocus>
<input type="hidden" name="kapi" id="k">
<button type="submit">Ideasoft ile giriş yap</button></form>
<p class="frame" id="note" hidden></p>
<small>Şifreniz bize gelmez; giriş Ideasoft üzerinden yapılır. Tarama mağazanızda hiçbir şey değiştirmez.</small></div>
<script>
// Ideasoft panelinin içinde (çerçevede) açıldıysa: Ideasoft'un izin sayfası çerçevede açılmaz; giriş yeni sekmede yapılır,
// bu sayfa tek kullanımlık kapı koduyla oturumunu teslim alır.
if (window.top !== window.self) {{
  const f = document.getElementById('f'), note = document.getElementById('note');
  const say = (t, full) => {{ note.hidden = false; note.innerHTML = t + (full ? ' <a href="/" target="_blank" rel="noopener">Tam ekranda aç</a>' : ''); }};
  say('Giriş yeni bir sekmede açılır; izin verdikten sonra bu pencereye dönün.');
  f.target = '_blank';
  let timer = null;
  f.addEventListener('submit', () => {{
    const b = new Uint8Array(24); crypto.getRandomValues(b);
    const code = btoa(String.fromCharCode(...b)).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
    document.getElementById('k').value = code;
    say('Yeni sekmede Ideasoft izni bekleniyor…');
    clearInterval(timer);
    const started = Date.now();
    timer = setInterval(async () => {{
      if (Date.now() - started > 300000) {{ clearInterval(timer); say('Süre doldu; yeniden giriş yapın.'); return; }}
      const r = await fetch('/kapi/al', {{method: 'POST', headers: {{'Content-Type': 'application/json', 'X-Seovisi': '1'}},
                                          body: JSON.stringify({{kapi: code}})}}).catch(() => null);
      const j = r ? await r.json().catch(() => ({{}})) : {{}};
      if (j.bekle) return;
      clearInterval(timer);
      if (!j.ok) {{ say(j.error || 'Giriş tamamlanamadı.'); return; }}
      const s = await fetch('/api/state').catch(() => null);
      if (s && s.ok) location.reload();
      else say('Tarayıcınız bu pencerede oturum açılmasına izin vermiyor. Paneli kendi sekmesinde kullanabilirsiniz:', true);
    }}, 2000);
  }});
}}
</script></html>"""


# ======================================================================= web


class H(BaseHTTPRequestHandler):
    server_version = "seovisi/1.0"
    yonetim = False               # /yonetim isteği: sayfa hiçbir çerçevede açılmaz
    timeout = 60                  # yavaş ya da yarım kalan bağlantı bir iş parçacığını süresiz tutmasın

    def log_message(self, *a):
        pass

    def _security_headers(self):
        t = getattr(_cur, "t", None)
        fa = "'none'" if self.yonetim else frame_ancestors(store_host(CFG.get("store")) if t else "")
        h = {"Content-Security-Policy": CSP.format(fa),
             "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin"}
        if SERVER["on"] and SRV.get("public_url", "").startswith("https://"):
            h["Strict-Transport-Security"] = "max-age=31536000"
        return h

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in dict(self._security_headers(), **(extra or {})).items():
            for one in (v if isinstance(v, list) else [v]):
                self.send_header(k, one)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise TooLarge()
        if not 0 <= n <= MAX_BODY:
            raise TooLarge()
        return self.rfile.read(n) if n else b""

    def client_ip(self):
        """İsteği gönderenin adresi. İstek güvenilen bir ters vekilden (aynı makinedeki ya da SEOVISI_VEKIL ağlarındaki
        Caddy) geldiyse onun eklediği son adres; yoksa bütün müşteriler vekilin tek adresinden geliyor görünürdü."""
        ip = self.client_address[0]
        fwd = (self.headers.get("X-Forwarded-For") or "").split(",")[-1].strip()
        try:
            if fwd and guvenilir_vekil(ip):
                ipaddress.ip_address(fwd)
                return fwd
        except ValueError:
            pass
        return ip

    def _json(self):
        raw = self._body()
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            return {}

    def do_GET(self):
        self._dispatch("GET", self.route_get)

    def do_POST(self):
        self._dispatch("POST", self.route_post)

    def _dispatch(self, method, route):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        _cur.t = None
        self.yonetim = False
        try:
            # Panelin kendi istekleri bu başlığı taşır. Başka bir site tarayıcıya başlık ekletemez; böylece çerez ya da
            # localhost üzerinden sahte istek gönderilemez.
            if method == "POST" and u.path != "/giris" and self.headers.get("X-Seovisi") != "1":
                return self._send(403, {"error": "İstek panelden gelmedi."})
            if self.route_public(method, u.path, q):
                return
            tid = session_tenant(self.headers.get("Cookie")) if SERVER["on"] else LOCAL["id"]
            if not tid and SERVER["on"] and u.path in ("/", "/index.html"):
                tid = ideasoft_launch(q)
                if tid:
                    _cur.t = tenant(tid)
                    with open(UI, encoding="utf-8") as f:
                        return self._send(200, f.read(), "text/html; charset=utf-8",
                                          {"Set-Cookie": [session_cookie(tid), session_cookie(tid, framed=True)]})
            if not tid:
                if u.path in ("/", "/index.html"):
                    return self._html(login_page())
                return self._send(401, {"error": "Oturum kapandı; yeniden giriş yapın.", "login": True})
            _cur.t = tenant(tid)
            route(u.path, q)
        except TooLarge:
            self.close_connection = True          # okunmayan gövde bağlantıda kalmasın
            self._send(413, {"error": "İstek çok büyük."})
        except ApiError as e:
            self._send(502, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            if getattr(_cur, "t", None) is not None:
                log(f"Beklenmeyen hata ({u.path}): {e}", "err")      # yönetici panelindeki hata listesine düşer
            self._send(500, {"error": str(e)})
        finally:
            _cur.t = None

    def _html(self, body, code=200, extra=None):
        return self._send(code, body, "text/html; charset=utf-8", extra)

    def _redirect(self, url, extra=None):
        self._send(302, b"", "text/plain", dict({"Location": url}, **(extra or {})))

    # ------------------------------------------------- oturum gerektirmeyenler
    def route_public(self, method, p, q):
        if method == "GET" and (p == "/favicon.ico" or p.startswith("/marka/")):   # logo ve simgeler (ui/marka)
            name = "favicon.ico" if p == "/favicon.ico" else os.path.basename(p)
            types = {".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
            path = os.path.join(MARKA, name)
            if os.path.splitext(name)[1] not in types or not os.path.isfile(path):
                self._send(404, {"error": "Yok"})
            else:
                with open(path, "rb") as f:
                    self._send(200, f.read(), types[os.path.splitext(name)[1]])
            return True
        if p == "/giris" and method == "POST" and SERVER["on"]:
            form = {k: v[0] for k, v in urllib.parse.parse_qs(self._body().decode("utf-8", "replace")).items()}
            host = store_host(form.get("store"))
            wait = LOGIN_TRIES.hit(self.client_ip())
            if wait:
                self._html(login_page(f"Çok fazla deneme yapıldı. {-(-wait // 60)} dakika sonra yeniden deneyin."),
                           429, {"Retry-After": str(wait)})
            elif not all(SRV.get(k) for k in ("client_id", "client_secret", "public_url")):
                self._html(login_page())
            elif not public_host(host):
                self._html(login_page("Bu adres bulunamadı. Mağazanızın adresini magaza.myideasoft.com ya da "
                                      "magaza.com biçiminde yazın."))
            else:
                info = {"store": host}
                if form.get("kapi"):          # çerçevedeki giriş sayfasından yeni sekmede açıldı
                    info["kapi"] = kapi_open(form["kapi"], self.client_ip())
                self._redirect(auth_link(host, new_state(info)))
            return True
        if p == "/kapi/al" and method == "POST" and SERVER["on"]:
            got = kapi_take(self._json().get("kapi"), self.client_ip())
            if got == "bekle":
                self._send(200, {"bekle": True})
            elif got:
                _cur.t = tenant(got)
                self._send(200, {"ok": True}, extra={"Set-Cookie": session_cookie(got, framed=True)})
            else:
                self._send(404, {"error": "Giriş kodu geçersiz ya da süresi doldu; yeniden giriş yapın."})
            return True
        if (p == "/yonetim" or p.startswith("/yonetim/")) and SERVER["on"]:
            self.yonetim = True
            self._yonetim(method, p, q)
            return True
        if p == "/saglik" and method == "GET":        # dışarıdan izleme: program ayakta ve veri klasörü yazılabilir mi
            ok = os.access(DATA, os.W_OK)
            self._send(200 if ok else 503, {"ok": ok})
            return True
        if p == "/cikis" and SERVER["on"]:
            self._redirect("/", {"Set-Cookie": clear_cookies()})
            return True
        if p == "/callback" and method == "GET":
            self._callback(q)
            return True
        return False

    def _yonetim(self, method, p, q):
        if p == "/yonetim" and method == "GET":
            with open(UI_YONETIM, encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        kayitli = YN.oku(DATA)
        if p == "/yonetim/giris" and method == "POST":
            wait = ADMIN_TRIES.hit(self.client_ip())
            if wait:
                return self._send(429, {"error": f"Çok fazla deneme yapıldı. {-(-wait // 60)} dakika sonra yeniden deneyin."},
                                  extra={"Retry-After": str(wait)})
            if not kayitli:
                return self._send(400, {"error": "Yönetici parolası belirlenmemiş. Sunucuda: python app.py --yonetici-parola"})
            if not YN.dogru(str(self._json().get("parola") or ""), kayitli):
                print(f"Yönetici paneli: hatalı parola ({self.client_ip()}).", flush=True)
                return self._send(403, {"error": "Parola yanlış."})
            print(f"Yönetici paneli: giriş yapıldı ({self.client_ip()}).", flush=True)
            return self._send(200, {"ok": True}, extra={"Set-Cookie": yonetici_cerezi(YN.cerez(SRV.get("secret"), kayitli))})
        if p == "/yonetim/cikis" and method == "POST":
            return self._send(200, {"ok": True}, extra={"Set-Cookie": yonetici_cerezi(clear=True)})
        if not yonetici_oturumu(self.headers.get("Cookie")):
            return self._send(401, {"error": "Oturum kapandı; yeniden giriş yapın.", "giris": True, "parola_var": bool(kayitli)})
        if p == "/yonetim/api/durum" and method == "GET":
            return self._send(200, yonetim_durum())
        if p == "/yonetim/api/hatalar" and method == "GET":
            return self._send(200, {"hatalar": yonetim_hatalar()})
        if p == "/yonetim/api/abonelik" and method == "POST":
            try:
                return self._send(200, {"ok": True, "magaza": yonetim_abonelik(self._json())})
            except ValueError as e:
                return self._send(400, {"error": str(e)})
        return self._send(404, {"error": "Yok"})

    def _callback(self, q):
        if q.get("error"):
            return self._html(page_msg("Bağlantı reddedildi", q.get("error_description") or q["error"]))
        st = take_state(q.get("state"))
        if not st:
            return self._html(page_msg("Güvenlik kontrolü başarısız",
                                       "İzin sayfası çok uzun açık kaldı ya da başka bir sekmeden geldi. "
                                       "Yeniden deneyin."), 400)
        try:
            if "tid" in st:                       # panelden "Mağazaya bağlan"
                _cur.t = tenant(st["tid"])
                API.exchange(q.get("code", ""))
            else:                                 # sunucuda giriş: anahtar alınamazsa mağaza klasörü açılmaz
                host = st["store"]
                tok = token_request(host, {"grant_type": "authorization_code", "code": q.get("code", ""),
                                           "client_id": SRV.get("client_id"), "client_secret": SRV.get("client_secret"),
                                           "redirect_uri": redirect_uri()})
                _cur.t = tenant(tenant_id(host))
                if not CFG.get("store"):
                    CFG.update(store=host)
                API.save_token(tok)
        except ApiError as e:
            return self._html(page_msg("Bağlantı kurulamadı", str(e)))
        log("Mağazaya bağlanıldı.", "ok")
        CFG.update(lookup_mode="")
        spawn(self._after_connect)
        name = PROFILE()["magaza"]
        extra = {"Set-Cookie": session_cookie(current().id)} if SERVER["on"] else None
        if st.get("kapi"):
            kapi_done(st["kapi"], current().id)
            return self._html(page_msg("Giriş tamam", "Bu sekmeyi kapatıp Ideasoft panelindeki seovisi penceresine "
                                       "dönebilirsiniz; panel orada kendiliğinden açılır.", ok=True, close=True),
                              extra=extra)
        return self._html(page_msg("Bağlantı tamam", (f"{name} mağazasına" if name else "Mağazaya") + " bağlanıldı. "
                                   "Panel açılıyor.", ok=True), extra=extra)

    # ---------------------------------------------------------------- GET
    def route_get(self, p, q):
        if p in ("/", "/index.html"):
            with open(UI, encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if p == "/api/state":
            t = current()
            with t.log_lock:
                lg = list(t.logs)[-120:]
            cfg = CFG.public()
            if SERVER["on"]:
                cfg["redirect_uri"] = redirect_uri()
            ab = abonelik_durumu()
            if ab:
                # ücretli özellik yoksa ücretsiz / süresi doldu / iptal mesajı; varsa yalnızca ürün sınırı denetlenir
                ab["uyari"] = AB.engel(ab, (ab["ozellikler"] or ["seo_gonder"])[0], ab["urun_sayisi"])
            return self._send(200, {"cfg": cfg, "rpm": API.rpm(), "log": lg, "abonelik": ab,
                                    "kurulum": kurulum_gerekli(), "mode": "sunucu" if SERVER["on"] else "yerel",
                                    "oto_onay": DBI.q("SELECT COUNT(*) n FROM oto WHERE durum='onay'", one=True)["n"]})
        if p == "/api/sablon":
            return self._send(200, {"sablon": sablon(), "secenekler": TPL.secenekler()})
        if p == "/api/otopilot":
            return self._send(200, OTO.state())
        if p == "/api/sablon/gecis":
            return self._send(200, GECIS.state())
        if p == "/api/rapor":
            r = rapor_al(q.get("ay"))
            son = DBI.q("SELECT v FROM kv WHERE k='haftalik_son'", one=True)
            ab = abonelik_durumu()
            r["haftalik"] = {"son": son["v"] if son else None, "gun": HAFTALIK_GUN, "acik": not ab or bool(ab["ozellikler"])}
            r["magaza"] = PROFILE()["magaza"] or store_host(CFG.get("store"))
            return self._send(200, r)
        if p == "/api/linkler":
            tur = q.get("tur") or ""
            rows = [dict(r, kaynaklar=json.loads(r["kaynaklar"] or "[]"), harita=bool(r["harita"]))
                    for r in DBI.q("SELECT * FROM kirik ORDER BY CASE tur WHEN 'sayfa' THEN 0 WHEN 'gorsel' THEN 1 ELSE 2 END, url")]
            sec = [r for r in rows if not tur or r["tur"] == tur]
            page = max(0, int(q.get("page") or 0))
            return self._send(200, {"tarama": LINKS.state(), "sayilar": Counter(r["tur"] for r in rows), "toplam": len(sec),
                                    "items": sec[page * 50:(page + 1) * 50], "turler": BG.TURLER})
        if p == "/api/kopyalar":
            gruplar = kopyalar()
            page = max(0, int(q.get("page") or 0))
            return self._send(200, {"sayilar": Counter(g["tur"] for g in gruplar), "toplam": len(gruplar),
                                    "gruplar": gruplar[page * 30:(page + 1) * 30], "turler": {k: v[0] for k, v in KP.TURLER.items()},
                                    "taranan": DBI.q("SELECT COUNT(*) n FROM urunbilgi", one=True)["n"],
                                    "panel": API.base() if CFG.get("store") else ""})
        if p == "/api/uyarilar":
            items, taranan = uyarilar()
            say = Counter(u["tur"] for u in items)
            tur, aranan = q.get("tur") or "", ST.tr_lower(q.get("q") or "")
            sec = [u for u in items if (not tur or u["tur"] == tur or u["grup"] == tur)
                   and (not aranan or aranan in ST.tr_lower(f"{u['name']} {u['sku']} {u['pid']}"))]
            page = max(0, int(q.get("page") or 0))
            return self._send(200, {"taranan": taranan, "sayilar": say, "toplam": len(sec), "items": sec[page * 50:(page + 1) * 50],
                                    "turler": UY.TURLER, "gruplar": UY.GRUPLAR,
                                    "panel": API.base() if CFG.get("store") else ""})
        if p == "/api/seo/state":
            st = SEOSCAN.state()
            st["jobs"] = SEOJOBS.state()
            st["prepare"] = bool(CFG.get("seo_prepare", True))
            st["eur_rate"] = float(CFG.get("eur_rate") or 55)
            return self._send(200, st)
        if p == "/api/seo/map":
            rows = DBI.q("SELECT pid, ok FROM seo ORDER BY pid")
            return self._send(200, {"s": "".join({1: "v", 0: "y"}.get(r["ok"], "u") for r in rows),
                                    "pids": [r["pid"] for r in rows], "total": SEOSCAN.total})
        if p == "/api/seo/items":
            where, args = [], []
            if q.get("ok") in ("0", "1"):
                where.append("ok=?")
                args.append(int(q["ok"]))
            if q.get("ok") == "-1":
                where.append("ok=-1")
            if q.get("pstate") in ("hazir", "gonderildi", "hata"):
                where.append("pstate=?" + (" AND ok=0" if q["pstate"] == "hazir" else ""))
                args.append(q["pstate"])
            if (q.get("code") or "").startswith("p"):
                where.append("ok=0 AND pscore=?")
                args.append(q["code"][1:])
            if q.get("q"):
                s_ = f"%{q['q'].strip()}%"
                where.append("(sku LIKE ? OR name LIKE ? OR kw LIKE ? OR CAST(pid AS TEXT)=?)")
                args += [s_, s_, s_, q["q"].strip()]
            w = ("WHERE " + " AND ".join(where)) if where else ""
            page = max(0, int(q.get("page") or 0))
            total = DBI.q(f"SELECT COUNT(*) n FROM seo {w}", args, one=True)["n"]
            rate = float(CFG.get("eur_rate") or 55)
            tl = f"(COALESCE(price, -1) * CASE WHEN UPPER(COALESCE(cur, '')) IN ('TL', 'TRY', '₺', 'USD', 'GBP') THEN 1 ELSE {rate} END)"
            rows = DBI.q(f"SELECT pid, sku, name, kw, top, bottom, ok, codes, pscore, pstate, price, cur, {tl} AS price_tl "
                         f"FROM seo {w} ORDER BY price_tl DESC, pid LIMIT 100 OFFSET ?",
                         args + [page * 100])
            return self._send(200, {"total": total, "items": [dict(r) for r in rows]})
        if p == "/api/seo/raw":
            prod = API.call("GET", f"products/{int(q.get('pid') or 0)}") or {}
            keep = {k: v for k, v in prod.items() if not isinstance(v, (list, dict))}
            keep["_nesneler"] = sorted(k for k, v in prod.items() if isinstance(v, (list, dict)))
            return self._send(200, keep)
        if p == "/api/seo/item":
            r = DBI.q("SELECT * FROM seo WHERE pid=?", (int(q.get("pid") or 0),), one=True)
            if not r:
                return self._send(200, {"error": "Bulunamadı"})
            d = dict(r)
            d["fails"] = json.loads(d["fails"] or "[]")
            d["plan"] = json.loads(d["plan"]) if d.get("plan") else None
            d["has_backup"] = bool(d.pop("backup", None))
            d["panel_url"] = f"{API.base()}/panel/products/edit/{d['pid']}"
            return self._send(200, d)
        if p == "/api/overview":
            return self._send(200, overview())
        if p == "/api/jobs":
            return self._send(200, jobs_state())
        if p == "/api/cat/state":
            return self._send(200, CATSCAN.state())
        if p == "/api/cat/list":
            items = CATSCAN.rows(q.get("kind") or "wrong", q.get("q") or "", q.get("f") or "",
                                 int(q.get("min") or 0), q.get("pending") == "1")
            page = max(0, int(q.get("page") or 0))
            out = [{k: v for k, v in it.items() if k != "pids"} for it in items[page * 100:(page + 1) * 100]]
            return self._send(200, {"total": len(items), "items": out})
        if p == "/api/cat/tree":   # elle kategori seçimi için bütün kategoriler (yol adıyla)
            return self._send(200, {"items": sorted(({"id": i, "path": s} for i, s in category_paths().items()),
                                                    key=lambda x: ST.tr_lower(x["path"]))})
        if p == "/api/cat/group":
            g = CATSCAN.group(int(q.get("i") or -1))
            return self._send(200, g or {"error": "Bulunamadı"})
        if p == "/api/cat/csv":
            kind = q.get("kind") if q.get("kind") in ("wrong", "uncat", "newcats", "categories") else "wrong"
            name = {"wrong": "yanlis_kategori", "uncat": "kategorisiz", "newcats": "yeni_kategori_onerileri",
                    "categories": "kategoriler"}[kind]
            return self._send(200, CATSCAN.csv(kind), "text/csv; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="{name}.csv"'})
        if p == "/api/img/state":
            return self._send(200, IMG.state())
        if p == "/api/img/item":
            r = DBI.q("SELECT * FROM img WHERE pid=?", (int(q.get("pid") or 0),), one=True)
            if not r:
                return self._send(200, {"error": "Bulunamadı"})
            d = dict(r)
            d["panel_url"] = f"{API.base()}/panel/products/edit/{d['pid']}"
            return self._send(200, d)
        if p == "/api/img/map":
            rows = DBI.q("SELECT pid, has FROM img ORDER BY pid")
            return self._send(200, {"s": "".join("v" if r["has"] else "y" for r in rows),
                                    "pids": [r["pid"] for r in rows], "total": IMG.total,
                                    "base": API.base()})
        if p == "/api/img/items":
            where, args = [], []
            if q.get("has") in ("0", "1"):
                where.append("has=?")
                args.append(int(q["has"]))
            if q.get("q"):
                s = f"%{q['q'].strip()}%"
                where.append("(sku LIKE ? OR name LIKE ? OR CAST(pid AS TEXT)=?)")
                args += [s, s, q["q"].strip()]
            w = ("WHERE " + " AND ".join(where)) if where else ""
            page = max(0, int(q.get("page") or 0))
            total = DBI.q(f"SELECT COUNT(*) n FROM img {w}", args, one=True)["n"]
            rows = DBI.q(f"SELECT * FROM img {w} ORDER BY pid LIMIT 100 OFFSET ?", args + [page * 100])
            return self._send(200, {"total": total, "base": API.base(),
                                    "items": [dict(r) for r in rows]})
        if p == "/api/connect":
            if not all(client_creds()):
                return self._send(200, {"error": "Önce Client ID ve Client Secret girip kaydedin."})
            return self._send(200, {"url": API.auth_url(new_state({"tid": current().id}))})
        return self._send(404, {"error": "Yok"})

    @staticmethod
    def _after_connect():
        try:
            mode = API.detect_lookup()
            if mode == "index":
                API.build_index()
            if not kw_loc() and CFG.get("kw_needle"):
                discover()
        except Exception as e:  # noqa: BLE001
            log(f"Bağlantı sonrası kontrol: {e}", "warn")

    # --------------------------------------------------------------- POST
    def route_post(self, p, q):
        if p in WRITE_ROUTES:
            msg = yazma_engeli(WRITE_ROUTES[p])
            if msg:
                return self._send(200, {"error": msg, "abonelik": True})
        if p == "/api/settings":
            d = self._json()
            allowed = {"store", "client_id", "client_secret", "target_density", "kw_needle", "eur_rate",
                       "sample_sku", "redirect_uri", "profil", "sablon"}
            if SERVER["on"]:
                allowed -= {"store", "client_id", "client_secret", "redirect_uri"}
            upd = {k: v for k, v in d.items() if k in allowed}
            if "client_secret" in upd and not upd["client_secret"]:
                upd.pop("client_secret")
            if "eur_rate" in upd:
                upd["eur_rate"] = max(1.0, float(str(upd["eur_rate"]).replace(",", ".")))
            if "target_density" in upd:
                upd["target_density"] = max(2.1, min(2.9, float(upd["target_density"])))
            if "profil" in upd:
                upd["profil"] = PR.load(upd["profil"])
            if "sablon" in upd:              # kısmi değişiklik kayıtlı şablona eklenir, geçersiz değerler düzeltilir
                upd["sablon"] = TPL.yukle(TPL.birlestir(sablon(), upd["sablon"]), sablon()["gorunum"])
                if upd["sablon"] != sablon():
                    # hazırlanıp gönderilmemiş açıklamalar yeni şablonla yeniden hazırlanır
                    DBI.x("UPDATE seo SET pstate='', plan=NULL, pmsg=NULL WHERE ok=0 AND pstate='hazir'")
            if "store" in upd and upd["store"] != CFG.get("store"):
                upd.update(access_token="", refresh_token="", expires_at=0, lookup_mode="")
            CFG.update(**upd)
            log("Ayarlar kaydedildi.")
            return self._send(200, {"ok": True, "cfg": CFG.public()})
        if p.startswith("/api/seo/"):
            act = p.rsplit("/", 1)[1]
            pid = int(q.get("pid") or 0)
            if act == "prepare":
                try:
                    prepare_plan(pid, int(q.get("variant") or 0))
                    return self._send(200, {"msg": "Açıklama yeniden oluşturuldu."})
                except ApiError as e:
                    return self._send(200, {"error": f"Ideasoft hatası: {e}"})
            if act == "score":
                d = self._json()
                r = DBI.q("SELECT name, plan FROM seo WHERE pid=?", (pid,), one=True)
                rp = r and r["plan"] and '"repair": true' in r["plan"]
                return self._send(200, ST.seo_score(clean_name((r or {"name": ""})["name"] or ""), d.get("keyword", ""),
                                                    d.get("details_html", ""), d.get("pageTitle", ""),
                                                    d.get("metaDescription", ""),
                                                    "panel_lo,panel,panel_hi" if rp else (CFG.get("count_method") or SAFE_METHODS)))
            if act == "send":
                if SEOJOBS.running:
                    return self._send(200, {"error": "Toplu işlem sürüyor; bitmesini bekleyin."})
                try:
                    state, msg = send_plan(pid, self._json() or None)
                except ApiError as e:
                    DBI.x("UPDATE seo SET pstate='hata', pmsg=? WHERE pid=?", (f"Ideasoft hatası: {str(e)[:200]}", pid))
                    return self._send(200, {"error": f"Ideasoft hatası: {e}"})
                return self._send(200, {"msg": msg, "state": state})
            if act == "calibrate_panel":
                oran = float(str(q.get("oran") or "0").replace(",", "."))
                prod = API.get_product(pid)
                det = (API.get_detail(prod) or {}).get("details") or ""
                kw, _ = kw_read(prod)
                c = ST.count_kw(ST.strip_tags(det), kw)
                w = ST.count_words(det, "asc_html")
                if not (oran > 0 and c and w):
                    return self._send(200, {"error": "Bu ürünün açıklaması/hedef kelimesi okunamadı."})
                f = max(1.0, min(1.8, oran / (c / w * 100)))
                CFG.update(panel_factor=round(f, 3))
                DBI.x("UPDATE seo SET pstate='', plan=NULL, pmsg=NULL WHERE ok=0 AND pstate='hazir'")
                log(f"Panel katsayısı {f:.3f} olarak ayarlandı (panel %{oran}, program %{c / w * 100:.2f}).", "ok")
                return self._send(200, {"msg": f"Ayarlandı: panel katsayısı {f:.2f}. Bekleyen açıklamalar yeniden hazırlanacak."})
            if act == "send_all":
                return self._send(200, {"msg": SEOJOBS.start("send")})
            if act == "prepare_all":
                return self._send(200, {"msg": SEOJOBS.start("prepare")})
            if act == "repair_all":
                return self._send(200, {"msg": SEOJOBS.start("repair")})
            if act == "repair":
                try:
                    repair_plan(pid)
                    return self._send(200, {"msg": "Onarım planı hazırlandı."})
                except ApiError as e:
                    return self._send(200, {"error": f"Ideasoft hatası: {e}"})
            if act == "jobs_stop":
                SEOJOBS.stop()
                return self._send(200, {"msg": "Durduruluyor; sıradaki ürünler gönderilmeyecek."})
            if act == "toggle_prepare":
                CFG.update(seo_prepare=not CFG.get("seo_prepare", True))
                return self._send(200, {"msg": "Eksiklere açıklama hazırla: " + ("açık" if CFG.get("seo_prepare") else "kapalı")})
            if act == "start":
                return self._send(200, {"msg": SEOSCAN.start()})
            if act == "pause":
                SEOSCAN.pause()
                return self._send(200, {"msg": "Duraklatıldı."})
            if act == "resume":
                SEOSCAN.resume()
                return self._send(200, {"msg": "Devam ediyor."})
            if act == "stop":
                SEOSCAN.stop()
                return self._send(200, {"msg": "Durduruluyor…"})
        if p == "/api/sablon/onizle":   # kaydetmeden: gönderilen (kısmi) şablonla örnek açıklama ve SEO puanı
            t = TPL.yukle(TPL.birlestir(sablon(), self._json().get("sablon")), sablon()["gorunum"])
            return self._send(200, sablon_onizleme(t))
        if p == "/api/sablon/tema_rengi":
            renk = tema_rengi_oner()
            return self._send(200, {"renk": renk} if renk else
                              {"error": "Sitenizde tema rengi bulunamadı; rengi kendiniz seçin."})
        if p == "/api/sablon/gecis/start":
            return self._send(200, {"msg": GECIS.start("gecir")})
        if p == "/api/sablon/gecis/geri":          # geri alma: abonelikten bağımsız
            return self._send(200, {"msg": GECIS.start("geri")})
        if p == "/api/sablon/gecis/stop":
            GECIS.stop()
            return self._send(200, {"msg": "Durduruluyor; sıradaki ürünlere dokunulmayacak."})
        if p == "/api/seo/undo":                   # geri alma: abonelikten bağımsız
            if SEOJOBS.running or GECIS.running:
                return self._send(200, {"error": "Toplu işlem sürüyor; bitmesini bekleyin."})
            state, msg = seo_geri_al(int(q.get("pid") or 0))
            return self._send(200, {"ok": state == "uygulandi", "msg": msg} if state == "uygulandi" else {"error": msg})
        if p == "/api/linkler/start":
            return self._send(200, {"msg": LINKS.start()})
        if p == "/api/linkler/stop":
            LINKS.stop()
            return self._send(200, {"msg": "Durduruluyor; önceki sonuçlar korunacak."})
        if p == "/api/otopilot/ayar":
            msg = OTO.ayarla(self._json())
            return self._send(200, {"error": msg} if msg else {"ok": True, "ayar": oto_ayar()})
        if p == "/api/otopilot/kontrol":
            if OTO.running:
                return self._send(200, {"msg": "Otopilot zaten çalışıyor."})
            spawn(OTO.kontrol)
            return self._send(200, {"msg": "Yeni ürünler kontrol ediliyor."})
        if p == "/api/otopilot/onayla":   # seçilenler ya da onay bekleyen bütün ürünler
            d = self._json()
            return self._send(200, {"msg": OTO.onayla([int(x) for x in d["pids"]] if d.get("pids") else None)})
        if p == "/api/otopilot/yoksay":
            Otopilot._set(int(q.get("pid") or 0), durum="yoksay", msg="Yok sayıldı; otopilot bu ürüne dokunmaz.")
            return self._send(200, {"ok": True})
        if p == "/api/kurulum/bitti":   # sihirbaz tamamlandı ya da geçildi
            CFG.update(kurulum_bitti=True)
            return self._send(200, {"ok": True})
        if p == "/api/overview/scan":   # genel bakıştan tarama: SEO ve kategori analizi (ikisi de sadece okur)
            return self._send(200, {"msg": " ".join(x for x in (SEOSCAN.start(), CATSCAN.start()) if x)})
        if p == "/api/cat/start":
            return self._send(200, {"msg": CATSCAN.start(fetch=q.get("fetch") != "0")})
        if p == "/api/cat/stop":
            CATSCAN.stop()
            return self._send(200, {"msg": "Durduruluyor…"})
        if p in ("/api/cat/apply", "/api/cat/undo"):  # tek ürün, hemen
            if CATJOBS.running:
                return self._send(200, {"error": "Toplu uygulama sürüyor; bitmesini bekleyin."})
            pid, kind = int(q.get("pid") or 0), q.get("kind") or "wrong"
            if p.endswith("undo"):
                state, msg = cat_undo(pid)
            else:
                it = CATSCAN.item(kind, pid)
                if not it:
                    return self._send(200, {"error": "Öneri bulunamadı; yeniden hesaplayın."})
                state, msg = cat_fix(pid, it["add"], it["rem"], it["sug"])
            return self._send(200, {"ok": state == "uygulandi", "msg": msg})
        if p == "/api/cat/apply_many":  # seçilenler ya da listedeki filtreye uyanların hepsi
            d = self._json()
            kind = d.get("kind") if d.get("kind") in ("wrong", "uncat") else "wrong"
            tasks = CATSCAN.tasks(kind, d.get("q") or "", d.get("f") or "", int(d.get("min") or 0),
                                  [int(x) for x in d["pids"]] if d.get("pids") is not None else None)
            return self._send(200, {"msg": CATJOBS.start(tasks, "kategori düzeltme")})
        if p == "/api/cat/jobstop":
            CATJOBS.stop()
            return self._send(200, {"msg": "Durduruluyor; sıradaki ürünlere dokunulmayacak."})
        if p in ("/api/cat/newpreview", "/api/cat/create"):  # alt kategori önerisi: SEO önizlemesi / açma
            g = (CATSCAN.report or {}).get("newcats") or []
            i = int(q.get("i") if q.get("i") is not None else -1)
            d = self._json()
            name = (d.get("name") or "").strip()
            if not 0 <= i < len(g) or g[i]["kind"] != "alt" or not name:
                return self._send(200, {"error": "Öneri ya da kategori adı geçersiz."})
            parent = g[i]["parent_id"]
            if p.endswith("newpreview"):
                rows = DBI.q(f"SELECT name, brand FROM catprod WHERE pid IN ({','.join('?' * len(g[i]['pids']))})", g[i]["pids"])
                seo = KT.category_seo(name, g[i]["parent"], [r["name"] for r in rows], PROFILE(), [r["brand"] for r in rows])
                imgs = category_image_candidates(g[i]["pids"]) if d.get("images") else []
                return self._send(200, {"seo": seo, "images": imgs})
            if CATJOBS.running:
                return self._send(200, {"error": "Başka bir işlem sürüyor; bitmesini bekleyin."})
            if DBI.q("SELECT 1 FROM catnew WHERE key=?", (newcat_key(g[i]),), one=True):
                return self._send(200, {"error": "Bu öneri için kategori zaten açıldı."})
            seo = {k: (d.get(k) or "").strip() for k in ("slug", "pageTitle", "metaDescription", "metaKeywords")}
            task = {"type": "create", "group": g[i], "name": name, "seo": seo, "image": (d.get("image") or "").strip()}
            return self._send(200, {"msg": CATJOBS.start([task], "yeni kategori açma")})
        if p == "/api/cat/create_many":  # seçilen (ya da bekleyen bütün) alt kategori önerilerini toplu aç
            if CATJOBS.running:
                return self._send(200, {"error": "Başka bir işlem sürüyor; bitmesini bekleyin."})
            d = self._json()
            g = (CATSCAN.report or {}).get("newcats") or []
            made = {r["key"] for r in DBI.q("SELECT key FROM catnew")}
            names = {int(k): (v or "").strip() for k, v in (d.get("names") or {}).items()}
            idx = [int(x) for x in d["items"]] if d.get("items") is not None else range(len(g))
            tasks = [{"type": "create", "group": g[i], "name": names.get(i) or g[i]["label"]}
                     for i in idx if 0 <= i < len(g) and g[i]["kind"] == "alt" and newcat_key(g[i]) not in made]
            return self._send(200, {"msg": CATJOBS.start(tasks, "toplu kategori açma") if tasks else "Açılacak öneri yok."})
        if p == "/api/cat/assign":   # öneri yoksa (ya da beğenilmediyse) kategoriyi kullanıcı seçer
            if CATJOBS.running:
                return self._send(200, {"error": "Toplu uygulama sürüyor; bitmesini bekleyin."})
            pid, cid = int(q.get("pid") or 0), int(q.get("cid") or 0)
            if not DBI.q("SELECT 1 FROM cat WHERE id=?", (cid,), one=True):
                return self._send(200, {"error": "Kategori bulunamadı."})
            state, msg = cat_fix(pid, [cid], [], category_paths().get(cid, ""))
            return self._send(200, {"ok": state == "uygulandi", "msg": msg})
        if p == "/api/cat/seocheck":  # önizlemede düzenlenen metnin SEO kontrolü
            d = self._json()
            return self._send(200, KT.category_seo_check(d.get("name") or "", d))
        if p.startswith("/api/img/"):
            act = p.rsplit("/", 1)[1]
            if act == "start":
                return self._send(200, {"msg": IMG.start()})
            if act == "pause":
                IMG.pause()
                return self._send(200, {"msg": "Duraklatıldı."})
            if act == "resume":
                IMG.resume()
                return self._send(200, {"msg": "Devam ediyor."})
            if act == "stop":
                IMG.stop()
                return self._send(200, {"msg": "Durduruluyor…"})
            if act == "reset":
                return self._send(200, {"msg": IMG.reset()})
        if p == "/api/discover":
            return self._send(200, discover(q.get("sku"), q.get("kw")))
        if p == "/api/calibrate":
            return self._send(200, calibrate(int(q.get("n") or 0), q.get("sku")))
        if p == "/api/count_method":
            CFG.update(count_method=",".join(m for m in (q.get("m") or "").split(",") if m in ST.COUNT_METHODS))
            return self._send(200, {"ok": True})
        if p == "/api/disconnect":
            CFG.update(access_token="", refresh_token="", expires_at=0)
            log("Bağlantı kaldırıldı.")
            extra = {"Set-Cookie": clear_cookies()} if SERVER["on"] else None
            return self._send(200, {"ok": True, "login": SERVER["on"]}, extra=extra)
        return self._send(404, {"error": "Yok"})


def page_msg(title, text, ok=False, close=False):
    """close: kapı girişinin açtığı sekme; panele dönmez, kendini kapatmayı dener."""
    col = "#1f8a4c" if ok else "#c0392b"
    if close:
        return f"""<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title>
<body style="font-family:Segoe UI,sans-serif;background:#e8ebee;display:grid;place-items:center;height:100vh;margin:0">
<div style="background:#fff;padding:36px 44px;border-left:8px solid {col};max-width:520px">
<h2 style="margin:0 0 10px">{html.escape(title)}</h2><p style="color:#38424d;line-height:1.5">{html.escape(text)}</p></div>
<script>setTimeout(()=>window.close(),1500)</script></body>"""
    return f"""<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title>
<body style="font-family:Bahnschrift,Segoe UI,sans-serif;background:#e8ebee;display:grid;place-items:center;height:100vh;margin:0">
<div style="background:#fff;padding:36px 44px;border-left:8px solid {col};max-width:520px">
<h2 style="margin:0 0 10px">{html.escape(title)}</h2><p style="color:#38424d;line-height:1.5">{html.escape(text)}</p>
<a href="/" style="color:#0f4d5c">Panele dön</a></div>
{'<script>setTimeout(()=>location.href="/",2500)</script>' if ok else ''}</body>"""


def open_panel(url):
    """Paneli Chrome/Edge uygulama penceresinde, yoksa varsayılan tarayıcıda açar."""
    if os.name == "nt":
        pf = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        cands = [os.path.join(p, r"Google\Chrome\Application\chrome.exe") for p in pf if p]
        cands += [os.path.join(p, r"Microsoft\Edge\Application\msedge.exe") for p in pf if p]
        cands += [shutil.which("chrome") or "", shutil.which("msedge") or ""]
        for exe in cands:
            if exe and os.path.exists(exe):
                try:
                    subprocess.Popen([exe, f"--app={url}", "--window-size=1440,920"])
                    return
                except OSError:
                    pass
    webbrowser.open(url)


def port_busy(port=None):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port or PORT)) == 0


def arg(name, default=""):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def abonelik_komutu():
    """Elle abonelik (yönetici paneli gelene kadar; beta mağazaları ve Ustapazar için):
      python app.py --abonelik magaza.com --paket baslangic --bitis 2027-10-31 [--durum aktif|deneme|iptal|ucretsiz]
      python app.py --abonelikler        bütün mağazaların kaydı
    Sunucuda aynı işler yönetici panelinden (/yonetim) de yapılır."""
    os.makedirs(STORES, exist_ok=True)
    if "--abonelikler" in sys.argv[1:]:
        for tid in sorted(os.listdir(STORES)):
            d = os.path.join(STORES, tid)
            if os.path.isfile(os.path.join(d, AB.FILE)):
                a = AB.gecerli(AB.oku(d))
                print(f"  {tid:40} {a['ad']:16} {a['durum_adi']:16} {a['bitis'] or '-'}")
        return 0
    host = store_host(arg("--abonelik"))
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host):
        print("Mağaza adresini yazın, örn. --abonelik magaza.myideasoft.com")
        return 1
    d = os.path.join(STORES, tenant_id(host))
    yeni = not os.path.isdir(d)
    try:
        AB.yaz(d, paket=arg("--paket") or None, durum=arg("--durum") or "aktif", bitis=arg("--bitis") or None)
    except ValueError as e:
        print(f"Kaydedilmedi: {e}")
        return 1
    a = AB.gecerli(AB.oku(d))
    print(f"{host}: {a['ad']}, {a['durum_adi']}" + (f", bitiş {a['bitis']}" if a["bitis"] else "")
          + (" (mağaza henüz giriş yapmadı; ilk girişte bu kayıt geçerli olur)" if yeni else ""))
    return 0


def main():
    """Yerel kip (baslat.bat): tek kullanıcı, bu bilgisayardaki mağaza, giriş yok.
    Sunucu kipi (python app.py --sunucu [--port 8080] [--host 127.0.0.1]): her mağaza Ideasoft ile giriş yapar,
    verisi data/magazalar altında kendi klasöründe durur. Önüne HTTPS sağlayan bir ters vekil (Caddy vb.) konur.
    Abonelik komutları için abonelik_komutu()."""
    global SRV
    if {"--abonelik", "--abonelikler"} & set(sys.argv[1:]):
        sys.exit(abonelik_komutu())
    if "--yonetici-parola" in sys.argv[1:]:            # yönetici paneli (/yonetim) parolası; düz hâli saklanmaz
        import getpass
        p1 = getpass.getpass("Yeni yönetici parolası: ")
        if p1 != getpass.getpass("Yeniden: "):
            print("Parolalar aynı değil; kaydedilmedi.")
            sys.exit(1)
        try:
            YN.yaz(DATA, p1)
        except ValueError as e:
            print(f"Kaydedilmedi: {e}")
            sys.exit(1)
        print("Yönetici parolası kaydedildi; açık yönetici oturumları kapandı.")
        return
    if "--yedek" in sys.argv[1:]:                      # python app.py --yedek /yedekler [--dongu]
        hedef = arg("--yedek")
        if "--dongu" in sys.argv[1:]:
            YD.dongu(DATA, hedef, sakla=int(arg("--sakla", "14")))
        print(f"Yedek alındı: {YD.yedekle(DATA, hedef, sakla=int(arg('--sakla', '14')))}")
        return
    SERVER["on"] = "--sunucu" in sys.argv[1:]
    port = int(arg("--port", PORT))
    host = arg("--host", "127.0.0.1")
    os.makedirs(STORES, exist_ok=True)
    url = f"http://localhost:{port}/"
    if not SERVER["on"] and port_busy(port):
        print("Program zaten açık; panel tarayıcıda açılıyor.")
        open_panel(url)
        return
    SRV = Config(SERVER_PATH, SERVER_DEFAULT)
    if not SRV.get("secret"):
        SRV.update(secret=secrets.token_hex(32))
    if SERVER["on"]:
        try:
            AB.paketler()
        except (OSError, ValueError) as e:
            print(f"Paket dosyası okunamadı ({AB.PAKET_PATH}): {e}")
            sys.exit(1)
        missing = [k for k in ("client_id", "client_secret", "public_url") if not SRV.get(k)]
        if missing:
            print(f"Uyarı: {SERVER_PATH} içinde eksik: {', '.join(missing)}. Bunlar girilene kadar giriş yapılamaz.")
        n = len([d for d in os.listdir(STORES) if known_tenant(d)])
        print(f"\n  seovisi sunucu kipinde: {host}:{port}  ({n} mağaza)\n")
    else:
        migrate_legacy()
        LOCAL["id"] = local_store()
        _cur.t = tenant(LOCAL["id"])
        log(f"Program açıldı. Panel: {url}")
        _cur.t = None
        threading.Timer(0.8, open_panel, args=(url,)).start()
        print("\n  seovisi çalışıyor. Bu pencereyi kapatırsanız program durur.\n")
    threading.Thread(target=oto_zamanlayici, daemon=True).start()   # mağaza bağlamını kendisi kurar
    srv = ThreadingHTTPServer((host, port), H)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
