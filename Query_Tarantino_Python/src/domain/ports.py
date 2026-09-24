# src/domain/ports.py
from typing import Protocol, Tuple, Set, Dict, List
from ..domain.model import Book  # Assuming Book is defined in model.py

class DatalakeStorage(Protocol):
    """
    Port defining how a book's raw content is persisted in the datalake.
    Implementations: time-based, book-based, or batch-based.
    """
    def save(self, book_id: int, header_text: str, body_text: str) -> Tuple[str, str]:
        """
        Stores header and body using safe writes.
        Returns: (header_path, body_path) relative to TARANTINO_DATA_DIR using '/' as separator.
        """
        ...

    def load(self, book_id: int) -> Tuple[str, str]:
        """
        Reads a book from the datalake.
        Returns: (header_text, body_text).
        """
        ...


class MetadataStorage(Protocol):
    """
    Port defining how metadata extracted from a book's header is persisted.
    Implementation: SQLite.
    """
    def save(self, book: Book, header_path: str, body_path: str) -> None:
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
    def write_book_terms(self, book_id: int, terms: Dict[str, int]) -> None:
        """Writes or appends the terms of a single book to the index."""
        ...


class BookDownloader(Protocol):
    """
    Port defining how to download a book's .txt from Project Gutenberg
    and split header/body using START/END markers.
    Implementations: HTTP or Local.
    """
    def download(self, book_id: int) -> Tuple[str, str]:
        """
        Downloads and splits the text.
        Returns: (header_text, body_text).
        Raises: DownloadException on HTTP_ERROR, NO_MARKERS, or EMPTY_BODY.
        """
        ...


class ControlStateStore(Protocol):
    """
    Port defining how to persist the control pipeline state.
    Implementation: text files in the control/ directory.
    """
    def record_download(self, book_id: int) -> None:
        ...

    def record_indexing(self, book_id: int) -> None:
        ...

    def record_failure(self, book_id: int, reason: str) -> None:
        ...

    def get_downloaded_books(self) -> Set[int]:
        ...

    def get_indexed_books(self) -> Set[int]:
        ...

    def get_failure_counts(self) -> Dict[int, int]:
        """Returns a dict mapping book_id to its total number of failed attempts."""
        ...
