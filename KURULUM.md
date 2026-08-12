# GOAT CUP — Instagram Gönderim Otomasyonu

Zamanı gelen gönderiyi GitHub Actions tetikler, caption'ı Claude görseli görerek
yazar, Instagram'ın resmi Content Publishing API'si yayınlar. Bilgisayarınızın
açık olması gerekmez.

```
content/queue.json  ──►  Claude (caption + hashtag)  ──►  Meta Graph API  ──►  Instagram
      ▲                                                                            │
      └──────────────── durum geri yazılır (published / hata) ◄────────────────────┘
```

---

## Neye ihtiyacınız var

| Gereksinim | Neden |
|---|---|
| Instagram **Business** veya **Creator** hesabı | Resmi API sadece bu hesap tiplerinde yayın yapar |
| Hesaba bağlı bir **Facebook Sayfası** | Meta'nın zorunlu kıldığı bağlantı |
| **Meta for Developers** uygulaması | Token buradan çıkar |
| **GitHub** reposu (tercihen public) | Cron + görsel barındırma |
| **Anthropic API** anahtarı | Caption üretimi |

> **Neden public repo?** Instagram görseli sizden almaz, **kendisi indirir** — bu
> yüzden görselin herkese açık bir URL'de olması şart. Public repo'da
> `raw.githubusercontent.com` bedava çözüyor. Repo private olacaksa
> [Private repo](#private-repo-kullanacaksanız) bölümüne bakın.

---

## 1. Instagram hesabını hazırlayın

1. Instagram → Ayarlar → Hesap türü → **Profesyonel hesaba geç** → İşletme
2. Aynı ekrandan hesabı bir **Facebook Sayfası**'na bağlayın (sayfa yoksa oluşturun)

Hesap zaten Business ise bir şey yapmanıza gerek yok.

## 2. Meta uygulaması oluşturun

1. [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App**
2. **App details** — isim ve e-posta girin
3. **Use cases** — sol filtreden **Content management** → **"Manage messaging &
   content on Instagram"** seçeneğini işaretleyin (diğerlerini seçmeyin)
4. **Business** — Instagram hesabınızın ve Sayfanızın bağlı olduğu işletme
   portföyünü seçin. *"I don't want to connect yet" seçmeyin* — System User
   token'ı portföy gerektirir
5. **Requirements** boş gelir, geçin → **Create app**
6. Panelde **Kullanım durumları → Customize** ile izinleri kontrol edin:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `business_management`

> **App Review gerekmez.** Uygulama *Development* modundayken, uygulamanın
> yöneticisi/geliştiricisi olduğunuz hesaplarda bu izinler incelemesiz çalışır.
> Kendi hesabınıza gönderi atmak için bu yeterli.

## 3. `IG_USER_ID` değerini bulun

En kolay yol Business Suite'ten okumaktır:

```
https://business.facebook.com/latest/settings/instagram_accounts?business_id=PORTFOY_ID
```

Instagram hesabınıza tıklayın — sağda **`Kod:`** satırındaki 17 haneli sayı
(`1784...` ile başlar) `IG_USER_ID` değerinizdir.

Alternatif olarak 4. adımdaki token'ı aldıktan sonra:

```bash
python -m automation.kesfet JETONUNUZ
```

Betik hangi Sayfa'nın hangi Instagram hesabına bağlı olduğunu ve `IG_USER_ID`'yi
yazdırır; bir şey eksikse hangi izin/varlık olduğunu söyler.

> **Graph API Explorer'ı denemeyin.** Kullanım-senaryosu akışıyla oluşturulan
> uygulamalarda "User or Page" listesi *"No configurations available"* diyerek
> boş gelir — ayrı bir Facebook Login yapılandırması ister. Gereksiz.
>
> **Dikkat:** `IG_USER_ID`, Facebook Sayfa ID'si **değildir** — en sık yapılan hata budur.

## 4. Kalıcı token alın

İki yol var. **Birincisini seçin** — ikincisi 60 günde bir sizi uyandırır.

### A) System User token — süresiz (önerilen)

1. [Business Settings](https://business.facebook.com/settings) → **Users → System Users**
2. **Add** → isim verin, rol: *Admin*
3. **Add Assets** → Sayfanızı ve Instagram hesabınızı seçin, tam yetki verin
4. **Generate New Token** → uygulamanızı seçin → 2. adımdaki izinleri işaretleyin
5. Token'ı kopyalayın — **bir daha gösterilmez**

Bu token süresiz. Elle iptal etmedikçe veya şifre değiştirmedikçe çalışır.

### B) Uzun ömürlü kullanıcı token'ı — 60 gün

Graph API Explorer'dan kısa ömürlü token alıp uzatın:

```bash
curl -G "https://graph.facebook.com/v26.0/oauth/access_token" \
  -d grant_type=fb_exchange_token \
  -d client_id=UYGULAMA_ID \
  -d client_secret=UYGULAMA_GIZLI_ANAHTARI \
  -d fb_exchange_token=KISA_OMURLU_TOKEN
```

60 günde bir tekrarlayıp `IG_ACCESS_TOKEN` secret'ını güncellemeniz gerekir.
`token-kontrol.yml` workflow'u haftalık yoklama yapar ve token öldüğünde issue açar.

## 5. Anthropic API anahtarı

[console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.

## 6. GitHub'a yükleyin

```bash
cd "d:/OneDrive/Desktop/GOAT CUP"
git init
git add .
git commit -m "GOAT CUP instagram otomasyonu"
git branch -M main
git remote add origin https://github.com/KULLANICI/goat-cup.git
git push -u origin main
```

Sonra repo → **Settings → Secrets and variables → Actions** → şu üçünü ekleyin:

| Secret | Değer |
|---|---|
| `IG_USER_ID` | Adım 3'teki 17 haneli ID |
| `IG_ACCESS_TOKEN` | Adım 4'teki token |
| `ANTHROPIC_API_KEY` | Adım 5'teki anahtar |

Ayrıca **Settings → Actions → General → Workflow permissions** altında
**Read and write permissions** seçili olmalı — otomasyon `queue.json`'ı geri
commit'liyor.

## 7. Test edin

Repo → **Actions → Instagram Gönderim → Run workflow** → `dry_run` **açık**.

Bu, caption'ı üretip loga basar ama **hiçbir şey yayınlamaz**. Metin beğeninize
göreyse aynı workflow'u `dry_run` kapalı çalıştırın.

---

## Gönderi ekleme

İki adım: görseli koyun, kuyruğa satır ekleyin.

```bash
# 1. Görseli ekleyin (JPEG olmalı — aşağıdaki uyarıya bakın)
cp ~/Desktop/kontenjan.jpg content/images/
```

```jsonc
// 2. content/queue.json içindeki "posts" dizisine ekleyin
{
  "id": "2026-08-14-kontenjan",          // benzersiz, tekrar edemez
  "publish_at": "2026-08-14T18:00:00+03:00",
  "goal": "kayit",                        // aşağıdaki tabloya bakın
  "brief": "32 takım kontenjanı var...",  // Claude'a ne anlatacağını söyler
  "cta": "Ön başvuru bio linkinde",       // boş bırakılabilir
  "media": [{ "file": "kontenjan.jpg", "type": "IMAGE" }],
  "status": "pending"
}
```

Commit'leyin — gerisi otomatik. Yayınlandığında bot `status`'ü `published` yapıp
`permalink`'i geri yazar.

### `goal` değerleri

| Değer | Ne için |
|---|---|
| `kayit` | Ön başvuru toplama |
| `duyuru` | Tarih/saat/yer bildirimi |
| `fikstur` | Maç programı |
| `sonuc` | Maç sonucu, skor |
| `sponsor` | Sponsor tanıtımı |
| `geri_sayim` | "X gün kaldı" |
| `atmosfer` | Kulis, hikâye, ortam |

Her biri Claude'a farklı yazım yönergesi verir — `automation/brand.py` içinde.

### Caption'ı elle yazmak

Modeli hiç çağırmadan kendi metninizi kullanabilirsiniz:

```jsonc
{
  "id": "elle-yazilan",
  "publish_at": "2026-09-01T18:00:00+03:00",
  "caption_override": "Metin buraya.\n\n#goatcup #bartin",
  "alt_text": "Görselin tarifi.",
  "media": [{ "file": "x.jpg", "type": "IMAGE" }],
  "status": "pending"
}
```

### Karusel ve Reels

```jsonc
// Karusel: 2-10 görsel
"media": [
  { "file": "1.jpg", "type": "IMAGE" },
  { "file": "2.jpg", "type": "IMAGE" }
]

// Reels: tek video
"media": [{ "file": "ozet.mp4", "type": "VIDEO" }]
```

Karusel içinde video bu otomasyonda desteklenmiyor.

---

## ⚠️ Görsel kuralları

Meta'nın Content Publishing API'si burada katıdır — kural dışı görsel
gönderiyi patlatır:

| Kural | Değer |
|---|---|
| **Format** | **Yalnızca JPEG.** PNG kabul edilmez — logolarınızı önce JPEG'e çevirin |
| Boyut | En fazla 8 MB |
| En/boy oranı | 4:5 (dikey) ile 1.91:1 (yatay) arası |
| Genişlik | 320–1440 piksel |

Elinizdeki `goatcup-logo-*.png` dosyaları bu haliyle **yayınlanamaz**. Dönüştürme:

```bash
python -c "
from PIL import Image
im = Image.open('goatcup-logo-pembe.png').convert('RGB')
im.save('content/images/logo.jpg', quality=92)
"
```

> Not: bu kural yalnızca **yayınlanan** görsel için geçerli. Claude'a giden kopya
> otomatik olarak küçültülüp JPEG'e çevriliyor, oraya PNG verebilirsiniz.

---

## Zamanlama

Workflow günde üç kez çalışır: **12:00, 18:00, 21:00** (Türkiye saati). Her
koşuda `publish_at` değeri geçmiş olan **en eski bir** gönderiyi yayınlar.

Yani `publish_at` bir *"şu andan önce olmasın"* eşiğidir, tam saat garantisi değil
— 13:00'a ayarlanmış bir gönderi 18:00 koşusunda çıkar. GitHub cron'u ayrıca
yoğunlukta 5–15 dakika gecikebilir.

Saatleri değiştirmek için `.github/workflows/instagram-post.yml` içindeki cron
satırını düzenleyin (**UTC yazılır**, Türkiye = UTC+3):

```yaml
- cron: "0 9,15,18 * * *"   # 12:00, 18:00, 21:00 TRT
```

Bir koşuda birden fazla gönderi çıkması için `MAX_POSTS_PER_RUN` değerini artırın.

---

## Yerelde çalıştırma

```bash
pip install -r requirements.txt
cp .env.example .env        # değerleri doldurun
python -m automation.publish --dry-run
```

Faydalı komutlar:

```bash
# Belirli bir gönderinin caption'ını üret, yayınlama
python -m automation.publish --dry-run --post-id 2026-08-14-kontenjan

# Zamanına bakmadan hemen yayınla
python -m automation.publish --post-id 2026-08-14-kontenjan
```

---

## Sorun giderme

| Belirti | Sebep |
|---|---|
| `The parameter image_url is required` | Görsel URL'si dışarıdan erişilemiyor. Repo private mi? Dosya commit'lendi mi? URL'yi tarayıcıda gizli sekmede açıp deneyin |
| `Unsupported post request... media type` | Görsel PNG. JPEG'e çevirin |
| `Invalid OAuth access token` | Token süresi doldu veya iptal edildi → Adım 4 |
| `(#10) Application does not have permission` | İzinler eksik → Adım 2 |
| `The Instagram account is restricted` | Hesap Business değil veya Sayfa bağlantısı kopmuş → Adım 1 |
| `Kota dolu` | Instagram 24 saatlik yayın kotası dolmuş (hesaba göre 50-100 gönderi). Otomasyon bekler, sonraki koşuda dener |
| `unsupported version` | Graph API sürümü kapandı. Workflow'daki `GRAPH_API_VERSION` değerini güncel sürümle değiştirin |
| Gönderi çıkmadı, hata da yok | `publish_at` gelecekte mi? `status` `pending` mi? Actions loguna bakın |

Hata alan gönderi `pending` kalır ve sonraki koşuda **tekrar denenir**. Kalıcı
olarak vazgeçmek için `status` değerini elle `skipped` yapın.

---

## Private repo kullanacaksanız

`raw.githubusercontent.com` private repo'da token ister, Instagram token
gönderemez. İki seçenek:

1. **Görseller için ayrı public repo** açın, `IMAGE_BASE_URL` repo değişkenini
   (Settings → Variables) o reponun raw adresine ayarlayın.
2. **GitHub Pages** açın (public), `IMAGE_BASE_URL`'i Pages adresine ayarlayın.

---

## Maliyet

- **GitHub Actions** — public repo'da ücretsiz. Private'ta koşu başına ~1 dk.
- **Claude API** — gönderi başına yaklaşık 1 kuruşun altında. Marka brifi
  cache'lendiği için ikinci gönderiden itibaren o kısım ~%90 daha ucuz.
- **Meta Graph API** — ücretsiz.

Model ve maliyet ayarı workflow'daki `CLAUDE_EFFORT` ile yapılır
(`low` · `medium` · `high`). Caption için `medium` fazlasıyla yeterli.

---

## Dosya haritası

```
.github/workflows/
  instagram-post.yml    zamanlanmış yayın işi
  token-kontrol.yml     haftalık token yoklaması, ölürse issue açar
automation/
  brand.py              GOAT CUP marka brifi ve ses tonu  ← metin buradan ayarlanır
  captions.py           Claude çağrısı, görsel analizi, caption birleştirme
  instagram.py          Meta Graph API istemcisi
  queue.py              kuyruk okuma/yazma, zamanı gelenleri seçme
  publish.py            giriş noktası
  config.py             ortam değişkenleri
content/
  queue.json            gönderi kuyruğu       ← gönderiler buraya
  images/               görseller (JPEG)      ← görseller buraya
```

Caption'ların tonunu beğenmiyorsanız düzeltilecek yer `automation/brand.py`.
