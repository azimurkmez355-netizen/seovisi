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
    return cats, prods


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
    raise app.ApiError(404, f"sahte api: {method} {path}")


app.Ideasoft.call = fake_call
app.public_host = lambda h: h in STORES
app.token_request = lambda host, data: {"access_token": "tok-" + host, "refresh_token": "r-" + host, "expires_in": 3600}
app.open_panel = lambda u: None
app.main()
