"""
Domain ports (interfaces). Implemented by the infrastructure adapters.
"""

from typing import Protocol

from src.domain.model import Book, BookText, FailureReason, StoredPaths, TermOccurrences


class DatalakeStorage(Protocol):
    """
    Port defining how a book's raw content is persisted in the datalake.
    Implementations: time-based, book-based, or batch-based.
    """

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        """Stores header and body using safe writes (SPEC 4.3)."""
        ...

    def load(self, book_id: int) -> BookText:
        """Reads a book from the datalake."""
        ...

    def get_paths(self, book_id: int) -> StoredPaths:
        """Paths of a stored book, in the same format as save()."""
        ...


class MetadataStorage(Protocol):
    """
    Port defining how metadata extracted from a book's header is persisted.
    Implementation: SQLite.
    """

    def save(self, book: Book, paths: StoredPaths) -> None:
        """Saves a book to the database with indexed_at as NULL."""
        ...

    def update_indexed_at(self, book_id: int, timestamp: str) -> None:
        """Updates the indexed_at UTC timestamp after successful indexing."""
        ...


class InvertedIndexStorage(Protocol):
    """
    Port defining how the inverted index is persisted.
    Implementations: monolithic JSON, MongoDB collection, or A-Z folders.
    """

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        """
        Writes or appends the terms of a single book to the index.
        JSON and folders store only tf; MongoDB also stores positions (SPEC 7).
        """
        ...


class BookDownloader(Protocol):
    """
    Port defining how to get a book's .txt from Project Gutenberg.
    Implementations: HTTP or Local. Both obtain the bytes and delegate
    decoding and splitting to src.domain.gutenberg_text.
    """

    def download(self, book_id: int) -> BookText:
        """Raises: DownloadException on HTTP_ERROR, NO_MARKERS, or EMPTY_BODY."""
        ...


class ControlStateStore(Protocol):
    """
    Port defining how to persist the control pipeline state.
    Implementation: text files in the control/ directory.
    """

    def record_download(self, book_id: int) -> None: ...

    def record_indexing(self, book_id: int) -> None: ...

    def record_failure(self, book_id: int, reason: FailureReason) -> None: ...

    def get_downloaded_books(self) -> set[int]: ...

    def get_indexed_books(self) -> set[int]: ...

    def get_failure_counts(self) -> dict[int, int]:
        """Returns a dict mapping book_id to its total number of failed attempts."""
        ...
