"""
Decodes a Project Gutenberg .txt and splits it into header and body following
SPEC 3.3 and 3.4. Shared by every BookDownloader adapter (HTTP and local).
"""

import re

from src.domain.model import BookText, DownloadException, FailureReason
from src.domain.text import ASCII_CASE_INSENSITIVE, strip_ascii_whitespace

_BOM = "\ufeff"
_START_MARKER = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG E-?BOOK.*?\*\*\*", ASCII_CASE_INSENSITIVE)
_END_MARKER = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG E-?BOOK.*?\*\*\*", ASCII_CASE_INSENSITIVE)


def decode_gutenberg_bytes(data: bytes) -> str:
    """UTF-8 (Latin-1 fallback), without BOM and with \\n line endings."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text.removeprefix(_BOM).replace("\r\n", "\n").replace("\r", "\n")


def split_header_body(text: str) -> BookText:
    """Raises DownloadException with NO_MARKERS or EMPTY_BODY."""
    start = _START_MARKER.search(text)
    end = _END_MARKER.search(text, start.end()) if start else None
    if not start or not end:
        raise DownloadException(FailureReason.NO_MARKERS)

    header = strip_ascii_whitespace(text[: start.start()])
    body = strip_ascii_whitespace(text[start.end() : end.start()])
    if not body:
        raise DownloadException(FailureReason.EMPTY_BODY)
    return BookText(header, body)
