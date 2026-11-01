# seovisi sunucu kurulumu

Bu rehber seovisi'yi `app.seovisi.com.tr` (canlı) ve `test.seovisi.com.tr` (test) adreslerinde çalıştırmak içindir.
Komutları sırayla kopyalayıp sunucunun terminaline yapıştırmanız yeterlidir. Takıldığınız adımda durup sorun.

## 1. Sunucuyu kiralayın (sizin işiniz)

- Türkiye'de bir sanal sunucu (KVKK için veriler yurt içinde kalır).
- Önerilen: **Ubuntu 24.04**, en az **2 işlemci, 4 GB bellek, 40 GB disk**. Birkaç yüz mağazaya yeter.
- Kiralayınca size bir **IP adresi**, kullanıcı adı ve şifre (ya da SSH anahtarı) verilir.

## 2. Alan adlarını sunucuya yönlendirin

Alan adını aldığınız firmanın panelinde (DNS ayarları) iki **A kaydı** ekleyin:

| Ad | Tür | Değer |
|---|---|---|
| `app` | A | sunucunun IP adresi |
| `test` | A | sunucunun IP adresi |

Yayılması birkaç dakika ile birkaç saat sürebilir.

## 3. Sunucuya Docker kurun

Sunucuya bağlanın (Windows'ta PowerShell: `ssh kullanici@IP-ADRESI`), sonra:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Çıkıp yeniden bağlanın (`exit`, sonra yeniden `ssh ...`).

## 4. seovisi'yi indirin

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

## 5. Gizli ayarlar

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
 "kw_loc": {"res": "product", "path": "USTAPAZARDA-BULUNAN-YER"}}
```

Test için aynısını `veri/test/sunucu.json` dosyasına `"public_url": "https://test.seovisi.com.tr"` ile yazın.
Ideasoft'taki yönlendirme adresi: `https://app.seovisi.com.tr/callback` (test için `https://test.seovisi.com.tr/callback`).
Program ilk açılışta bu dosyadaki gizli değerleri şifreler.

## 6. Başlatın

```bash
sudo chown -R 1000:1000 veri
docker compose up -d --build
docker compose ps
```

Birkaç dakika içinde `https://app.seovisi.com.tr` açılır; HTTPS sertifikasını Caddy kendisi alır ve yeniler.

## 7. Yönetici paneli ve abonelikler

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

## 8. Yedek ve izleme

- **Yedek:** her gece 03:00'te `yedekler/` klasörüne alınır, son 14 gün tutulur. Şifreleme anahtarı yedeğe girmez (yedek çalınsa da mağaza
  anahtarları okunamaz). Haftada bir yedekleri sunucu dışına da kopyalayın (ör. kendi bilgisayarınıza: `scp kullanici@IP:seovisi/yedekler/* .`).
- **Geri yükleme:** `docker compose down`, ilgili zip'i `veri/canli/` içine açın, `docker compose up -d`.
- **İzleme:** ücretsiz bir izleme hizmetinde (ör. UptimeRobot) `https://app.seovisi.com.tr/saglik` adresini 5 dakikada bir denetletin;
  erişilemezse size e-posta / SMS gelir.
- **Kayıtlar:** `docker compose logs -f app`

## 9. Güncelleme

```bash
cd ~/seovisi
GIT_SSH_COMMAND="ssh -i ~/.ssh/seovisi" git pull
docker compose up -d --build
```

Önce test ortamında denemek için yalnızca `app-test` kabını güncelleyin: `docker compose up -d --build app-test`.
