"""Application settings. ALL tunable thresholds live here (spec §8.3)."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://trustrail:tr41l_dev_pg_2026@localhost:5434/trustrail"
    redis_url: str = "redis://localhost:6380/0"
    secret_key: str = "change-me"
    base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    artifact_dir: Path = Path("var/artifacts")
    trust_dir: Path = Path("var/trust")

    @field_validator("artifact_dir", "trust_dir", mode="after")
    @classmethod
    def _anchor_to_repo_root(cls, v: Path) -> Path:
        # relative paths in .env resolve against the repo root, not the cwd
        return v if v.is_absolute() else (REPO_ROOT / v).resolve()
    cert_link_ttl_minutes: int = 15
    default_locale: str = "en"
    sebi_check_url: str = "#"

    llm_enabled: bool = False
    anthropic_api_key: str = ""

    channel_whatsapp_enabled: bool = False
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    channel_telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    channel_email_enabled: bool = False
    email_imap_host: str = ""
    email_imap_port: int = 993
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_poll_interval_seconds: int = 30

    # Matching thresholds (spec §8.3)
    phash_match_max_dist: int = 10
    phash_near_max_dist: int = 16
    pdq_match_max_dist: int = 31
    video_frame_match_ratio: float = 0.55
    simhash_match_max_dist: int = 6
    fuzzy_entity_min_score: int = 88

    # Ingest caps (spec §8.1)
    max_image_bytes: int = 10 * 1024 * 1024
    max_video_bytes: int = 64 * 1024 * 1024
    max_pdf_bytes: int = 20 * 1024 * 1024
    max_eml_bytes: int = 5 * 1024 * 1024
    max_text_chars: int = 20_000

    # Rate limit (spec §9)
    verify_rate_limit_per_min: int = 30

    # Trust Circle (elder<->guardian pairing + alerting)
    trust_circle_enabled: bool = True
    circle_pairing_code_ttl_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
