"""
Domain models. No external dependencies. Rules: shared/SPEC.md.
"""

from dataclasses import dataclass
from enum import Enum

INDEXABLE_LANGUAGE = "en"

MAX_FAILED_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class BookText:
    """Header and body of a book, split at the Gutenberg markers (SPEC 3.4)."""

    header: str
    body: str


@dataclass(frozen=True, slots=True)
class StoredPaths:
    """Datalake paths, relative to TARANTINO_DATA_DIR with '/' separators (SPEC 5.4)."""

    header: str
    body: str


@dataclass(frozen=True, slots=True)
class Book:
    """Metadata extracted from a book header (SPEC 5). Missing fields are ""."""

    book_id: int
    title: str
    author: str
    language: str
    release_date: str

    def is_indexable(self) -> bool:
        return self.language == INDEXABLE_LANGUAGE


@dataclass(frozen=True, slots=True)
class TermOccurrences:
    """Occurrences of a term in one book (SPEC 6.2)."""

    tf: int
    positions: tuple[int, ...]


class FailureReason(Enum):
    """
    Why a download failed (SPEC 3.4). A book that reaches
    MAX_FAILED_ATTEMPTS failures is never proposed again (SPEC 3.5).
    """

    HTTP_ERROR = "HTTP_ERROR"
    NO_MARKERS = "NO_MARKERS"
    EMPTY_BODY = "EMPTY_BODY"


class DownloadException(Exception):
    def __init__(self, reason: FailureReason):
        super().__init__(reason.value)
        self.reason = reason
