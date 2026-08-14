"""Gonderi metnini uretip tools/metin.txt'e yazar.

Provalar (HTML ve PDF) bu dosyayi okur, boylece uc yerde ayri metin
tutulmuyor. Yayin sirasinda otomasyon metni yeniden uretir - bu dosya
yalnizca prova icindir.

Kullanim:  python tools/metin_uret.py [gonderi-id]
"""
import sys
from datetime import datetime
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from automation import queue as content_queue  # noqa: E402
from automation.config import ISTANBUL, Settings  # noqa: E402
from automation.publish import _build_caption  # noqa: E402

HEDEF = Path(__file__).resolve().parent / "metin.txt"


def main() -> int:
    post_id = sys.argv[1] if len(sys.argv) > 1 else "kurallar-sss"

    data = content_queue.load_queue()
    secili = [p for p in data["posts"] if p["id"] == post_id]
    if not secili:
        print(f"'{post_id}' kuyrukta yok.", file=sys.stderr)
        return 1

    caption, _alt = _build_caption(secili[0], Settings.load(), datetime.now(ISTANBUL))
    HEDEF.write_text(caption + "\n", encoding="utf-8")

    print(f"{HEDEF.name} yazildi - {len(caption)} karakter\n")
    print(caption)
    return 0


if __name__ == "__main__":
    sys.exit(main())
