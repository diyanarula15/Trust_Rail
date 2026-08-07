"""Where communications come in from, before anything is published.

The point of this module is the boundary: a feed is anything that can hand
back a list of `FeedItem`. A JSON file, an HTTP endpoint, an exchange's
announcement API, a DLT gateway's template export — the pipeline downstream
neither knows nor cares.

That boundary is what makes "ingested passively from infrastructure that
already exists" a configuration change rather than a rewrite: point
`HttpJsonSource` at a real filings endpoint and the rest of the path —
hashing, signing, transparency log, verification — is unchanged.

The shipped sample feeds are fictional and live in fixtures/feeds/.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field


class FeedItem(BaseModel):
    """One communication as it arrives, before we know who published it.

    Normalised shape — every adapter converts its own feed format into this,
    so the publisher only ever sees one kind of thing.
    """

    external_id: str            # the source's own id, for traceability
    entity_hint: str            # reg no, name, or SMS header — resolved later
    title: str
    channel: str                # filing | sms | email | image | video | pdf | social
    impact: str = "standard"    # standard | market_moving
    body_text: str | None = None
    document_path: str | None = None   # local file, relative to repo root
    document_url: str | None = None    # or fetched over http
    published_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class FeedSource(Protocol):
    """Anything that can produce feed items."""

    name: str

    def fetch(self) -> list[dict[str, Any]]:
        ...


class JsonFileSource:
    """Reads a JSON array from disk. Used by the shipped sample feeds and by
    tests; also the honest default when no real endpoint is configured."""

    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self.path = path

    def fetch(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):  # tolerate {"items": [...]} envelopes
            payload = payload.get("items", [])
        return list(payload)


class HttpJsonSource:
    """Polls a real endpoint. This is the class you point at an exchange's
    announcements API or a DLT gateway export in a live deployment; nothing
    downstream changes when you do."""

    def __init__(self, name: str, url: str, *, headers: dict[str, str] | None = None,
                 timeout: float = 20.0) -> None:
        self.name = name
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    def fetch(self) -> list[dict[str, Any]]:
        resp = httpx.get(self.url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict):
            payload = payload.get("items", [])
        return list(payload)


def parse_when(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
