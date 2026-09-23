from typing import Dict, Any, Protocol
from datetime import datetime, timezone
from src.domain.ports import DatalakeStorage, MetadataStorage, InvertedIndexStorage, ControlStateStore
from src.domain.model import Book


class HeaderParser(Protocol):
    """Domain service to parse metadata from the header text."""

    def parse(self, book_id: int, header_text: str) -> Book:
        ...


class Tokenizer(Protocol):
    """Domain service to tokenize the body text."""

    def tokenize(self, text: str) -> Dict[str, Any]:
        ...


class IndexBookUseCase:
    """
    Orchestrates the indexing process for a single book.
    Follows strictly the order defined in SPEC 8.2.
    """

    def __init__(
            self,
            datalake: DatalakeStorage,
            metadata_store: MetadataStorage,
            index_store: InvertedIndexStorage,
            control: ControlStateStore,
            header_parser: HeaderParser,
            tokenizer: Tokenizer
    ):
        self.datalake = datalake
        self.metadata_store = metadata_store
        self.index_store = index_store
        self.control = control
        self.header_parser = header_parser
        self.tokenizer = tokenizer

    def execute(self, book_id: int) -> Dict[str, Any]:
        """Executes the indexing pipeline and returns the result as structured data."""

        # 1. Read header and body from the datalake
        header_text, body_text = self.datalake.load(book_id)

        # Note: DatalakeStorage needs a method to return paths for the DB schema
        header_path, body_path = self.datalake.get_paths(book_id)

        # 2. Extract metadata and write to SQLite (indexed_at is NULL initially)
        book = self.header_parser.parse(book_id, header_text)
        self.metadata_store.save(book, header_path, body_path)

        # 3. If the language is not 'en', stop here (SPEC 8.2.3)
        if not book.is_indexable():
            self.control.record_indexing(book_id)
            return {
                "status": "SKIPPED",
                "book_id": book_id,
                "language": book.language,
                "message": "Book not in English. Metadata saved, indexing skipped."
            }

        # 4. Tokenize the body and write to the index
        terms = self.tokenizer.tokenize(body_text)
        self.index_store.write_book_terms(book_id, terms)

        # 5. Update indexed_at in SQLite (SPEC 8.2.5)
        # Format: YYYY-MM-DDTHH:MM:SSZ as required by SPEC 5.4
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.metadata_store.update_indexed_at(book_id, now_utc)

        # Register in control files
        self.control.record_indexing(book_id)

        return {
            "status": "INDEXED",
            "book_id": book_id,
            "terms_count": len(terms)
        }