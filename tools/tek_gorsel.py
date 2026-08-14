"""WhatsApp icin tek gorsel: butun kurallar tek karede.

Karusel kaydirmayi gerektiriyor; WhatsApp'ta tek gorsel daha rahat
iletiliyor. Icerik icerik.py'den okunur, kartlarla birebir ayni kalir.

Yukseklik icerige gore hesaplanir - kural eklenince gorsel uzar,
tasma olmaz.

Kullanim:  python tools/tek_gorsel.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from icerik import KAPAK_BASLIK, KARTLAR

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "Goat-Cup-Kurallar.jpg"

W = 1080
KENAR = 84

GROUND = (6, 18, 6)
INK = (233, 241, 230)
INK2 = (175, 194, 178)
MUTED = (140, 163, 145)
NEON = (235, 163, 213)
TURF = (76, 199, 99)
LINE = (36, 70, 43)

F = "C:/Windows/Fonts/"
DISPLAY = F + "ariblk.ttf"
BODY = F + "segoeui.ttf"
BODY_B = F + "segoeuib.ttf"

ALT_NOT = "Detaylar ve fikstür: instagram.com/goatcuptr"


def font(yol, boy):
    return ImageFont.truetype(yol, boy)


def sar(d, metin, f, maks):
    satirlar, gecerli = [], ""
    for kelime in metin.split():
        deneme = f"{gecerli} {kelime}".strip()
        if d.textlength(deneme, font=f) <= maks:
            gecerli = deneme
        else:
            if gecerli:
                satirlar.append(gecerli)
            gecerli = kelime
    if gecerli:
        satirlar.append(gecerli)
    return satirlar


def sigdir(d, metin, yol, maks, maks_satir, bas, alt):
    """Hem satir sayisi hem satir genisligi kontrol edilir."""
    boy = bas
    while boy > alt:
        f = font(yol, boy)
        satirlar = sar(d, metin, f, maks)
        if len(satirlar) <= maks_satir and all(
            d.textlength(s, font=f) <= maks for s in satirlar
        ):
            return f, satirlar
        boy -= 2
    f = font(yol, alt)
    return f, sar(d, metin, f, maks)


def tracked(d, xy, metin, f, renk, tr, ciz=True):
    x, y = xy
    for ch in metin:
        if ciz:
            d.text((x, y), ch, font=f, fill=renk)
        x += d.textlength(ch, font=f) + tr
    return x


def logo_getir(yukseklik):
    im = Image.open(KOK / "goatcup-logo-pembe.png").convert("RGBA")
    im = im.crop(im.getbbox())
    oran = yukseklik / im.height
    return im.resize((round(im.width * oran), yukseklik), Image.LANCZOS)


def yerlestir(d, img=None):
    """Tek gecisde hem olcer hem cizer.

    img None ise yalnizca olcum yapilir; boylece tuvali dogru yukseklikte
    olusturabiliyoruz."""
    ciz = img is not None
    ic = W - 2 * KENAR
    y = 92

    # --- baslik ---
    if ciz:
        lg = logo_getir(96)
        img.paste(lg, (KENAR, y), lg)
    y += 96 + 44

    bf, satirlar = sigdir(d, KAPAK_BASLIK, DISPLAY, ic, 2, 78, 52)
    for s in satirlar:
        if ciz:
            d.text((KENAR, y), s, font=bf, fill=INK)
        y += bf.size * 1.06
    y += 18

    af = font(BODY, 33)
    if ciz:
        d.text((KENAR, y), "GOAT CUP · Bartın · en çok sorulan kurallar", font=af, fill=MUTED)
    y += 52

    if ciz:
        d.rectangle([KENAR, y, KENAR + 96, y + 5], fill=NEON)
    y += 58

    # --- kural bloklari ---
    sf = font(BODY, 33)
    df = font(BODY, 31)
    nf = font(BODY_B, 25)

    for i, (soru, cevap, detaylar) in enumerate(KARTLAR, start=1):
        if i > 1:
            if ciz:
                d.line([(KENAR, y), (W - KENAR, y)], fill=LINE, width=2)
            y += 46

        if ciz:
            tracked(d, (KENAR, y), f"{i:02d}", nf, NEON, 3)
        y += 40

        for s in sar(d, soru, sf, ic):
            if ciz:
                d.text((KENAR, y), s, font=sf, fill=INK2)
            y += 44
        y += 10

        cf, csatir = sigdir(d, cevap, DISPLAY, ic, 3, 58, 34)
        for s in csatir:
            if ciz:
                d.text((KENAR, y), s, font=cf, fill=INK)
            y += cf.size * 1.08
        y += 20

        for detay in detaylar:
            if ciz:
                d.rectangle([KENAR + 2, y + 14, KENAR + 14, y + 17], fill=TURF)
            for s in sar(d, detay, df, ic - 36):
                if ciz:
                    d.text((KENAR + 34, y), s, font=df, fill=INK2)
                y += 42
            y += 8
        y += 34

    # --- alt bilgi ---
    y += 14
    if ciz:
        d.rectangle([KENAR, y, W - KENAR, y + 3], fill=TURF)
    y += 36
    ff = font(BODY_B, 29)
    if ciz:
        d.text((KENAR, y), ALT_NOT, font=ff, fill=NEON)
    y += 62

    return round(y)


def main():
    olcum = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    H = yerlestir(olcum)

    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=NEON)
    d.rectangle([0, H - 8, W, H], fill=TURF)
    yerlestir(d, img)

    img.save(CIKTI, "JPEG", quality=90, optimize=True, progressive=True)
    kb = CIKTI.stat().st_size // 1024
    print(f"{CIKTI.name}  {W}x{H}  {kb} KB  (oran 1:{H / W:.2f})")


if __name__ == "__main__":
    main()
