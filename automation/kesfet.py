"""IG_USER_ID bulucu.

Graph API Explorer'la uğraşmadan, elinizdeki token ile Instagram hesap
kimliğini bulur.

Kullanım:
    python -m automation.kesfet TOKEN
    python -m automation.kesfet          # IG_ACCESS_TOKEN ortam değişkeninden
"""

from __future__ import annotations

import os
import sys

import requests

try:  # .env varsa oradan da okuyabilelim
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

VERSION = os.environ.get("GRAPH_API_VERSION", "v26.0")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    token = args[0] if args else os.environ.get("IG_ACCESS_TOKEN", "").strip()

    if not token:
        print(
            "Token verilmedi.\n\n"
            "  python -m automation.kesfet BURAYA_TOKEN\n",
            file=sys.stderr,
        )
        return 2

    print(f"Graph API {VERSION} sorgulanıyor...\n")

    response = requests.get(
        f"https://graph.facebook.com/{VERSION}/me/accounts",
        params={
            "fields": "name,instagram_business_account{id,username}",
            "access_token": token,
        },
        timeout=30,
    )
    body = response.json()

    if "error" in body:
        err = body["error"]
        print(f"HATA: {err.get('message')}", file=sys.stderr)
        print(f"  kod: {err.get('code')}  alt kod: {err.get('error_subcode')}\n", file=sys.stderr)

        code = err.get("code")
        if code == 190:
            print("-> Token geçersiz veya süresi dolmuş. Yeni token üretin.", file=sys.stderr)
        elif code in (10, 200):
            print(
                "-> Token'da izin eksik. Şunların hepsi seçili olmalı:\n"
                "  instagram_basic, instagram_content_publish, pages_show_list,\n"
                "  pages_read_engagement, business_management",
                file=sys.stderr,
            )
        return 1

    pages = body.get("data", [])
    if not pages:
        print(
            "Bu token'a bağlı Facebook Sayfası bulunamadı.\n\n"
            "Olası sebepler:\n"
            "  - System User'a Sayfa varlığı atanmamış\n"
            "  - Token'da pages_show_list izni yok",
            file=sys.stderr,
        )
        return 1

    bulundu = False
    for page in pages:
        ig = page.get("instagram_business_account")
        print(f"Sayfa: {page.get('name')}  (id {page.get('id')})")
        if ig:
            bulundu = True
            print(f"     Instagram: @{ig.get('username')}")
            print(f"     IG_USER_ID = {ig['id']}")
        else:
            print("     bağlı Instagram işletme hesabı yok")
        print()

    if not bulundu:
        print(
            "Hiçbir sayfada bağlı Instagram işletme hesabı yok.\n\n"
            "Instagram uygulamasından: Ayarlar -> Hesap türü ve araçlar ->\n"
            "hesabı İşletme yapın ve yukarıdaki sayfalardan birine bağlayın.",
            file=sys.stderr,
        )
        return 1

    print("Yukarıdaki 'IG_USER_ID =' satırındaki sayıyı GitHub Secrets'a girin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
