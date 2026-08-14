"""Kural karuselinin TEK icerik kaynagi.

kartlar.py, onizleme.py ve prova_pdf.py hepsi buradan okur. Kural
degistiginde yalnizca bu dosya duzenlenir; kartlar, HTML provasi ve PDF
provasi ayni metni gosterir.

Gonderi metni ayri: model uretiyor, snapshot'i metin.txt'de duruyor.
Yenilemek icin:  python tools/metin_uret.py
"""
from pathlib import Path

BURASI = Path(__file__).resolve().parent
METIN_DOSYASI = BURASI / "metin.txt"

KAPAK_BASLIK = "KİMLER OYNAYABİLİR?"
KAPAK_ALT = ["En çok sorulan {n} soru,", "net cevaplarıyla."]

# (soru, kartta buyuk yazan cevap, alt maddeler)
KARTLAR = [
    (
        "Takımımızda lisanslı oyuncu oynatabilir miyiz?",
        "SAHADA EN FAZLA 4 LİSANSLI",
        ["Aynı anda sahada 4 lisanslı oyuncu bulunabilir"],
    ),
    (
        "Kim lisanslı oyuncu sayılmaz?",
        "1992 ÖNCESİ VE 2007 SONRASI DOĞANLAR",
        [
            "1992 öncesi doğumlular: 35 yaş üzeri direkt lisanssız sayılır",
            "2007 sonrası doğumlular: lisansı olsa da lisanssız sayılır",
            "Son bir yıl içinde oynamamış oyuncular lisanssız sayılır",
        ],
    ),
    (
        "Yaş sınırı var mı?",
        "YAŞ SINIRI YOK",
        [
            "Ne üst ne alt yaş sınırı var",
            "18 yaş altı oyuncular veli izniyle katılabilir",
        ],
    ),
    (
        "Sonradan oyuncu alabilir miyiz?",
        "TRANSFER SERBEST",
        [
            "Turnuva boyunca istediğiniz zaman transfer yapabilirsiniz",
            "Transfer sayısında sınır yok",
            "Her transfer 5.000 TL",
        ],
    ),
]

# Ekibin PDF'te isaretleyecegi dogrulama listesi - kartlardaki her iddia.
KONTROL = [
    "Sahada aynı anda en fazla 4 lisanslı oyuncu — doğru mu?",
    "1992 öncesi doğumlular lisanssız sayılır (35 üstü) — doğru mu?",
    "2007 sonrası doğumlular, lisansı olsa da lisanssız sayılır — doğru mu?",
    "Son bir yıl içinde oynamamış oyuncular lisanssız sayılır — doğru mu?",
    "Ne üst ne alt yaş sınırı yok, 18 altı veli izniyle katılır — doğru mu?",
    "Transfer serbest, sayı sınırı yok, her transfer 5.000 TL — doğru mu?",
    "Metindeki “29 Ağustos'ta ilk düdük” tarihi doğru mu?",
]

TOPLAM_KART = len(KARTLAR) + 1  # kapak dahil


def metin() -> str:
    """Gonderi metninin son uretilmis hali."""
    if not METIN_DOSYASI.exists():
        raise SystemExit(
            f"{METIN_DOSYASI.name} yok. Once metni uretin:\n"
            "    python tools/metin_uret.py"
        )
    return METIN_DOSYASI.read_text(encoding="utf-8").strip()


def metin_parcala(ham: str | None = None) -> tuple[str, list[str], str]:
    """Metni (kanca, govde paragraflari, hashtag satiri) diye ayirir.

    Instagram akista ilk satirdan sonrasini kisaltiyor; onizlemede ayni
    davranisi taklit edebilmek icin kancayi ayirmak gerekiyor."""
    paragraflar = [p.strip() for p in (ham or metin()).split("\n\n") if p.strip()]
    if not paragraflar:
        return "", [], ""

    etiket = ""
    if paragraflar[-1].lstrip().startswith("#"):
        etiket = paragraflar.pop()

    kanca = paragraflar.pop(0) if paragraflar else ""
    return kanca, paragraflar, etiket
