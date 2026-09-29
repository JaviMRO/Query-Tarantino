"""
Extracts metadata from a Project Gutenberg header following SPEC 5.1 and 5.2.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice

from src.domain.model import Book
from src.domain.text_processing.text import ASCII_CASE_INSENSITIVE, strip_ascii_whitespace

_TITLE_PATTERN = re.compile(r"^Title:\s*(.*)$", ASCII_CASE_INSENSITIVE)
_AUTHOR_PATTERN = re.compile(r"^Author:\s*(.*)$", ASCII_CASE_INSENSITIVE)
_LANGUAGE_PATTERN = re.compile(r"^Language:\s*(.*)$", ASCII_CASE_INSENSITIVE)
_RELEASE_DATE_PATTERN = re.compile(r"^Release date:\s*([^\[]*)", ASCII_CASE_INSENSITIVE)

_CONTINUATION_PREFIXES = (" ", "\t")

_LANGUAGE_CODES = {
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "dutch": "nl",
    "finnish": "fi",
    "latin": "la",
    "chinese": "zh",
}

_ASCII_LOWERCASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


@dataclass(frozen=True, slots=True)
class _FieldMatch:
    value: str
    line_index: int


def parse_header(book_id: int, header: str) -> Book:
    """Metadata of a book; a missing field is stored as "" and never makes the book fail (SPEC 5.1)."""
    lines = header.split("\n")
    return Book(
        book_id=book_id,
        title=_find_title(lines),
        author=_field_value(lines, _AUTHOR_PATTERN),
        language=_normalize_language(_field_value(lines, _LANGUAGE_PATTERN)),
        release_date=_field_value(lines, _RELEASE_DATE_PATTERN),
    )


def _find_field(lines: list[str], pattern: re.Pattern[str]) -> _FieldMatch | None:
    """The trimmed value of the first matching line and its index."""
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            return _FieldMatch(strip_ascii_whitespace(match.group(1)), index)
    return None


def _field_value(lines: list[str], pattern: re.Pattern[str]) -> str:
    found = _find_field(lines, pattern)
    return "" if found is None else found.value


def _find_title(lines: list[str]) -> str:
    found = _find_field(lines, _TITLE_PATTERN)
    if found is None:
        return ""
    return _join_continuation_lines(found.value, islice(lines, found.line_index + 1, None))


def _join_continuation_lines(title: str, following_lines: Iterable[str]) -> str:
    """Appends the following indented, non-blank lines, separated by a single space (SPEC 5.1)."""
    parts = [title]
    for line in following_lines:
        continuation = strip_ascii_whitespace(line)
        if not line.startswith(_CONTINUATION_PREFIXES) or not continuation:
            break
        parts.append(continuation)
    return " ".join(parts)


def _normalize_language(value: str) -> str:
    language = strip_ascii_whitespace(value.split(",", 1)[0]).translate(_ASCII_LOWERCASE)
    return _LANGUAGE_CODES.get(language, language)
