"""Instagram onizleme sayfasi: tek dosyalik, calisan karusel.

Gorseller data URI olarak gomulur - dosya tek basina her tarayicida
acilir, internet gerektirmez, e-postayla/WhatsApp'la gonderilebilir.

Icerik icerik.py'den, gonderi metni tools/metin.txt'den okunur.

Kullanim:  python tools/onizleme.py
"""
import base64
import html
import io
from pathlib import Path

from PIL import Image

from icerik import KAPAK_BASLIK, KARTLAR, KONTROL, metin_parcala

KOK = Path(__file__).resolve().parent.parent
GORSEL = KOK / "content" / "images"
SABLON = Path(__file__).resolve().parent / "sablon.html"
CIKTI = KOK / "Goat-Cup-Kurallar-Provasi.html"


def veri_uri(yol: Path, genislik: int | None = None, kalite: int = 82) -> str:
    with Image.open(yol) as im:
        im = im.convert("RGB")
        if genislik and im.width > genislik:
            oran = genislik / im.width
            im = im.resize((genislik, round(im.height * oran)), Image.LANCZOS)
        tampon = io.BytesIO()
        im.save(tampon, "JPEG", quality=kalite, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(tampon.getvalue()).decode("ascii")


def avatar() -> str:
    """Logodan yuvarlak profil resmi (kare, CSS yuvarlatiyor)."""
    logo = Image.open(KOK / "goatcup-logo-pembe.png").convert("RGBA")
    logo = logo.crop(logo.getbbox())
    boy = 132
    oran = min(boy * 0.82 / logo.width, boy * 0.82 / logo.height)
    logo = logo.resize((round(logo.width * oran), round(logo.height * oran)), Image.LANCZOS)
    tuval = Image.new("RGB", (boy, boy), (6, 18, 6))
    tuval.paste(logo, ((boy - logo.width) // 2, (boy - logo.height) // 2), logo)
    tampon = io.BytesIO()
    tuval.save(tampon, "JPEG", quality=90, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(tampon.getvalue()).decode("ascii")


def main() -> None:
    yollar = [GORSEL / f"kurallar-{n}.jpg" for n in range(1, len(KARTLAR) + 2)]
    eksik = [p.name for p in yollar if not p.exists()]
    if eksik:
        raise SystemExit(
            f"Kart bulunamadi: {', '.join(eksik)}\nOnce: python tools/kartlar.py"
        )

    basliklar = [("kapak", KAPAK_BASLIK.rstrip("?").capitalize() + "?")]
    basliklar += [(soru, cevap) for soru, cevap, _ in KARTLAR]

    # Gonderide 900px yeterli (mockup 400px genis, retina icin 2x)
    buyuk = [veri_uri(p, 900) for p in yollar]
    kucuk = [veri_uri(p, 160, kalite=72) for p in yollar]

    slaytlar = "\n              ".join(
        f'<img src="{u}" alt="Kart {n}: {html.escape(basliklar[n-1][1])}" draggable="false">'
        for n, u in enumerate(buyuk, start=1)
    )

    satirlar = []
    for n, (soru, cevap) in enumerate(basliklar, start=1):
        satirlar.append(
            f'<li><button type="button">'
            f'<span class="n">{n:02d}</span>'
            f'<img src="{kucuk[n-1]}" alt="">'
            f'<span><span class="a">{html.escape(cevap)}</span><br>'
            f'<span class="q">{html.escape(soru)}</span></span>'
            f"</button></li>"
        )

    # --- gonderi metni: kanca akista gorunen kisim, gerisi "daha fazla" ---
    kanca, govde, etiket = metin_parcala()
    etiket_html = f'<span class="tags">{html.escape(etiket)}</span>' if etiket else ""
    govde_html = "\n\n".join(html.escape(p) for p in govde)

    caption = html.escape(kanca) + '<span class="rest">'
    if govde_html:
        caption += "\n\n" + govde_html
    if etiket_html:
        caption += "\n\n" + etiket_html
    caption += "</span>"

    kopya = html.escape(kanca)
    if govde_html:
        kopya += "\n\n" + govde_html
    if etiket_html:
        kopya += "\n\n" + etiket_html

    kontrol = "\n          ".join(
        f"<div><span>{html.escape(madde)}</span><b>onayınıza</b></div>"
        for madde in KONTROL
    )

    yerine = {
        "__SLIDES__": slaytlar,
        "__SHEET__": "\n          ".join(satirlar),
        "__AVATAR__": avatar(),
        "__CAPTION__": caption,
        "__COPY__": kopya,
        "__KONTROL__": kontrol,
        "__KART_SAYISI__": str(len(yollar)),
    }

    sayfa = SABLON.read_text(encoding="utf-8")
    for anahtar, deger in yerine.items():
        sayfa = sayfa.replace(anahtar, deger)

    kalan = [a for a in yerine if a in sayfa]
    if kalan:
        raise SystemExit(f"Sablonda doldurulmamis yer tutucu kaldi: {kalan}")

    CIKTI.write_text(sayfa, encoding="utf-8")
    print(f"{CIKTI.name}  {CIKTI.stat().st_size // 1024} KB  ({len(yollar)} kart)")


if __name__ == "__main__":
    main()
