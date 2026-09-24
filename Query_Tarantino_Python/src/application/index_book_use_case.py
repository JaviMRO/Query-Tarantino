from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.header_parser import parse_header
from src.domain.model import Book, BookText
from src.domain.ports import ControlStateStore, DatalakeStorage, InvertedIndexStorage, MetadataStorage
from src.domain.tokenizer import tokenize

INDEXED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True, slots=True)
class BookIndexed:
    book_id: int
    terms_count: int


@dataclass(frozen=True, slots=True)
class BookSkipped:
    """Not in English: only its metadata was saved."""

    book_id: int
    language: str


IndexResult = BookIndexed | BookSkipped


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IndexBookUseCase:
    """
    Indexes a book already stored in the datalake (SPEC 8.2):
    metadata is always saved, but only English books reach the index.
    The book is recorded as indexed only after its data is written (SPEC 8).
    indexed_at uses INDEXED_AT_FORMAT, in UTC (SPEC 5.4).
    """

    def __init__(
        self,
        datalake: DatalakeStorage,
        metadata_store: MetadataStorage,
        index_store: InvertedIndexStorage,
        control: ControlStateStore,
        stopwords: frozenset[str],
        clock: Callable[[], datetime] = utc_now,
    ):
        self.datalake = datalake
        self.metadata_store = metadata_store
        self.index_store = index_store
        self.control = control
        self.stopwords = stopwords
        self.clock = clock

    def execute(self, book_id: int) -> IndexResult:
        text = self.datalake.load(book_id)
        book = self._save_metadata(book_id, text)
        result = self._index_or_skip(book, text.body)
        self.control.record_indexing(book_id)
        return result

    def _save_metadata(self, book_id: int, text: BookText) -> Book:
        book = parse_header(book_id, text.header)
        self.metadata_store.save(book, self.datalake.get_paths(book_id))
        return book

    def _index_or_skip(self, book: Book, body: str) -> IndexResult:
        if not book.is_indexable():
            return BookSkipped(book.book_id, book.language)
        return self._index_body(book, body)

    def _index_body(self, book: Book, body: str) -> BookIndexed:
        terms = tokenize(body, self.stopwords)
        self.index_store.write_book_terms(book.book_id, terms)
        self.metadata_store.update_indexed_at(book.book_id, self.clock().strftime(INDEXED_AT_FORMAT))
        return BookIndexed(book.book_id, len(terms))
