"""Ortam değişkenlerinden okunan ayarlar.

Gizli değerler GitHub Secrets'tan, geri kalanı workflow env bloğundan gelir.
Yerelde çalıştırmak için proje kökündeki .env dosyası kullanılır.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:  # yerelde .env varsa yükle; Actions'ta gerekmez
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
IMAGE_DIR = CONTENT_DIR / "images"
QUEUE_PATH = CONTENT_DIR / "queue.json"

def _istanbul_tz():
    """Türkiye saati.

    Windows'ta sistem saat dilimi veritabanı yoktur; tzdata paketi kuruluysa
    ZoneInfo çalışır. Kurulu değilse sabit +03:00'a düşeriz — Türkiye 2016'dan
    beri yaz saati uygulamıyor, yani pratikte aynı sonuç.
    """
    try:
        return ZoneInfo("Europe/Istanbul")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=3), "TRT")


ISTANBUL = _istanbul_tz()


class ConfigError(RuntimeError):
    """Eksik veya hatalı yapılandırma."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} tanımlı değil. GitHub Secrets'a ekleyin "
            f"(yerelde çalışıyorsanız .env dosyasına)."
        )
    return value


@dataclass(frozen=True)
class Settings:
    # --- Meta / Instagram ---
    ig_user_id: str
    access_token: str
    graph_version: str

    # --- Görsel barındırma ---
    # Instagram görseli kendisi indirir, bu yüzden herkese açık bir URL şart.
    image_base_url: str

    # --- Claude ---
    anthropic_api_key: str
    model: str
    effort: str

    # --- Davranış ---
    max_posts_per_run: int
    dry_run: bool

    @classmethod
    def load(cls) -> "Settings":
        # Önce gizli değerler: en sık yapılan hata eksik secret, hata mesajı
        # da onu göstermeli.
        ig_user_id = _required("IG_USER_ID")
        access_token = _required("IG_ACCESS_TOKEN")
        anthropic_api_key = _required("ANTHROPIC_API_KEY")

        repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        branch = os.environ.get("CONTENT_BRANCH", "main").strip()

        image_base_url = os.environ.get("IMAGE_BASE_URL", "").strip()
        if not image_base_url and repo:
            # Public repo'da raw.githubusercontent.com doğrudan çalışır.
            image_base_url = (
                f"https://raw.githubusercontent.com/{repo}/{branch}/content/images"
            )
        if not image_base_url:
            raise ConfigError(
                "IMAGE_BASE_URL tanımlı değil ve GITHUB_REPOSITORY'den türetilemedi. "
                "Görsellerin herkese açık bir URL'de olması Instagram API'sinin şartı."
            )

        return cls(
            ig_user_id=ig_user_id,
            access_token=access_token,
            graph_version=os.environ.get("GRAPH_API_VERSION", "v26.0").strip(),
            image_base_url=image_base_url.rstrip("/"),
            anthropic_api_key=anthropic_api_key,
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-5").strip(),
            effort=os.environ.get("CLAUDE_EFFORT", "medium").strip(),
            max_posts_per_run=int(os.environ.get("MAX_POSTS_PER_RUN", "1")),
            dry_run=os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"},
        )
