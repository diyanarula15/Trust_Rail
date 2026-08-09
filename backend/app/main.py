"""FastAPI app factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import text

from app.api.artifacts import router as artifacts_router
from app.api.circle import router as circle_router
from app.api.ingest import router as ingest_router
from app.api.issuer import router as issuer_router
from app.api.log import router as log_router
from app.api.registry import router as registry_router
from app.api.sim import router as sim_router
from app.api.telemetry import router as telemetry_router
from app.api.tokens import router as tokens_router
from app.api.verify import router as verify_router
from app.api.webhooks_sms import router as webhooks_sms_router
from app.api.webhooks_telegram import router as webhooks_telegram_router
from app.api.webhooks_whatsapp import router as webhooks_whatsapp_router
from app.config import get_settings
from app.db import engine


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="TrustRail", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.base_url],
        # Next.js dev falls through to 3001, 3002, ... whenever 3000 is
        # already taken (stale process, another project). Accept any local
        # dev port so CORS doesn't break just because the frontend landed
        # on a different one than settings.base_url assumes.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(registry_router)
    app.include_router(issuer_router)
    app.include_router(log_router)
    app.include_router(verify_router)
    app.include_router(tokens_router)
    app.include_router(telemetry_router)
    app.include_router(artifacts_router)
    app.include_router(ingest_router)
    app.include_router(webhooks_whatsapp_router)
    app.include_router(webhooks_telegram_router)
    app.include_router(webhooks_sms_router)
    app.include_router(sim_router)
    app.include_router(circle_router)

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        db_ok = False
        redis_ok = False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            pass
        try:
            redis_ok = bool(Redis.from_url(settings.redis_url, socket_timeout=2).ping())
        except Exception:
            pass
        return {"ok": db_ok and redis_ok, "db": db_ok, "redis": redis_ok}

    return app


app = create_app()
