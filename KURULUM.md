# seovisi sunucu kurulumu

İki yol var:

- **A. Railway** (deneme dönemi): sunucu yönetimi yok, her şey Railway'in web sayfasından yapılır. Veriler Avrupa'da
  (Amsterdam) durur; gerçek satışa geçerken KVKK için yurt dışı aktarım hukuki metinlere yazılmalı ya da B'ye taşınmalı.
- **B. Kendi sunucunuz** (Türkiye'de VPS): `app.seovisi.com.tr` (canlı) ve `test.seovisi.com.tr` (test), Docker ve Caddy ile.

Taşımak kolaydır: verinin tamamı tek klasördedir (`/app/data`).

# A. Railway

Hepsi tarayıcıdan yapılır. Takıldığınız adımda durup sorun.

## A1. Hesap

1. https://railway.com adresinde **GitHub ile giriş** yapın.
2. **Hobby** paketine geçin (aylık 5 dolar, bu tutar kadar kullanım dahil). Ücretsiz pakette disk 0,5 GB ve bellek az; yetmez.

## A2. Proje

1. **New Project > Deploy from GitHub repo**. Railway GitHub'a erişim isterse yalnızca **seovisi** reposuna izin verin.
2. **seovisi**'yi seçin. Railway repodaki `railway.json` ve `Dockerfile` ile kurar. İlk kurulum değişkenler girilmeden
   hata verebilir; sorun değil, aşağıdaki adımlardan sonra yeniden başlar.
3. Servise tıklayın > **Settings > Region**: **EU West (Amsterdam)** (Türkiye'ye en yakın).

## A3. Disk (veriler burada durur)

Proje ekranında servise sağ tıklayın > **Attach volume** (ya da Ctrl+K, "volume"). **Mount path: `/app/data`**.
Disk olmadan her güncellemede bütün mağaza verisi silinir.

## A4. Değişkenler

Servis > **Variables > Raw Editor**, aşağıdakini yapıştırıp değerleri doldurun:

```
SEOVISI_ANAHTAR=
SEOVISI_YONETICI_PAROLA=
SEOVISI_PUBLIC_URL=https://app.seovisi.com.tr
SEOVISI_CLIENT_ID=
SEOVISI_CLIENT_SECRET=
RAILWAY_RUN_UID=0
SEOVISI_VEKIL=0.0.0.0/0,::/0
SEOVISI_IP_BASLIGI=X-Real-IP
```

- `SEOVISI_ANAHTAR`: şifreleme anahtarı. Kendi bilgisayarınızda üretin:
  `python -c "import secrets; print(secrets.token_hex(32))"`.
  **Ayrıca güvenli bir yere (parola yöneticisi) not edin.** Kaybolursa mağazalar Ideasoft'a yeniden bağlanmak zorunda kalır.
- `SEOVISI_YONETICI_PAROLA`: yönetici paneli (`/yonetim`) parolası, en az 10 karakter. Değiştirince açık oturumlar kapanır.
- `SEOVISI_PUBLIC_URL`: dışarıdan açılan adres (A5). Ideasoft'taki yönlendirme adresi bunun sonuna `/callback` eklenmiş hâli.
- `SEOVISI_CLIENT_ID` / `SEOVISI_CLIENT_SECRET`: Ideasoft uygulama anahtarları. Ideasoft verene kadar boş kalabilir;
  o zamana kadar program açılır ama mağaza girişi yapılamaz.
- Son üç satırı olduğu gibi bırakın: diske yazma izni (Railway diski yönetici kullanıcıyla bağlar) ve müşterinin gerçek
  adresinin okunması (giriş deneme sınırı için; Railway adresi `X-Real-IP` başlığıyla iletir).

Program açılışta bu değerleri diske (`sunucu.json`, gizli olanlar şifreli) yazar. Bir değişkeni silmek diskteki değeri silmez.

**Deploy** düğmesine basın.

## A5. Adres

Servis > **Settings > Networking**:

- Hemen denemek için **Generate Domain** (ör. `seovisi-production.up.railway.app`). Kapı sorulursa **8080**.
  `SEOVISI_PUBLIC_URL`'yi bu adresle değiştirin.
- Kendi adresiniz için **Custom Domain**: `app.seovisi.com.tr` yazın. Railway'in gösterdiği **CNAME** (ve varsa TXT) kaydını alan
  adını aldığınız firmanın DNS ayarlarına ekleyin. HTTPS sertifikasını Railway kendisi alır.

Kontrol: `https://ADRES/saglik` adresi `{"ok": true}` göstermeli; `https://ADRES/yonetim` yönetici girişini açmalı.

## A6. Yedek

Servis > **Backups**: **Daily** ve **Weekly**'yi seçin (günlük 6 gün, haftalık yaklaşık 1 ay tutulur). Geri yüklemek için aynı
sekmedeki **Restore**. Dikkat: diski (volume) silerseniz yedekleri de silinir; diski hiçbir zaman silmeyin.

## A7. Test ortamı (sonra, Ideasoft test mağazası gelince)

Proje ekranında üstteki ortam adı (**production**) > **New Environment** > **Duplicate**, adı `test`. Test ortamının kendi diski
ve değişkenleri olur: `SEOVISI_ANAHTAR` için yeni bir anahtar üretin, `SEOVISI_PUBLIC_URL` test adresi olsun.

## A8. Güncelleme, kayıtlar, izleme

- **Güncelleme:** GitHub'a gönderilen her değişiklik kendiliğinden yayına çıkar (birkaç dakikalık kesintiyle; diskli serviste
  Railway eskisini kapatıp yenisini açar). Servis > Settings'te **Wait for CI** seçeneğini açın: GitHub'daki testler
  geçmeden yayına çıkmaz.
- **Kayıtlar:** servis > **Deployments** > son kurulum > **View logs**.
- **Abonelikler:** yönetici panelinden (`/yonetim`).
- **İzleme:** UptimeRobot gibi bir hizmette `https://ADRES/saglik` adresini 5 dakikada bir denetletin.
- **Veri silme:** uygulamayı kaldıran mağazanın verisi 30 gün sonra kendiliğinden silinir; hemen silme yönetici panelinden.

# B. Kendi sunucunuz (VPS)

Komutları sırayla kopyalayıp sunucunun terminaline yapıştırmanız yeterlidir. Takıldığınız adımda durup sorun.

## B1. Sunucuyu kiralayın (sizin işiniz)

- Türkiye'de bir sanal sunucu (KVKK için veriler yurt içinde kalır).
- Önerilen: **Ubuntu 24.04**, en az **2 işlemci, 4 GB bellek, 40 GB disk**. Birkaç yüz mağazaya yeter.
- Kiralayınca size bir **IP adresi**, kullanıcı adı ve şifre (ya da SSH anahtarı) verilir.

## B2. Alan adlarını sunucuya yönlendirin

Alan adını aldığınız firmanın panelinde (DNS ayarları) iki **A kaydı** ekleyin:

| Ad | Tür | Değer |
|---|---|---|
| `app` | A | sunucunun IP adresi |
| `test` | A | sunucunun IP adresi |

Yayılması birkaç dakika ile birkaç saat sürebilir.

## B3. Sunucuya Docker kurun

Sunucuya bağlanın (Windows'ta PowerShell: `ssh kullanici@IP-ADRESI`), sonra:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Çıkıp yeniden bağlanın (`exit`, sonra yeniden `ssh ...`).

## B4. seovisi'yi indirin

Repo gizli olduğu için GitHub'da sunucuya yalnızca okuma izni verilir:

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/seovisi
cat ~/.ssh/seovisi.pub
```

Çıkan satırı GitHub'da **seovisi reposu > Settings > Deploy keys > Add deploy key** sayfasına yapıştırın ("Allow write access" işaretlemeyin). Sonra:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/seovisi" git clone git@github.com:azimurkmez355-netizen/seovisi.git
cd seovisi
mkdir -p veri/canli veri/test yedekler && sudo chown -R 1000:1000 veri yedekler
```

## B5. Gizli ayarlar

**Şifreleme anahtarları** (`.env`):

```bash
cp .env.ornek .env
python3 -c "import secrets; print(secrets.token_hex(32))"
python3 -c "import secrets; print(secrets.token_hex(32))"
nano .env
```

Üretilen iki uzun metni `SEOVISI_ANAHTAR=` ve `SEOVISI_ANAHTAR_TEST=` satırlarının sonuna yapıştırın, kaydedin (Ctrl+O, Enter, Ctrl+X).
**Bu iki anahtarı ayrıca güvenli bir yere (ör. parola yöneticisi) not edin.** Kaybolursa mağazalar Ideasoft'a yeniden bağlanmak zorunda kalır.

**Ideasoft uygulama anahtarları** (her ortam için ayrı):

```bash
nano veri/canli/sunucu.json
```

```json
{"client_id": "IDEASOFT-CLIENT-ID", "client_secret": "IDEASOFT-CLIENT-SECRET",
 "public_url": "https://app.seovisi.com.tr",
 "kw_loc": {"res": "product", "path": "targetKeyword"}}
```

Test için aynısını `veri/test/sunucu.json` dosyasına `"public_url": "https://test.seovisi.com.tr"` ile yazın.
Ideasoft'taki yönlendirme adresi: `https://app.seovisi.com.tr/callback` (test için `https://test.seovisi.com.tr/callback`).
Program ilk açılışta bu dosyadaki gizli değerleri şifreler.

## B6. Başlatın

```bash
sudo chown -R 1000:1000 veri
docker compose up -d --build
docker compose ps
```

Birkaç dakika içinde `https://app.seovisi.com.tr` açılır; HTTPS sertifikasını Caddy kendisi alır ve yeniler.

## B7. Yönetici paneli ve abonelikler

Yönetici parolasını bir kez belirleyin (en az 10 karakter; ekranda görünmez, iki kez sorulur). Canlı ve test için ayrı ayrı:

```bash
docker compose exec app python app.py --yonetici-parola
docker compose exec app-test python app.py --yonetici-parola
```

Sonra `https://app.seovisi.com.tr/yonetim` adresinden girin: bütün mağazalar (paket, bitiş, ürün sayısı, bağlantı, son işlem),
abonelik açma / uzatma ve son 7 günün hataları. Parolayı unutursanız aynı komutla yenisini belirleyin; açık oturumlar kapanır.
Ideasoft bildirimi gelene kadar abonelikler buradan elle açılır. Aynı işi komutla yapmak için:

```bash
docker compose exec app python app.py --abonelik magaza.com --paket baslangic --bitis 2027-10-31
docker compose exec app python app.py --abonelikler
```

## B8. Yedek ve izleme

- **Yedek:** her gece 03:00'te `yedekler/` klasörüne alınır, son 14 gün tutulur. Şifreleme anahtarı yedeğe girmez (yedek çalınsa da mağaza
  anahtarları okunamaz). Haftada bir yedekleri sunucu dışına da kopyalayın (ör. kendi bilgisayarınıza: `scp kullanici@IP:seovisi/yedekler/* .`).
- **Geri yükleme:** `docker compose down`, ilgili zip'i `veri/canli/` içine açın, `docker compose up -d`.
- **İzleme:** ücretsiz bir izleme hizmetinde (ör. UptimeRobot) `https://app.seovisi.com.tr/saglik` adresini 5 dakikada bir denetletin;
  erişilemezse size e-posta / SMS gelir.
- **Kayıtlar:** `docker compose logs -f app`
- **Veri silme:** uygulamayı kaldıran mağazanın verisi 30 gün sonra kendiliğinden silinir (yedeklerdeki kopyası 14 gün sonra gider).
  Bir mağaza verisinin silinmesini isterse (KVKK) yönetici panelinde mağazayı "Düzenle" > "Verileri kalıcı olarak sil".
  Silinen mağazalar `veri/canli/silme.log` dosyasına yazılır.

## B9. Güncelleme

```bash
cd ~/seovisi
GIT_SSH_COMMAND="ssh -i ~/.ssh/seovisi" git pull
docker compose up -d --build
```

Önce test ortamında denemek için yalnızca `app-test` kabını güncelleyin: `docker compose up -d --build app-test`.
