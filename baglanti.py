# -*- coding: utf-8 -*-
"""Kırık bağlantı taraması: mağazanın herkese açık sitesini gezer, 404 ve benzeri hata veren sayfa bağlantılarını,
görselleri ve dış bağlantıları bulur. Ideasoft API'si kullanılmaz; mağazaya hiçbir şey yazılmaz.

- Başlangıç: ana sayfa ve site haritası (sitemap.xml, bir seviye alt site haritasıyla). Site haritasındaki hatalı sayfa ayrıca işaretlenir.
- Yalnızca aynı alan adındaki, sorgusuz (?...) sayfalar gezilir; filtre ve sıralama adresleri e-ticaret sitelerinde sonsuz sayfa üretir.
- robots.txt'nin izin vermediği adreslere istek gönderilmez. İstekler arasında bekleme yapılır; bir taramada en çok `sinir` sayfa.
- Ağ erişimi dışarıdan verilen `getir(url, govde)` işleviyle yapılır (güvenlik denetimi orada); böylece modül ağsız test edilir.
"""
import re
import time
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser

TURLER = {"sayfa": "Kırık sayfa bağlantısı", "gorsel": "Kırık görsel", "dis": "Kırık dış bağlantı"}
KAYNAK_ORNEK = 5           # her kırık adres için en çok bu kadar "bulunduğu sayfa" saklanır
DIS_SINIR = 500            # bir taramada denetlenen en çok dış bağlantı / görsel


class _Linkler(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self._a = [], None            # [(tür, adres, metin)]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._a = [a["href"], ""]
        elif tag == "img" and a.get("src"):
            self.out.append(("gorsel", a["src"], a.get("alt") or ""))
        elif tag == "base" and a.get("href"):
            self.out.append(("base", a["href"], ""))

    def handle_data(self, data):
        if self._a is not None:
            self._a[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.out.append(("a", self._a[0], re.sub(r"\s+", " ", self._a[1]).strip()[:80]))
            self._a = None


def linkler(html, sayfa):
    """Sayfadaki bağlantılar: [(tür "a" | "gorsel", tam adres, metin)]. Parça (#...) atılır; mailto, tel, javascript atlanır."""
    p = _Linkler()
    try:
        p.feed(html or "")
        p.close()
    except Exception:  # noqa: BLE001 - bozuk HTML'de elde ne varsa
        pass
    taban = next((u for t, u, _ in p.out if t == "base"), sayfa)
    out = []
    for tur, adres, metin in p.out:
        adres = (adres or "").strip()
        if tur == "base" or not adres or re.match(r"(?i)(mailto|tel|javascript|data|sms|whatsapp):", adres) or adres.startswith("#"):
            continue
        tam = urllib.parse.urljoin(taban, adres).split("#", 1)[0]
        if tam.startswith(("http://", "https://")):
            out.append((tur, tam, metin))
    return out


def site_haritasi(xml):
    """sitemap.xml içindeki adresler ve alt site haritaları: ([sayfa], [alt harita])."""
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or "", re.I)
    if re.search(r"<sitemapindex", xml or "", re.I):
        return [], locs
    return locs, []


def _host(u):
    return (urllib.parse.urlsplit(u).hostname or "").lower()


def _ayni_site(u, host):
    h = _host(u)
    return h == host or h == "www." + host or "www." + h == host


def tara(kok, getir, sinir=10000, bekle=0.25, dur=lambda: False, ilerleme=None, dis=True):
    """kok: "https://magaza.com". getir(url, govde=True) -> (durum kodu, içerik türü, metin, son adres); ağ hatasında durum 0.
    Dönüş: {"sayfa": gezilen sayfa sayısı, "kirik": [{"url", "durum", "tur", "kaynaklar": [{"sayfa", "metin"}],
    "site_haritasi": bool}], "sinira_ulasti": bool, "durduruldu": bool}."""
    kok = kok.rstrip("/")
    host = _host(kok)
    robots = urllib.robotparser.RobotFileParser()
    st, _, txt, _ = getir(kok + "/robots.txt", True)
    robots.parse((txt or "").splitlines() if st == 200 else [])
    izinli = lambda u: robots.can_fetch("*", u)          # noqa: E731

    haritada = set()
    st, _, xml, _ = getir(kok + "/sitemap.xml", True)
    if st == 200:
        sayfalar, alt = site_haritasi(xml)
        for a in alt[:50]:
            s2, _, x2, _ = getir(a, True)
            if s2 == 200:
                sayfalar += site_haritasi(x2)[0]
        haritada = {u.split("#", 1)[0] for u in sayfalar if _ayni_site(u, host) and "?" not in u}

    sira, gorulen = [kok + "/"], {kok + "/"}
    for u in sorted(haritada):
        if u not in gorulen:
            gorulen.add(u)
            sira.append(u)
    kaynak, kontrol, kirik = {}, {}, {}
    gezilen, i, sinira = 0, 0, False

    def kaynak_ekle(u, sayfa, metin):
        k = kaynak.setdefault(u, [])
        if len(k) < KAYNAK_ORNEK and all(x["sayfa"] != sayfa for x in k):
            k.append({"sayfa": sayfa, "metin": metin})

    while i < len(sira):
        if dur():
            break
        u = sira[i]
        i += 1
        if not izinli(u):
            continue
        st, ctype, govde, son = getir(u, True)
        gezilen += 1
        if ilerleme:
            ilerleme(gezilen, len(sira))
        if bekle:
            time.sleep(bekle)
        if st >= 400 or st == 0:
            kirik[u] = {"url": u, "durum": st, "tur": "sayfa"}
            continue
        if "html" not in (ctype or "") or not _ayni_site(son or u, host):
            continue
        for tur, hedef, metin in linkler(govde, son or u):
            ic = _ayni_site(hedef, host)
            if tur == "a" and ic:
                if "?" in hedef:
                    continue                                   # filtre / sıralama adresleri gezilmez
                kaynak_ekle(hedef, u, metin)
                if hedef not in gorulen:
                    if len(gorulen) >= sinir:
                        sinira = True
                        continue
                    gorulen.add(hedef)
                    sira.append(hedef)
            elif tur == "gorsel" or (dis and tur == "a"):
                kaynak_ekle(hedef, u, metin)
                kontrol.setdefault(hedef, "gorsel" if tur == "gorsel" else "dis")
    for hedef, tur in list(kontrol.items())[:DIS_SINIR]:
        if dur():
            break
        if _ayni_site(hedef, host) and not izinli(hedef):
            continue
        st, _, _, _ = getir(hedef, False)
        if bekle and _ayni_site(hedef, host):
            time.sleep(bekle)
        if st >= 400 or st == 0:
            kirik[hedef] = {"url": hedef, "durum": st, "tur": tur}
    out = []
    for u, k in kirik.items():
        out.append(dict(k, kaynaklar=kaynak.get(u, []), site_haritasi=u in haritada))
    sira_tur = list(TURLER)
    out.sort(key=lambda k: (sira_tur.index(k["tur"]), -len(k["kaynaklar"]), k["url"]))
    return {"sayfa": gezilen, "kirik": out, "sinira_ulasti": sinira, "durduruldu": dur()}
