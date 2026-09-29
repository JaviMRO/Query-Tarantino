"""
Generation of the 100 benchmark queries (SPEC 1.2): terms drawn with a seeded
random generator from three document-frequency bands of the full index.
"""

import random
from collections.abc import Iterator
from enum import Enum
from itertools import islice

from src.domain.ports import BookCatalog, TermStatistics

QUERY_SEED = 42
TERMS_PER_QUERY = (1,) * 40 + (2,) * 30 + (3,) * 30
QUERY_TERM_SEPARATOR = " "

_RARE_MIN_BOOKS = 2
_RARE_MAX_BOOKS = 5
_FREQUENT_SHARE_DIVISOR = 2
_MEDIUM_SHARE_DIVISOR = 20


class FrequencyBand(Enum):
    """Bands of SPEC 1.2, in the order the term slots take them in turns."""

    FREQUENT = "frequent"
    MEDIUM = "medium"
    RARE = "rare"


_BAND_ORDER = (FrequencyBand.FREQUENT, FrequencyBand.MEDIUM, FrequencyBand.RARE)


class GenerateQueriesUseCase:
    """
    Term slot i, counted over all the queries in order, belongs to band i mod 3. Each band draws its terms
    without replacement from its candidates in alphabetical order, so the same index and seed always give the
    same queries, and a query never repeats a term.
    """

    def __init__(self, statistics: TermStatistics, catalog: BookCatalog, rng: random.Random) -> None:
        self._statistics = statistics
        self._catalog = catalog
        self._rng = rng

    def execute(self) -> list[str]:
        """The query lines; raises ValueError if a band has fewer terms than it needs."""
        slot_bands = [_BAND_ORDER[slot % len(_BAND_ORDER)] for slot in range(sum(TERMS_PER_QUERY))]
        drawn = self._draw_terms(slot_bands)
        slot_terms = iter([next(drawn[band]) for band in slot_bands])
        return [QUERY_TERM_SEPARATOR.join(islice(slot_terms, count)) for count in TERMS_PER_QUERY]

    def _draw_terms(self, slot_bands: list[FrequencyBand]) -> dict[FrequencyBand, Iterator[str]]:
        candidates = _terms_by_band(self._statistics.document_frequencies(), self._catalog.count_indexed_books())
        drawn: dict[FrequencyBand, Iterator[str]] = {}
        for band in _BAND_ORDER:
            needed = slot_bands.count(band)
            if len(candidates[band]) < needed:
                raise ValueError(f"Band {band.value} has {len(candidates[band])} terms; {needed} are needed")
            drawn[band] = iter(self._rng.sample(candidates[band], needed))
        return drawn


def _terms_by_band(document_frequencies: dict[str, int], total_books: int) -> dict[FrequencyBand, list[str]]:
    """Candidates of each band in alphabetical order; terms outside every band are left out."""
    candidates: dict[FrequencyBand, list[str]] = {band: [] for band in _BAND_ORDER}
    for term in sorted(document_frequencies):
        band = _band_of(document_frequencies[term], total_books)
        if band is not None:
            candidates[band].append(term)
    return candidates


def _band_of(books_with_term: int, total_books: int) -> FrequencyBand | None:
    """Frequent: more than 50 % of the books; medium: 5 % to 50 %; rare: 2 to 5 books (integer arithmetic)."""
    if books_with_term * _FREQUENT_SHARE_DIVISOR > total_books:
        return FrequencyBand.FREQUENT
    if books_with_term * _MEDIUM_SHARE_DIVISOR >= total_books:
        return FrequencyBand.MEDIUM
    if _RARE_MIN_BOOKS <= books_with_term <= _RARE_MAX_BOOKS:
        return FrequencyBand.RARE
    return None
