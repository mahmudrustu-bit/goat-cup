"""GitHub Issue formundan gönderi oluşturma.

Akış:
  1. Kullanıcı "Yeni gönderi" formunu doldurur -> issue açılır.
  2. hazirla : form okunur, görseller repoya indirilir, kuyruğa TASLAK eklenir,
               metin üretilip issue'ya yorum olarak yazılır. Yayın yapılmaz.
  3. Kullanıcı beğenirse issue'ya 'onay' etiketini ekler.
  4. onayla  : taslak 'pending' olur. Tarih geçmişse hemen yayınlanır,
               ileriyse cron zamanı gelince yayınlar.
  5. bildir  : sonucu issue'ya yorum olarak yazar.

Kuyruktaki id her zaman "issue-<numara>" - yani formu düzenlemek yeni gönderi
oluşturmaz, mevcut taslağın üstüne yazar.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from . import captions, queue as content_queue
from .config import ISTANBUL, IMAGE_DIR

# --- Instagram medya sınırları (Content Publishing API) ---
MIN_WIDTH = 320
MAX_WIDTH = 1440
MIN_ASPECT = 0.8  # 4:5 dikey
MAX_ASPECT = 1.91  # 1.91:1 yatay
MAX_BYTES = 8 * 1024 * 1024
MAX_CAROUSEL = 10

# --- Form alan başlıkları. gonderi.yml'deki 'label' değerleriyle birebir aynı olmalı. ---
F_MEDIA = "Görseller"
F_DATE = "Yayın tarihi"
F_TIME = "Saat"
F_GOAL = "Amaç"
F_BRIEF = "Ne anlatalım?"
F_CTA = "Yönlendirme (isteğe bağlı)"
F_TEXT = "Metni kendim yazacağım (isteğe bağlı)"

GOAL_MAP = {
    "Kayıt çağrısı": "kayit",
    "Duyuru": "duyuru",
    "Fikstür": "fikstur",
    "Maç sonucu": "sonuc",
    "Sponsor": "sponsor",
    "Geri sayım": "geri_sayim",
    "Atmosfer": "atmosfer",
}

AYLAR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]

EMPTY = {"", "_no response_", "_none_"}


class FormError(RuntimeError):
    """Form eksik veya hatalı doldurulmuş."""


# --------------------------------------------------------------- form okuma


def _sections(body: str) -> dict[str, str]:
    """Issue gövdesini '### Başlık' bloklarına ayırır.

    GitHub issue form'ları gövdeyi hep bu biçimde üretir; doldurulmayan
    isteğe bağlı alanlar '_No response_' olarak gelir."""
    out: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    for line in body.replace("\r\n", "\n").split("\n"):
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            if current is not None:
                out[current] = "\n".join(buffer).strip()
            current = heading.group(1)
            buffer = []
        elif current is not None:
            buffer.append(line)

    if current is not None:
        out[current] = "\n".join(buffer).strip()
    return out


def _value(sections: dict[str, str], label: str) -> str:
    raw = sections.get(label, "").strip()
    return "" if raw.lower() in EMPTY else raw


def _extract_urls(section: str) -> list[str]:
    """Markdown görsel bağlantılarını ve çıplak URL'leri sırayla toplar."""
    urls: list[str] = []
    seen: set[str] = set()

    patterns = [
        r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?[^)]*\)",  # ![alt](url "title")
        r"""<img[^>]+src=["']([^"']+)["']""",  # <img src="...">
        # GitHub gömemediği ekleri (HEIC, TIFF...) düz bağlantı olarak yazar.
        r"\[[^\]]*\]\(\s*<?(https://github\.com/user-attachments/[^)\s>]+)",
        r"(?<![(\"'=])\bhttps?://\S+",  # tek başına duran URL
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, section):
            url = (match.group(1) if match.groups() else match.group(0)).strip().rstrip(">)")
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _parse_when(date_text: str, time_text: str, now: datetime) -> datetime:
    """Tarih + saati Türkiye saatinde datetime'a çevirir.

    Tarih boşsa 'hemen' demektir - now döner."""
    if not date_text:
        return now

    cleaned = date_text.strip()
    day: int | None = None
    month: int | None = None
    year = now.year

    iso = re.match(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$", cleaned)
    if iso:
        year, month, day = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
    else:
        tr = re.match(r"^(\d{1,2})[-./](\d{1,2})(?:[-./](\d{2,4}))?$", cleaned)
        if not tr:
            raise FormError(
                f"Yayın tarihi anlaşılmadı: '{date_text}'. "
                "2026-08-20 veya 20.08.2026 biçiminde yazın."
            )
        day, month = int(tr.group(1)), int(tr.group(2))
        if tr.group(3):
            year = int(tr.group(3))
            if year < 100:
                year += 2000

    hour, minute = 18, 0
    if time_text:
        clock = re.match(r"^(\d{1,2})(?:[:.](\d{2}))?$", time_text.strip())
        if not clock:
            raise FormError(f"Saat anlaşılmadı: '{time_text}'. 18:00 biçiminde yazın.")
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)

    try:
        when = datetime(year, month, day, hour, minute, tzinfo=ISTANBUL)
    except ValueError as exc:
        raise FormError(f"Geçersiz tarih/saat: {exc}") from exc

    # Yıl yazılmadıysa ve tarih geçmişte kaldıysa gelecek yıl kastedilmiştir.
    if not re.search(r"\d{4}", cleaned) and when < now - timedelta(days=1):
        when = when.replace(year=year + 1)
    return when


def _format_when(when: datetime) -> str:
    return f"{when.day} {AYLAR[when.month - 1]} {when.year}, {when:%H:%M}"


# ------------------------------------------------------------ görsel indirme


def _download(url: str) -> bytes:
    """Issue ekini indirir.

    Public repo'da eklentiler kimlik doğrulaması istemez; private'a
    dönülürse GITHUB_TOKEN ile ilk atlama yeniden denenir."""
    try:
        response = requests.get(url, timeout=90)
        if response.ok and response.content:
            return response.content
        status = response.status_code
    except requests.RequestException as exc:
        raise FormError(f"Görsel indirilemedi ({url}): {exc}") from exc

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and status in (401, 403, 404):
        # Authorization başlığını yalnızca github.com'a gönder; imzalı
        # depolama adresi kendi kimlik doğrulamasını kullanıyor.
        first = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            allow_redirects=False,
            timeout=90,
        )
        target = first.headers.get("Location")
        if target:
            second = requests.get(target, timeout=90)
            if second.ok and second.content:
                return second.content
        elif first.ok and first.content:
            return first.content

    raise FormError(
        f"Görsel indirilemedi (HTTP {status}): {url}\n"
        "Dosyayı forma yeniden sürükleyip issue'yu kaydedin."
    )


def _to_jpeg(raw: bytes, dest: Path) -> tuple[int, int]:
    """PNG/HEIC/JPEG farketmez - Instagram'ın kabul ettiği JPEG'e çevirir.

    (genişlik, yükseklik) döner."""
    try:
        opened = Image.open(io.BytesIO(raw))
        opened.load()
    except Exception as exc:  # Pillow çok çeşitli istisna atıyor
        raise FormError(
            "Dosya görsel olarak açılamadı. Muhtemel sebepler:\n"
            "- iPhone'dan HEIC olarak yüklenmiş: Fotoğraflar > Paylaş > "
            "'En Uyumlu' seçeneğiyle yeniden gönderin ya da ekran görüntüsü alın.\n"
            "- Video yüklenmiş: video bu formdan gönderilemiyor, "
            "queue.json'a elle satır ekleyin."
        ) from exc

    if opened.mode in ("RGBA", "LA", "P"):
        rgba = opened.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        image = flat
    else:
        image = opened.convert("RGB")

    width, height = image.size
    if width > MAX_WIDTH:
        height = max(1, round(height * MAX_WIDTH / width))
        width = MAX_WIDTH
        image = image.resize((width, height), Image.LANCZOS)

    dest.parent.mkdir(parents=True, exist_ok=True)
    quality = 88
    while True:
        image.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
        if dest.stat().st_size <= MAX_BYTES or quality <= 60:
            break
        quality -= 10

    return width, height


def _media_note(width: int, height: int) -> str:
    """Instagram sınırlarına göre kısa uyarı metni (sorun yoksa 'uygun')."""
    if width < MIN_WIDTH:
        return f"cok kucuk (en az {MIN_WIDTH}px genislik)"
    aspect = width / height
    if aspect < MIN_ASPECT:
        return f"cok uzun ({aspect:.2f}), Instagram kirpar - 4:5 yapin"
    if aspect > MAX_ASPECT:
        return f"cok genis ({aspect:.2f}), Instagram kirpar - 1.91:1 yapin"
    return "uygun"


# ----------------------------------------------------------------- yardımcı


def _gh_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")


def _find(data: dict[str, Any], post_id: str) -> dict[str, Any] | None:
    for post in data["posts"]:
        if post.get("id") == post_id:
            return post
    return None


def _write(path: Path | None, text: str) -> None:
    if path:
        path.write_text(text, encoding="utf-8")


# ------------------------------------------------------------------ hazirla


def _build_post(issue: int, body: str, now: datetime) -> tuple[dict[str, Any], list[str]]:
    """Form gövdesinden kuyruk nesnesi ve görsel notlarını üretir."""
    sections = _sections(body)
    if not sections:
        raise FormError(
            "Issue gövdesi form biçiminde değil. Gönderi eklemek için "
            "'New issue' > 'Yeni gönderi' şablonunu kullanın."
        )

    brief = _value(sections, F_BRIEF)
    override = _value(sections, F_TEXT)
    if not brief and not override:
        raise FormError("'Ne anlatalım?' alanı boş. Ne paylaşacağınızı yazın.")

    goal_label = _value(sections, F_GOAL)
    goal = GOAL_MAP.get(goal_label, "duyuru")

    when = _parse_when(_value(sections, F_DATE), _value(sections, F_TIME), now)

    urls = _extract_urls(sections.get(F_MEDIA, ""))
    if not urls:
        raise FormError(
            "Görsel bulunamadı. Dosyayı 'Görseller' kutusunun içine sürükleyin "
            "(yorum kutusuna değil)."
        )
    if len(urls) > MAX_CAROUSEL:
        raise FormError(
            f"{len(urls)} görsel eklenmiş. Instagram karusel sınırı {MAX_CAROUSEL}."
        )

    post_id = f"issue-{issue}"
    media: list[dict[str, str]] = []
    notes: list[str] = []
    kept: set[str] = set()

    for index, url in enumerate(urls, start=1):
        name = f"{post_id}-{index}.jpg"
        width, height = _to_jpeg(_download(url), IMAGE_DIR / name)
        media.append({"file": name, "type": "IMAGE"})
        notes.append(f"| {index} | `{name}` | {width}x{height} | {_media_note(width, height)} |")
        kept.add(name)

    # Form düzenlenip görsel sayısı azaldıysa artakalan dosyaları temizle.
    for stale in IMAGE_DIR.glob(f"{post_id}-*.jpg"):
        if stale.name not in kept:
            stale.unlink()

    post: dict[str, Any] = {
        "id": post_id,
        "publish_at": when.isoformat(),
        "goal": goal,
        "brief": brief,
        "cta": _value(sections, F_CTA),
        "media": media,
        "status": "draft",  # onaylanana kadar cron dokunmaz
        "issue": issue,
    }
    if override:
        post["caption_override"] = override
    return post, notes


def cmd_hazirla(args: argparse.Namespace) -> int:
    issue = args.issue
    comment_path = Path(args.comment_out) if args.comment_out else None
    body = os.environ.get(args.body_env, "")
    now = datetime.now(ISTANBUL)

    try:
        data = content_queue.load_queue()
        # Yayınlanmış gönderinin görselini indirip üzerine yazmayalım.
        existing = _find(data, f"issue-{issue}")
        if existing is not None and existing.get("status") == "published":
            print("Bu issue'nun gonderisi zaten yayinlanmis, dokunulmuyor.")
            _write(
                comment_path,
                "## Bu gönderi zaten yayınlandı\n\n"
                "Formu düzenlemek yayındaki gönderiyi değiştirmez. "
                "Yeni bir gönderi için yeni issue açın.\n\n"
                f"{existing.get('permalink') or ''}\n",
            )
            _gh_output("ok", "false")
            return 0
        post, notes = _build_post(issue, body, now)
    except (FormError, content_queue.QueueError) as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        _write(
            comment_path,
            "## Gönderi hazırlanamadı\n\n"
            f"> {exc}\n\n"
            "Formu düzeltip kaydedin (başlıktaki kalem ikonu), yeniden denenir.\n",
        )
        _gh_output("ok", "false")
        return 1

    if existing is not None:
        # Form düzenlenmiş: aynı kaydın üstüne yaz, kuyrukta çoğaltma.
        existing.clear()
        existing.update(post)
        post = existing
    else:
        data["posts"].append(post)

    # Metni üret - hata olursa taslak yine kuyruğa yazılsın diye ayrı try.
    caption = ""
    alt_text = ""
    caption_error = ""
    try:
        if post.get("caption_override"):
            caption = post["caption_override"]
            alt_text = "(elle yazılmış gönderi - alt metin üretilmedi)"
        else:
            generated = captions.generate_caption(
                api_key=os.environ["ANTHROPIC_API_KEY"],
                model=os.environ.get("CLAUDE_MODEL", "claude-opus-5"),
                effort=os.environ.get("CLAUDE_EFFORT", "medium"),
                brief=post["brief"],
                goal=post.get("goal", ""),
                cta_hint=post.get("cta", ""),
                image_paths=content_queue.resolve_media_paths(post),
                today=now.date(),
            )
            caption = captions.assemble(generated)
            alt_text = generated.alt_text
            post["alt_text"] = alt_text
    except Exception as exc:  # metin üretimi kritik değil, taslak durur
        caption_error = str(exc)
        print(f"Metin uretilemedi: {exc}", file=sys.stderr)

    content_queue.save_queue(data)
    print(f"Taslak kuyruga yazildi: {post['id']}")

    when = content_queue.parse_publish_at(post)
    zamanlama = (
        "Onay verdiğiniz an yayınlanır."
        if when <= now + timedelta(minutes=2)
        else f"**{_format_when(when)}** (Türkiye saati) için planlandı."
    )

    lines = [
        "## Önizleme",
        "",
        f"**Zamanlama:** {zamanlama}  ",
        f"**Amaç:** `{post.get('goal')}` · **Görsel:** {len(post['media'])} adet · "
        f"**Kuyruk id:** `{post['id']}`",
        "",
    ]

    if caption_error:
        lines += [
            "### Metin üretilemedi",
            "",
            f"> {caption_error}",
            "",
            "Görseller ve taslak kaydedildi. Formu kaydedip yeniden deneyebilir "
            "veya metni 'Metni kendim yazacağım' alanına elle yazabilirsiniz.",
            "",
        ]
    else:
        lines += [
            f"### Metin ({len(caption)} karakter)",
            "",
            "```text",
            caption,
            "```",
            "",
            "**Görsel açıklaması (alt text):**",
            f"> {alt_text}",
            "",
        ]

    lines += [
        "### Görseller",
        "",
        "| # | Dosya | Boyut | Durum |",
        "|---|---|---|---|",
        *notes,
        "",
        "---",
        "",
        "- Beğendiyseniz bu issue'ya **`onay`** etiketini ekleyin.",
        "- Beğenmediyseniz **formu düzenleyin** (başlıktaki kalem) - metin yeniden üretilir.",
        "- Vazgeçtiyseniz issue'yu kapatın, taslak kuyrukta kalır ama yayınlanmaz.",
    ]

    _write(comment_path, "\n".join(lines) + "\n")
    _gh_output("ok", "true")
    return 0


# ------------------------------------------------------------------- onayla


def cmd_onayla(args: argparse.Namespace) -> int:
    post_id = f"issue-{args.issue}"
    now = datetime.now(ISTANBUL)

    data = content_queue.load_queue()
    post = _find(data, post_id)
    if post is None:
        print(f"HATA: '{post_id}' kuyrukta yok. Once form islenmeli.", file=sys.stderr)
        _gh_output("publish_now", "false")
        _gh_output("durum", "yok")
        return 1

    if post.get("status") == "published":
        print("Zaten yayinlanmis, tekrar yayinlanmayacak.")
        _gh_output("publish_now", "false")
        _gh_output("durum", "zaten-yayinda")
        return 0

    post["status"] = "pending"
    content_queue.save_queue(data)

    when = content_queue.parse_publish_at(post)
    due = when <= now + timedelta(minutes=2)
    print(f"Onaylandi. Yayin zamani {when.isoformat()} - hemen: {due}")
    _gh_output("publish_now", "true" if due else "false")
    _gh_output("durum", "hemen" if due else "planlandi")
    return 0


# ------------------------------------------------------------------- bildir


def cmd_bildir(args: argparse.Namespace) -> int:
    post_id = f"issue-{args.issue}"
    comment_path = Path(args.comment_out) if args.comment_out else None

    data = content_queue.load_queue()
    post = _find(data, post_id)
    if post is None:
        _write(comment_path, f"`{post_id}` kuyrukta bulunamadı.\n")
        _gh_output("kapat", "false")
        return 1

    status = post.get("status")
    if status == "published":
        link = post.get("permalink")
        body = (
            "## Yayınlandı\n\n"
            + (f"{link}\n" if link else f"Instagram medya id: `{post.get('media_id')}`\n")
        )
        _gh_output("kapat", "true")
    elif post.get("error"):
        body = (
            "## Yayınlanamadı\n\n"
            f"> {post['error']}\n\n"
            "Kuyrukta `pending` olarak duruyor; sonraki zamanlı koşuda yeniden denenecek. "
            "Kalıcı bir hataysa (ör. görsel bozuk) formu düzeltin.\n"
        )
        _gh_output("kapat", "false")
    else:
        when = content_queue.parse_publish_at(post)
        body = (
            "## Onaylandı, sıraya alındı\n\n"
            f"**{_format_when(when)}** (Türkiye saati) civarında yayınlanacak.\n\n"
            "Zamanlı koşular 12:00 / 18:00 / 21:00'de çalışır, yayın en yakın koşuda gerçekleşir.\n\n"
            "Vazgeçerseniz `onay` etiketini kaldırmak yetmez - "
            "[queue.json](../../blob/main/content/queue.json) içinde bu gönderinin "
            "`status` alanını `skipped` yapın.\n"
        )
        _gh_output("kapat", "false")

    _write(comment_path, body)
    return 0


# --------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue formundan gönderi")
    subs = parser.add_subparsers(dest="komut", required=True)

    hazirla = subs.add_parser("hazirla", help="formu oku, taslak oluştur, metni üret")
    hazirla.add_argument("--issue", type=int, required=True)
    hazirla.add_argument("--body-env", default="ISSUE_BODY", help="gövdeyi taşıyan ortam değişkeni")
    hazirla.add_argument("--comment-out", help="issue yorumunun yazılacağı dosya")
    hazirla.set_defaults(func=cmd_hazirla)

    onayla = subs.add_parser("onayla", help="taslağı yayına al")
    onayla.add_argument("--issue", type=int, required=True)
    onayla.set_defaults(func=cmd_onayla)

    bildir = subs.add_parser("bildir", help="sonucu yorum olarak hazırla")
    bildir.add_argument("--issue", type=int, required=True)
    bildir.add_argument("--comment-out")
    bildir.set_defaults(func=cmd_bildir)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
