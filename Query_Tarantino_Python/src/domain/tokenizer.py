"""
Tokenizes a book body or a query following SPEC 6. Stopwords are injected by
the caller, so the domain does no I/O.
"""

import re

from src.domain.model import TermOccurrences

MIN_TERM_LENGTH = 2

# bytes.lower() only converts ASCII A-Z and [a-z]+ only matches ASCII letters,
# so every other byte (digits, punctuation, non-ASCII) closes a term (SPEC 6.1).
_TERM_PATTERN = re.compile(rb"[a-z]+")


def tokenize(text: str, stopwords: frozenset[str]) -> dict[str, TermOccurrences]:
    positions: dict[str, list[int]] = {}
    for position, match in enumerate(_TERM_PATTERN.finditer(text.encode("utf-8").lower())):
        term = match.group().decode("ascii")
        if len(term) >= MIN_TERM_LENGTH and term not in stopwords:
            positions.setdefault(term, []).append(position)
    return {term: TermOccurrences(len(found), tuple(found)) for term, found in positions.items()}
