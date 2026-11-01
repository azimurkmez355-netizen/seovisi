"""Panel betiği (ui/index.html): sözdizimi ve yinelenen üst düzey adlar. Diğer testler tarayıcı tarafını çalıştırmadığı için
bir JS hatası bütün paneli durdurabilir ("Identifier 'G' has already been declared" gibi)."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

UI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "index.html")
YONETIM = os.path.join(os.path.dirname(UI), "yonetim.html")      # yönetici paneli, ayrı sayfa


def betik(yol=UI):
    with open(yol, encoding="utf-8") as f:
        html = f.read()
    return "\n".join(re.findall(r"(?is)<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html))


def ust_duzey_adlar(js):
    adlar = []
    for satir in js.splitlines():
        m = re.match(r"(let|const|var)\s+(.*)", satir)
        if m:
            # "let A = 1, B = [], C = null;" → A, B, C (yalnızca üst düzeydeki atamalar; parantez içleri atlanır)
            derinlik, parca, govde = 0, "", m.group(2)
            for ch in govde:
                derinlik += ch in "([{"
                derinlik -= ch in ")]}"
                parca += ch if derinlik == 0 and ch not in ")]}" else ""
            adlar += re.findall(r"(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?:=|;|$)", parca)
        m = re.match(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", satir)
        if m:
            adlar.append(m.group(1))
    return adlar


class Panel(unittest.TestCase):
    def test_ust_duzey_adlar_yinelenmez(self):
        adlar = ust_duzey_adlar(betik())
        self.assertGreater(len(adlar), 50)
        self.assertEqual([a for a, n in Counter(adlar).items() if n > 1], [])

    def test_oge_kimlikleri_benzersiz(self):
        # aynı kimlik iki öğede olursa $('#...') ilkini bulur; bir sayfanın düğmesi başka sayfanın işini yapar
        with open(UI, encoding="utf-8") as f:
            html = f.read()
        statik = re.findall(r'\bid="([^"$]+)"', re.sub(r"(?is)<script.*?</script>", "", html))
        self.assertEqual([k for k, n in Counter(statik).items() if n > 1], [])
        js = set(re.findall(r'\bid="([A-Za-z][\w-]*)"', betik()))        # çekmece ve pencerelerde üretilenler
        self.assertEqual(sorted(js & set(statik)), [])

    def test_yinelenen_ad_yakalanir(self):
        self.assertEqual(Counter(ust_duzey_adlar("let G = null;\nlet A = 1, G = 2;\nfunction f(){}\n"))["G"], 2)

    @unittest.skipUnless(shutil.which("node"), "Node.js yok; sözdizimi denetimi atlandı")
    def test_sozdizimi(self):
        for yol in (UI, YONETIM):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(betik(yol))
            try:
                r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(r.returncode, 0, f"{os.path.basename(yol)}: {r.stderr[-800:]}")
            finally:
                os.remove(f.name)

    def test_yonetim_sayfasi(self):
        adlar = ust_duzey_adlar(betik(YONETIM))
        self.assertEqual([a for a, n in Counter(adlar).items() if n > 1], [])
        with open(YONETIM, encoding="utf-8") as f:
            html = f.read()
        statik = re.findall(r'\bid="([^"$]+)"', re.sub(r"(?is)<script.*?</script>", "", html))
        self.assertEqual([k for k, n in Counter(statik).items() if n > 1], [])
        # betikte aranan her kimlik sayfada var
        aranan = set(re.findall(r"\$\('#([\w-]+)'\)", betik(YONETIM)))
        self.assertEqual(sorted(aranan - set(statik)), [])


if __name__ == "__main__":
    unittest.main()
