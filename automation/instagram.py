"""Instagram Content Publishing API (Meta Graph API) istemcisi.

Yayın akışı iki adımlıdır:
  1. Konteyner oluştur  -> POST /{ig-user-id}/media
  2. Konteyneri yayınla -> POST /{ig-user-id}/media_publish

Instagram görseli/videoyu KENDİSİ indirir; bu yüzden medya herkese açık bir
URL'de olmak zorunda. Yerel dosya yükleme diye bir şey yok.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

log = logging.getLogger(__name__)

TIMEOUT = 60
POLL_INTERVAL = 5
POLL_MAX_ATTEMPTS = 60  # video işleme birkaç dakika sürebilir
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


class InstagramError(RuntimeError):
    """Graph API hatası."""

    def __init__(self, message: str, *, code: Any = None, subcode: Any = None, trace: Any = None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode
        self.trace = trace


@dataclass
class PublishResult:
    media_id: str
    permalink: str | None


class InstagramClient:
    def __init__(self, *, ig_user_id: str, access_token: str, version: str = "v26.0"):
        self.ig_user_id = ig_user_id
        self.access_token = access_token
        self.base = f"https://graph.facebook.com/{version}"
        self.session = requests.Session()

    # ------------------------------------------------------------------ HTTP

    def _request(self, method: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base}/{path.lstrip('/')}"
        payload = {**params, "access_token": self.access_token}

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.request(
                    method,
                    url,
                    data=payload if method == "POST" else None,
                    params=payload if method == "GET" else None,
                    timeout=TIMEOUT,
                )
            except requests.RequestException as exc:
                last_error = exc
                log.warning("Ağ hatası (deneme %s/3): %s", attempt, exc)
                time.sleep(2**attempt)
                continue

            if response.status_code in RETRYABLE_HTTP and attempt < 3:
                log.warning(
                    "Geçici hata %s (deneme %s/3): %s",
                    response.status_code,
                    attempt,
                    response.text[:300],
                )
                time.sleep(2**attempt)
                continue

            try:
                body = response.json()
            except ValueError:
                raise InstagramError(
                    f"Graph API JSON olmayan yanıt döndürdü ({response.status_code}): "
                    f"{response.text[:300]}"
                )

            if "error" in body:
                err = body["error"]
                raise InstagramError(
                    err.get("message", "bilinmeyen hata"),
                    code=err.get("code"),
                    subcode=err.get("error_subcode"),
                    trace=err.get("fbtrace_id"),
                )
            return body

        raise InstagramError(f"Graph API'ye 3 denemede ulaşılamadı: {last_error}")

    # ------------------------------------------------------------ Kota

    def remaining_quota(self) -> int | None:
        """24 saatlik yayın kotasından kalan gönderi sayısı (Meta sınırı: 50).

        Kota okunamazsa None döner — bu yüzden yayını engellemeyiz."""
        try:
            body = self._request(
                "GET",
                f"{self.ig_user_id}/content_publishing_limit",
                {"fields": "config,quota_usage"},
            )
        except InstagramError as exc:
            log.warning("Kota okunamadı, yayına devam ediliyor: %s", exc)
            return None

        data = (body.get("data") or [{}])[0]
        used = data.get("quota_usage", 0)
        total = (data.get("config") or {}).get("quota_total", 50)
        return max(total - used, 0)

    # ------------------------------------------------- Konteyner oluşturma

    def create_image_container(
        self,
        *,
        image_url: str,
        caption: str | None = None,
        alt_text: str | None = None,
        is_carousel_item: bool = False,
    ) -> str:
        params: dict[str, Any] = {"image_url": image_url}
        if is_carousel_item:
            params["is_carousel_item"] = "true"
        else:
            if caption:
                params["caption"] = caption
        if alt_text:
            params["alt_text"] = alt_text
        return self._request("POST", f"{self.ig_user_id}/media", params)["id"]

    def create_reel_container(
        self,
        *,
        video_url: str,
        caption: str | None = None,
        cover_url: str | None = None,
        share_to_feed: bool = True,
    ) -> str:
        params: dict[str, Any] = {
            "media_type": "REELS",
            "video_url": video_url,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if caption:
            params["caption"] = caption
        if cover_url:
            params["cover_url"] = cover_url
        return self._request("POST", f"{self.ig_user_id}/media", params)["id"]

    def create_carousel_container(self, *, children: list[str], caption: str | None) -> str:
        if not 2 <= len(children) <= 10:
            raise InstagramError(
                f"Karusel 2-10 medya içermeli, {len(children)} verildi."
            )
        params: dict[str, Any] = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
        }
        if caption:
            params["caption"] = caption
        return self._request("POST", f"{self.ig_user_id}/media", params)["id"]

    # ----------------------------------------------------------- Yayınlama

    def wait_until_ready(self, container_id: str) -> None:
        """Konteyner FINISHED olana kadar bekler.

        Görseller genelde anında hazır; video/reels işlenmesi dakikalar sürebilir."""
        for attempt in range(POLL_MAX_ATTEMPTS):
            body = self._request(
                "GET", container_id, {"fields": "status_code,status"}
            )
            status = body.get("status_code")

            if status == "FINISHED":
                return
            if status in {"ERROR", "EXPIRED"}:
                raise InstagramError(
                    f"Konteyner {container_id} durumu {status}: {body.get('status', '')}"
                )
            log.info(
                "Konteyner %s hazırlanıyor (%s), %s sn bekleniyor…",
                container_id,
                status,
                POLL_INTERVAL,
            )
            time.sleep(POLL_INTERVAL)

        raise InstagramError(
            f"Konteyner {container_id} {POLL_MAX_ATTEMPTS * POLL_INTERVAL} sn içinde hazır olmadı."
        )

    def publish(self, container_id: str) -> PublishResult:
        media_id = self._request(
            "POST", f"{self.ig_user_id}/media_publish", {"creation_id": container_id}
        )["id"]

        permalink = None
        try:
            permalink = self._request("GET", media_id, {"fields": "permalink"}).get(
                "permalink"
            )
        except InstagramError as exc:
            # Yayın başarılı; sadece link okunamadı — hata sayma.
            log.warning("Permalink okunamadı: %s", exc)

        return PublishResult(media_id=media_id, permalink=permalink)

    # ------------------------------------------------------- Üst seviye API

    def publish_post(
        self,
        *,
        media: list[dict[str, str]],
        caption: str,
        alt_text: str | None = None,
    ) -> PublishResult:
        """media: [{"url": ..., "type": "IMAGE"|"VIDEO"}, ...]"""
        if not media:
            raise InstagramError("Yayınlanacak medya yok.")

        if len(media) == 1:
            item = media[0]
            if item["type"] == "VIDEO":
                container = self.create_reel_container(
                    video_url=item["url"], caption=caption
                )
            else:
                container = self.create_image_container(
                    image_url=item["url"], caption=caption, alt_text=alt_text
                )
        else:
            children = []
            for item in media:
                if item["type"] == "VIDEO":
                    raise InstagramError(
                        "Bu otomasyon karusel içinde video desteklemiyor; "
                        "videoyu tek başına Reels olarak paylaşın."
                    )
                child = self.create_image_container(
                    image_url=item["url"], is_carousel_item=True
                )
                self.wait_until_ready(child)
                children.append(child)
            container = self.create_carousel_container(
                children=children, caption=caption
            )

        self.wait_until_ready(container)
        return self.publish(container)
