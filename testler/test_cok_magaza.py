"""Çok mağaza testi: sunucu kipinde iki mağaza (giriş, oturum, ayrım, eşzamanlı analiz), yerel kipte eski kurulumun taşınması.
Uygulamanın geçici bir kopyasını sahte Ideasoft ile çalıştırır; projenin data klasörüne ve gerçek mağazaya dokunmaz.

Çalıştırma: python -X utf8 testler/test_cok_magaza.py"""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="seovisi-test-")
VIOL = os.path.join(TMP, "ihlal.txt")
OK, BAD = [], []


def check(name, cond, info=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  ->  {info}"))


def copy_app(dst):
    os.makedirs(os.path.join(dst, "data"))
    for f in os.listdir(SRC):
        if f.endswith((".py", ".json")):
            shutil.copy(os.path.join(SRC, f), dst)
    shutil.copytree(os.path.join(SRC, "ui"), os.path.join(dst, "ui"))


def req(port, method, path, body=None, cookie=None, form=False, headers=None, panel=True):
    """panel: istek panelin kendi JS'inden geliyormuş gibi X-Seovisi başlığını taşır."""
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    h = dict({"Cookie": cookie} if cookie else {}, **({"X-Seovisi": "1"} if panel else {}), **(headers or {}))
    if body is not None:
        body = urllib.parse.urlencode(body) if form else json.dumps(body)
        h["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    raw = r.read().decode("utf-8", "replace")
    try:
        data = json.loads(raw)
    except ValueError:
        data = raw
    return r.status, dict(r.getheaders()), data


def start(appdir, *args):
    log = open(os.path.join(TMP, f"{os.path.basename(appdir)}.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-X", "utf8", os.path.join(HERE, "sahte_ideasoft.py"), appdir, VIOL, *args],
                         stdout=log, stderr=log)
    port = int(args[args.index("--port") + 1])
    for _ in range(50):
        try:
            req(port, "GET", "/favicon.ico")
            return p
        except OSError:
            time.sleep(0.2)
    p.terminate()
    raise SystemExit(f"Uygulama açılmadı; kayıt: {log.name}")


def login(port, store):
    st, h, _ = req(port, "POST", "/giris", {"store": store}, form=True)
    loc = h.get("Location", "")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(loc).query))
    st2, h2, page = req(port, "GET", f"/callback?code=kod&state={q.get('state', '')}")
    return st, loc, q, st2, h2.get("Set-Cookie", "").split(";")[0]


def wait_cat(port, cookie):
    for _ in range(300):
        s = req(port, "GET", "/api/cat/state", cookie=cookie)[2]
        if not s.get("running"):
            return s
        time.sleep(0.3)


def sunucu_kipi():
    print("Sunucu kipi")
    A = os.path.join(TMP, "sunucu")
    copy_app(A)
    with open(os.path.join(A, "data", "sunucu.json"), "w", encoding="utf-8") as f:
        json.dump({"client_id": "cid", "client_secret": "sec", "public_url": "http://localhost:8770",
                   "kw_loc": {"res": "product", "path": "targetKeyword"}}, f)
    proc = start(A, "--sunucu", "--port", "8770")
    try:
        st, _, page = req(8770, "GET", "/")
        check("oturumsuz ana sayfa giriş sayfasını gösterir", st == 200 and "Mağazanızla giriş yapın" in page)
        st, _, j = req(8770, "GET", "/api/state")
        check("oturumsuz API 401 döner", st == 401 and j.get("login"), (st, j))
        st, _, page = req(8770, "POST", "/giris", {"store": "localhost"}, form=True)
        check("geçersiz adres reddedilir", "Bu adres bulunamadı" in page)

        st, loc, q, st2, ca = login(8770, "https://A-Magaza.com/panel")
        check("giriş Ideasoft izin sayfasına yönlendirir", st == 302 and loc.startswith("https://a-magaza.com/panel/auth?"), loc)
        check("izin isteği sunucunun anahtarı ve dönüş adresini taşır",
              q.get("client_id") == "cid" and q.get("redirect_uri") == "http://localhost:8770/callback", q)
        check("dönüşte oturum çerezi verilir", st2 == 200 and ca.startswith("sv=") and len(ca) > 20, (st2, ca))
        st, _, _ = req(8770, "GET", f"/callback?code=kod&state={q['state']}")
        check("aynı state ikinci kez kullanılamaz", st == 400, st)
        cb = login(8770, "b-moda.com")[4]

        sa = req(8770, "GET", "/api/state", cookie=ca)[2]
        sb = req(8770, "GET", "/api/state", cookie=cb)[2]
        check("A çerezi A mağazasını açar", sa["cfg"]["store"] == "a-magaza.com" and sa["mode"] == "sunucu")
        check("B çerezi B mağazasını açar", sb["cfg"]["store"] == "b-moda.com")
        check("API anahtarları panele gönderilmez", "access_token" not in sa["cfg"] and "client_secret" not in sa["cfg"])

        _, exp, sig = ca[3:].rsplit(".", 2)
        st, _, _ = req(8770, "GET", "/api/state", cookie=f"sv=b-moda-com.{exp}.{sig}")
        check("imzası tutmayan çerez reddedilir", st == 401, st)
        st, _, _ = req(8770, "GET", "/api/state", cookie=f"sv=../../data.{exp}.{sig}")
        check("klasör adı oyunu reddedilir", st == 401, st)

        req(8770, "POST", "/api/cat/start", {}, cookie=ca)
        req(8770, "POST", "/api/cat/start", {}, cookie=cb)
        ra, rb = wait_cat(8770, ca), wait_cat(8770, cb)
        check("iki mağazanın analizi aynı anda çalışır ve ayrı kalır", ra["stored"] == 425 and rb["stored"] == 275,
              (ra.get("stored"), rb.get("stored"), ra.get("note"), rb.get("note")))
        sa_, sb_ = ra.get("summary") or {}, rb.get("summary") or {}
        # yanlış yere konan ürünler emin olunan yerde "taşı", emin olunmayan yerde "şüpheli" olarak işaretlenir
        found = [s.get("tasi", 0) + s.get("supheli", 0) for s in (sa_, sb_)]
        check("analiz yanlış kategorideki ürünleri bulur", all(found), (sa_, sb_))
        check("kategorisiz ürünler sayılır", sa_.get("kategorisiz") == 5 and sb_.get("kategorisiz") == 5, (sa_, sb_))

        req(8770, "POST", "/api/settings", {"store": "c-baska.com", "profil": {"magaza": "Moda Evi"}}, cookie=cb)
        sb = req(8770, "GET", "/api/state", cookie=cb)[2]
        check("sunucuda mağaza adresi panelden değiştirilemez", sb["cfg"]["store"] == "b-moda.com", sb["cfg"]["store"])
        check("profil kaydedilir", sb["cfg"]["profil"]["magaza"] == "Moda Evi")
        la = " ".join(x["m"] for x in req(8770, "GET", "/api/state", cookie=ca)[2]["log"])
        check("kayıtlar mağazaya özel", "Ayarlar kaydedildi" not in la and "Kategori analizi" in la, la[-300:])
        check("her mağazanın klasörü ayrı",
              sorted(os.listdir(os.path.join(A, "data", "magazalar"))) == ["a-magaza-com", "b-moda-com"])
        disk = "".join(open(os.path.join(A, "data", *p), encoding="utf-8").read() for p in (
            ("magazalar", "a-magaza-com", "ayarlar.json"), ("magazalar", "b-moda-com", "ayarlar.json"), ("sunucu.json",)))
        check("erişim anahtarları ve client secret diskte şifreli",
              not any(s in disk for s in ("tok-a-magaza.com", "r-b-moda.com", '"sec"')) and "sifreli:v1:" in disk)
        uyarilar(8770, ca, cb)
        linkler(8770, ca)

        st, h, j = req(8770, "POST", "/api/disconnect", {}, cookie=cb)
        check("bağlantıyı kaldırınca oturum da kapanır", j.get("login") and "Max-Age=0" in h.get("Set-Cookie", ""))
        st, h, _ = req(8770, "GET", "/cikis", cookie=ca)
        check("çıkış çerezi siler", st == 302 and "Max-Age=0" in h.get("Set-Cookie", ""))
        kurulum(8770, ca)       # ilk girişte (henüz taranmamışken) açılan sihirbaz, tarama bitse de sürer
        abonelik(8770, A, ca, cb_state=lambda: req(8770, "GET", "/api/state", cookie=login(8770, "b-moda.com")[4])[2])
        otopilot(8770, A, ca)
        kapi(8770)
        guvenlik(8770, ca)
    finally:
        proc.terminate()
        proc.wait()
    viol = open(VIOL, encoding="utf-8").read() if os.path.exists(VIOL) else ""
    check("hiçbir istek başka mağazanın anahtarıyla gitmedi", not viol, viol[:300])


def raw_post(port, path, length, cookie=""):
    """Gövdesini göndermeden büyük bir Content-Length bildirir; sunucunun okumadan reddetmesi beklenir."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nX-Seovisi: 1\r\n"
                  f"Content-Length: {length}\r\n"
                  f"{'Cookie: ' + cookie + chr(13) + chr(10) if cookie else ''}\r\n".encode())
        return s.recv(4096).decode("utf-8", "replace").split(" ", 2)[1]


def kurulum(port, ca):
    s = req(port, "GET", "/api/state", cookie=ca)[2]
    check("yeni mağazaya kurulum sihirbazı açılır", s["kurulum"] is True, s.get("kurulum"))
    check("hedef kelime yeri sunucudaki varsayılandan gelir (keşif gerekmez)",
          req(port, "GET", "/api/seo/state", cookie=ca)[2].get("has_loc") is True)
    on = lambda t: req(port, "POST", "/api/sablon/onizle", {"sablon": t}, cookie=ca)[2]
    sade, bantli = on({"gorunum": "sade"}), on({"gorunum": "bantli", "renk": "#c0392b"})
    check("şablon önizlemesi görünümü, rengi ve SEO puanını gösterir",
          "Termos" in sade["html"] and "c0392b" not in sade["html"] and "c0392b" in bantli["html"]
          and sade["puan"] == 100 and bantli["puan"] == 100, (sade.get("puan"), bantli.get("puan")))
    g0 = req(port, "GET", "/api/sablon", cookie=ca)[2]
    check("şablon ekranı seçenekleri ve kayıtlı şablonu alır",
          set(g0["secenekler"]["gorunumler"]) == {"sade", "bantli", "cizgili", "kutulu"} and g0["sablon"]["gorunum"] == "sade")
    req(port, "POST", "/api/settings", {"sablon": {"gorunum": "<script>", "renk": "kırmızı"}}, cookie=ca)
    g1 = req(port, "GET", "/api/sablon", cookie=ca)[2]["sablon"]
    req(port, "POST", "/api/settings", {"sablon": {"gorunum": "cizgili", "renk": "#C0392B"}}, cookie=ca)
    req(port, "POST", "/api/settings", {"sablon": {"madde": "•"}}, cookie=ca)       # kısmi değişiklik diğerlerini korur
    g2 = req(port, "GET", "/api/sablon", cookie=ca)[2]["sablon"]
    check("şablon kaydedilir, geçersiz değerler düzeltilir, kısmi değişiklik korunur",
          g1["gorunum"] == "sade" and g1["renk"] == "#1b4f72"
          and (g2["gorunum"], g2["renk"], g2["madde"]) == ("cizgili", "#c0392b", "•"), (g1, g2))
    req(port, "POST", "/api/settings", {"sablon": {"gorunum": "sade"}}, cookie=ca)
    req(port, "POST", "/api/kurulum/bitti", {}, cookie=ca)
    check("sihirbaz bitince bir daha açılmaz", req(port, "GET", "/api/state", cookie=ca)[2]["kurulum"] is False)


def abonelik(port, appdir, ca, cb_state):
    sys.path.insert(0, SRC)
    from app import WRITE_ROUTES

    def komut(*a):
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(appdir, "app.py"), *a], cwd=appdir,
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout

    ab = req(port, "GET", "/api/state", cookie=ca)[2]["abonelik"]
    check("yeni mağaza ücretsiz analizle başlar", ab["paket"] == "ucretsiz" and "Ücretsiz analiz" in (ab["uyari"] or ""), ab)
    blocked = {p: req(port, "POST", p, {}, cookie=ca)[2] for p in WRITE_ROUTES}
    check("ücretsiz analizde mağazaya yazan her yol kapalı", all(j.get("abonelik") for j in blocked.values()),
          [p for p, j in blocked.items() if not j.get("abonelik")])
    j = req(port, "POST", "/api/cat/undo?pid=1", {}, cookie=ca)[2]
    check("geri alma abonelikten bağımsız açık", not j.get("abonelik") and "geri alınacak" in j.get("msg", ""), j)

    code, out = komut("--abonelik", "a-magaza.com", "--paket", "baslangic", "--bitis", "2099-12-31")
    check("komutla abonelik açılır", code == 0 and "Başlangıç, Aktif" in out, out)
    ab = req(port, "GET", "/api/state", cookie=ca)[2]["abonelik"]
    check("abonelik sunucu yeniden başlatılmadan geçerli olur",
          ab["paket"] == "baslangic" and ab["durum"] == "aktif" and not ab["uyari"] and ab["urun_sayisi"] == 425, ab)
    j = req(port, "POST", "/api/cat/assign?pid=1&cid=999999", {}, cookie=ca)[2]
    check("aktif abonelikte yazma yolu açık", not j.get("abonelik") and j.get("error") == "Kategori bulunamadı.", j)
    check("başka mağazanın aboneliği değişmez", cb_state()["abonelik"]["paket"] == "ucretsiz")

    path = os.path.join(appdir, "paketler.json")
    with open(path, encoding="utf-8") as f:
        pk = json.load(f)
    pk["paketler"]["baslangic"]["urun"] = 100
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pk, f)
    os.utime(path, (time.time() + 5, time.time() + 5))
    j = req(port, "POST", "/api/cat/assign?pid=1&cid=999999", {}, cookie=ca)[2]
    check("ürün sınırı aşılınca yazılamaz (paket dosyası değişince hemen)", j.get("abonelik") and "425 ürün" in j["error"], j)

    code, out = komut("--abonelik", "a-magaza.com", "--paket", "yok")
    check("geçersiz paket komutla yazılmaz", code == 1 and "Kaydedilmedi" in out, out)
    code, out = komut("--abonelikler")
    check("abonelikler listelenir", code == 0 and "a-magaza-com" in out and "b-moda-com" in out, out)


def uyarilar(port, ca, cb):
    """SEO taraması fiyat ve stok bilgilerini de kaydeder; uyarılar bunlardan hesaplanır, mağazaya yazılmaz."""
    for c in (ca, cb):
        req(port, "POST", "/api/seo/start", {}, cookie=c)
    for c in (ca, cb):
        for _ in range(150):
            if not req(port, "GET", "/api/seo/state", cookie=c)[2].get("running"):
                break
            time.sleep(0.2)
    a = req(port, "GET", "/api/uyarilar", cookie=ca)[2]
    check("uyarılar bırakılan beş hatayı bulur", a["taranan"] == 425 and a["sayilar"] == {
        "fiyat_yok": 1, "indirim": 1, "uc_fiyat": 1, "zarar": 1, "stok_yok": 1}, (a.get("taranan"), a.get("sayilar")))
    check("uyarı satırı açıklama ve panel bağlantısı taşır",
          all(x["mesaj"] and x["sku"] for x in a["items"]) and a["panel"] == "https://a-magaza.com", a["items"][:1])
    f = req(port, "GET", "/api/uyarilar?tur=fiyat", cookie=ca)[2]
    check("uyarılar gruba göre süzülür", f["toplam"] == 4 and all(x["grup"] == "fiyat" for x in f["items"]), f.get("toplam"))
    b = req(port, "GET", "/api/uyarilar", cookie=cb)[2]
    check("temiz mağazada uyarı yok, mağazalar ayrı", b["taranan"] == 275 and b["sayilar"] == {}, b.get("sayilar"))
    c = req(port, "GET", "/api/overview", cookie=ca)[2]["counts"]
    check("genel bakış uyarı sayılarını gösterir", (c["uyari_fiyat"], c["uyari_satilamaz"]) == (4, 1), c)
    ka, kb = (req(port, "GET", "/api/kopyalar", cookie=x)[2] for x in (ca, cb))
    check("kopya: aynı stok kodu ve barkod bulunur", ka["sayilar"].get("ayni_sku") == 1 and ka["sayilar"].get("ayni_barkod") == 1
          and ka["sayilar"].get("ayni_ad", 0) > 0, ka.get("sayilar"))
    check("kopya grubu ürünleri ve panel bağlantısını taşır",
          all(len(g["urunler"]) >= 2 and g["mesaj"] for g in ka["gruplar"]) and ka["panel"] == "https://a-magaza.com")
    check("kopya: diğer mağazada stok kodu / barkod kopyası yok, mağazalar ayrı",
          not kb["sayilar"].get("ayni_sku") and not kb["sayilar"].get("ayni_barkod"), kb.get("sayilar"))
    check("genel bakış kopya grubu sayısını gösterir", c["kopya"] == ka["toplam"] > 0, (c["kopya"], ka["toplam"]))


def linkler(port, ca):
    """Kırık bağlantı taraması: mağazanın (sahte) sitesini gezer, kırık sayfa ve görseli bulduğu sayfalarla bildirir."""
    j = req(port, "POST", "/api/linkler/start", {}, cookie=ca)[2]
    check("bağlantı taraması başlar", "başladı" in j.get("msg", ""), j)
    for _ in range(100):
        r = req(port, "GET", "/api/linkler", cookie=ca)[2]
        if not r["tarama"]["running"]:
            break
        time.sleep(0.1)
    check("kırık sayfa bağlantısı ve görsel bulunur", r["sayilar"] == {"sayfa": 1, "gorsel": 1}
          and r["tarama"]["son"]["sayfa"] == 4, (r.get("sayilar"), r["tarama"]))
    k = next((x for x in r["items"] if x["tur"] == "sayfa"), {})
    check("kırık bağlantının bulunduğu sayfalar ve metni bildirilir",
          k.get("url") == "https://a-magaza.com/eski-kampanya" and k.get("durum") == 404
          and {x["sayfa"] for x in k.get("kaynaklar", [])} == {"https://a-magaza.com/", "https://a-magaza.com/bosch-matkap"}
          and k["kaynaklar"][0]["metin"] == "Kampanya", k)
    check("genel bakış kırık bağlantı sayısını gösterir", req(port, "GET", "/api/overview", cookie=ca)[2]["counts"]["kirik"] == 2)


def otopilot(port, appdir, ca):
    """Otopilot HTTP üzerinden: ücretsizde açılmaz; abonelikle açılır, yalnızca açıldıktan sonra eklenen ürünü hazırlar,
    onaylı kipte mağazaya yazmaz. (Abonelik testi mağazayı Başlangıç'a geçirdi; ürün sınırı orada 100'e düşürüldü.)"""
    j = req(port, "GET", "/api/otopilot", cookie=ca)[2]
    check("otopilot başta kapalı ve ayarları gelir", j["ayar"]["acik"] is False and j["items"] == [], j.get("ayar"))
    once = req(port, "POST", "/__test/urun", {"store": "a-magaza.com", "name": "Bosch Darbeli Matkap 900W"})[2]["pid"]
    j = req(port, "POST", "/api/otopilot/ayar", {"acik": True}, cookie=ca)[2]
    check("otopilot ürün sınırı aşılan pakette açılmaz", "error" in j and "ürün" in j["error"], j)
    subprocess.run([sys.executable, "-X", "utf8", os.path.join(appdir, "app.py"), "--abonelik", "a-magaza.com",
                    "--paket", "sinirsiz"], cwd=appdir, capture_output=True)
    j = req(port, "POST", "/api/otopilot/ayar", {"acik": True}, cookie=ca)[2]
    check("abonelikle otopilot açılır", j.get("ok") and j["ayar"]["acik"] and j["ayar"]["mod"] == "onay", j)
    yeni = req(port, "POST", "/__test/urun", {"store": "a-magaza.com", "name": "Makita Darbeli Matkap 650W"})[2]["pid"]
    req(port, "POST", "/api/otopilot/kontrol", {}, cookie=ca)
    for _ in range(100):
        j = req(port, "GET", "/api/otopilot", cookie=ca)[2]
        if not j["running"] and j["items"] and j["items"][0]["durum"] != "bekliyor":
            break
        time.sleep(0.2)
    pids = {r["pid"]: r for r in j["items"]}
    check("açılmadan önce eklenen ürüne dokunulmaz, sonra ekleneni bulur", once not in pids and yeni in pids, list(pids))
    r = pids.get(yeni, {})
    check("yeni ürünün SEO'su ve kategori önerisi hazırlanır, onaya kalır",
          (r.get("durum"), r.get("seo"), r.get("kat")) == ("onay", "hazir", "oneri") and "Matkap" in (r.get("kat_sug") or ""), r)
    check("panelde onay bekleyen sayısı görünür", req(port, "GET", "/api/state", cookie=ca)[2]["oto_onay"] == 1)
    st, _, _ = req(port, "POST", "/api/otopilot/ayar", {"acik": False}, cookie=ca)
    check("otopilot kapatılır", req(port, "GET", "/api/otopilot", cookie=ca)[2]["ayar"]["acik"] is False)


def kapi(port):
    """Çerçeve içinden giriş: giriş yeni sekmede yapılır, çerçeve tek kullanımlık kodla oturumunu alır."""
    code = "K" * 10 + "abcdefghij-_12"
    al = lambda c=code, **kw: req(port, "POST", "/kapi/al", {"kapi": c}, **kw)
    st, h, _ = req(port, "POST", "/giris", {"store": "a-magaza.com", "kapi": code}, form=True)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(h.get("Location", "")).query))
    check("kapı kodu giriş bitmeden oturum vermez", al()[2] == {"bekle": True}, al()[2])
    st, _, page = req(port, "GET", f"/callback?code=kod&state={q.get('state', '')}")
    check("yeni sekmedeki giriş kendini kapatmayı önerir", st == 200 and "Bu sekmeyi kapatıp" in page)
    st, h, _ = al(headers={"X-Forwarded-For": "203.0.113.50"})
    check("kapı kodu başka internet adresine verilmez", st == 404, st)
    st, h, j = al()
    ck = h.get("Set-Cookie", "").split(";")[0]
    check("kapı kodu çerçeveye oturum verir", st == 200 and j.get("ok") and ck.startswith("sv="), (st, j))
    s = req(port, "GET", "/api/state", cookie=ck)[2]
    check("çerçeve oturumu doğru mağazayı açar", s.get("cfg", {}).get("store") == "a-magaza.com")
    check("kapı kodu ikinci kez kullanılamaz", al()[0] == 404)
    st, _, _ = req(port, "POST", "/giris", {"store": "a-magaza.com", "kapi": code}, form=True)
    check("kullanılmış kod yeniden açılamaz", al()[0] == 404)
    check("kısa / bozuk kod kabul edilmez", al("kisa")[0] == 404)
    st, _, j = req(port, "POST", "/api/settings", {"profil": {"magaza": "Saldırgan"}}, cookie=ck, panel=False)
    check("panel işareti olmayan istek reddedilir (başka siteden sahte istek)", st == 403, (st, j))
    st, _, _ = req(port, "POST", "/kapi/al", {"kapi": code}, panel=False)
    check("kapı kodu da yalnızca panelden alınır", st == 403, st)


def guvenlik(port, cookie):
    _, h, _ = req(port, "GET", "/api/state", cookie=cookie)
    csp = h.get("Content-Security-Policy", "")
    fa = csp.split("frame-ancestors", 1)[-1]
    check("panel yalnızca mağazanın ve Ideasoft'un sayfalarında çerçevede açılır",
          "https://a-magaza.com" in fa and "https://*.myideasoft.com" in fa and "https:;" not in fa + ";"
          and "https://b-moda.com" not in fa, csp)
    check("güvenlik başlıkları gönderilir", h.get("X-Content-Type-Options") == "nosniff"
          and h.get("Referrer-Policy") == "same-origin" and "object-src 'none'" in csp, h)
    _, h, _ = req(port, "GET", "/")
    check("giriş sayfası Ideasoft panelinde açılabilir", h.get("Content-Security-Policy", "").endswith("frame-ancestors 'self' https:"))
    check("çok büyük istek okunmadan reddedilir", raw_post(port, "/api/settings", 50 * 1024 * 1024, cookie) == "413")
    check("bozuk boyut bilgisi reddedilir", raw_post(port, "/giris", "-5") == "413")
    st, _, _ = req(port, "POST", "/api/settings", {"profil": {"magaza": "x" * 1000}}, cookie=cookie)
    check("normal boyuttaki istek çalışır", st == 200, st)
    codes = [req(port, "POST", "/giris", {"store": "localhost"}, form=True)[0] for _ in range(25)]
    st, h, page = req(port, "POST", "/giris", {"store": "localhost"}, form=True)
    check("art arda giriş denemesi engellenir", 429 in codes and st == 429 and "Çok fazla deneme" in page
          and int(h.get("Retry-After", 0)) > 0, codes)
    st, _, _ = req(port, "POST", "/giris", {"store": "localhost"}, form=True, headers={"X-Forwarded-For": "203.0.113.9"})
    check("engel yalnızca o adrese uygulanır (ters vekil arkasında)", st == 200, st)


def yerel_kip():
    print("Yerel kip (eski kurulumun taşınması)")
    L = os.path.join(TMP, "yerel")
    copy_app(L)
    with open(os.path.join(L, "data", "ayarlar.json"), "w", encoding="utf-8") as f:
        json.dump({"store": "https://a-magaza.com/", "client_id": "kendi", "client_secret": "gizli",
                   "access_token": "tok-a-magaza.com", "refresh_token": "r", "expires_at": time.time() + 9999,
                   "profil": {"magaza": "Deneme Hırdavat"}}, f)
    with open(os.path.join(L, "data", "islem.log"), "w", encoding="utf-8") as f:
        f.write("eski kayıt\n")
    proc = start(L, "--port", "8771")
    try:
        dest = os.path.join(L, "data", "magazalar", "a-magaza-com")
        check("eski dosyalar mağaza klasörüne taşındı",
              os.path.isfile(os.path.join(dest, "ayarlar.json")) and os.path.isfile(os.path.join(dest, "islem.log"))
              and not os.path.exists(os.path.join(L, "data", "ayarlar.json")), os.listdir(os.path.join(L, "data")))
        disk = open(os.path.join(dest, "ayarlar.json"), encoding="utf-8").read()
        check("eski kurulumdaki düz metin anahtarlar şifrelendi",
              "tok-a-magaza.com" not in disk and '"gizli"' not in disk and "sifreli:v1:" in disk)
        st, _, s = req(8771, "GET", "/api/state")
        check("yerel kipte giriş istenmez, eski ayarlar korunur",
              st == 200 and s["mode"] == "yerel" and s["cfg"]["profil"]["magaza"] == "Deneme Hırdavat" and s["cfg"]["connected"])
        st, _, j = req(8771, "GET", "/api/connect")
        check("yerel kipte kendi API anahtarıyla bağlanılır", "client_id=kendi" in j.get("url", ""), j)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(j["url"]).query))
        st, _, page = req(8771, "GET", f"/callback?code=kod&state={q['state']}")
        check("yerel bağlantı dönüşü çalışır", st == 200 and "Bağlantı tamam" in page, (st, str(page)[:200]))
        req(8771, "POST", "/api/cat/start", {})
        s = wait_cat(8771, None)
        check("yerel kipte analiz çalışır", s["stored"] == 425, s.get("stored"))
        st, _, _ = req(8771, "POST", "/giris", {"store": "b-moda.com"}, form=True)
        check("yerel kipte giriş yolu kapalı", st == 404, st)
        s = req(8771, "GET", "/api/state")[2]
        j = req(8771, "POST", "/api/cat/assign?pid=1&cid=999999", {})[2]
        check("yerel kipte abonelik sınırı yok", s["abonelik"] is None and not j.get("abonelik"), (s.get("abonelik"), j))
        check("yerel kipte (Ustapazar) kurulum sihirbazı açılmaz", s["kurulum"] is False)
        st, _, _ = req(8771, "POST", "/api/disconnect", {}, panel=False)
        check("yerel kipte de başka siteden sahte istek reddedilir", st == 403 and
              req(8771, "GET", "/api/state")[2]["cfg"]["connected"], st)
    finally:
        proc.terminate()
        proc.wait()


try:
    sunucu_kipi()
    yerel_kip()
finally:
    print(f"\n{len(OK)} geçti, {len(BAD)} kaldı")
    if not BAD:
        shutil.rmtree(TMP, ignore_errors=True)
    else:
        print(f"Kayıtlar: {TMP}")
sys.exit(1 if BAD else 0)
