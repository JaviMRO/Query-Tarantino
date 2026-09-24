"""
In-memory implementations of the ports, with their exact signatures so mypy
checks them against the Protocols. They share a CallLog to assert call order
across ports.
"""

from dataclasses import dataclass, field

from src.domain.model import Book, BookText, DownloadException, FailureReason, StoredPaths, TermOccurrences


@dataclass
class CallLog:
    calls: list[tuple[object, ...]] = field(default_factory=list)

    def record(self, method: str, *args: object) -> None:
        self.calls.append((method, *args))

    def methods(self) -> list[str]:
        return [str(call[0]) for call in self.calls]


def paths_for(book_id: int) -> StoredPaths:
    return StoredPaths(f"lake/{book_id}.header.txt", f"lake/{book_id}.body.txt")


class FakeDownloader:
    def __init__(self, text: BookText | None = None, failure: FailureReason | None = None) -> None:
        self.text = text
        self.failure = failure

    def download(self, book_id: int) -> BookText:
        if self.text is None:
            raise DownloadException(self.failure or FailureReason.HTTP_ERROR)
        return self.text


class FakeDatalake:
    def __init__(self, log: CallLog, books: dict[int, BookText] | None = None) -> None:
        self.log = log
        self.books = dict(books or {})

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        self.log.record("save_text", book_id, text)
        self.books[book_id] = text
        return paths_for(book_id)

    def load(self, book_id: int) -> BookText:
        return self.books[book_id]

    def get_paths(self, book_id: int) -> StoredPaths:
        return paths_for(book_id)


class FakeMetadataStorage:
    def __init__(self, log: CallLog) -> None:
        self.log = log

    def save(self, book: Book, paths: StoredPaths) -> None:
        self.log.record("save_metadata", book, paths)

    def update_indexed_at(self, book_id: int, timestamp: str) -> None:
        self.log.record("update_indexed_at", book_id, timestamp)


class FakeIndexStorage:
    def __init__(self, log: CallLog) -> None:
        self.log = log

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        self.log.record("write_book_terms", book_id, terms)


class FakeControlStateStore:
    def __init__(
        self,
        log: CallLog | None = None,
        downloaded: set[int] | None = None,
        indexed: set[int] | None = None,
        failures: dict[int, int] | None = None,
    ) -> None:
        self.log = log or CallLog()
        self.downloaded = set(downloaded or ())
        self.indexed = set(indexed or ())
        self.failures = dict(failures or {})

    def record_download(self, book_id: int) -> None:
        self.log.record("record_download", book_id)
        self.downloaded.add(book_id)

    def record_indexing(self, book_id: int) -> None:
        self.log.record("record_indexing", book_id)
        self.indexed.add(book_id)

    def record_failure(self, book_id: int, reason: FailureReason) -> None:
        self.log.record("record_failure", book_id, reason)
        self.failures[book_id] = self.failures.get(book_id, 0) + 1

    def get_downloaded_books(self) -> set[int]:
        return self.downloaded

    def get_indexed_books(self) -> set[int]:
        return self.indexed

    def get_failure_counts(self) -> dict[int, int]:
        return self.failures
