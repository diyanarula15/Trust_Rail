"""Frontend-facing channel simulators — NOT the real webhook contracts.
Those are api/webhooks_telegram.py / api/webhooks_whatsapp.py, built to
Telegram's and Meta's actual specs for external callers (signature/secret
verification, media-id resolution, always-200 semantics). This router
exists purely so the frontend's /channels page can show the literal
message text a Telegram or WhatsApp reply would contain, without faking a
webhook payload or reading server logs.

Deliberately calls only `channels.telegram.build_reply` /
`channels.whatsapp.build_reply` — never `send_message`/`send_text` — so
this can NEVER trigger a real outbound send, regardless of whether
TELEGRAM_BOT_TOKEN / WHATSAPP_TOKEN happen to be configured.
"""
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.channels import telegram, whatsapp
from app.config import get_settings
from app.db import get_db, get_redis
from app.pipeline.ingest import IngestError, ingest_file, ingest_text
from app.pipeline.verify_service import rate_limit
from app.schemas import err, ok

router = APIRouter(prefix="/api/sim", tags=["sim"])


def _bad(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=err(code, message))


async def _ingest_one(request: Request, file: UploadFile | None, text: str | None):
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    try:
        allowed, retry_after = rate_limit(get_redis(), f"sim:{ip}", settings.verify_rate_limit_per_min)
    except Exception:
        allowed, retry_after = True, 0  # rate limiting is best-effort, never blocks the demo
    if not allowed:
        return _bad(429, "rate_limited", f"Too many requests. Retry in {retry_after}s.")
    if sum(x is not None for x in (file, text)) != 1:
        return _bad(422, "bad_input", "Provide exactly one of file or text.")
    try:
        if file is not None:
            return ingest_file(await file.read(), file.filename)
        assert text is not None
        return ingest_text(text)
    except IngestError as exc:
        return _bad(422, exc.code, exc.message)


@router.post("/telegram")
async def sim_telegram(
    request: Request,
    file: UploadFile | None = None,
    text: str | None = Form(None),
    caption: str | None = Form(None),
    db: Session = Depends(get_db),
):
    ingest_result = await _ingest_one(request, file, text)
    if isinstance(ingest_result, JSONResponse):
        return ingest_result

    reply_text, buttons, card = telegram.build_reply(ingest_result, caption, db)
    return ok({"text": reply_text, "buttons": buttons, "card": card})


@router.post("/whatsapp")
async def sim_whatsapp(
    request: Request,
    file: UploadFile | None = None,
    text: str | None = Form(None),
    caption: str | None = Form(None),
    db: Session = Depends(get_db),
):
    ingest_result = await _ingest_one(request, file, text)
    if isinstance(ingest_result, JSONResponse):
        return ingest_result

    reply_text, card = whatsapp.build_reply(ingest_result, caption, db)
    return ok({"text": reply_text, "card": card})
