"""Channel-agnostic entrypoint onto api/verify.py's pipeline.

api/verify.py owns the real ingest -> hash -> registry match -> claims/risk ->
decide() -> render_verdict() sequence (including the TAMPERED_CONTENT
figures-altered check) and its own rate limiter. This module just re-exports
those under channel-neutral names so Telegram/email/WhatsApp adapters can
share the identical pipeline without each doing their own local, cycle-
avoiding import of api/verify.py's private helpers.
"""
from app.api.verify import _rate_limit as rate_limit, _run_verification as run_verification

__all__ = ["rate_limit", "run_verification"]
