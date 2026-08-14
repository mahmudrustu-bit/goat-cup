"""Ekibe gonderilecek prova dosyasi.

Cikti: Goat-Cup-Kurallar-Provasi.pdf  (A4, 150 DPI)
  s.1  ozet - kartlar, metin, ekipten istenen
  s.2+ her kart tam sayfa

Kullanim:  python tools/prova_pdf.py
"""
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import icerik

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

METIN = icerik.metin()

# (soru, kartta yazan cevap) - kapak dahil, karusel sirasiyla
KARTLAR = [("kapak", icerik.KAPAK_BASLIK.rstrip("?").capitalize() + "?")]
KARTLAR += [(soru, cevap.capitalize()) for soru, cevap, _ in icerik.KARTLAR]

KONTROL = icerik.KONTROL


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


def ozet_ciz(kart_olcek=1.0, metin_boy=25):
    """Ozet sayfasini cizer. Sigmazsa None doner - bkz. ozet()."""
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
    d.text((M, y), f"{len(KARTLAR)} kartlık Instagram karuseli · henüz yayınlanmadı",
           font=af, fill=INK2)

    # --- kartlar seridi ---
    y = baslik(d, y + 76, "Kartlar")
    tam_g = (W - 2 * M - (len(KARTLAR) - 1) * 22) // len(KARTLAR)
    kart_g = round(tam_g * kart_olcek)
    kart_y = round(kart_g * 1350 / 1080)
    x = M + (tam_g - kart_g) // 2
    for i in range(1, len(KARTLAR) + 1):
        with Image.open(GORSEL / f"kurallar-{i}.jpg") as k:
            img.paste(k.convert("RGB").resize((kart_g, kart_y), Image.LANCZOS), (x, y))
        d.rectangle([x, y, x + kart_g - 1, y + kart_y - 1], outline=LINE, width=1)
        d.text((x, y + kart_y + 12), f"{i:02d}", font=fnt(BODY_B, 20), fill=INK3)
        x += tam_g + 22

    # --- metin ---
    satir_y = round(metin_boy * 1.52)
    bos_y = round(metin_boy * 0.64)
    y = baslik(d, y + kart_y + 54, "Gönderi metni")
    mf = fnt(BODY, metin_boy)
    satirlar = sar(d, METIN, mf, W - 2 * M - 60)
    # Kutu yuksekligi cizim dongusuyle birebir ayni hesaplanmali; ayri
    # formul kullanmak kutuyu sisiriyordu.
    kutu_y = sum(bos_y if not s else satir_y for s in satirlar) + 56
    d.rounded_rectangle([M, y, W - M, y + kutu_y], radius=10, fill=SUNKEN)
    d.rectangle([M, y, M + 4, y + kutu_y], fill=ACCENT)

    ty = y + 28
    for s in satirlar:
        if not s:
            ty += bos_y
            continue
        d.text((M + 30, ty), s, font=mf, fill=ACCENT if s.startswith("#") else INK)
        ty += satir_y

    # --- kontrol listesi ---
    y = baslik(d, y + kutu_y + 44, "Ekipten istenen: doğrulama")
    kf = fnt(BODY, metin_boy)
    for madde in KONTROL:
        d.rounded_rectangle([M + 2, y + 4, M + 26, y + 28], radius=5, outline=TURF, width=2)
        for s in sar(d, madde, kf, W - 2 * M - 50):
            d.text((M + 46, y), s, font=kf, fill=INK)
            y += satir_y - 2
        y += 5

    if y > H - 126:
        return None  # sigmadi; cagiran daha kucuk olcekle tekrar dener

    # --- alt bilgi ---
    lg = logo(34, pembe=False)
    img.paste(lg, (M, H - 96), lg)
    ff = fnt(BODY, 20)
    bugun = date.today().strftime("%d.%m.%Y")
    d.text((W - M - d.textlength(f"Hazırlanma: {bugun}", font=ff), H - 88),
           f"Hazırlanma: {bugun}", font=ff, fill=INK3)
    return img


def ozet():
    """Sayfayi sigana kadar kucultur.

    Gonderi metni her uretimde farkli uzunlukta cikiyor; sabit olculerle
    her seferinde elle ayar gerekiyordu. Once kart seridi kuculur (sadece
    kucuk onizleme), yetmezse yazi puntosu."""
    for kart_olcek, metin_boy in [
        (1.00, 25), (0.92, 25), (0.86, 24), (0.80, 23), (0.72, 22), (0.64, 21),
    ]:
        img = ozet_ciz(kart_olcek, metin_boy)
        if img is not None:
            return img
    raise SystemExit(
        "Sayfa 1 en kucuk olcekte bile sigmadi. Gonderi metni veya "
        "dogrulama listesi kisaltilmali."
    )


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
