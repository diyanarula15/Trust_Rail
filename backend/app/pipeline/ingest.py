"""Input sniffing + validation (spec §8.1). Never trust the extension."""
import logging

from pydantic import BaseModel

from app.config import get_settings
from app.models import InputKind

logger = logging.getLogger(__name__)

try:
    import magic

    _HAS_MAGIC = True
except Exception:  # libmagic missing — degrade to signature sniffing
    magic = None
    _HAS_MAGIC = False
    logger.warning("python-magic unavailable; using built-in signature sniffer")

_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
    (b"GIF8", "image/gif"),
    (b"RIFF", "image/webp"),
]

_MIME_TO_KIND: dict[str, InputKind] = {
    "image/jpeg": InputKind.image,
    "image/png": InputKind.image,
    "image/webp": InputKind.image,
    "image/gif": InputKind.image,
    "video/mp4": InputKind.video,
    "video/quicktime": InputKind.video,
    "application/pdf": InputKind.pdf,
    "message/rfc822": InputKind.eml,
}


class IngestError(Exception):
    """Maps to a clean 422 at the API boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class IngestResult(BaseModel):
    kind: InputKind
    data: bytes | None = None
    mime: str | None = None
    text: str | None = None
    url: str | None = None


def _sniff_mime(data: bytes, filename: str | None) -> str:
    if _HAS_MAGIC:
        try:
            return magic.from_buffer(data[:8192], mime=True)
        except Exception as exc:
            logger.warning("magic sniff failed (%s); falling back", exc)
    for sig, mime in _SIGNATURES:
        if data.startswith(sig):
            return mime
    if data[4:12] in (b"ftypisom", b"ftypmp42", b"ftypMSNV", b"ftypM4V ", b"ftypmp41", b"ftypiso5"):
        return "video/mp4"
    if filename and filename.lower().endswith(".eml"):
        return "message/rfc822"
    return "application/octet-stream"


def ingest_file(data: bytes, filename: str | None) -> IngestResult:
    settings = get_settings()
    mime = _sniff_mime(data, filename)
    # forwarded .eml files often sniff as text/plain — trust the extension only
    # as a tiebreaker within text-family types, never to upgrade to executable kinds
    if mime.startswith("text/") and filename and filename.lower().endswith(".eml"):
        mime = "message/rfc822"

    kind = _MIME_TO_KIND.get(mime)
    if kind is None and mime.startswith("text/"):
        text = data.decode("utf-8", errors="replace")
        return ingest_text(text)
    if kind is None:
        raise IngestError("unsupported_type", f"Unsupported content type: {mime}.")

    caps = {
        InputKind.image: settings.max_image_bytes,
        InputKind.video: settings.max_video_bytes,
        InputKind.pdf: settings.max_pdf_bytes,
        InputKind.eml: settings.max_eml_bytes,
    }
    if len(data) > caps[kind]:
        raise IngestError(
            "too_large",
            f"{kind.value} exceeds the {caps[kind] // (1024 * 1024)} MB limit.",
        )
    return IngestResult(kind=kind, data=data, mime=mime)


def ingest_text(text: str) -> IngestResult:
    settings = get_settings()
    if len(text) > settings.max_text_chars:
        raise IngestError("too_large", f"Text exceeds {settings.max_text_chars} characters.")
    if not text.strip():
        raise IngestError("empty", "Text input is empty.")
    return IngestResult(kind=InputKind.text, text=text)


def ingest_eml_bytes(raw: bytes) -> IngestResult:
    """Raw .eml bytes straight from an IMAP fetch — bypasses the filename-
    sniffing path in ingest_file, which has nothing to sniff from a mailbox
    fetch (there's no upload filename to fall back on)."""
    settings = get_settings()
    if len(raw) > settings.max_eml_bytes:
        raise IngestError("too_large", f"eml exceeds the {settings.max_eml_bytes // (1024 * 1024)} MB limit.")
    return IngestResult(kind=InputKind.eml, data=raw, mime="message/rfc822")


def ingest_url(url: str) -> IngestResult:
    url = url.strip()
    if not url or len(url) > 2048:
        raise IngestError("bad_url", "URL is empty or too long.")
    return IngestResult(kind=InputKind.url, url=url, text=url)
