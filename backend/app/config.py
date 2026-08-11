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

    @field_validator("database_url", mode="after")
    @classmethod
    def _force_psycopg3_driver(cls, v: str) -> str:
        # Managed Postgres add-ons (Railway, Heroku, ...) hand back a bare
        # postgresql:// or postgres:// URL, which makes SQLAlchemy reach for
        # psycopg2 — not installed here, only psycopg (v3) is (requirements.txt).
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

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

    # See docs/SETUP_SMS.md. Two integration paths, both real: a Twilio
    # number (channel_sms_enabled + these three) for a bot number people
    # text directly, and Trust Circle "Auto-Guard" (trust_circles.guard_token,
    # always available once trust_circle_enabled — no Twilio account needed)
    # for scanning everything arriving on someone's own phone via an SMS-
    # forwarder app. Ships simulated (scripts/sms_sim.py) until these are set.
    channel_sms_enabled: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

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
