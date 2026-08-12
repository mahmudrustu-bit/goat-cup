"""Otomasyonun giriş noktası.

Kullanım:
    python -m automation.publish                 # zamanı gelenleri yayınla
    python -m automation.publish --dry-run       # caption üret, yayınlama
    python -m automation.publish --post-id x     # belirli gönderiyi hemen yayınla
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import captions, queue as content_queue
from .captions import CaptionError, GeneratedCaption
from .config import ISTANBUL, ConfigError, Settings
from .instagram import InstagramClient, InstagramError

log = logging.getLogger("goatcup")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _summary(line: str) -> None:
    """GitHub Actions çalıştırma özetine yazar (varsa)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _build_caption(
    post: dict[str, Any], settings: Settings, now: datetime
) -> tuple[str, str | None]:
    """(caption metni, alt_text) döndürür."""
    override = post.get("caption_override")
    if override:
        log.info("[%s] caption_override kullanılıyor, model çağrılmayacak.", post["id"])
        return override, post.get("alt_text")

    image_paths = content_queue.resolve_media_paths(post)
    generated: GeneratedCaption = captions.generate_caption(
        api_key=settings.anthropic_api_key,
        model=settings.model,
        effort=settings.effort,
        brief=post["brief"],
        goal=post.get("goal", ""),
        cta_hint=post.get("cta", ""),
        image_paths=[p for p, m in zip(image_paths, post["media"]) if m.get("type", "IMAGE") == "IMAGE"],
        today=now.date(),
    )
    return captions.assemble(generated), generated.alt_text


def _process(
    post: dict[str, Any],
    *,
    settings: Settings,
    client: InstagramClient | None,
    now: datetime,
) -> bool:
    post_id = post["id"]
    log.info("── [%s] işleniyor", post_id)

    try:
        caption, alt_text = _build_caption(post, settings, now)
    except (CaptionError, content_queue.QueueError) as exc:
        log.error("[%s] caption üretilemedi: %s", post_id, exc)
        content_queue.mark_failed(post, error=str(exc), now=now)
        _summary(f"- ❌ `{post_id}` — caption üretilemedi: {exc}")
        return False

    print(f"\n{'=' * 60}\n[{post_id}] CAPTION\n{'=' * 60}\n{caption}\n{'=' * 60}\n")

    if settings.dry_run or client is None:
        log.info("[%s] dry-run — yayınlanmadı.", post_id)
        _summary(f"- 🧪 `{post_id}` — dry-run, yayınlanmadı")
        return True

    try:
        media = content_queue.media_urls(post, settings.image_base_url)
        result = client.publish_post(media=media, caption=caption, alt_text=alt_text)
    except InstagramError as exc:
        detail = f"{exc} (kod: {exc.code}, alt kod: {exc.subcode}, trace: {exc.trace})"
        log.error("[%s] yayınlanamadı: %s", post_id, detail)
        content_queue.mark_failed(post, error=detail, now=now)
        _summary(f"- ❌ `{post_id}` — yayınlanamadı: {exc}")
        return False

    content_queue.mark_published(
        post,
        media_id=result.media_id,
        permalink=result.permalink,
        caption=caption,
        now=now,
    )
    log.info("[%s] yayınlandı → %s", post_id, result.permalink or result.media_id)
    link = f"[gönderi]({result.permalink})" if result.permalink else result.media_id
    _summary(f"- ✅ `{post_id}` — yayınlandı: {link}")
    return True


def main(argv: list[str] | None = None) -> int:
    _setup_logging()

    parser = argparse.ArgumentParser(description="GOAT CUP Instagram otomasyonu")
    parser.add_argument("--dry-run", action="store_true", help="caption üret, yayınlama")
    parser.add_argument("--post-id", help="belirli bir gönderiyi zamanına bakmadan işle")
    parser.add_argument("--limit", type=int, help="bu koşuda en fazla kaç gönderi")
    args = parser.parse_args(argv)

    try:
        settings = Settings.load()
    except ConfigError as exc:
        log.error("Yapılandırma hatası: %s", exc)
        return 2

    if args.dry_run:
        settings = Settings(**{**settings.__dict__, "dry_run": True})

    now = datetime.now(ISTANBUL)
    log.info("Şu an: %s", now.isoformat(timespec="minutes"))

    try:
        data = content_queue.load_queue()
    except content_queue.QueueError as exc:
        log.error("Kuyruk hatası: %s", exc)
        return 2

    if args.post_id:
        selected = [p for p in data["posts"] if p["id"] == args.post_id]
        if not selected:
            log.error("'%s' id'li gönderi kuyrukta yok.", args.post_id)
            return 2
    else:
        selected = content_queue.due_posts(
            data, now=now, limit=args.limit or settings.max_posts_per_run
        )

    if not selected:
        log.info("Zamanı gelmiş gönderi yok. Çıkılıyor.")
        _summary("Zamanı gelmiş gönderi yok.")
        return 0

    client: InstagramClient | None = None
    if not settings.dry_run:
        client = InstagramClient(
            ig_user_id=settings.ig_user_id,
            access_token=settings.access_token,
            version=settings.graph_version,
        )
        remaining = client.remaining_quota()
        if remaining is not None:
            log.info("24 saatlik yayın kotasından kalan: %s", remaining)
            if remaining < len(selected):
                log.warning("Kota yetersiz, %s gönderiye kırpılıyor.", remaining)
                selected = selected[:remaining]
            if not selected:
                log.error("24 saatlik yayın kotası dolmuş. Sonraki koşuda denenecek.")
                _summary("⚠️ Instagram 24 saatlik yayın kotası dolu.")
                return 0

    failures = 0
    try:
        for post in selected:
            if not _process(post, settings=settings, client=client, now=now):
                failures += 1
    finally:
        # Kısmi ilerleme kaybolmasın — hata olsa da kuyruğu yaz.
        if not settings.dry_run:
            content_queue.save_queue(data)

    log.info("Bitti: %s işlendi, %s hata.", len(selected), failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
