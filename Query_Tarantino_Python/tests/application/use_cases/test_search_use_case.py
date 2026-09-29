from src.application.use_cases.search_use_case import SearchResult, SearchUseCase
from src.domain.model import Book
from src.domain.search import SearchHit
from tests.application.fakes import FakeBookCatalog, FakePostingsReader

POSTINGS = {"best": {3: 1}, "car": {1: 1, 2: 1, 3: 1}, "mine": {2: 1}, "nice": {1: 1}}
BOOKS = {book_id: Book(book_id, f"Title {book_id}", "Author", "en", "") for book_id in (1, 2, 3)}


def build(official_stopwords: frozenset[str]) -> tuple[SearchUseCase, FakePostingsReader, FakeBookCatalog]:
    reader = FakePostingsReader(POSTINGS)
    catalog = FakeBookCatalog(BOOKS, indexed_count=3)
    return SearchUseCase(reader, catalog, official_stopwords), reader, catalog


def test_execute_returns_the_ranked_books_with_their_metadata(official_stopwords: frozenset[str]) -> None:
    use_case, _, _ = build(official_stopwords)

    results = use_case.execute("car best")

    assert [(result.book, f"{result.score:.6f}") for result in results] == [(BOOKS[3], "2.079442")]
    assert isinstance(results[0], SearchResult)


def test_rank_reads_only_the_distinct_query_terms_and_n_once(official_stopwords: frozenset[str]) -> None:
    use_case, reader, catalog = build(official_stopwords)

    hits = use_case.rank("CAR car Best")

    assert [hit.book_id for hit in hits] == [3]
    assert reader.requested_terms == [["best", "car"]]
    assert catalog.count_calls == 1


def test_a_query_without_terms_reads_nothing(official_stopwords: frozenset[str]) -> None:
    use_case, reader, catalog = build(official_stopwords)

    assert use_case.execute("the") == ()
    assert reader.requested_terms == []
    assert catalog.count_calls == 0


def test_rank_returns_search_hits(official_stopwords: frozenset[str]) -> None:
    use_case, _, _ = build(official_stopwords)

    assert all(isinstance(hit, SearchHit) for hit in use_case.rank("car"))
