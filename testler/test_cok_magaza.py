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
        if f.endswith(".py"):
            shutil.copy(os.path.join(SRC, f), dst)
    shutil.copytree(os.path.join(SRC, "ui"), os.path.join(dst, "ui"))


def req(port, method, path, body=None, cookie=None, form=False, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    h = dict({"Cookie": cookie} if cookie else {}, **(headers or {}))
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
        json.dump({"client_id": "cid", "client_secret": "sec", "public_url": "http://localhost:8770"}, f)
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

        st, h, j = req(8770, "POST", "/api/disconnect", {}, cookie=cb)
        check("bağlantıyı kaldırınca oturum da kapanır", j.get("login") and "Max-Age=0" in h.get("Set-Cookie", ""))
        st, h, _ = req(8770, "GET", "/cikis", cookie=ca)
        check("çıkış çerezi siler", st == 302 and "Max-Age=0" in h.get("Set-Cookie", ""))
        guvenlik(8770, ca)
    finally:
        proc.terminate()
        proc.wait()
    viol = open(VIOL, encoding="utf-8").read() if os.path.exists(VIOL) else ""
    check("hiçbir istek başka mağazanın anahtarıyla gitmedi", not viol, viol[:300])


def raw_post(port, path, length, cookie=""):
    """Gövdesini göndermeden büyük bir Content-Length bildirir; sunucunun okumadan reddetmesi beklenir."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: {length}\r\n"
                  f"{'Cookie: ' + cookie + chr(13) + chr(10) if cookie else ''}\r\n".encode())
        return s.recv(4096).decode("utf-8", "replace").split(" ", 2)[1]


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
