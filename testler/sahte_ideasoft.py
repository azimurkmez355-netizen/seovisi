"""Uygulamayı iki uydurma mağazayla, sahte bir Ideasoft'a bağlı çalıştırır. Gerçek Ideasoft'a hiçbir istek gitmez.

Kullanım: python sahte_ideasoft.py <uygulama klasörü> <ihlal dosyası> [uygulama argümanları]
Başka mağazanın anahtarıyla yapılan her istek <ihlal dosyası>na yazılır (mağaza ayrımı testi için)."""
import copy
import os
import random
import sys
import threading
import time

APP_DIR, VIOL = sys.argv[1], sys.argv[2]
sys.argv = [sys.argv[0]] + sys.argv[3:]
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)
import app  # noqa: E402

lock = threading.Lock()


def build(tree, words, prefix, n_each, seed):
    """tree: {id: (ad, üst id)}; words: {kategori id: [ürün adı parçaları]}. Ürünlerin ~%4'ü yanlış kategoriye konur."""
    rnd = random.Random(seed)
    cats = {i: {"id": i, "name": n, "parent": {"id": p} if p else None} for i, (n, p) in tree.items()}
    prods, pid = {}, seed * 10000
    for cid, (adj, nouns) in words.items():
        for _ in range(n_each):
            pid += 1
            put = rnd.choice([c for c in words if c != cid]) if rnd.random() < 0.04 else cid
            prods[pid] = {"id": pid, "name": f"{rnd.choice(adj)} {rnd.choice(nouns)}", "sku": f"{prefix}-{pid}",
                          "status": 1, "categories": [{"id": put}]}
    for _ in range(5):                                   # birkaç kategorisiz ürün
        pid += 1
        cid = rnd.choice(list(words))
        prods[pid] = {"id": pid, "name": f"{rnd.choice(words[cid][0])} {rnd.choice(words[cid][1])}", "sku": f"{prefix}-{pid}",
                      "status": 1, "categories": []}
    fiyat = random.Random(seed + 100)                    # ad ve kategori sırası değişmesin diye ayrı rastgele kaynak
    for p in prods.values():
        cid = (p["categories"] or [{"id": 0}])[0]["id"]
        p.update(price1=round(fiyat.uniform(0.8, 1.2) * (200 + 50 * (cid % 10)), 2), stockAmount=fiyat.randint(1, 20),
                 currency={"id": 1, "abbr": "TL"}, discount=0, discountType=0)
        p["buyingPrice"] = round(p["price1"] * 0.6, 2)
        p["barcode"] = f"869{seed}{p['id']:08d}"
    return cats, prods


def fiyat_hatalari(prods):
    """Uyarı testi için A mağazasında bilerek bırakılan hatalar: fiyatı 0, %100 indirim, 100 kat fiyat,
    alış fiyatının altında satış, stokta yok."""
    p = [prods[i] for i in sorted(prods)[:5]]
    p[0]["price1"] = 0
    p[1].update(discount=100, discountType=1)
    p[2]["price1"] *= 100
    p[3]["buyingPrice"] = p[3]["price1"] * 2
    p[4]["stockAmount"] = 0
    return prods


def kopya_hatalari(prods):
    """Kopya testi için A mağazasında: iki ürün aynı stok kodu, iki ürün aynı barkod. (Uydurma adlar zaten tekrarlıdır.)"""
    p = [prods[i] for i in sorted(prods)[5:9]]
    p[1]["sku"] = p[0]["sku"]
    p[3]["barcode"] = p[2]["barcode"]
    return prods


def hirdavat():
    tree = {1: ("Elektrikli El Aletleri", None), 2: ("El Aletleri", None),
            11: ("Matkaplar", 1), 12: ("Vidalama Makineleri", 1), 13: ("Taşlama Makineleri", 1),
            21: ("Pense ve Kerpetenler", 2), 22: ("Tornavidalar", 2), 23: ("Çekiçler", 2)}
    brands = ["Bosch", "Makita", "Dewalt", "Einhell", "Stanley"]
    words = {11: (brands, ["Darbeli Matkap 750W", "Kırıcı Delici Matkap", "Sds Plus Matkap 800W"]),
             12: (brands, ["Akülü Vidalama 12V", "Şarjlı Vidalama 18V", "Darbeli Somun Sıkma"]),
             13: (brands, ["Avuç Taşlama 125mm", "Büyük Taşlama 230mm", "Spiral Taşlama 115mm"]),
             21: (brands, ["Kombine Pense", "Yan Keski", "Kargaburun Pense"]),
             22: (brands, ["Düz Tornavida Seti", "Yıldız Tornavida", "Lokma Tornavida Takımı"]),
             23: (brands, ["Marangoz Çekici", "Lastik Çekiç", "Balyoz 2 Kg"])}
    return build(tree, words, "HR", 70, 1)


def giyim():
    tree = {1: ("Kadın", None), 2: ("Erkek", None), 11: ("Elbiseler", 1), 12: ("Bluzlar", 1), 13: ("Etekler", 1),
            21: ("Gömlekler", 2), 22: ("Pantolonlar", 2), 23: ("Tişörtler", 2)}
    kadin = ["Kadın Siyah", "Kadın Bej", "Kadın Kırmızı", "Kadın Lacivert"]
    erkek = ["Erkek Beyaz", "Erkek Haki", "Erkek Gri", "Erkek Lacivert"]
    words = {11: (kadin, ["Midi Elbise", "Abiye Elbise", "Saten Elbise"]), 12: (kadin, ["Saten Bluz", "Krep Bluz"]),
             13: (kadin, ["Pileli Etek", "Kalem Etek"]), 21: (erkek, ["Slim Fit Gömlek", "Oxford Gömlek"]),
             22: (erkek, ["Kumaş Pantolon", "Chino Pantolon"]), 23: (erkek, ["Basic Tişört", "Polo Yaka Tişört"])}
    return build(tree, words, "MD", 45, 2)


STORES = {"a-magaza.com": hirdavat(), "b-moda.com": giyim()}
fiyat_hatalari(STORES["a-magaza.com"][1])
kopya_hatalari(STORES["a-magaza.com"][1])


def fake_call(self, method, path, params=None, body=None, tries=6):
    host = app.store_host(app.CFG.get("store"))
    if app.CFG.get("access_token") != "tok-" + host:
        with lock, open(VIOL, "a", encoding="utf-8") as f:
            f.write(f"{host} {app.CFG.get('access_token')} {method} {path}\n")
    cats, prods = STORES[host]
    self.req_times.append(time.time())
    params = params or {}
    parts = path.strip("/").split("/")
    lim = int(params.get("limit", 100))
    if method == "GET" and parts == ["categories"]:
        rows = sorted(cats.values(), key=lambda c: c["id"])
        pg = int(params.get("page", 1))
        return copy.deepcopy(rows[(pg - 1) * lim: pg * lim])
    if method == "GET" and parts == ["products"]:
        since = int(params.get("sinceId", 0))
        return copy.deepcopy([p for _, p in sorted(prods.items()) if p["id"] > since][:lim])
    if method == "GET" and parts == ["products", "count"]:
        return {"total": len(prods)}
    if method == "GET" and parts[0] == "products" and len(parts) == 2 and parts[1].isdigit() and int(parts[1]) in prods:
        return copy.deepcopy(prods[int(parts[1])])
    det = DETAILS.setdefault(host, {})
    if method == "GET" and parts == ["products"] and params.get("ids"):
        return [dict(copy.deepcopy(prods[int(params["ids"])]), solvedCount=13, seoTotalRuleCount=13)]
    if method == "PUT" and parts[0] == "products" and len(parts) == 2:
        with lock:
            prods[int(parts[1])].update(copy.deepcopy({k: v for k, v in body.items() if k != "id"}))
        return copy.deepcopy(prods[int(parts[1])])
    if method == "GET" and parts == ["product_details"]:
        return copy.deepcopy([d for d in det.values() if d["product"]["id"] == int(params.get("product", 0))])
    if method == "POST" and parts == ["product_details"]:
        with lock:
            d = dict(copy.deepcopy(body), id=len(det) + 1)
            det[d["id"]] = d
            prods[body["product"]["id"]]["detail"] = {"id": d["id"]}
        return copy.deepcopy(d)
    if parts[0] == "product_details" and len(parts) == 2 and int(parts[1]) in det:
        if method == "PUT":
            with lock:
                det[int(parts[1])].update(copy.deepcopy(body))
        return copy.deepcopy(det[int(parts[1])])
    raise app.ApiError(404, f"sahte api: {method} {path}")


DETAILS = {}                                             # mağaza -> ürün açıklamaları (product_details)


_route_public = app.H.route_public


def route_public(self, method, p, q):
    """Yalnızca testler için: POST /__test/urun {store, name, cats} mağazaya (sahte) yeni ürün ekler."""
    if p == "/__test/urun" and method == "POST":
        d = self._json()
        _, prods = STORES[d["store"]]
        pid = max(prods) + 1
        with lock:
            prods[pid] = {"id": pid, "name": d["name"], "sku": f"YN-{pid}", "status": 1,
                          "categories": [{"id": c} for c in d.get("cats") or []]}
        self._send(200, {"pid": pid})
        return True
    return _route_public(self, method, p, q)


# A mağazasının herkese açık sitesi (kırık bağlantı taraması için): bir kırık sayfa bağlantısı, bir kırık görsel
SITE = {
    "https://a-magaza.com/": (200, "text/html", '<a href="/matkaplar">Matkaplar</a> <a href="/eski-kampanya">Kampanya</a>'
                                                '<img src="/resim/logo.png"><img src="/resim/silinen.jpg">'),
    "https://a-magaza.com/matkaplar": (200, "text/html", '<a href="/bosch-matkap">Bosch</a><a href="/">Ana sayfa</a>'),
    "https://a-magaza.com/bosch-matkap": (200, "text/html", '<a href="/eski-kampanya">Kampanya</a>'),
    "https://a-magaza.com/resim/logo.png": (200, "image/png", ""),
}


def sahte_getirici():
    def getir(url, govde=True):
        st, ct, txt = SITE.get(url, (404, "text/html", ""))
        return st, ct, txt if govde else "", url
    return getir


app.Ideasoft.call = fake_call
app.site_getirici = sahte_getirici
app.LINK_BEKLE = 0
app.H.route_public = route_public
app.OTO_BEKLE_DK = 0                     # testte yeni ürün beklemeden işlenir
app.public_host = lambda h: h in STORES
app.token_request = lambda host, data: {"access_token": "tok-" + host, "refresh_token": "r-" + host, "expires_in": 3600}
app.open_panel = lambda u: None
app.main()
