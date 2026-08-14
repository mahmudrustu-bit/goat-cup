"""Instagram onizleme sayfasi: tek dosyalik, calisan karusel.

Gorseller data URI olarak gomulur - dosya tek basina her tarayicida
acilir, internet gerektirmez, e-postayla/WhatsApp'la gonderilebilir.

Kullanim:  python tools/onizleme.py
"""
import base64
import io
from pathlib import Path

from PIL import Image

KOK = Path(__file__).resolve().parent.parent
GORSEL = KOK / "content" / "images"
SABLON = Path(__file__).resolve().parent / "sablon.html"
CIKTI = KOK / "Goat-Cup-Kurallar-Provasi.html"

# Kart basliklari - prova sayfasindaki metinler
KARTLAR = [
    ("", "Kimler oynayabilir?"),
    ("Takımımızda lisanslı oyuncu oynatabilir miyiz?", "Sahada en fazla 4 lisanslı"),
    ("Kim lisanslı oyuncu sayılmaz?", "35 üstü ve 1 yıldır oynamayan"),
    ("Yaş sınırı var mı?", "Üst yaş sınırı kaldırıldı"),
    ("Sonradan oyuncu alabilir miyiz?", "Grup sonrası 2 transfer"),
]


def veri_uri(yol: Path, genislik: int | None = None, kalite: int = 82) -> str:
    with Image.open(yol) as im:
        im = im.convert("RGB")
        if genislik and im.width > genislik:
            oran = genislik / im.width
            im = im.resize((genislik, round(im.height * oran)), Image.LANCZOS)
        tampon = io.BytesIO()
        im.save(tampon, "JPEG", quality=kalite, optimize=True, progressive=True)
    b64 = base64.b64encode(tampon.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


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
    yollar = [GORSEL / f"kurallar-{n}.jpg" for n in range(1, 6)]
    eksik = [p.name for p in yollar if not p.exists()]
    if eksik:
        raise SystemExit(f"Kart bulunamadi: {', '.join(eksik)}")

    # Gonderide 900px yeterli (mockup 400px genisliginde, retina icin 2x)
    buyuk = [veri_uri(p, 900) for p in yollar]
    kucuk = [veri_uri(p, 160, kalite=72) for p in yollar]

    slaytlar = "\n              ".join(
        f'<img src="{u}" alt="Kart {n}: {KARTLAR[n-1][1]}" draggable="false">'
        for n, u in enumerate(buyuk, start=1)
    )

    satirlar = []
    for n, (soru, cevap) in enumerate(KARTLAR, start=1):
        soru_html = f'<span class="q">{soru}</span>' if soru else '<span class="q">kapak</span>'
        satirlar.append(
            f'<li><button type="button">'
            f'<span class="n">{n:02d}</span>'
            f'<img src="{kucuk[n-1]}" alt="">'
            f'<span><span class="a">{cevap}</span><br>{soru_html}</span>'
            f"</button></li>"
        )

    html = SABLON.read_text(encoding="utf-8")
    html = html.replace("__SLIDES__", slaytlar)
    html = html.replace("__SHEET__", "\n          ".join(satirlar))
    html = html.replace("__AVATAR__", avatar())

    CIKTI.write_text(html, encoding="utf-8")
    print(f"{CIKTI.name}  {CIKTI.stat().st_size // 1024} KB")
    for isim in ("__SLIDES__", "__SHEET__", "__AVATAR__"):
        assert isim not in html, f"{isim} yerine kondu mu?"
    print("Tum yer tutucular dolduruldu.")


if __name__ == "__main__":
    main()
