"""Claude API ile caption + hashtag üretimi.

Görseli de modele gönderiyoruz — caption'ın gerçekten o karede ne olduğuyla
ilgili olması için. Marka brifi sistem promptunda ve cache'li, yani ikinci
gönderiden itibaren o kısım ~%90 daha ucuz.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import anthropic
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from .brand import BRAND_BRIEF, GOAL_GUIDANCE

log = logging.getLogger(__name__)

CAPTION_LIMIT = 2200  # Instagram'ın sert sınırı
HASHTAG_LIMIT = 30
VISION_MAX_EDGE = 1024  # caption yazmak için fazlası gereksiz token

# Modelin görmediği bir tarihe göre "3 gün kaldı" yazmasın diye
# bugünün tarihini ve turnuva takvimini her istekte veriyoruz.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class GeneratedCaption(BaseModel):
    """Modelin döndüreceği yapı. Alan kısıtları Python tarafında doğrulanıyor —
    structured outputs şeması minLength/maxLength desteklemiyor."""

    model_config = ConfigDict(extra="forbid")

    hook: str = Field(
        description="Akışta görünen ilk satır. Tek cümle, en fazla 90 karakter, "
        "nokta ile bitmesi şart değil."
    )
    body: str = Field(
        description="Gövde metni. En fazla 3 kısa paragraf, satır aralarında "
        "boş satır bırak. Hook'u tekrar etme. Hashtag koyma."
    )
    cta: str = Field(
        description="Tek cümlelik eylem çağrısı. Gerekmiyorsa boş string."
    )
    hashtags: list[str] = Field(
        description="8-15 arası hashtag, '#' işareti DAHİL, küçük harf. "
        "Türkçe karakter kullanma (Instagram'da #bartin, #bartın'dan iyi çalışır)."
    )
    alt_text: str = Field(
        description="Görsel için erişilebilirlik metni. Görselde ne olduğunu "
        "nesnel olarak tarif et, en fazla 2 cümle."
    )


class CaptionError(RuntimeError):
    """Caption üretilemedi."""


def _sanitize_schema(node: Any) -> Any:
    """Structured outputs'un kabul etmediği anahtarları şemadan çıkarır.

    Pydantic 'title' üretir ve kısıt alanları (minLength vb.) desteklenmez.
    """
    unsupported = {
        "title",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "pattern",
        "default",
    }
    if isinstance(node, dict):
        cleaned = {k: _sanitize_schema(v) for k, v in node.items() if k not in unsupported}
        if cleaned.get("type") == "object":
            cleaned["additionalProperties"] = False
        return cleaned
    if isinstance(node, list):
        return [_sanitize_schema(item) for item in node]
    return node


def _encode_image(path: Path) -> tuple[str, str]:
    """Görseli küçültüp base64'e çevirir. (media_type, base64) döner."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((VISION_MAX_EDGE, VISION_MAX_EDGE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _build_user_content(
    *,
    brief: str,
    goal: str,
    cta_hint: str,
    today: date,
    image_paths: list[Path],
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []

    for path in image_paths[:4]:  # karusel için ilk 4 kare yeter
        media_type, data = _encode_image(path)
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            }
        )

    goal_line = GOAL_GUIDANCE.get(goal, "Amaç: genel paylaşım.")
    cta_line = (
        f"\nİstenen eylem çağrısı: {cta_hint}"
        if cta_hint
        else "\nEylem çağrısı: gerekiyorsa sen karar ver, gerekmiyorsa cta alanını boş bırak."
    )

    content.append(
        {
            "type": "text",
            "text": (
                f"Bugünün tarihi: {today.isoformat()} (Türkiye saati).\n"
                f"{goal_line}\n\n"
                f"Bu gönderi için brif:\n{brief}\n"
                f"{cta_line}\n\n"
                "Yukarıdaki görsel(ler) gönderide kullanılacak. Caption'ı görselde "
                "gerçekten ne olduğuna bakarak yaz — görselde olmayan bir şeyi anlatma. "
                "Brifte olmayan rakam, tarih veya isim uydurma."
            ),
        }
    )
    return content


def _call_claude(
    client: anthropic.Anthropic,
    *,
    model: str,
    effort: str,
    system: list[dict[str, Any]],
    content: list[dict[str, Any]],
    schema: dict[str, Any],
):
    """Modeli çağırır. Önce sunucu taraflı fallback'li beta uçla dener —
    içerik politikası reddi gelirse istek aynı çağrı içinde yedek modelde
    yeniden koşar. Beta bayrağı hesapta açık değilse standart uca düşer."""
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 4000,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
    }
    try:
        return client.beta.messages.create(
            betas=[FALLBACK_BETA], fallbacks="default", **kwargs
        )
    except anthropic.BadRequestError as exc:
        log.warning(
            "Sunucu taraflı fallback kullanılamadı (%s). Standart uçla devam ediliyor.",
            exc.message,
        )
        return client.messages.create(**kwargs)


def generate_caption(
    *,
    api_key: str,
    model: str,
    effort: str,
    brief: str,
    goal: str,
    cta_hint: str,
    image_paths: list[Path],
    today: date,
) -> GeneratedCaption:
    client = anthropic.Anthropic(api_key=api_key)

    system = [
        {
            "type": "text",
            "text": BRAND_BRIEF,
            # Marka brifi her gönderide aynı — cache'le.
            "cache_control": {"type": "ephemeral"},
        }
    ]
    content = _build_user_content(
        brief=brief, goal=goal, cta_hint=cta_hint, today=today, image_paths=image_paths
    )
    schema = _sanitize_schema(GeneratedCaption.model_json_schema())

    response = _call_claude(
        client,
        model=model,
        effort=effort,
        system=system,
        content=content,
        schema=schema,
    )

    # Reddi içerik okumadan önce kontrol et — content boş veya kısmi olabilir.
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        raise CaptionError(
            f"Model isteği reddetti (kategori: {category}). Brifi gözden geçirin."
        )
    if response.stop_reason == "max_tokens":
        raise CaptionError("Yanıt max_tokens sınırında kesildi; brif çok uzun olabilir.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise CaptionError("Model metin bloğu döndürmedi.")

    try:
        parsed = GeneratedCaption.model_validate_json(text)
    except Exception as exc:  # pydantic ValidationError dahil
        raise CaptionError(f"Yanıt beklenen yapıda değil: {exc}\nHam yanıt: {text[:500]}") from exc

    usage = response.usage
    log.info(
        "Caption üretildi — girdi %s, cache okuma %s, çıktı %s token",
        usage.input_tokens,
        getattr(usage, "cache_read_input_tokens", 0),
        usage.output_tokens,
    )
    return _normalize(parsed)


def _normalize(caption: GeneratedCaption) -> GeneratedCaption:
    """Model kurallara uymadıysa sessizce düzelt — yayın anında patlamasın."""
    tags: list[str] = []
    seen: set[str] = set()
    for raw in caption.hashtags:
        tag = raw.strip().lower()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        tag = "#" + "".join(ch for ch in tag[1:] if ch.isalnum() or ch == "_")
        if len(tag) > 1 and tag not in seen:
            seen.add(tag)
            tags.append(tag)

    return caption.model_copy(
        update={
            "hook": caption.hook.strip(),
            "body": caption.body.strip(),
            "cta": caption.cta.strip(),
            "hashtags": tags[:HASHTAG_LIMIT],
            "alt_text": caption.alt_text.strip()[:1000],
        }
    )


def assemble(caption: GeneratedCaption) -> str:
    """Instagram'a gidecek nihai caption metnini kurar.

    2200 karakteri aşarsa önce hashtag'ler kırpılır — gövde metnini kesmek
    caption'ı cümle ortasında bırakır, hashtag atmak zararsızdır.
    """
    parts = [caption.hook, caption.body]
    if caption.cta:
        parts.append(caption.cta)
    core = "\n\n".join(p for p in parts if p).strip()

    tags = list(caption.hashtags)
    while tags:
        candidate = f"{core}\n\n{' '.join(tags)}"
        if len(candidate) <= CAPTION_LIMIT:
            return candidate
        tags.pop()

    return core[:CAPTION_LIMIT]
