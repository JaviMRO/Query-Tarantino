"""
Search rules (SPEC 9): query terms, AND matching, TF-IDF score and result
order. Pure functions; the postings and N are read by the caller.
"""

import math
from dataclasses import dataclass

from src.domain.text_processing.tokenizer import tokenize

ORDERING_DECIMALS = 9


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A matching book and its unrounded TF-IDF score (SPEC 9.3)."""

    book_id: int
    score: float


def query_terms(query: str, stopwords: frozenset[str]) -> list[str]:
    """Distinct terms of the query, tokenized like a body (SPEC 9.1), in alphabetical order (SPEC 9.3)."""
    return sorted(tokenize(query, stopwords))


def rank_books(terms: list[str], postings: dict[str, dict[int, int]], total_books: int) -> list[SearchHit]:
    """
    Books containing every term (SPEC 9.2), scored with TF-IDF adding the terms in the given alphabetical
    order (SPEC 9.3), sorted by score rounded to 9 decimals descending, then book_id ascending (SPEC 9.4).
    """
    if not terms:
        return []
    hits = [
        SearchHit(book_id, _score(book_id, terms, postings, total_books))
        for book_id in _matching_books(terms, postings)
    ]
    hits.sort(key=lambda hit: (-round(hit.score, ORDERING_DECIMALS), hit.book_id))
    return hits


def _matching_books(terms: list[str], postings: dict[str, dict[int, int]]) -> list[int]:
    """Walks the shortest posting list and keeps the books present in every other one."""
    shortest = min((postings[term] for term in terms), key=len)
    return [book_id for book_id in shortest if all(book_id in postings[term] for term in terms)]


def _score(book_id: int, terms: list[str], postings: dict[str, dict[int, int]], total_books: int) -> float:
    """
    Plain left-to-right additions, like Java and C++: sum() is not used because since Python 3.12 it
    compensates the rounding error of floats, which would change the last bits (SPEC 13.2).
    """
    score = 0.0
    for term in terms:
        score += _term_weight(float(postings[term][book_id]), float(len(postings[term])), float(total_books))
    return score


def _term_weight(tf: float, df: float, total_books: float) -> float:
    """(1 + ln tf) x ln(1 + N / df), in 64-bit floating point with the integers converted first (SPEC 13.2)."""
    return (1.0 + math.log(tf)) * math.log(1.0 + total_books / df)
