"""
Decodes a Project Gutenberg .txt and splits it into header and body following
SPEC 3.3 and 3.4. Shared by every BookDownloader adapter (HTTP and local).
"""

import re

from src.domain.header_parser import ASCII_WHITESPACE
from src.domain.model import DownloadException, FailureReason

_BOM = "﻿"
_START_MARKER = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG E-?BOOK.*?\*\*\*", re.IGNORECASE)
_END_MARKER = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG E-?BOOK.*?\*\*\*", re.IGNORECASE)


def decode_gutenberg_bytes(data: bytes) -> str:
    """UTF-8 (Latin-1 fallback), without BOM and with \\n line endings."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text.removeprefix(_BOM).replace("\r\n", "\n").replace("\r", "\n")


def split_header_body(text: str) -> tuple[str, str]:
    """Returns (header, body). Raises DownloadException with NO_MARKERS or EMPTY_BODY."""
    start = _START_MARKER.search(text)
    end = _END_MARKER.search(text, start.end()) if start else None
    if not start or not end:
        raise DownloadException(FailureReason.NO_MARKERS)

    header = text[:start.start()].strip(ASCII_WHITESPACE)
    body = text[start.end():end.start()].strip(ASCII_WHITESPACE)
    if not body:
        raise DownloadException(FailureReason.EMPTY_BODY)
    return header, body
