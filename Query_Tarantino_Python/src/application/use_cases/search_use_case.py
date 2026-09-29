"""Search use case (SPEC 9): ranks the books for a query and attaches their metadata."""

from dataclasses import dataclass

from src.domain.model import Book
from src.domain.ports import BookCatalog, PostingsReader
from src.domain.search import SearchHit, query_terms, rank_books


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One result book with its metadata and unrounded score (SPEC 9.4)."""

    book: Book
    score: float


class SearchUseCase:
    """
    Opening the index is building the injected readers; each query then reads only the postings of its
    terms and N, once (SPEC 9.3). rank() stops at the ordered (book_id, score) list, as SPEC 11.5.3 measures.
    """

    def __init__(self, postings_reader: PostingsReader, catalog: BookCatalog, stopwords: frozenset[str]) -> None:
        self._postings_reader = postings_reader
        self._catalog = catalog
        self._stopwords = stopwords

    def rank(self, query: str) -> list[SearchHit]:
        """Ordered hits of the query; empty if no term remains after tokenizing (SPEC 9.1)."""
        terms = query_terms(query, self._stopwords)
        if not terms:
            return []
        postings = self._postings_reader.read_postings(terms)
        return rank_books(terms, postings, self._catalog.count_indexed_books())

    def execute(self, query: str) -> tuple[SearchResult, ...]:
        """Ordered results of the query, with the metadata of each book."""
        hits = self.rank(query)
        books = self._catalog.get_books([hit.book_id for hit in hits])
        return tuple(SearchResult(books[hit.book_id], hit.score) for hit in hits)
