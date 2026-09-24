"""
Extracts metadata from a Project Gutenberg header following SPEC 5.1 and 5.2.
"""

import re

from src.domain.model import Book

ASCII_WHITESPACE = " \t\n\r\f\v"

_FIELD_PATTERNS = {
    "title": re.compile(r"^Title:\s*(.*)$", re.IGNORECASE),
    "author": re.compile(r"^Author:\s*(.*)$", re.IGNORECASE),
    "language": re.compile(r"^Language:\s*(.*)$", re.IGNORECASE),
    "release_date": re.compile(r"^Release date:\s*([^\[]*)", re.IGNORECASE),
}

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


def parse_header(book_id: int, header: str) -> Book:
    lines = header.split("\n")
    return Book(
        book_id=book_id,
        title=_find_title(lines),
        author=_find_field(lines, "author")[0],
        language=_normalize_language(_find_field(lines, "language")[0]),
        release_date=_find_field(lines, "release_date")[0],
    )


def _find_field(lines: list[str], field: str) -> tuple[str, int]:
    """Returns the trimmed value of the first matching line and its index, or ("", -1)."""
    for index, line in enumerate(lines):
        match = _FIELD_PATTERNS[field].match(line)
        if match:
            return match.group(1).strip(ASCII_WHITESPACE), index
    return "", -1


def _find_title(lines: list[str]) -> str:
    title, index = _find_field(lines, "title")
    if index < 0:
        return title
    for line in lines[index + 1:]:
        continuation = line.strip(ASCII_WHITESPACE)
        if not line.startswith((" ", "\t")) or not continuation:
            break
        title = f"{title} {continuation}"
    return title


def _normalize_language(value: str) -> str:
    language = value.split(",", 1)[0].strip(ASCII_WHITESPACE).translate(_ASCII_LOWERCASE)
    return _LANGUAGE_CODES.get(language, language)
