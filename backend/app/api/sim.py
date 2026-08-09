"""Frontend-facing channel simulators — NOT the real webhook contracts.
Those are api/webhooks_telegram.py / api/webhooks_whatsapp.py /
api/webhooks_sms.py, built to each platform's actual spec for external
callers (signature/secret verification, media-id resolution, always-200
semantics). This router exists purely so the frontend's /channels page can
show the literal reply text a real conversation would contain, without
faking a webhook payload or reading server logs.

Deliberately calls only `channels.<x>.build_reply` — never
`send_message`/`send_text`/`send_sms` — so this can NEVER trigger a real
outbound send, regardless of what credentials happen to be configured. For
the SMS case specifically this also means never passing a real
`sender_external_id`, which is what stops a demo-page click from being
able to complete a Trust Circle pairing or fire a real guardian alert —
see channels/sms.build_reply's docstring.
"""
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.channels import sms, telegram, whatsapp
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


@router.post("/sms")
async def sim_sms(
    text: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Text only, deliberately no `file` parameter: unlike Telegram/WhatsApp,
    neither of the two real SMS integrations this codebase actually builds
    (a Twilio number, an SMS-forwarder app) carries images through this
    endpoint — MMS attachment download isn't implemented in
    channels/sms.py, so accepting a file here would silently pretend to a
    capability that doesn't exist rather than reflecting the real system."""
    try:
        ingest_text(text or "")  # validated the same way every other channel's input is
    except IngestError as exc:
        return _bad(422, exc.code, exc.message)
    reply_text, card = sms.build_reply(db, text or "")  # sender_external_id None — see build_reply's docstring
    return ok({"text": reply_text, "card": card})
