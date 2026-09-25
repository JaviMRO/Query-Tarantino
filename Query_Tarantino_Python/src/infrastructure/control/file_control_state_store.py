"""
Implementation of ControlStateStore that persists the pipeline state as
append-only text files under control/ (SPEC 8).
"""

from pathlib import Path

from src.domain.model import FailureReason

_DOWNLOADED_FILE = "downloaded_books.txt"
_INDEXED_FILE = "indexed_books.txt"
_FAILED_FILE = "failed_books.txt"


class FileControlStateStore:
    def __init__(self, data_dir: Path) -> None:
        self._control_dir = data_dir / "control"

    def record_download(self, book_id: int) -> None:
        self._append(_DOWNLOADED_FILE, str(book_id))

    def record_indexing(self, book_id: int) -> None:
        self._append(_INDEXED_FILE, str(book_id))

    def record_failure(self, book_id: int, reason: FailureReason) -> None:
        """Appends a line with the cumulative attempt count for book_id."""
        attempts = self.get_failure_counts().get(book_id, 0) + 1
        self._append(_FAILED_FILE, f"{book_id};{reason.value};{attempts}")

    def get_downloaded_books(self) -> set[int]:
        return {int(line) for line in self._read_lines(_DOWNLOADED_FILE)}

    def get_indexed_books(self) -> set[int]:
        return {int(line) for line in self._read_lines(_INDEXED_FILE)}

    def get_failure_counts(self) -> dict[int, int]:
        """The line with the highest ATTEMPTS counts for each book_id (SPEC 8)."""
        counts: dict[int, int] = {}
        for line in self._read_lines(_FAILED_FILE):
            book_id_text, _reason, attempts_text = line.split(";")
            book_id, attempts = int(book_id_text), int(attempts_text)
            counts[book_id] = max(counts.get(book_id, 0), attempts)
        return counts

    def _append(self, file_name: str, line: str) -> None:
        self._control_dir.mkdir(parents=True, exist_ok=True)
        with (self._control_dir / file_name).open("a", encoding="utf-8", newline="") as file:
            file.write(f"{line}\n")

    def _read_lines(self, file_name: str) -> list[str]:
        path = self._control_dir / file_name
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").split("\n") if line]
