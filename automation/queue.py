"""İçerik kuyruğu — content/queue.json okuma/yazma ve zamanı gelen gönderileri seçme."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ISTANBUL, IMAGE_DIR, QUEUE_PATH

log = logging.getLogger(__name__)

# draft: issue formundan gelmiş ama henüz onaylanmamış gönderi. due_posts
# yalnızca 'pending' seçtiği için zamanlı koşular taslaklara dokunmaz.
VALID_STATUSES = {"draft", "pending", "published", "failed", "skipped"}
VALID_MEDIA_TYPES = {"IMAGE", "VIDEO"}


class QueueError(RuntimeError):
    """Kuyruk dosyası hatalı."""


def load_queue(path: Path = QUEUE_PATH) -> dict[str, Any]:
    if not path.exists():
        raise QueueError(f"Kuyruk dosyası yok: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise QueueError(f"queue.json geçerli JSON değil: {exc}") from exc

    posts = data.get("posts")
    if not isinstance(posts, list):
        raise QueueError("queue.json içinde 'posts' listesi bulunamadı.")

    seen_ids: set[str] = set()
    for index, post in enumerate(posts):
        _validate(post, index, seen_ids)
    return data


def save_queue(data: dict[str, Any], path: Path = QUEUE_PATH) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _validate(post: dict[str, Any], index: int, seen_ids: set[str]) -> None:
    where = f"posts[{index}]"

    post_id = post.get("id")
    if not post_id:
        raise QueueError(f"{where}: 'id' zorunlu.")
    if post_id in seen_ids:
        raise QueueError(f"{where}: '{post_id}' id'si birden fazla kez kullanılmış.")
    seen_ids.add(post_id)

    status = post.setdefault("status", "pending")
    if status not in VALID_STATUSES:
        raise QueueError(
            f"{where} ({post_id}): geçersiz status '{status}'. "
            f"Geçerli değerler: {', '.join(sorted(VALID_STATUSES))}"
        )

    try:
        parse_publish_at(post)
    except Exception as exc:
        raise QueueError(f"{where} ({post_id}): publish_at okunamadı — {exc}") from exc

    media = post.get("media")
    if not isinstance(media, list) or not media:
        raise QueueError(f"{where} ({post_id}): en az bir medya girmelisiniz.")
    for item in media:
        if item.get("type", "IMAGE") not in VALID_MEDIA_TYPES:
            raise QueueError(
                f"{where} ({post_id}): medya tipi IMAGE veya VIDEO olmalı."
            )
        if not item.get("file"):
            raise QueueError(f"{where} ({post_id}): medya 'file' alanı zorunlu.")

    if not post.get("brief") and not post.get("caption_override"):
        raise QueueError(
            f"{where} ({post_id}): 'brief' veya 'caption_override' gerekli."
        )


def parse_publish_at(post: dict[str, Any]) -> datetime:
    """publish_at'i timezone'lu datetime'a çevirir.

    Saat dilimi yazılmamışsa Türkiye saati varsayılır."""
    value = post.get("publish_at")
    if not value:
        raise ValueError("'publish_at' zorunlu (ISO 8601, örn. 2026-08-20T18:00:00+03:00)")
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ISTANBUL)
    return parsed


def due_posts(
    data: dict[str, Any], *, now: datetime, limit: int
) -> list[dict[str, Any]]:
    """Zamanı gelmiş, henüz yayınlanmamış gönderiler — en eskiden başlayarak."""
    ready = [
        post
        for post in data["posts"]
        if post.get("status") == "pending" and parse_publish_at(post) <= now
    ]
    ready.sort(key=parse_publish_at)

    if len(ready) > limit:
        log.info(
            "%s gönderinin zamanı gelmiş, bu koşuda ilk %s tanesi işlenecek.",
            len(ready),
            limit,
        )
    return ready[:limit]


def resolve_media_paths(post: dict[str, Any]) -> list[Path]:
    """Yerel dosya yollarını döndürür ve hepsinin var olduğunu doğrular."""
    paths = [IMAGE_DIR / item["file"] for item in post["media"]]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise QueueError(
            f"'{post['id']}' için görsel bulunamadı: {', '.join(missing)}. "
            f"Dosyaları content/images/ altına ekleyip commit'lediniz mi?"
        )
    return paths


def media_urls(post: dict[str, Any], base_url: str) -> list[dict[str, str]]:
    """Instagram'ın indireceği herkese açık URL'leri kurar."""
    from urllib.parse import quote

    return [
        {
            "url": f"{base_url}/{quote(item['file'])}",
            "type": item.get("type", "IMAGE"),
        }
        for item in post["media"]
    ]


def mark_published(
    post: dict[str, Any], *, media_id: str, permalink: str | None, caption: str, now: datetime
) -> None:
    post.update(
        status="published",
        published_at=now.isoformat(),
        media_id=media_id,
        permalink=permalink,
        caption=caption,
        error=None,
    )


def mark_failed(post: dict[str, Any], *, error: str, now: datetime) -> None:
    """Başarısız gönderi 'pending' kalır — sonraki koşuda tekrar denenir.

    Kalıcı hatalarda (ör. görsel yok) queue.json'ı elle 'skipped' yapın."""
    post.update(error=error, last_attempt_at=now.isoformat())
