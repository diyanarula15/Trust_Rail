"""Dispatches a guardian alert when the verification pipeline flags content
from a sender enrolled in a Trust Circle. Fire-and-forget: never raises,
mirroring channels/whatsapp.send_text's "a failed send must never take down
the verification that produced it" posture.

Deliberately does not touch `Verification`/telemetry — that table's whole
point (api/telemetry.py) is that a submitter's identity is never persisted.
Only senders who opt into a circle get this extra, separate `CircleAlert`
log, and only via the transient `sender_external_id` passed in per call.
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.render import _load
from app.config import get_settings
from app.models import CircleAlert, CircleChannel, CircleStatus, TrustCircle, VerifyChannel
from app.pipeline.verdict import Decision
from app.pipeline.verdict import Verdict as VerdictEnum

logger = logging.getLogger(__name__)

ALERT_VERDICTS = {VerdictEnum.LIKELY_FAKE, VerdictEnum.OFFICIAL_CLAIM_UNVERIFIED}

_CHANNEL_MAP = {
    VerifyChannel.whatsapp: CircleChannel.whatsapp,
    VerifyChannel.telegram: CircleChannel.telegram,
    VerifyChannel.email: CircleChannel.email,
    VerifyChannel.sms: CircleChannel.sms,
}


def _lookup_circles(db: Session, channel: CircleChannel, external_id: str) -> list[TrustCircle]:
    return db.execute(
        select(TrustCircle).where(
            TrustCircle.elder_channel == channel,
            TrustCircle.elder_external_id == external_id,
            TrustCircle.status == CircleStatus.active,
        )
    ).scalars().all()


def _alert_text(card: dict) -> str:
    """Minimal-disclosure message: headline + top reason, never the raw
    forwarded text/link — so the alert itself never re-propagates whatever
    made the original message dangerous."""
    strings = _load(get_settings().default_locale).get("circle", {})
    headline = card.get("plain_headline") or card.get("headline") or "Risky content flagged"
    reasons = card.get("plain_reason_strings") or card.get("reason_strings") or []
    intro = strings.get(
        "alert_intro", "This was flagged and blocked automatically — no action needed from you."
    )
    lines = [strings.get("alert_subject", "TrustRail Trust Circle alert"), "", headline]
    if reasons:
        lines.append(reasons[0])
    lines += ["", intro]
    return "\n".join(lines)


def _deliver(circle: TrustCircle, text: str) -> str:
    """Returns "channel" | "email" | "none" for what was actually attempted.
    Prefers the guardian's own paired bot channel, falling back to email —
    imported lazily to avoid a module-load cycle with the channel adapters,
    which import this package's caller (api/verify.py) indirectly."""
    if circle.guardian_channel == CircleChannel.telegram and circle.guardian_channel_external_id:
        from app.channels import telegram
        telegram.send_message(circle.guardian_channel_external_id, text, [])
        return "channel"
    if circle.guardian_channel == CircleChannel.whatsapp and circle.guardian_channel_external_id:
        from app.channels import whatsapp
        whatsapp.send_text(circle.guardian_channel_external_id, text)
        return "channel"
    if circle.guardian_email:
        from app.channels.email_channel import _send_reply
        subject = _load(get_settings().default_locale).get("circle", {}).get(
            "alert_subject", "TrustRail Trust Circle alert"
        )
        _send_reply(to_addr=circle.guardian_email, subject=subject, body=text,
                    in_reply_to=None, references=None)
        return "email"
    return "none"


def _dispatch_and_log(db: Session, circle: TrustCircle, decision: Decision, card: dict) -> str:
    """One circle, one alert: deliver it, log it (even on failed delivery —
    an undeliverable alert is still a real event worth the guardian seeing
    in their history), return what actually happened."""
    text = _alert_text(card)
    try:
        delivered_via = _deliver(circle, text)
    except Exception:
        logger.exception("circle alert dispatch failed for circle %s", circle.id)
        delivered_via = "none"
    db.add(CircleAlert(
        circle_id=circle.id,
        verdict=decision.verdict.value,
        plain_headline=(card.get("plain_headline") or card.get("headline") or "")[:300],
        campaign=decision.campaign,
        delivered_via=delivered_via,
    ))
    return delivered_via


def maybe_alert_guardians(
    db: Session,
    *,
    channel: VerifyChannel,
    sender_external_id: str | None,
    decision: Decision,
    card: dict,
    also_alert_circle_id: uuid.UUID | None = None,
) -> bool:
    """Returns whether at least one alert was actually dispatched, so the
    calling channel adapter can append a "your family member has been
    notified" line to its already-formatted reply.

    Two independent dispatch paths, both gated on the same verdict check:

    - identity lookup: `sender_external_id` is who sent this (a chat_id, an
      email, a phone number that texted the bot directly) — every circle
      whose *elder* matches that identity gets alerted. This is what every
      channel adapter uses.
    - direct (`also_alert_circle_id`): the caller already knows exactly
      which circle this concerns and there is no sender identity to look up
      against — this is Auto-Guard's case (see channels/sms.py's
      handle_guard_inbound): the forwarded message's sender is whoever
      texted the elder, not the elder, so identity lookup is meaningless
      here and would silently alert nobody.

    Both can fire on the same call without double-alerting anyone, since
    they necessarily target disjoint circles in practice.
    """
    if not get_settings().trust_circle_enabled or decision.verdict not in ALERT_VERDICTS:
        return False

    attempted = False   # any circle found and logged, delivered or not
    dispatched = False  # at least one delivery actually succeeded

    if sender_external_id is not None:
        circle_channel = _CHANNEL_MAP.get(channel)
        if circle_channel is not None:
            external_id = sender_external_id.strip()
            if circle_channel == CircleChannel.email:
                external_id = external_id.lower()
            for circle in _lookup_circles(db, circle_channel, external_id):
                attempted = True
                if _dispatch_and_log(db, circle, decision, card) != "none":
                    dispatched = True

    if also_alert_circle_id is not None:
        circle = db.get(TrustCircle, also_alert_circle_id)
        if circle is not None and circle.status == CircleStatus.active:
            attempted = True
            if _dispatch_and_log(db, circle, decision, card) != "none":
                dispatched = True

    # Commit whenever a circle was actually processed, not only on a
    # successful delivery — an undeliverable alert (guardian has neither a
    # linked channel nor an email, say) is still a real CircleAlert row the
    # guardian dashboard's history should show, not a silently dropped write.
    if attempted:
        db.commit()
    return dispatched
