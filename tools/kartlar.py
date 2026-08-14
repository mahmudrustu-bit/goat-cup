"""GOAT CUP - 'En cok sorulan kurallar' karusel kartlari.

Renkler ve tipografi Goat-Cup-On-Basvuru.html'deki koyu tema degiskenlerinden.
Icerik kullanicinin verdigi guncel kural setinden - uydurma yok.
Cikti: content/images/kurallar-1..N.jpg  (1080x1350, 4:5)

Kullanim:  python tools/kartlar.py
Kural metni icerik.py'de - kart, HTML provasi ve PDF provasi hep oradan okur.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from icerik import KAPAK_ALT, KAPAK_BASLIK, KARTLAR

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "content" / "images"
W, H = 1080, 1350
KENAR = 92
UST = 250        # eyebrow'un altindan itibaren icerik alani
ALT = H - 210    # logo ve noktalarin ustu

GROUND = (6, 18, 6)
INK = (233, 241, 230)
INK2 = (175, 194, 178)
MUTED = (140, 163, 145)
NEON = (235, 163, 213)
TURF = (76, 199, 99)
LINE = (36, 70, 43)

F = "C:/Windows/Fonts/"
DISPLAY = F + "ariblk.ttf"   # Archivo Black yedegi, markanin CSS'inde boyle
BODY = F + "segoeui.ttf"
BODY_B = F + "segoeuib.ttf"

SORU_BOY = 44
DETAY_BOY = 36


def font(yol, boy):
    return ImageFont.truetype(yol, boy)


def tracked(d, xy, metin, fnt, renk, tracking):
    """PIL'de letter-spacing yok; harf harf cizip aciyoruz."""
    x, y = xy
    for ch in metin:
        d.text((x, y), ch, font=fnt, fill=renk)
        x += d.textlength(ch, font=fnt) + tracking


def tracked_gen(d, metin, fnt, tracking):
    return d.textlength(metin, font=fnt) + tracking * max(0, len(metin) - 1)


def sar(d, metin, fnt, maks_gen):
    satirlar, gecerli = [], ""
    for kelime in metin.split():
        deneme = f"{gecerli} {kelime}".strip()
        if d.textlength(deneme, font=fnt) <= maks_gen:
            gecerli = deneme
        else:
            if gecerli:
                satirlar.append(gecerli)
            gecerli = kelime
    if gecerli:
        satirlar.append(gecerli)
    return satirlar


def sigdir(d, metin, yol, maks_gen, maks_satir, bas=126, alt=58):
    """Hem satir sayisina hem satir genisligine bakar.

    Sadece satir sayisina bakmak yetmiyor: 'OYNAMAYAN' gibi tek basina
    kutudan genis bir kelime sar() tarafindan kendi satirina konur ve
    tasar. Her satirin gercekten sigdigini de dogrulamak gerekiyor."""
    boy = bas
    while boy > alt:
        fnt = font(yol, boy)
        satirlar = sar(d, metin, fnt, maks_gen)
        sigar = all(d.textlength(s, font=fnt) <= maks_gen for s in satirlar)
        if len(satirlar) <= maks_satir and sigar:
            return fnt, satirlar
        boy -= 4
    fnt = font(yol, alt)
    return fnt, sar(d, metin, fnt, maks_gen)


def logo_getir(yukseklik):
    logo = Image.open(KOK / "goatcup-logo-pembe.png").convert("RGBA")
    logo = logo.crop(logo.getbbox())
    oran = yukseklik / logo.height
    return logo.resize((round(logo.width * oran), yukseklik), Image.LANCZOS)


def zemin():
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=NEON)
    d.rectangle([0, H - 8, W, H], fill=TURF)
    return img, d


def noktalar(d, aktif, toplam):
    r, ara = 7, 26
    genis = toplam * ara - (ara - 2 * r)
    x, y = (W - genis) // 2, H - 62
    for i in range(toplam):
        d.ellipse([x, y - r, x + 2 * r, y + r], fill=NEON if i == aktif else LINE)
        x += ara


# ------------------------------------------------------------------ kapak


def kapak(dosya, soru_sayisi):
    img, d = zemin()

    logo = logo_getir(270)
    img.paste(logo, ((W - logo.width) // 2, 210), logo)

    fnt, satirlar = sigdir(d, KAPAK_BASLIK, DISPLAY, W - 2 * KENAR, 3, 116, 76)
    y = 620
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fnt)) / 2, y), s, font=fnt, fill=INK)
        y += fnt.size * 1.06

    y += 30
    d.line([(W / 2 - 60, y), (W / 2 + 60, y)], fill=NEON, width=3)
    y += 46

    alt = font(BODY, 38)
    for satir in [s.format(n=soru_sayisi) for s in KAPAK_ALT]:
        d.text(((W - d.textlength(satir, font=alt)) / 2, y), satir, font=alt, fill=INK2)
        y += 52

    kf = font(BODY_B, 30)
    metin = "KAYDIR"
    gen = tracked_gen(d, metin, kf, 6)
    ok = font(DISPLAY, 34)
    ok_gen = d.textlength("›", font=ok)
    x0 = (W - (gen + 18 + ok_gen)) / 2
    tracked(d, (x0, H - 168), metin, kf, NEON, 6)
    d.text((x0 + gen + 18, H - 172), "›", font=ok, fill=NEON)

    img.save(dosya, "JPEG", quality=92, optimize=True, progressive=True)
    return dosya


# ------------------------------------------------------------------- kart


def kart(dosya, sira, toplam, soru, cevap, detaylar):
    img, d = zemin()
    ic = W - 2 * KENAR

    # --- once olc, sonra ciz: blok dikeyde ortalansin ---
    sf = font(BODY, SORU_BOY)
    soru_satir = sar(d, soru, sf, ic)
    cf, cevap_satir = sigdir(d, cevap, DISPLAY, ic, 3)
    df = font(BODY, DETAY_BOY)
    detay_satir = [sar(d, t, df, ic - 40) for t in detaylar]

    yuk = len(soru_satir) * 60
    yuk += 34 + len(cevap_satir) * cf.size * 1.04
    yuk += 46 + 4 + 52  # ayirici
    yuk += sum(len(s) * 50 + 14 for s in detay_satir)

    y = UST + max(0, (ALT - UST - yuk) / 2)

    # eyebrow (sabit, ustte)
    d.rectangle([KENAR, 144, KENAR + 26, 147], fill=NEON)
    tracked(d, (KENAR + 42, 132), f"SORU {sira}", font(BODY_B, 26), NEON, 4)

    for s in soru_satir:
        d.text((KENAR, y), s, font=sf, fill=INK2)
        y += 60

    y += 34
    for s in cevap_satir:
        d.text((KENAR, y), s, font=cf, fill=INK)
        y += cf.size * 1.04

    y += 46
    d.line([(KENAR, y), (KENAR + 120, y)], fill=TURF, width=4)
    y += 52

    for satirlar in detay_satir:
        d.rectangle([KENAR, y + 15, KENAR + 14, y + 18], fill=MUTED)
        for s in satirlar:
            d.text((KENAR + 40, y), s, font=df, fill=INK2)
            y += 50
        y += 14

    logo = logo_getir(52)
    img.paste(logo, (KENAR, H - 150), logo)
    noktalar(d, sira, toplam)

    img.save(dosya, "JPEG", quality=92, optimize=True, progressive=True)
    return dosya


def main():
    CIKTI.mkdir(parents=True, exist_ok=True)
    toplam = len(KARTLAR) + 1
    uretilen = [kapak(CIKTI / "kurallar-1.jpg", len(KARTLAR))]
    for i, (soru, cevap, detaylar) in enumerate(KARTLAR, start=1):
        uretilen.append(
            kart(CIKTI / f"kurallar-{i + 1}.jpg", i, toplam, soru, cevap, detaylar)
        )
    for yol in uretilen:
        print(f"  {yol.name}  {yol.stat().st_size // 1024} KB")
    print(f"\n{len(uretilen)} kart uretildi.")


if __name__ == "__main__":
    main()
