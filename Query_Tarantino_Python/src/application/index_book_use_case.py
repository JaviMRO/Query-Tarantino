from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Dict

from ..domain.header_parser import parse_header
from ..domain.ports import ControlStateStore, DatalakeStorage, InvertedIndexStorage, MetadataStorage
from ..domain.tokenizer import tokenize

STATUS_INDEXED = "INDEXED"
STATUS_SKIPPED = "SKIPPED"

# SPEC 5.4: YYYY-MM-DDTHH:MM:SSZ in UTC
INDEXED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IndexBookUseCase:
    """
    Indexes a single book already stored in the datalake, in the order
    defined in SPEC 8.2.
    """

    def __init__(
            self,
            datalake: DatalakeStorage,
            metadata_store: MetadataStorage,
            index_store: InvertedIndexStorage,
            control: ControlStateStore,
            stopwords: frozenset[str],
            clock: Callable[[], datetime] = utc_now
    ):
        self.datalake = datalake
        self.metadata_store = metadata_store
        self.index_store = index_store
        self.control = control
        self.stopwords = stopwords
        self.clock = clock

    def execute(self, book_id: int) -> Dict[str, Any]:
        """Runs SPEC 8.2 and returns the outcome as structured data."""

        # 1. Read header and body from the datalake
        header_text, body_text = self.datalake.load(book_id)
        header_path, body_path = self.datalake.get_paths(book_id)

        # 2. Extract metadata and write it with indexed_at empty
        book = parse_header(book_id, header_text)
        self.metadata_store.save(book, header_path, body_path)

        # 3-5. Only English books are indexed (SPEC 5.2)
        terms_count = self._index_body(book_id, body_text) if book.is_indexable() else 0

        # Appended only after the data is written (SPEC 8), indexed or not
        self.control.record_indexing(book_id)

        return {
            "status": STATUS_INDEXED if book.is_indexable() else STATUS_SKIPPED,
            "book_id": book_id,
            "language": book.language,
            "terms_count": terms_count,
        }

    def _index_body(self, book_id: int, body_text: str) -> int:
        terms = tokenize(body_text, self.stopwords)
        self.index_store.write_book_terms(book_id, terms)
        self.metadata_store.update_indexed_at(book_id, self.clock().strftime(INDEXED_AT_FORMAT))
        return len(terms)
