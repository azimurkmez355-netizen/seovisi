# -*- coding: utf-8 -*-
"""SEO analizindeki eksik ürünler için açıklama üretir (her sektör).

Ürünün mevcut açıklamasını inceler: teknik özellik tablolarını/listelerini, paket içeriğini ve
kullanım alanlarını çıkarır; bunları ürün adından okunan bilgilerle birleştirip
"Teknik Özellikler / Kullanım Alanları / Paket İçeriği" bölümlü, hedef kelime yoğunluğu
%2-%3 olan bir açıklama kurar. Sadece Python standart kütüphanesi.
"""
import hashlib
import html
import random
import re
from html.parser import HTMLParser

import profil as PR
import sablon as TPL
import seo_text as ST

# ------------------------------------------------------------ mevcut açıklamayı okuma


class _Blocks(HTMLParser):
    """HTML'i başlık / paragraf / liste maddesi / tablo satırı bloklarına ayırır."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.buf, self.kind, self.cells, self.in_cell = [], [], None, [], False

    def _flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t and self.kind:
            self.blocks.append((self.kind, t))
        self.buf, self.kind = [], None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "div"):
            self._flush()
            self.kind = "h" if tag.startswith("h") else ("li" if tag == "li" else "p")
        elif tag == "tr":
            self._flush()
            self.cells = []
        elif tag in ("td", "th"):
            self.in_cell, self.buf = True, []
        elif tag in ("strong", "b") and not self.buf:
            self.kind = self.kind or "p"
        elif tag == "br":
            self._flush()
            self.kind = "p"

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cells.append(re.sub(r"\s+", " ", "".join(self.buf)).strip())
            self.buf, self.in_cell = [], False
        elif tag == "tr":
            cells = [c for c in self.cells if c]
            if len(cells) >= 2:
                self.blocks.append(("row", f"{cells[0].rstrip(':')}: {' '.join(cells[1:])}"))
            elif cells:
                self.blocks.append(("p", cells[0]))
            self.cells = []
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "div"):
            self._flush()

    def handle_data(self, data):
        if self.kind is None and not self.in_cell:
            self.kind = "p"
        self.buf.append(data)

    def close(self):
        super().close()
        self._flush()


SECTION_RX = [
    ("pkg", r"paket|kutu içeri|teslimat|set içeri|kutuda|kapsam"),
    ("use", r"kullanım alan|nerelerde|nerede|kullanılır|uygulama alan"),
    ("feat", r"avantaj|öne çıkan|neden|faydalar"),
    ("spec", r"teknik|özellik|spesifikasyon|veriler"),
]
_SKIP = r"stok kodu|barkod|kargo|sipariş|resmi satış|ilgili kategori|garanti belgesi"


def read_existing(details_html, keyword="", store=""):
    """Mevcut açıklamadan bölümleri sırasını ve alt gruplarını koruyarak çıkarır (mağazanın kendi
    tanıtım cümleleri atlanır). Dönüş: (spec, pkg, use, feat). spec = [(madde, [alt maddeler]), ...]"""
    skip = _SKIP + ("|" + re.escape(ST.tr_lower(store)) if store else "")
    p = _Blocks()
    try:
        p.feed(details_html or "")
        p.close()
    except Exception:  # noqa: BLE001 - bozuk HTML'de elde ne varsa
        pass
    sec = {"spec": [], "pkg": [], "use": [], "feat": []}
    cur, group = None, None
    kwl = ST.tr_lower(keyword)
    for kind, t in p.blocks:
        t = re.sub(r"^[\s✔✓✅☑•▪►▸\-–—*]+", "", t).strip()   # eski madde işaretleri (✔ ✔ olmasın)
        low = ST.tr_lower(t)
        if not t or re.search(skip, low):
            continue
        hit = next((k for k, rx in SECTION_RX if re.search(rx, low)), None)
        heading = kind == "h" or (kind == "p" and len(t) < 90 and not t.endswith(".") and not re.search(r":\s*\S", t))
        if heading and (hit or kind == "h"):
            cur, group = hit, None
            continue
        if cur is None:
            continue
        if cur == "spec":
            if t.endswith(":") and len(t) < 60:          # "Tork ayar aralıkları:" gibi alt grup başlığı
                group = (t, [])
                sec["spec"].append(group)
                continue
            if group and re.match(r"^\d+\.?\s*(vites|kademe|seviye|hız)|^\d+\.\s", low):
                group[1].append(t)
                continue
            group = None
            if len(t) <= 200:
                sec["spec"].append((t, []))
        else:
            if len(t) <= 240:
                sec[cur].append(t)
    out = []
    for k in ("spec", "pkg", "use", "feat"):
        seen, items = set(), []
        for it in sec[k]:
            key = it[0] if isinstance(it, tuple) else it
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
        out.append(items)
    spec, pkg, use, feat = out
    return spec[:30], pkg[:15], use[:8], feat[:6]


# ------------------------------------------------------------ ürün adından okuma

def machine_type(name, prof=None, product=None):
    """(ürün tipi etiketi, kullanım alanları); etiket ürünün kategorisinden gelir."""
    t = ST.detect_type(name, prof, product)
    return t[2], [u[0].upper() + u[1:] for u in t[3]]


def name_specs(name, sku):
    """Ürün adından kesin okunabilen bilgi: ürün kodu."""
    return [f"Ürün kodu: {sku}"] if sku else []


# ------------------------------------------------------------ hedef kelime

def machine_keyword(name, current="", prof=None):
    """Mevcut hedef kelime ad içinde geçiyorsa onu korur; yoksa adın model kısmından kısa bir kelime çıkarır."""
    n = re.sub(r"\s+", " ", name or "").strip()
    cur = (current or "").strip()
    if cur and ST.tr_lower(cur) in ST.tr_lower(n) and 3 <= len(cur) <= 55:
        return cur
    rx = PR.brand_prefix_rx(PR.load(prof))
    t = re.sub(rx, "", n, flags=re.I).strip() if rx else n
    t = re.split(r"\s[\(\+–-]\s?|\s\(|\s-\s|\s\+", t)[0]
    t = re.sub(r"\s[0-9A-Z]{10}$", "", t).strip()  # sondaki stok kodu
    words, out = t.split(), []
    for w in words:
        if len(" ".join(out + [w])) > 55:
            break
        out.append(w)
    kw = " ".join(out).strip(" ,-")
    if len(kw.split()) < 2 or ST.tr_lower(kw) not in ST.tr_lower(n):
        kw = ST.extract_keyword(n, max_words=8, max_len=60)
    return kw


# ------------------------------------------------------------ açıklama

# Cümle havuzları ({kw} hedef kelime, {label} ürün tipi, {magaza}/{marka} profil değerleri, {at} "Mağaza'da").
# Mağazanın sunmadığı bir hizmeti (aynı gün kargo, faturalı satış...) vaat etmeyen, ürünü anlatan nötr cümleler.
POOLS = {
    "genel": {
        "intro": ["{kw}, {label} arayan kullanıcılar için kullanışlı ve güvenilir bir seçenektir.",
                  "{kw}, {marka} kalitesini {label} kategorisinde bir araya getirir.",
                  "{kw}; özenli tasarımı ve kaliteli yapısıyla öne çıkan bir {label} modelidir."],
        "closing": ["{kw} ürününü {magaza} güvencesiyle kolayca sipariş edebilirsiniz.",
                    "{kw} ve benzer ürünleri {magaza} mağazasında inceleyebilirsiniz.",
                    "{kw} için {magaza} ürün sayfasındaki seçenekleri karşılaştırabilirsiniz."],
        "closing_nostore": ["{kw} ürününü hemen sipariş edebilirsiniz.",
                            "{kw} ve benzer ürünleri bu kategoride inceleyebilirsiniz.",
                            "{kw} seçeneklerini bu sayfada kolayca karşılaştırabilirsiniz."],
        "kw_extra": [
            "{kw} ile ihtiyacınızı pratik bir şekilde karşılayabilirsiniz.",
            "{kw} hakkında merak ettikleriniz için {magaza} müşteri hizmetlerine ulaşabilirsiniz.",
            "{kw} kutusundan çıktığı gibi kullanıma hazırdır.",
            "{kw} siparişleriniz özenle paketlenerek gönderilir.",
            "{kw} ile ilgili detaylar yukarıda listelenmiştir.",
            "{kw}, {marka} kalitesiyle üretilmiştir.",
            "{kw} günlük kullanım için tasarlanmıştır.",
            "{kw} uygun fiyatla {at}.",
            "{kw} güvenli ödeme seçenekleriyle satın alınabilir.",
        ],
        "fill": [
            "Kullanışlı tasarımı günlük kullanımda konfor sağlar.",
            "{marka} kalitesiyle üretilen bu ürün, uzun süre kullanılacak şekilde tasarlanmıştır.",
            "Kullanmadan önce ürünle birlikte gelen bilgileri okumanızı öneririz.",
            "Düzenli bakım ile ürünün kullanım ömrünü uzatabilirsiniz.",
            "Sipariş öncesinde ürünle ilgili sorularınızı bize iletebilirsiniz.",
            "Ürün görsellerini ve detaylarını inceleyerek size en uygun seçimi yapabilirsiniz.",
        ],
        "first": ["Ürün, {use} için kullanışlı bir seçenektir.",
                  "Ürün; {use} gibi ihtiyaçlarda rahatlıkla kullanılabilir."],
    },
}


def pool(prof, key):
    """Şablonlar: profil değerleri doldurulmuş, karşılığı olmayanlar atılmış."""
    pk = POOLS["genel"]
    at = PR.loc(prof["magaza"]) if prof["magaza"] else ""
    out = [x.replace("{at}", at) for x in PR.pick(pk[key], prof) if at or "{at}" not in x]
    if not out and key == "closing":
        out = PR.pick(pk.get("closing_nostore") or POOLS["genel"]["closing_nostore"], prof)
    return out


def _put(template, **vals):
    """Şablona değerleri yerleştirir (ürün adında süslü parantez olabileceği için format kullanılmaz)."""
    for k, v in vals.items():
        template = template.replace("{" + k + "}", v)
    return template


def build_machine_seo(product, details_html="", current_kw="", sku="", barcode="", method="", target=2.5,
                      variant=0, min_words=60, prof=None, sablon=None):
    """sablon: mağazanın açıklama şablonu (sablon.py); yoksa varsayılan sade şablon."""
    t = TPL.yukle(sablon)
    name = re.sub(r"\s+", " ", (product.get("name") or "").strip())
    prof = PR.with_brand(prof, product)
    kw = machine_keyword(name, current_kw, prof)
    rng = random.Random(int(hashlib.md5(f"{sku or name}-{variant}".encode()).hexdigest()[:8], 16))
    label, uses_default = machine_type(name, prof, product)
    ex_spec, ex_pkg, ex_use, ex_feat = read_existing(details_html, kw, prof["magaza"])
    have = " ".join(ST.tr_lower(x[0]) for x in ex_spec)
    extra_spec = [s for s in name_specs(name, sku)
                  if ST.tr_lower(s.split(":")[0]) not in have]
    specs = ex_spec + [(s, []) for s in extra_spec]
    pkg = ex_pkg
    uses = ex_use or uses_default
    feats = ex_feat
    specs = [x for x in specs if ST.count_kw(x[0] + " " + " ".join(x[1]), kw) == 0]
    pkg = [x for x in pkg if ST.count_kw(x, kw) == 0]
    uses = [x for x in uses if ST.count_kw(x, kw) == 0]
    feats = [x for x in feats if ST.count_kw(x, kw) == 0]

    intro = _put(rng.choice(pool(prof, "intro")), label=label, kw=kw)
    closing = _put(rng.choice(pool(prof, "closing")), kw=kw)
    if t["kapanis"]["metin"]:                          # mağazanın kendi kapanış metni: {urun} hedef kelime, {magaza}
        closing = _put(PR.fill(t["kapanis"]["metin"], prof), urun=kw)
    kw_more = [_put(x, kw=kw) for x in pool(prof, "kw_extra")]
    rng.shuffle(kw_more)
    fill = [f for f in pool(prof, "fill") if ST.count_kw(f, kw) == 0]
    rng.shuffle(fill)
    first_fill = rng.choice([_put(x, use=uses[0].split(":")[0].lower()) if uses else "" for x in pool(prof, "first")])

    def esc(t):
        return html.escape(t, quote=False)

    # Görünüm şablondan; her görünüm aynı sayıda kelime üretir, panel katsayısı kaymaz (sablon.py).
    # Madde işaretleri harf olmadığı için sayılmaz.
    st = TPL.stiller(t)
    H = f'<h3 style="{st["h"]}">{{}}</h3>'
    BOX = f'<div style="{st["kutu"]}">{{}}</div>'
    mark = t["madde"] + " " if t["madde"] else ""
    order = [b["k"] for b in t["bolumler"] if b["acik"]]
    head = {b["k"]: esc(b["baslik"]) for b in t["bolumler"]}

    def label_li(t):
        m = re.match(r"^([^:]{2,80}):\s*(.+)$", t)
        return f"<strong>{esc(m.group(1))}:</strong> {esc(m.group(2))}" if m else esc(t)

    def ul(items, marked=False):
        open_ = f'<ul style="{st["liste"]}">' if marked else "<ul>"
        return open_ + "".join(f"<li>{mark if marked else ''}{label_li(i)}</li>" for i in items) + "</ul>"

    def spec_ul(items):
        out = []
        for t, kids in items:
            head_ = f"<strong>{esc(t)}</strong>" if kids else label_li(t)
            out.append(f"<li>{head_}{ul(kids) if kids else ''}</li>")
        return "<ul>" + "".join(out) + "</ul>"

    uses_short = [u.split(":")[0].strip() if ":" in u and len(u) > 70 else u for u in uses]
    first = "" if ex_use else first_fill
    leads = {"spec": f"{kw} teknik özellikleri:", "use": f"{kw} kullanım alanları:", "pkg": f"{kw} paket içeriği:"}
    tech = " ".join(x for x in (f"Stok kodu: {sku}" if sku and t["stok_kodu"] else "",
                                f"Barkod: {barcode}" if barcode and t["barkod"] else "") if x)

    def render(k, n, with_feats=True, short_uses=False, lead=True):
        extra, ks = fill[:n], kw_more[:k]
        p2 = ks[2:] + extra[(n + 1) // 2:]
        rest = ([first] if first else []) + extra[: (n + 1) // 2] + ks[:1]
        if "neden" not in order:                       # "Neden tercih" kapalıysa o cümleler giriş paragrafına
            rest, p2 = rest + p2, []
        rest = " ".join(rest)
        intro_html = f"<strong>{esc(kw)}</strong>" + esc(intro[len(kw):]) if intro.startswith(kw) else esc(intro)
        parts = ["<p>" + intro_html + (" " + esc(rest) if rest else "") + "</p>"]
        blocks = {
            "one_cikan": H.format(head["one_cikan"]) + ul(feats, True) if feats and with_feats else "",
            "teknik": H.format(head["teknik"]) + (f"<p><em>{esc(leads['spec'])}</em></p>" if lead else "")
            + spec_ul(specs) if specs else "",
            "kullanim": H.format(head["kullanim"]) + (f"<p><em>{esc(leads['use'])}</em></p>" if lead else "")
            + ul(uses_short if short_uses else uses, True) if uses else "",
            "paket": H.format(head["paket"]) + (f"<p><em>{esc(leads['pkg'])}</em></p>" if lead else "")
            + ul(pkg, True) if pkg else "",
            "neden": H.format(head["neden"]) + ul(p2, True) if p2 else "",
        }
        ara = "<p>" + esc(ks[1]) + "</p>" if len(ks) > 1 else ""   # bölümler arasındaki tek hedef kelimeli cümle
        if ara and "teknik" not in order:
            parts.append(ara)
        for key in order:
            if blocks[key]:
                parts.append(blocks[key])
            if key == "teknik" and ara:
                parts.append(ara)
        store = esc(prof["magaza"])
        if t["kapanis"]["acik"]:
            parts.append(BOX.format("<p>" + (esc(closing).replace(store, f"<strong>{store}</strong>", 1) if store else esc(closing))
                                    + "</p>" + (f"<p>{esc(tech)}</p>" if tech else "")))
        elif tech:
            parts.append(f"<p>{esc(tech)}</p>")
        return "\n".join(parts)

    methods = [m for m in (method or "").split(",") if m in ST.COUNT_METHODS] or list(ST.COUNT_METHODS)
    best = None
    for lead in (False, True):
        for with_feats, short_uses in ((True, False), (True, True), (False, False), (False, True)):
            for k in range(0, len(kw_more) + 1):
                for n in range(0, len(fill) + 1):
                    h = render(k, n, with_feats, short_uses, lead)
                    c = ST.count_kw(ST.strip_tags(h), kw)
                    ws = [ST.count_words(h, m) for m in methods]
                    dens = [c / w * 100 if w else 0 for w in ws]
                    margin = min(min(d - 2.0, 3.0 - d) for d in dens)
                    # önce güvenli yoğunluk, sonra içeriğin tamamı (özellikler ve uzun kullanım alanları), sonra kısalık
                    key = (min(margin, 0.35) - (0 if min(ws) >= min_words else 5), with_feats, not short_uses,
                           not lead, -k, -max(ws))
                    if best is None or key > best[0]:
                        best = (key, h, dens)
    _, body, dens = best

    meta = ST.make_meta(kw, label, [], random.Random(0), prof)
    title = ST.make_title(name, kw, prof)
    return {"keyword": kw, "details_html": body, "pageTitle": title, "metaDescription": meta,
            "metaKeywords": ST.make_keywords(kw, name, label, prof), "label": label,
            "densities": {m: round(d, 2) for m, d in zip(methods, dens)},
            "found": {"spec": len(ex_spec), "pkg": len(ex_pkg), "use": len(ex_use), "feat": len(ex_feat)}}


# ------------------------------------------------------------ sorunlu ürünler için teşhis

RISKY = "®™©&:;'\"()[]*+%/<>|#’“”"


def safe_keyword(name, max_len=55):
    """Ürün adının içinden; ®, &, :, tırnak, parantez gibi HTML'de farklı yazılabilen ya da panelin
    farklı yorumlayabileceği karakterler İÇERMEYEN, en az 2 kelimelik en uzun parçayı seçer."""
    n = re.sub(r"\s+", " ", name or "").strip()
    toks = n.split(" ")
    runs, cur = [], []
    for t in toks:
        if t and not any(c in RISKY for c in t):
            cur.append(t)
            continue
        head = re.sub(r"[:;,.®™]+$", "", t)          # "SpeedClic:" -> "SpeedClic" (kelime orada biter)
        if head and head != t and not any(c in RISKY for c in head):
            cur.append(head)
        if cur:
            runs.append(cur)
        cur = []
    if cur:
        runs.append(cur)
    best = ""
    for r in runs:
        while r and r[-1][-1:] in ",.-":
            r = r[:-1] if len(r[-1]) <= 1 else r[:-1] + [r[-1].rstrip(",.-")]
        # baştaki marka gibi genel kelimeleri koru ama uzunluğu sınırla
        out = []
        for w in r:
            if len(" ".join(out + [w])) > max_len:
                break
            out.append(w)
        cand = " ".join(out)
        score = (len(out) >= 2, sum(any(ch.isdigit() for ch in w) for w in out) > 0, len(out), len(cand))
        if cand and ST.tr_lower(cand) in ST.tr_lower(n) and (not best or score > best[0]):
            best = (score, cand)
    return best[1] if best and best[0][0] else ""


def diagnose(name, kw, details_html, page_title, meta, factor):
    """Ideasoft panelinde kuralın neden tutmadığına dair olası sebepler (insan okunur)."""
    out = []
    raw_name = name or ""
    if re.search(r"\s{2,}|^\s|\s$|\u00a0", raw_name):
        out.append("Ürün adında fazla / görünmez boşluk var.")
    if not kw:
        out.append("Hedef kelime boş.")
        return out
    bad = sorted({c for c in kw if c in RISKY})
    if bad:
        out.append(f"Hedef kelimede panelin farklı yorumlayabileceği karakter var: {' '.join(bad)} "
                   f"(ör. ® açıklamada &reg; olarak kaydedilebilir, eşleşme bozulur).")
    if ST.tr_lower(kw) not in ST.tr_lower(re.sub(r"\s+", " ", raw_name)):
        out.append("Hedef kelime ürün adında birebir geçmiyor.")
    raw = details_html or ""
    if kw not in raw and ST.tr_lower(kw) in ST.tr_lower(ST.strip_tags(raw)):
        out.append("Hedef kelime açıklamanın HTML kaynağında farklı yazılmış (özel karakter kodlanmış).")
    c = ST.count_kw(ST.strip_tags(raw), kw)
    w = ST.count_words(raw, "asc_html")
    if w:
        est = c / w * 100 * factor
        if not 2.0 < est < 3.0:
            out.append(f"Tahmini panel yoğunluğu %{est:.2f} (%2-%3 dışında ya da sınırda).")
        elif est > 2.8 or est < 2.2:
            out.append(f"Tahmini panel yoğunluğu %{est:.2f}; sınıra çok yakın.")
    pt = page_title or ""
    if not (20 <= len(pt) <= 60):
        out.append(f"Etiket başlığı {len(pt)} karakter (20-60 olmalı).")
    if ST.tr_lower(kw) not in ST.tr_lower(pt):
        out.append("Hedef kelime etiket başlığında geçmiyor.")
    md = meta or ""
    if not (50 <= len(md) <= 155):
        out.append(f"Meta açıklama {len(md)} karakter (50-155 olmalı).")
    if ST.tr_lower(kw) not in ST.tr_lower(md):
        out.append("Hedef kelime meta açıklamada geçmiyor.")
    return out or ["Programın kontrollerinde belirgin bir hata yok; panel yoğunluğu farklı hesaplıyor olabilir."]
