"""
Implementation of ControlStateStore that persists the pipeline state as
append-only text files under control/ (SPEC 8).
"""

from collections.abc import Iterator
from pathlib import Path

from src.domain.model import FailureReason
from src.infrastructure.data_layout import CONTROL_FOLDER
from src.infrastructure.file_writes import append_line

_DOWNLOADED_FILE = "downloaded_books.txt"
_INDEXED_FILE = "indexed_books.txt"
_FAILED_FILE = "failed_books.txt"
_FIELD_SEPARATOR = ";"


class FileControlStateStore:
    """Control files are only ever appended to; reading them is a single line-by-line pass (SPEC 8)."""

    def __init__(self, data_dir: Path) -> None:
        self._control_dir = data_dir / CONTROL_FOLDER
        self._control_dir.mkdir(parents=True, exist_ok=True)

    def record_download(self, book_id: int) -> None:
        """Appends the id to downloaded_books.txt."""
        append_line(self._control_dir / _DOWNLOADED_FILE, str(book_id))

    def record_indexing(self, book_id: int) -> None:
        """Appends the id to indexed_books.txt."""
        append_line(self._control_dir / _INDEXED_FILE, str(book_id))

    def record_failure(self, book_id: int, reason: FailureReason) -> None:
        """Appends N;REASON;ATTEMPTS, where ATTEMPTS is the highest previous count plus one."""
        attempts = self.get_failure_counts().get(book_id, 0) + 1
        line = _FIELD_SEPARATOR.join((str(book_id), reason.value, str(attempts)))
        append_line(self._control_dir / _FAILED_FILE, line)

    def get_downloaded_books(self) -> set[int]:
        """Ids in downloaded_books.txt; repeated lines change nothing."""
        return {int(line) for line in self._read_lines(_DOWNLOADED_FILE)}

    def get_indexed_books(self) -> set[int]:
        """Ids in indexed_books.txt; repeated lines change nothing."""
        return {int(line) for line in self._read_lines(_INDEXED_FILE)}

    def get_failure_counts(self) -> dict[int, int]:
        """The line with the highest ATTEMPTS counts for each book_id (SPEC 8)."""
        counts: dict[int, int] = {}
        for line in self._read_lines(_FAILED_FILE):
            book_id_text, _reason, attempts_text = line.split(_FIELD_SEPARATOR)
            book_id, attempts = int(book_id_text), int(attempts_text)
            counts[book_id] = max(counts.get(book_id, 0), attempts)
        return counts

    def _read_lines(self, file_name: str) -> Iterator[str]:
        """Streams the non-empty lines of a control file; a missing file is an empty state."""
        path = self._control_dir / file_name
        if not path.is_file():
            return
        with path.open(encoding="utf-8", newline="") as file:
            for line in file:
                content = line.rstrip("\n")
                if content:
                    yield content
