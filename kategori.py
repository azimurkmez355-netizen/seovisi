# -*- coding: utf-8 -*-
"""Kategori analizi — ürün adlarına bakarak yanlış kategorideki ürünleri, kategorisiz ürünleri ve
açılması gereken yeni kategorileri bulur. Mağazaya hiçbir şey yazmaz; sadece standart kütüphane.

Yöntem: öneriler kategori ADINA dayanır. Bir kategori ancak adındaki ayırt edici kelimelerin hepsi
ürün adında geçiyorsa önerilir ("Kadın Abiye Elbiseler" için ürün adında "kadın", "abiye" ve "elbise" olmalı).
Ürün adında kendi kategorisinin kelimelerinden biri geçiyorsa o kategori doğru sayılır; bir ürün birden
fazla kategoride olabilir (ör. hem "Yeni Sezon" hem "Elbiseler"). Kategorilerin ürün adlarından
çıkarılan kelime profili (Naive Bayes) sadece adaylar arasında seçim ve ikinci kontrol için kullanılır.
Hiçbir sektöre özgü kelime listesi yoktur: ürün tipleri mağazanın kendi kategori adlarından, ürünlerin
çoğunda geçen (ana marka gibi) ayırt edici olmayan kelimeler mağazanın kendi ürün adlarından öğrenilir.
"""
import math
import re
from collections import Counter, defaultdict

import profil as PR
import seo_text as ST

# Ürün adında kategori bilgisi taşımayan kelimeler (bağlaç, ölçü birimi...). Marka adları burada değil:
# mağazanın ürünlerinin çoğunda geçen kelimeler analiz sırasında kendiliğinden ayıklanır (COMMON).
NOISE = set("""
ve ile için icin veya with for and the için adet parça parca li lı lu lü lik lık luk lük
mm cm inch inç volt watt kg gr ml lt mt
yeni new orijinal original uyumlu model tip type seri serisi
""".split())

ALPHA = 0.2          # Laplace düzeltmesi
NAME_W = 3           # kategori adının profile katkısı (sanal ürün sayısı)
MIN_DOCS = 3         # bu kadar ürünü olmayan kategoriye ürün önerilmez
MIN_GROUP = 8        # yeni kategori önerisi için en az ürün
SPLIT_MIN = 20       # alt kategori önerisi aranacak kategorinin en az ürün sayısı
COMMON = 0.3         # ürünlerin bu oranından fazlasında ve kategorilerin çoğunda geçen kelime ayırt edici sayılmaz
COMMON_CATS = 0.6    # (ör. mağazanın ana markası her kategoride geçer; "elbise" ise yalnızca elbise kategorisinde)


def tr_title(s):
    def up(w):
        return (w[0].replace("i", "İ").replace("ı", "I").upper() + w[1:]) if w else w
    return " ".join(up(w) for w in s.split())


# "(Akü ve Şarj Cihazı Dahil Değildir)", "Akü Şarj Hariç" gibi ifadeler ürünün NE OLMADIĞINI söyler
_NEG = re.compile(r"\([^)]*(?:hariç|haric|dahil değil|dâhil değil|kapsam)[^)]*\)"
                  r"|(?:\s|ak[üu]\w*|şarj\w*|sarj\w*|cihaz\w*|ve|&|\+)+(?:hariç|haric|dahil değil\w*)")


def tokens(name):
    """Ürün adındaki anlamlı kelimeler (küçük harf, sıralı). Sayılar, ölçüler ve marka düşer."""
    low = _NEG.sub(" ", ST.tr_lower(re.sub(r"[®™©]", " ", name or "")))
    out = []
    for m in re.finditer(r"(?<![\d.,])(\d{1,2})(?:[.,]\d)?\s?v\b|[a-zçğıöşüâîû]+", low):
        if m.group(1):  # voltaj: "12V", "18 V", "10,8V" -> "12v" / "18v" / "10v"
            out.append(m.group(1) + "v")
            continue
        t = m.group(0)
        if len(t) >= 3 and t.replace("ı", "i") not in _NOISE_I:
            out.append(t)
    return out


_PLURAL = ("ları", "leri", "lar", "ler")
_POSS = ("sı", "si", "su", "sü", "ı", "i", "u", "ü")
_SOFT = {"ğ": "k", "c": "ç", "b": "p", "d": "t"}


def stem(t):
    """Türkçe için kaba kök: çoğul ve iyelik eki atılır, yumuşayan ünsüz sertleşir, ilk 6 harf alınır.
    uç / ucu / uçları -> uç, bıçak / bıçağı / bıçakları -> bıçak, disk / diski / diskleri -> disk"""
    for s in _PLURAL:
        if t.endswith(s) and len(t) - len(s) >= 2:
            t = t[:-len(s)]
            break
    for s in _POSS:
        if t.endswith(s) and len(t) - len(s) >= 2:
            t = t[:-len(s)]
            break
    if len(t) > 1 and t[-1] in _SOFT:
        t = t[:-1] + _SOFT[t[-1]]
    return t[:6]


# Kategori adlarında ürün tipini belirtmeyen kelimeler: "Mutfak Ürünleri" -> sadece "mutfak" aranır
GENERIC = {stem(w) for w in """
ürünler ürün ürünleri aksesuarlar aksesuar ekipmanları ekipman malzemeleri malzeme çeşitleri çeşit
diğer diğerleri modelleri model grubu grup sistem sistemi genel tüm tümü kategori koleksiyon koleksiyonu
""".split()}
# Tek başına bir kategori önermeye yetmeyen kelimeler ("Aksesuar Setleri" her "... Seti"ne önerilmesin)
WEAK = {stem(w) for w in "set seti setleri takım takımı kit karışık".split()}
# Seri / kalite adları: eşleştirmede kullanılır ("Pro Max") ama yeni kategori adı olamaz ("Premium" bir ürün tipi değil)
LINE = {stem(w) for w in """
pro plus premium lüks standart standard mini maxi max extra ekstra klasik classic serisi seri yeni sezon
""".split()}
# Malzeme ve renk adları ürün tipi değildir ("Pamuklu Ürünler" kategorisinin son kelimesi "pamuk" olsa da)
MATERIAL = {stem(w) for w in """
ahşap metal çelik paslanmaz cam plastik seramik deri pamuk pamuklu keten ipek yün polyester kumaş
siyah beyaz kırmızı mavi yeşil sarı gri lacivert pembe mor kahverengi bej
""".split()}
# İş adları ürün tipi değildir ("Temizleme", "Bakım"); yeni kategori adı bunlarla bitmez
VERB = {stem(w) for w in "kullanım bakım temizleme temizlik koruma onarım montaj kurulum".split()}
# İfade içinde geçince öneriyi bozan genel kelimeler ("Malzemeler İçin ...")
FILLER = {stem(w) for w in "malzeme malzemeler malzemeleri material materials genel".split()}


def _both_i(words):
    """Büyük harfle yazılmış yabancı kelimeler ("INOX") Türkçe kuralla "ınox" olur; iki hâli de tanınsın."""
    return set(words) | {w.replace("i", "ı") for w in words}


NOISE, GENERIC, WEAK, LINE, MATERIAL, VERB, FILLER = (
    _both_i(s) for s in (NOISE, GENERIC, WEAK, LINE, MATERIAL, VERB, FILLER))
_NOISE_I = {w.replace("ı", "i") for w in NOISE}  # "Için", "IÇIN", "için" hepsi aynı kelime


def prefixes(stems):
    """Kaba eşleştirme için ilk 4 harf: "temizleme" ile "temizleyici" aynı sayılır."""
    return {s[:4] for s in stems if "_" not in s}


def features(toks):
    st = [stem(t) for t in toks]
    f = set(st)
    f.update(f"{a}_{b}" for a, b in zip(st, st[1:]))
    return f


def extra_features(name, sku):
    """Adın dışındaki ipucu: stok kodu ön eki (birçok markada ürün grubunu belirtir)."""
    f = set()
    s = re.sub(r"[^0-9A-Za-z]", "", sku or "").upper()
    if len(s) >= 8:
        f.add("sku_" + s[:4])
    return f


class Analyzer:
    def __init__(self, cats, products):
        """cats: {id: {"name": str, "parent": id|None}}
        products: [{"pid", "sku", "name", "cats": [id, ...]}]"""
        self.cats = cats
        self.products = products
        self.children = defaultdict(list)
        for cid, c in cats.items():
            if c.get("parent") in cats:
                self.children[c["parent"]].append(cid)
        self._path = {}
        self.surface = defaultdict(Counter)  # kök -> ürün adlarında görülen hâlleri

    # ------------------------------------------------------------ ağaç
    def ancestors(self, cid):
        out, seen = [], set()
        p = self.cats.get(cid, {}).get("parent")
        while p in self.cats and p not in seen:
            seen.add(p)
            out.append(p)
            p = self.cats[p].get("parent")
        return out

    def path(self, cid):
        if cid not in self._path:
            names = [self.cats[a]["name"] for a in reversed(self.ancestors(cid))]
            self._path[cid] = " › ".join(names + [self.cats.get(cid, {}).get("name") or f"#{cid}"])
        return self._path[cid]

    def related(self, a, b):
        return a == b or a in self.ancestors(b) or b in self.ancestors(a)

    def specific(self, ids):
        """Ürünün en alt kategorileri: atanmış başka bir kategorinin üst kategorisi olanlar çıkarılır."""
        ids = [i for i in dict.fromkeys(ids) if i in self.cats]
        anc = set()
        for i in ids:
            anc.update(self.ancestors(i))
        return [i for i in ids if i not in anc]

    def word(self, f):
        """Kökten okunabilir kelime: en sık görülen hâli."""
        parts = f.split("_")
        return " ".join(self.surface[p].most_common(1)[0][0] if self.surface[p] else p for p in parts)

    # ------------------------------------------------------------ model
    def fit(self):
        self.docs = {}          # pid -> özellik kümesi
        self.toks = {}
        self.spec = {}          # pid -> en alt kategoriler
        self.cnt = defaultdict(Counter)
        self.tot = Counter()
        self.n = Counter()
        self.raw = {}           # pid -> üründe kayıtlı bütün kategoriler (üst kategoriler dahil)
        df, cat_df, cat_n = Counter(), defaultdict(Counter), Counter()
        for p in self.products:
            tk = tokens(p["name"])
            for t in tk:
                self.surface[stem(t)][t] += 1
            self.toks[p["pid"]] = tk
            self.docs[p["pid"]] = features(tk) | extra_features(p["name"], p.get("sku"))
            spec = self.specific(p.get("cats") or [])
            words = {stem(t) for t in tk}
            df.update(words)
            for c in spec:
                cat_n[c] += 1
                cat_df[c].update(words)
        # ürünlerin çoğunda VE kategorilerin çoğunda geçen kelime (mağazanın ana markası gibi) hiçbir kategoriyi
        # ayırt etmez; bir ürün tipine özgü sık kelime ("elbise") yalnızca kendi kategorilerinde geçtiği için kalır
        n_all = len(self.products)
        used = [c for c in cat_n if cat_n[c] >= MIN_DOCS]

        def widespread(s):   # kelime, kategorilerin çoğunda o kategorinin ürünlerinin en az %20'sinde geçiyor
            return sum(1 for c in used if cat_df[c][s] >= 0.2 * cat_n[c]) >= COMMON_CATS * len(used)
        self.common = {s for s, k in df.items() if n_all >= 50 and len(used) >= 3 and k > COMMON * n_all and widespread(s)}
        for p in self.products:
            pid = p["pid"]
            if self.common:
                self.docs[pid] = {x for x in self.docs[pid] if not set(x.split("_")) & self.common}
                self.toks[pid] = [t for t in self.toks[pid] if stem(t) not in self.common]
            f = self.docs[pid]
            self.raw[pid] = list(dict.fromkeys(p.get("cats") or []))
            self.spec[pid] = self.specific(p.get("cats") or [])
            for c in self.spec[pid]:
                self.n[c] += 1
                self.cnt[c].update(f)
                self.tot[c] += len(f)
        self.name_f = {}
        for cid, c in self.cats.items():
            f = {x for x in features(tokens(c.get("name") or "")) if not set(x.split("_")) & self.common}
            self.name_f[cid] = f
            if self.n[cid] >= MIN_DOCS:
                for x in f:
                    self.cnt[cid][x] += NAME_W
                self.tot[cid] += NAME_W * len(f)
        self.classes = [c for c in self.cats if self.n[c] >= MIN_DOCS]
        vocab = set()
        for c in self.classes:
            vocab.update(self.cnt[c])
        self.V = max(1, len(vocab))
        self.post = defaultdict(list)  # özellik -> onu içeren sınıflar
        for c in self.classes:
            for x in self.cnt[c]:
                self.post[x].append(c)
        total = sum(self.n[c] for c in self.classes) or 1
        # büyük kategoriler her şeyi yutmasın diye önsel olasılık yumuşatılır (karekök)
        self.prior = {c: 0.5 * math.log(self.n[c] / total) for c in self.classes}

        # kategori adının ayırt edici kelimeleri ve ürün adlarıyla ne kadar örtüştüğü
        self.dist = {cid: {stem(t) for t in tokens(c.get("name") or "")} - GENERIC - self.common
                     for cid, c in self.cats.items()}
        self.root = {cid: (self.ancestors(cid) or [cid])[-1] for cid in self.cats}
        # öneri için kategorinin tüm yolundaki kelimeler aranır: "Kadın Giyim › Elbiseler"
        # ancak adında "kadın" da geçen ürüne önerilir
        self.dist_path = {cid: set().union(self.dist[cid], *(self.dist[a] for a in self.ancestors(cid)))
                          for cid in self.cats}
        self.dist_pre = {cid: prefixes(d) for cid, d in self.dist.items()}
        self.doc_pre = {pid: prefixes(f) for pid, f in self.docs.items()}
        hit = Counter()
        for pid, cs in self.spec.items():
            for c in cs:
                if self.dist_pre[c] & self.doc_pre[pid]:
                    hit[c] += 1
        # "Kampanyalı Ürünler", "Yeni Gelenler" gibi koleksiyon kategorilerinde ürün adları kategori adını
        # içermez; bunlar ne yanlış sayılır ne de önerilir
        self.judge = {c: bool(self.dist[c]) and (self.n[c] < MIN_DOCS or hit[c] >= 0.5 * self.n[c])
                      for c in self.cats}
        self.dist_idx = defaultdict(list)
        for c, d in self.dist.items():
            if self.judge[c] and not d <= WEAK:
                for x in d:
                    self.dist_idx[x].append(c)

        # aynı seriden ürünler: adının ilk üç kelimesi aynı olanlar ("Kadın Çiçek Desenli ...")
        self.fam_key, self.fam, self.fam_n = {}, defaultdict(Counter), Counter()
        for pid, tk in self.toks.items():
            if len(tk) >= 3:
                k = "_".join(stem(t) for t in tk[:3])
                self.fam_key[pid] = k
                self.fam_n[k] += 1
                for a in {a for c in self.spec[pid] for a in [c] + self.ancestors(c)}:
                    self.fam[k][a] += 1
        # mağazada ürünler üst kategorilere de bağlanıyor mu? Öneri uygulanırken aynı düzen korunur.
        has_anc = [pid for pid, cs in self.spec.items() if any(self.ancestors(c) for c in cs)]
        with_anc = sum(1 for pid in has_anc
                       if any(a in self.raw[pid] for c in self.spec[pid] for a in self.ancestors(c)))
        self.with_parents = bool(has_anc) and with_anc >= 0.5 * len(has_anc)

        # seri adları: mağazada birçok farklı kategoriye yayılmış kelimeler ("Pro", "Premium" ya da markanın seri adı);
        # eşleştirmede kullanılır ama yeni kategori adı bunlarla başlamaz
        spread = defaultdict(set)
        for pid, tk in self.toks.items():
            for s in {stem(x) for x in tk}:
                spread[s].update(self.spec[pid])
        self.series = {s for s, cs in spread.items() if len(cs) >= 8 and df.get(s, 0) >= max(10, 0.005 * n_all)}
        return self

    def fam_share(self, pid, c):
        """Aynı serideki DİĞER ürünlerin kaçta kaçı c kategorisinde (ya da altında). Seri küçükse None."""
        k = self.fam_key.get(pid)
        others = self.fam_n[k] - 1 if k else 0
        if others < 2:
            return None, 0, 0
        own = 1 if any(c == m or c in self.ancestors(m) for m in self.spec[pid]) else 0
        n = self.fam[k][c] - own
        return n / others, n, others

    def plan(self, pid, add_c, remove=()):
        """Uygulanacak değişiklik: eklenecek ve çıkarılacak kategori numaraları."""
        raw = self.raw[pid]
        add = [add_c] + (self.ancestors(add_c) if self.with_parents else [])
        add = [a for a in dict.fromkeys(add) if a not in raw]
        rem = {r for r in remove if r in raw}
        # çıkarılan kategorinin artık hiçbir kategoriye üst olmayan üst kategorileri de çıkarılır
        keep = [c for c in self.spec[pid] if c not in rem] + [add_c]
        need = {a for c in keep for a in [c] + self.ancestors(c)}
        for r in list(rem):
            rem.update(a for a in self.ancestors(r) if a in raw and a not in need)
        return add, [r for r in raw if r in rem]

    def _logp(self, c, x, own=None):
        k = self.cnt[c][x] - (1 if own and x in own else 0)
        t = self.tot[c] - (len(own) if own else 0)
        return math.log((max(k, 0) + ALPHA) / (t + ALPHA * self.V))

    def scores(self, pid):
        """{kategori: olasılık}; ürün kendi kategorilerinin profilinden çıkarılarak hesaplanır."""
        f = self.docs[pid]
        mine = set(self.spec[pid])
        sc = {}
        cand = set()
        for x in f:
            cand.update(self.post.get(x, ()))
        cand.update(c for c in mine if c in self.prior)
        if not cand:
            return {}
        for c in cand:
            own = f if c in mine else None
            if own and self.n[c] - 1 < 1:
                continue
            sc[c] = self.prior[c] + sum(self._logp(c, x, own) for x in f)
        if not sc:
            return {}
        # aday dışında kalan kategoriler hiçbir kelimeyi paylaşmıyor; olasılıkları ihmal edilebilir
        m = max(sc.values())
        z = sum(math.exp(v - m) for v in sc.values())
        return {c: math.exp(v - m) / z for c, v in sc.items()}

    def words(self, stems):
        return ", ".join(f"“{self.word(s)}”" for s in sorted(stems))

    def name_candidates(self, pid, mine):
        """Adındaki ayırt edici kelimelerin HEPSİ ürün adında geçen, ürünün henüz bulunmadığı kategoriler."""
        f = self.docs[pid]
        roots = {self.root[c] for c in mine}
        seen, out = set(), []
        for x in f:
            for c in self.dist_idx.get(x, ()):
                if c in seen:
                    continue
                seen.add(c)
                if not self.dist_path[c] <= f:
                    continue
                # başka bir ana kategoriye ancak o ana kategorinin adı da ürün adında geçiyorsa önerilir
                # ("Erkek"teki "Kadın Midi Elbise" -> "Kadın › Elbiseler"; adı genel olan ana kategoriler arası öneri yok)
                if roots and self.root[c] not in roots and not self.dist[self.root[c]]:
                    continue
                if not self.ancestors(c) and self.children[c]:   # alt kategorileri olan ana kategori çok genel
                    continue
                if any(c == m or c in self.ancestors(m) for m in mine):
                    continue
                # ürün daha özel bir kardeş kategoride: "Abiye Elbiseler"deki ürüne "Elbiseler" kardeşi önerilmez
                if any(self.dist_path[m] and self.dist_path[c] <= self.dist_path[m] for m in mine):
                    continue
                out.append(c)
        # adayın alt kategorisi de adaysa daha özel olan kalır
        return [c for c in out if not any(o != c and c in self.ancestors(o) for o in out)]

    def misfit(self, pid, c, pr):
        """Ürün bu kategoriye uymuyor mu? Adında kategorinin hiçbir kelimesi yoksa ve profil de benzemiyorsa."""
        return self.judge[c] and not (self.dist_pre[c] & self.doc_pre[pid]) and pr.get(c, 0) < 0.02

    # ------------------------------------------------------------ analiz
    def run(self, progress=None):
        self.fit()
        wrong, uncat = [], []
        agree = Counter()
        for i, p in enumerate(self.products):
            if progress and i % 250 == 0:
                progress(i, len(self.products))
            pid = p["pid"]
            if p.get("active") is False:   # pasif ürün sitede görünmez; kategorisi analiz edilmez
                continue
            if not self.docs[pid]:
                if not self.spec[pid]:
                    uncat.append({"pid": pid, "sku": p.get("sku"), "name": p["name"], "raw": self.raw[pid],
                                  "sug_id": None, "sug": "", "prob": None, "score": 0, "strength": "yok",
                                  "add": [], "rem": [], "add_p": [], "rem_p": [],
                                  "reason": "Ürün adında kategori belirlemeye yarayan bir kelime yok; kategoriyi elle seçin."})
                continue
            pr = self.scores(pid)
            mine = self.spec[pid]
            cands = self.name_candidates(pid, mine)
            best = max(cands, key=lambda c: (len(self.dist_path[c]), pr.get(c, 0), self.n[c])) if cands else None
            base = {"pid": pid, "sku": p.get("sku"), "name": p["name"], "raw": self.raw[pid]}

            def evidence(c):
                """(profil benzerliği 0-1, seri desteği 0-1, açıklama)"""
                nb = pr.get(c, 0.0) if c in self.prior else 0.5
                fs, n, others = self.fam_share(pid, c)
                txt = f"aynı seriden {others} ürünün {n} tanesi bu kategoride" if fs is not None else ""
                return nb, (0.5 if fs is None else fs), txt

            def plan_fields(c, remove=()):
                add, rem = self.plan(pid, c, remove)
                return {"add": add, "rem": rem, "add_p": [self.path(a) for a in add], "rem_p": [self.path(r) for r in rem]}

            if not mine:
                # kategorisiz ürünlerin HEPSİ listelenir (sayaç ile liste aynı sayıyı göstersin):
                # adı bir kategori adını karşılıyorsa güçlü öneri, benzer ürünler bir kategorideyse olası öneri, yoksa öneri yok
                # olası öneri için ürün adında o kategorinin en az bir kelimesi de geçmeli (benzer ama alakasız kategori önerilmesin)
                top = max((c for c in pr if self.judge[c] and self.dist_pre[c] & self.doc_pre[pid]), key=pr.get, default=None)
                if best:
                    nb, fs, ftxt = evidence(best)
                    uncat.append(dict(base, sug_id=best, sug=self.path(best), prob=pr.get(best), strength="guclu",
                                      score=round(50 + 30 * nb + 20 * fs), **plan_fields(best),
                                      reason=f"Adında {self.words(self.dist_path[best])} geçiyor"
                                             + (f"; {ftxt}" if ftxt else "") + "."))
                elif top is not None and pr[top] >= 0.5:
                    nb, fs, ftxt = evidence(top)
                    uncat.append(dict(base, sug_id=top, sug=self.path(top), prob=pr[top], strength="olasi",
                                      score=round(min(60, 20 + 30 * pr[top] + 10 * fs)), **plan_fields(top),
                                      reason="Adı bir kategori adıyla birebir eşleşmiyor; benzer adlı ürünler bu kategoride"
                                             + (f" ({ftxt})" if ftxt else "") + ". Uygulamadan önce kontrol edin."))
                else:
                    uncat.append(dict(base, sug_id=None, sug="", prob=None, score=0, strength="yok",
                                      add=[], rem=[], add_p=[], rem_p=[],
                                      reason="Adına uyan bir kategori bulunamadı; kategoriyi elle seçin."))
                continue
            bad = [c for c in mine if self.misfit(pid, c, pr)]
            for c in mine:
                if c not in bad:
                    agree[c] += 1
            item = dict(base, cur=[self.path(c) for c in mine], cur_ids=mine, bad=[self.path(c) for c in bad])
            why_bad = "; ".join(f"adında “{self.cats[c]['name']}” kategorisinin kelimelerinden ({self.words(self.dist[c])}) "
                                f"hiçbiri yok" for c in bad)
            down = best is not None and any(m in self.ancestors(best) for m in mine)
            # mevcut kategorileri doğruysa ekleme önerisi için ürün adlarının profili de aynı yönü göstermeli
            # ("Çim Biçme Makası" Bahçe Makası'nda doğru; adında "çim biçme" geçiyor diye Çim Biçme Makineleri'ne eklenmez)
            if best is not None and not bad and not down and best in self.prior and pr.get(best, 0) < 0.05:
                best = None
            if best:
                nb, fs, ftxt = evidence(best)
                act = "tasi" if bad or down else "ekle"
                if act == "tasi":
                    own = max((pr.get(c, 0) for c in bad), default=0)
                    score = 55 + 20 * nb + 15 * fs + (10 if down else 10 * (1 - own))
                    if self.children[best]:  # alt kategorileri olan genel bir kategoriye taşımak zayıf bir öneri
                        score -= 10
                else:
                    score = 30 + 45 * nb + 25 * fs
                    # ad uyuyor ama ne benzer ürünler ne aynı seri bu kategoride ya da kategori çok genel: öneri zayıf
                    if score < 55 or self.children[best]:
                        continue
                why = f"Adında {self.words(self.dist_path[best])} geçiyor"
                if down:
                    why += "; ürün üst kategoride duruyor, uygun alt kategorisi var"
                if ftxt:
                    why += f"; {ftxt}"
                wrong.append(dict(item, act=act, sug_id=best, sug=self.path(best), prob=pr.get(best),
                                  score=round(min(score, 100)), **plan_fields(best, bad),
                                  reason=why + (f"; {why_bad}." if bad else ".")))
            elif bad and len(bad) == len(mine):
                # hiçbir kategorisine uymuyor; ürün adlarının profiline göre başka bir kategori çok daha yakınsa bildirilir
                roots = {self.root[c] for c in mine}
                alt = [c for c in pr if self.judge[c] and self.root[c] in roots
                       and self.dist_pre[c] & self.doc_pre[pid] and not any(self.related(c, m) for m in mine)]
                top = max(alt, key=pr.get) if alt else None
                if top is not None and pr[top] >= 0.8:
                    nb, fs, ftxt = evidence(top)
                    wrong.append(dict(item, act="supheli", sug_id=top, sug=self.path(top), prob=pr[top],
                                      score=round(35 + 30 * nb + 15 * fs), **plan_fields(top, bad),
                                      reason=why_bad[0].upper() + why_bad[1:] + "; benzer adlı ürünler önerilen kategoride"
                                             + (f"; {ftxt}" if ftxt else "") + "."))
        order = {"tasi": 0, "supheli": 1, "ekle": 2}
        wrong.sort(key=lambda w: (order[w["act"]], -w["score"]))
        uncat.sort(key=lambda w: -w["score"])
        newcats = self.split_suggestions() + self.spread_suggestions()
        acts = Counter(w["act"] for w in wrong)
        return {
            "v": 4, "with_parents": self.with_parents, "wrong": wrong, "uncat": uncat, "newcats": newcats,
            "categories": self.category_table(agree),
            "summary": {"urun": len(self.products), "kategori": len(self.cats),
                        "kategorisiz": len(uncat), "pasif": sum(1 for p in self.products if p.get("active") is False),
                        "tasi": acts["tasi"], "ekle": acts["ekle"], "supheli": acts["supheli"],
                        "oneri": len(newcats),
                        "az": sum(1 for c in self.cats if self.total_count(c) <= 2 and not self.children[c])},
        }

    def total_count(self, cid):
        if not hasattr(self, "_tc"):
            self._tc = Counter()
            for pid, cs in self.spec.items():
                seen = set()
                for c in cs:
                    for a in [c] + self.ancestors(c):
                        if a not in seen:
                            seen.add(a)
                            self._tc[a] += 1
        return self._tc[cid]

    def category_table(self, agree):
        out = []
        for cid in self.cats:
            n = self.n[cid]
            out.append({"id": cid, "path": self.path(cid), "depth": len(self.ancestors(cid)),
                        "direct": n, "total": self.total_count(cid), "children": len(self.children[cid]),
                        "uyum": round(100 * agree[cid] / n) if n >= MIN_DOCS else None})
        out.sort(key=lambda r: r["path"])
        return out

    # ------------------------------------------------------------ yeni kategori önerileri
    def _phrases(self, pid):
        """Ürün adının başındaki kelimelerden 1-3 kelimelik ifadeler (kök anahtarı -> kelime dizisi)."""
        tk = self.toks[pid][:6]
        out = {}
        for n in (1, 2, 3):
            for i in range(len(tk) - n + 1):
                seq = tk[i:i + n]
                out["_".join(stem(t) for t in seq)] = seq
        return out

    def _known(self, key, skip=()):
        """İfade zaten var olan bir kategoriyi karşılıyor mu? ("Abiye Elbise" -> "Kadın Abiye Elbiseler")
        skip: önerinin içine açılacağı üst kategori ve onun üstleri (onların adı ifadede geçebilir)."""
        ks = set(key.split("_"))
        for c, d in self.dist.items():
            if c not in skip and d and not d <= WEAK and d <= ks:
                return True
        return False

    def heads(self):
        """Ürün tipi bildiren kelimeler: mağazadaki kategori adlarının son kelimeleri (Elbiseler, Ayakkabılar...).
        Yeni kategori adı bunlardan biriyle bitmeli: "Abiye Elbise" olur, "Uzun Kollu" ya da "Siyah Pamuk" olmaz."""
        if not hasattr(self, "_heads"):
            out = set()
            for c in self.cats.values():
                st = [stem(t) for t in tokens(c.get("name") or "")]
                st = [s for s in st if s not in GENERIC and s not in self.common]
                if st:
                    out.add(st[-1])
            # "-ma/-me" ile biten iş adları ("temizleme", "kesme") ürün tipi değildir
            verbal = {s for s in out if len(self.word(s)) >= 5 and self.word(s).endswith(("ma", "me"))}
            self._heads = out - MATERIAL - WEAK - LINE - VERB - FILLER - verbal
        return self._heads

    def _label(self, keys_seq):
        c = Counter(" ".join(s) for s in keys_seq)
        return tr_title(c.most_common(1)[0][0])

    def _groups(self, pids, exclude_stems, min_sup, max_share=0.85, ok=None, limit=6, skip=()):
        sup, seqs = defaultdict(set), defaultdict(list)
        for pid in pids:
            for k, seq in self._phrases(pid).items():
                sup[k].add(pid)
                seqs[k].append(seq)
        N = len(pids)
        cand = []
        for k, s in sup.items():
            parts = k.split("_")
            if len(s) < min_sup or len(s) > max_share * N:
                continue
            # en az iki kelime ve bir ürün tipiyle bitmeli; "Premium ..." gibi seri adıyla başlamamalı
            if len(parts) < 2 or parts[-1] not in self.heads() or parts[0] in LINE or parts[0] in self.series:
                continue
            # ürün tipini niteleyen en az bir kelime olmalı: "Elbise Etek" yetmez, "Abiye Elbise" olur
            mods = parts[:-1]
            if any(p in FILLER for p in parts) or all(p in self.heads() or p in VERB or p in GENERIC for p in mods):
                continue
            if all(p in exclude_stems for p in parts) or self._known(k, skip):
                continue
            if ok and not ok(k, s):
                continue
            cand.append(k)

        # daha uzun ifade neredeyse aynı ürünleri kapsıyorsa kısa olanı ele (ör. "elmas" < "elmas kesme diski")
        def worth(k):
            return len(sup[k]) * (1 + 0.35 * (k.count("_")))
        cand.sort(key=worth, reverse=True)
        picked, covered = [], set()
        for k in cand:
            free = sup[k] - covered
            if len(free) < min_sup:
                continue
            if any(set(k.split("_")) <= set(j.split("_")) and len(sup[j]) >= 0.7 * len(sup[k]) for j in picked):
                continue
            picked.append(k)
            covered |= sup[k]
            if len(picked) >= limit:
                break
        return [(k, sup[k], self._label(seqs[k])) for k in picked]

    def split_suggestions(self):
        """Kalabalık kategorilerde, ortak bir ürün tipine sahip ürün gruplarını alt kategori olarak önerir."""
        by_cat = defaultdict(list)
        for pid, cs in self.spec.items():
            for c in cs:
                by_cat[c].append(pid)
        out = []
        for cid, pids in by_cat.items():
            if len(pids) < SPLIT_MIN:
                continue
            excl = set()
            for a in [cid] + self.ancestors(cid):
                excl.update(x for x in self.name_f.get(a, ()) if "_" not in x)
            min_sup = max(MIN_GROUP, round(0.08 * len(pids)))
            for k, s, label in self._groups(pids, excl, min_sup, skip={cid, *self.ancestors(cid)}):
                out.append({"kind": "alt", "parent_id": cid, "parent": self.path(cid), "label": label,
                            "count": len(s), "share": round(100 * len(s) / len(pids)),
                            "pids": sorted(s), "spread": []})
        out.sort(key=lambda r: -r["count"])
        return out

    def spread_suggestions(self):
        """Mağazanın geneline dağılmış, hiçbir kategoride toplanmamış ürün tiplerini bulur."""
        pids = [p["pid"] for p in self.products]

        def explained(pid):
            # ürün adında kendi kategorisinin adı geçiyorsa yeri belli demektir ("Abiye Elbise" -> Elbiseler)
            return any(self.dist[c] & self.docs[pid] for c in self.spec[pid])

        def scattered(k, s):
            where = Counter(c for pid in s for c in (self.spec[pid] or [None]))
            if len(where) < 3 or where.most_common(1)[0][1] / len(s) >= 0.6:
                return False
            return sum(1 for pid in s if not explained(pid)) / len(s) >= 0.6

        out = []
        for k, s, label in self._groups(pids, set(), max(15, MIN_GROUP), max_share=0.5, ok=scattered, limit=30):
            where = Counter()
            for pid in s:
                for c in self.spec[pid] or [None]:
                    where[c] += 1
            out.append({"kind": "genel", "parent_id": None, "parent": "", "label": label, "count": len(s),
                        "share": None, "pids": sorted(s),
                        "spread": [{"path": self.path(c) if c else "Kategorisiz", "n": n}
                                   for c, n in where.most_common(5)]})
        out.sort(key=lambda r: -r["count"])
        return out[:30]


def analyze(cats, products, progress=None):
    return Analyzer(cats, products).run(progress)


# ================================================================ yeni kategori SEO bilgileri
#
# Kategorilerde hedef kelime kategori adının kendisidir. Ideasoft'un SEO kuralları (ürünlerde ölçülen): sayfa başlığı
# 20-60 karakter ve hedef kelimeyi içeriyor, meta açıklama 50-155 karakter ve hedef kelimeyi içeriyor.

def category_seo(name, parent="", product_names=(), prof=None, brands=()):
    """Yeni kategori için SEO adresi, sayfa başlığı, meta açıklama ve anahtar kelimeler üretir.
    brands: kategorideki ürünlerin marka alanları; en sık geçen marka kullanılır (yoksa profildeki marka)."""
    prof = PR.load(prof)
    kw = re.sub(r"\s+", " ", name or "").strip()
    count = len([n for n in product_names if n])
    common = Counter(b for b in brands if b).most_common(1)
    brand = common[0][0] if common else prof["marka"]
    store = prof["magaza"]
    at = PR.loc(store) if store else ""
    where = parent.split(" › ")[-1] if parent else ""
    titles = [f"{kw} Modelleri ve Fiyatları | {store}", f"{kw} Fiyatları | {store}", f"{kw} | {store}"] if store else \
        [f"{kw} Modelleri ve Fiyatları", f"{kw} Fiyatları"]
    title = next((x for x in titles + [kw] if 20 <= len(x) <= 60), kw[:60])
    if at:
        metas = [f"{kw} modelleri ve fiyatları {at}. {count} farklı ürünü inceleyin, size en uygun modeli seçin.",
                 f"{kw} modelleri {at}. Ürün detaylarını inceleyin, kolayca sipariş verin.",
                 f"{kw} çeşitleri ve fiyatları {at}."]
        last = f"{kw} {at}."
    else:
        metas = [f"{kw} modelleri ve fiyatları. {count} farklı ürünü inceleyin, size en uygun modeli seçin.",
                 f"{kw} modelleri. Ürün detaylarını inceleyin, kolayca sipariş verin."]
        last = f"{kw} modelleri ve fiyatları."
    meta = next((x for x in metas if 50 <= len(x) <= 155), last[:155])
    seen, keys = set(), []
    for k in (kw, f"{brand} {kw}" if brand else "", f"{kw} fiyatları", where, store):
        if k and ST.tr_lower(k) not in seen:
            seen.add(ST.tr_lower(k))
            keys.append(k)
    out = {"slug": _slug(kw), "pageTitle": title, "metaDescription": meta, "metaKeywords": ", ".join(keys)}
    out["check"] = category_seo_check(name, out)
    return out


def _slug(s):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").translate(tr)).strip("-").lower()[:60] or "kategori"


def category_seo_check(name, seo):
    """Ideasoft'un SEO kurallarına göre kontrol listesi (hedef kelime = kategori adı) ve yüzde."""
    kwl = ST.tr_lower((name or "").strip())
    pt, md = seo.get("pageTitle") or "", seo.get("metaDescription") or ""
    rules = [
        (bool(kwl), "Kategori adı (hedef kelime) dolu"),
        (bool(pt), "Sayfa başlığı dolu"),
        (20 <= len(pt) <= 60, f"Sayfa başlığı 20-60 karakter (şu an {len(pt)})"),
        (bool(kwl) and kwl in ST.tr_lower(pt), "Kategori adı sayfa başlığında geçiyor"),
        (bool(md), "Meta açıklama dolu"),
        (50 <= len(md) <= 155, f"Meta açıklama 50-155 karakter (şu an {len(md)})"),
        (bool(kwl) and kwl in ST.tr_lower(md), "Kategori adı meta açıklamada geçiyor"),
    ]
    return {"pct": round(100 * sum(ok for ok, _ in rules) / len(rules)), "rules": [{"ok": ok, "t": t} for ok, t in rules]}
