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
    decoding and splitting to src.domain.text_processing.gutenberg_text.
    """

    def download(self, book_id: int) -> BookText:
        """Raises: DownloadException on HTTP_ERROR, NO_MARKERS, or EMPTY_BODY."""
        ...


class ControlStateStore(Protocol):
    """
    Port defining how to persist the control pipeline state.
    Implementation: text files in the control/ directory.
    """

    def record_download(self, book_id: int) -> None:
        """Records a book stored in the datalake (downloaded_books.txt)."""
        ...

    def record_indexing(self, book_id: int) -> None:
        """Records a book processed by the indexer (indexed_books.txt)."""
        ...

    def record_failure(self, book_id: int, reason: FailureReason) -> None:
        """Records one more failed download attempt (failed_books.txt)."""
        ...

    def get_downloaded_books(self) -> set[int]:
        """Ids of the books stored in the datalake."""
        ...

    def get_indexed_books(self) -> set[int]:
        """Ids of the books processed by the indexer."""
        ...

    def get_failure_counts(self) -> dict[int, int]:
        """Returns a dict mapping book_id to its total number of failed attempts."""
        ...


class PostingsReader(Protocol):
    """
    Read side of the inverted index, used by searches (SPEC 9.2, 9.3).
    Implementations: monolithic JSON, MongoDB collection, or A-Z folders.
    """

    def read_postings(self, terms: list[str]) -> dict[str, dict[int, int]]:
        """For each requested term, book_id -> tf; a term that is not indexed maps to an empty dict."""
        ...


class BookCatalog(Protocol):
    """
    Read side of the metadata, used by searches (SPEC 9.3, 9.4).
    Implementation: SQLite.
    """

    def count_indexed_books(self) -> int:
        """N of the TF-IDF formula: the number of indexed books (SPEC 9.3)."""
        ...

    def get_books(self, book_ids: list[int]) -> dict[int, Book]:
        """Metadata of each requested book, by id."""
        ...


class RawTextSource(Protocol):
    """
    Port defining how to get a book's whole text, normalized (SPEC 3.3) but not split, as the local corpus
    stores it (SPEC 3.6). Implementation: HTTP.
    """

    def fetch_text(self, book_id: int) -> str:
        """Raises: DownloadException with HTTP_ERROR if no URL returned 200."""
        ...


class CorpusStore(Protocol):
    """
    Port defining how the benchmark corpus is persisted while it is selected (SPEC 1.1, 3.6).
    Implementation: corpus_raw/N.txt files plus the append-only list of selected ids.
    """

    def save_text(self, book_id: int, text: str) -> None:
        """Stores the normalized text of a selected book."""
        ...

    def record_selected(self, book_id: int) -> None:
        """Appends a selected book to the list, after its text is stored."""
        ...

    def get_selected_books(self) -> list[int]:
        """Selected ids, in selection (ascending) order."""
        ...


class TermStatistics(Protocol):
    """Port defining how to read the document frequency of every indexed term (SPEC 1.2). Implementation: JSON."""

    def document_frequencies(self) -> dict[str, int]:
        """Number of books each indexed term appears in."""
        ...
