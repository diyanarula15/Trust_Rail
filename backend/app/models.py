"""SQLAlchemy models (spec §6). Every table: UUID pk + tz-aware created_at."""
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EntityKind(str, enum.Enum):
    regulator = "regulator"
    exchange = "exchange"
    listed_company = "listed_company"
    broker = "broker"
    mutual_fund = "mutual_fund"
    ria = "ria"


class EntityStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class DomainKind(str, enum.Enum):
    web = "web"
    email = "email"


class KeyRole(str, enum.Enum):
    maker = "maker"
    checker = "checker"
    entity = "entity"
    registry = "registry"


class KeyStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class CommChannel(str, enum.Enum):
    filing = "filing"
    sms = "sms"
    email = "email"
    video = "video"
    image = "image"
    pdf = "pdf"
    social = "social"


class CommImpact(str, enum.Enum):
    standard = "standard"
    market_moving = "market_moving"


class CommStatus(str, enum.Enum):
    draft = "draft"
    maker_signed = "maker_signed"
    published = "published"
    revoked = "revoked"


class VerifyChannel(str, enum.Enum):
    sim = "sim"
    whatsapp = "whatsapp"
    telegram = "telegram"
    email = "email"


class InputKind(str, enum.Enum):
    image = "image"
    video = "video"
    pdf = "pdf"
    text = "text"
    url = "url"
    eml = "eml"


class Verdict(str, enum.Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_NOTICE = "VERIFIED_NOTICE"
    OFFICIAL_CLAIM_UNVERIFIED = "OFFICIAL_CLAIM_UNVERIFIED"
    LIKELY_FAKE = "LIKELY_FAKE"
    INFORMATIONAL = "INFORMATIONAL"


class BlacklistKind(str, enum.Enum):
    domain = "domain"
    phash = "phash"
    phrase = "phrase"


class CircleChannel(str, enum.Enum):
    whatsapp = "whatsapp"
    telegram = "telegram"
    email = "email"


class CircleStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    revoked = "revoked"


class TimestampedBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Entity(TimestampedBase):
    __tablename__ = "entities"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[EntityKind] = mapped_column(Enum(EntityKind, name="entity_kind"))
    sebi_reg_no: Mapped[str] = mapped_column(String(40))
    status: Mapped[EntityStatus] = mapped_column(
        Enum(EntityStatus, name="entity_status"), default=EntityStatus.active
    )

    domains: Mapped[list["EntityDomain"]] = relationship(back_populates="entity")
    sms_headers: Mapped[list["EntitySmsHeader"]] = relationship(back_populates="entity")
    keys: Mapped[list["Key"]] = relationship(back_populates="entity")


class EntityDomain(TimestampedBase):
    __tablename__ = "entity_domains"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    domain: Mapped[str] = mapped_column(String(255), unique=True)  # lowercase
    kind: Mapped[DomainKind] = mapped_column(Enum(DomainKind, name="domain_kind"))

    entity: Mapped[Entity] = relationship(back_populates="domains")


class EntitySmsHeader(TimestampedBase):
    __tablename__ = "entity_sms_headers"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    header: Mapped[str] = mapped_column(String(6), unique=True)  # uppercase, 6 chars

    entity: Mapped[Entity] = relationship(back_populates="sms_headers")


class Key(TimestampedBase):
    __tablename__ = "keys"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    label: Mapped[str] = mapped_column(String(120))
    role: Mapped[KeyRole] = mapped_column(Enum(KeyRole, name="key_role"))
    public_key_ed25519: Mapped[str] = mapped_column(String(64))  # b64
    # DEMO ONLY — private keys in the DB so the demo is reproducible and
    # inspectable. TODO(prod): HSM custody; never persist private material.
    private_key_ed25519: Mapped[str] = mapped_column(String(120))  # b64
    cert_pem: Mapped[str | None] = mapped_column(Text, nullable=True)  # P-256 leaf (C2PA)
    status: Mapped[KeyStatus] = mapped_column(
        Enum(KeyStatus, name="key_status"), default=KeyStatus.active
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    entity: Mapped[Entity] = relationship(back_populates="keys")


class Artifact(TimestampedBase):
    __tablename__ = "artifacts"

    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime: Mapped[str] = mapped_column(String(100))
    bytes_size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))  # under ARTIFACT_DIR
    phash64: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    pdq256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    video_frame_hashes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    simhash64: Mapped[str | None] = mapped_column(String(16), nullable=True)
    c2pa_embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    envelope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Communication(TimestampedBase):
    __tablename__ = "communications"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"))
    title: Mapped[str] = mapped_column(String(300))
    channel: Mapped[CommChannel] = mapped_column(Enum(CommChannel, name="comm_channel"))
    impact: Mapped[CommImpact] = mapped_column(
        Enum(CommImpact, name="comm_impact"), default=CommImpact.standard
    )
    status: Mapped[CommStatus] = mapped_column(
        Enum(CommStatus, name="comm_status"), default=CommStatus.draft
    )
    canonical_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), nullable=True
    )
    maker_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("keys.id"))
    maker_sig: Mapped[str | None] = mapped_column(String(120), nullable=True)  # b64
    checker_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("keys.id"), nullable=True
    )
    checker_sig: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    log_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)

    entity: Mapped[Entity] = relationship()
    artifact: Mapped[Artifact | None] = relationship()


class LogEntry(TimestampedBase):
    __tablename__ = "log_entries"

    seq: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    leaf_hash: Mapped[str] = mapped_column(String(64))  # hex
    entry: Mapped[dict[str, Any]] = mapped_column(JSONB)
    tree_size: Mapped[int] = mapped_column(Integer)
    root_hash: Mapped[str] = mapped_column(String(64))  # hex
    sth_sig: Mapped[str] = mapped_column(String(120))  # b64, registry key over STH


class Verification(TimestampedBase):
    __tablename__ = "verifications"

    channel: Mapped[VerifyChannel] = mapped_column(
        Enum(VerifyChannel, name="verify_channel"), default=VerifyChannel.sim
    )
    input_kind: Mapped[InputKind] = mapped_column(Enum(InputKind, name="input_kind"))
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, name="verdict"))
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    signals: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    matched_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True
    )
    matched_communication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communications.id"), nullable=True
    )
    claimed_entity_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(6), nullable=True)  # IN-KA
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_verifications_created_at", "created_at"),)


class ScamBlacklist(TimestampedBase):
    __tablename__ = "scam_blacklist"

    kind: Mapped[BlacklistKind] = mapped_column(Enum(BlacklistKind, name="blacklist_kind"))
    value: Mapped[str] = mapped_column(Text)  # domain / phrase / phash hex
    campaign: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ViewToken(TimestampedBase):
    __tablename__ = "view_tokens"

    token: Mapped[str] = mapped_column(String(64), unique=True)  # urlsafe
    verification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("verifications.id"), nullable=True
    )
    communication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communications.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TrustCircle(TimestampedBase):
    """One elder<->guardian link. Deliberately NOT joined to `Verification` —
    that table's whole point (see api/telemetry.py) is that a submitter's
    identity is never persisted. Only senders who opt into a circle get this
    extra, separate identity linkage."""

    __tablename__ = "trust_circles"

    elder_channel: Mapped[CircleChannel] = mapped_column(Enum(CircleChannel, name="circle_channel"))
    elder_external_id: Mapped[str] = mapped_column(String(200))  # normalized phone/chat_id/email

    pairing_code: Mapped[str] = mapped_column(String(6))
    pairing_code_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    guardian_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_channel: Mapped[CircleChannel | None] = mapped_column(
        Enum(CircleChannel, name="circle_channel"), nullable=True
    )
    guardian_channel_external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    circle_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    status: Mapped[CircleStatus] = mapped_column(
        Enum(CircleStatus, name="circle_status"), default=CircleStatus.pending
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_trust_circles_elder", "elder_channel", "elder_external_id"),
    )


class CircleAlert(TimestampedBase):
    """Append-only log of guardian notifications fired for a TrustCircle."""

    __tablename__ = "circle_alerts"

    circle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trust_circles.id"))
    verdict: Mapped[str] = mapped_column(String(40))
    plain_headline: Mapped[str] = mapped_column(String(300))
    campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivered_via: Mapped[str] = mapped_column(String(20))  # "channel" | "email" | "none"
