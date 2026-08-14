"""Ekibe gonderilecek prova dosyasi.

Cikti: Goat-Cup-Kurallar-Provasi.pdf  (A4, 150 DPI)
  s.1  ozet - kartlar, metin, ekipten istenen
  s.2+ her kart tam sayfa

Kullanim:  python tools/prova_pdf.py
"""
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

KOK = Path(__file__).resolve().parent.parent
GORSEL = KOK / "content" / "images"
CIKTI = KOK / "Goat-Cup-Kurallar-Provasi.pdf"

W, H = 1240, 1754          # A4 @ 150 DPI
M = 92                     # kenar bosluk

AK = (255, 255, 255)
INK = (20, 26, 21)
INK2 = (90, 102, 89)
INK3 = (128, 140, 127)
LINE = (215, 220, 211)
ACCENT = (179, 58, 134)
TURF = (31, 138, 59)
SUNKEN = (243, 245, 240)

F = "C:/Windows/Fonts/"
DISPLAY = F + "ariblk.ttf"
BODY = F + "segoeui.ttf"
BODY_B = F + "segoeuib.ttf"

METIN = """\
"Bizim takımda lisanslı var, olmaz mı?" — olur.

Kimler oynayabilir sorusunun cevabı 4 kartta duruyor: lisanslı oyuncu sınırı, \
kimin lisanslı sayılmadığı, yaş meselesi ve grup sonrası transfer hakkı.

Kaydırıp bak, kadronu ona göre kur. 29 Ağustos'ta ilk düdük çalıyor.

Aklına takılan varsa yoruma yaz, istersen DM'den de cevaplıyoruz.

#goatcup #bartin #bartinhalisaha #halisaha #halisahafutbolu #bartinspor \
#amatorfutbol #turnuva #halisahaturnuvasi #futbolturnuvasi #karadeniz #futbol"""

KARTLAR = [
    ("kapak", "Kimler oynayabilir?"),
    ("Takımımızda lisanslı oyuncu oynatabilir miyiz?", "Sahada en fazla 4 lisanslı"),
    ("Kim lisanslı oyuncu sayılmaz?", "35 üstü ve 1 yıldır oynamayan"),
    ("Yaş sınırı var mı?", "Üst yaş sınırı kaldırıldı"),
    ("Sonradan oyuncu alabilir miyiz?", "Grup sonrası 2 transfer"),
]

KONTROL = [
    "Sahada aynı anda en fazla 4 lisanslı oyuncu — doğru mu?",
    "35 yaş üzeri oyuncular lisanslı sayılmaz — doğru mu?",
    "Son bir yıl içinde oynamamış oyuncular lisanslı sayılmaz — doğru mu?",
    "Üst yaş sınırı kaldırıldı, 18 altı aile izniyle katılır — doğru mu?",
    "Grup sonrası 2 transfer, ikisi de lisanslı olabilir — doğru mu?",
    "Metindeki \u201c29 Ağustos'ta ilk düdük\u201d tarihi doğru mu?",
]


def fnt(yol, boy):
    return ImageFont.truetype(yol, boy)


def tracked(d, xy, metin, f, renk, tr):
    x, y = xy
    for ch in metin:
        d.text((x, y), ch, font=f, fill=renk)
        x += d.textlength(ch, font=f) + tr


def sar(d, metin, f, maks):
    cikti = []
    for paragraf in metin.split("\n"):
        if not paragraf.strip():
            cikti.append("")
            continue
        satir = ""
        for kelime in paragraf.split():
            deneme = f"{satir} {kelime}".strip()
            if d.textlength(deneme, font=f) <= maks:
                satir = deneme
            else:
                if satir:
                    cikti.append(satir)
                satir = kelime
        if satir:
            cikti.append(satir)
    return cikti


def baslik(d, y, metin):
    """Ince cizgili bolum basligi."""
    f = fnt(BODY_B, 21)
    tracked(d, (M, y), metin.upper(), f, INK3, 3)
    d.line([(M, y + 42), (W - M, y + 42)], fill=LINE, width=2)
    return y + 70


def logo(yukseklik, pembe=True):
    ad = "goatcup-logo-pembe.png" if pembe else "goatcup-logo-siyah.png"
    im = Image.open(KOK / ad).convert("RGBA")
    im = im.crop(im.getbbox())
    oran = yukseklik / im.height
    return im.resize((round(im.width * oran), yukseklik), Image.LANCZOS)


# ------------------------------------------------------------------ sayfa 1


def ozet():
    img = Image.new("RGB", (W, H), AK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ACCENT)

    y = 108
    d.rectangle([M, y + 12, M + 26, y + 15], fill=ACCENT)
    tracked(d, (M + 42, y), "GÖNDERİ PROVASI · @GOATCUPTR", fnt(BODY_B, 21), ACCENT, 3)

    y += 62
    bf = fnt(DISPLAY, 74)
    d.text((M, y), "KİMLER OYNAYABİLİR?", font=bf, fill=INK)

    y += 104
    af = fnt(BODY, 27)
    d.text((M, y), "5 kartlık Instagram karuseli · henüz yayınlanmadı", font=af, fill=INK2)

    # --- kartlar seridi ---
    y = baslik(d, y + 76, "Kartlar")
    kart_g = (W - 2 * M - 4 * 22) // 5
    kart_y = round(kart_g * 1350 / 1080)
    x = M
    for i in range(1, 6):
        with Image.open(GORSEL / f"kurallar-{i}.jpg") as k:
            img.paste(k.convert("RGB").resize((kart_g, kart_y), Image.LANCZOS), (x, y))
        d.rectangle([x, y, x + kart_g - 1, y + kart_y - 1], outline=LINE, width=1)
        d.text((x, y + kart_y + 12), f"{i:02d}", font=fnt(BODY_B, 20), fill=INK3)
        x += kart_g + 22

    # --- metin ---
    y = baslik(d, y + kart_y + 54, "Gönderi metni")
    mf = fnt(BODY, 25)
    satirlar = sar(d, METIN, mf, W - 2 * M - 60)
    # Kutu yuksekligi cizim dongusuyle birebir ayni hesaplanmali: dolu satir
    # 38, bos satir 16 px. Ayri formul kullanmak kutuyu sisiriyordu.
    ic_yukseklik = sum(16 if not s else 38 for s in satirlar)
    kutu_y = ic_yukseklik + 56
    d.rounded_rectangle([M, y, W - M, y + kutu_y], radius=10, fill=SUNKEN)
    d.rectangle([M, y, M + 4, y + kutu_y], fill=ACCENT)

    ty = y + 28
    for s in satirlar:
        if not s:
            ty += 16
            continue
        d.text((M + 30, ty), s, font=mf, fill=ACCENT if s.startswith("#") else INK)
        ty += 38

    # --- kontrol listesi ---
    y = baslik(d, y + kutu_y + 54, "Ekipten istenen: doğrulama")
    kf = fnt(BODY, 25)
    for madde in KONTROL:
        d.rounded_rectangle([M + 2, y + 4, M + 26, y + 28], radius=5, outline=TURF, width=2)
        for s in sar(d, madde, kf, W - 2 * M - 50):
            d.text((M + 46, y), s, font=kf, fill=INK)
            y += 36
        y += 8

    if y > H - 126:
        raise SystemExit(
            f"Sayfa 1 tasti: icerik {y}px'e kadar iniyor, sinir {H - 126}px. "
            "Kontrol listesi kisaltilmali veya kart seridi kucultulmeli."
        )

    # --- alt bilgi ---
    lg = logo(34, pembe=False)
    img.paste(lg, (M, H - 96), lg)
    ff = fnt(BODY, 20)
    bugun = date.today().strftime("%d.%m.%Y")
    d.text((W - M - d.textlength(f"Hazırlanma: {bugun}", font=ff), H - 88),
           f"Hazırlanma: {bugun}", font=ff, fill=INK3)
    return img


# --------------------------------------------------------------- kart sayfa


def kart_sayfa(i):
    img = Image.new("RGB", (W, H), AK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ACCENT)

    soru, cevap = KARTLAR[i - 1]

    y = 112
    d.rectangle([M, y + 12, M + 26, y + 15], fill=ACCENT)
    tracked(d, (M + 42, y), f"KART {i} / 5", fnt(BODY_B, 21), ACCENT, 3)

    g = 830
    yk = round(g * 1350 / 1080)
    x = (W - g) // 2
    ky = y + 66
    with Image.open(GORSEL / f"kurallar-{i}.jpg") as k:
        img.paste(k.convert("RGB").resize((g, yk), Image.LANCZOS), (x, ky))

    ty = ky + yk + 46
    if soru != "kapak":
        sf = fnt(BODY, 26)
        for s in sar(d, soru, sf, W - 2 * M):
            d.text(((W - d.textlength(s, font=sf)) / 2, ty), s, font=sf, fill=INK3)
            ty += 38
        ty += 8
    cf = fnt(BODY_B, 34)
    for s in sar(d, cevap, cf, W - 2 * M):
        d.text(((W - d.textlength(s, font=cf)) / 2, ty), s, font=cf, fill=INK)
        ty += 46

    lg = logo(30, pembe=False)
    img.paste(lg, (M, H - 92), lg)
    return img


def main():
    sayfalar = [ozet()] + [kart_sayfa(i) for i in range(1, 6)]
    sayfalar[0].save(
        CIKTI, "PDF", resolution=150.0, save_all=True, append_images=sayfalar[1:]
    )
    print(f"{CIKTI.name}  {CIKTI.stat().st_size // 1024} KB  ({len(sayfalar)} sayfa)")


if __name__ == "__main__":
    main()
