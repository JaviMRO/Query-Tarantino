"""Size of an inverted index, the same in every structure for the same books (SPEC 11.5.3 step 4, 11.7)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexCounts:
    """Distinct terms and distinct term-book pairs of an index."""

    terms: int
    postings: int
