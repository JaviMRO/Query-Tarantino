"""
Tokenizes a book body or a query following SPEC 6. Stopwords are injected by
the caller, so the domain does no I/O.
"""

import re

from src.domain.model import TermOccurrences

MIN_TERM_LENGTH = 2

_ASCII_LETTER_RUN = re.compile(rb"[a-z]+")


def tokenize(text: str, stopwords: frozenset[str]) -> dict[str, TermOccurrences]:
    """
    Works on the UTF-8 bytes: bytes.lower() only folds ASCII A-Z and
    [a-z]+ only matches ASCII letters, so any other byte (digits,
    punctuation, non-ASCII) closes a term. Every closed term takes a
    position, including the ones discarded afterwards (SPEC 6.1).
    """
    positions: dict[str, list[int]] = {}
    for position, match in enumerate(_ASCII_LETTER_RUN.finditer(text.encode("utf-8").lower())):
        term = match.group().decode("ascii")
        if len(term) >= MIN_TERM_LENGTH and term not in stopwords:
            positions.setdefault(term, []).append(position)
    return {
        term: TermOccurrences(len(term_positions), tuple(term_positions)) for term, term_positions in positions.items()
    }
