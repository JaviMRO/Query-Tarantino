"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg by download date and hour, in UTC (SPEC 4.1 "time").

Unlike the book-id and batch layouts, a book's folder cannot be derived from
its id alone: it depends on when it was downloaded, which this adapter does
not keep across calls (a book is typically indexed in a separate run from
the one that downloaded it). get_paths() and load() therefore locate an
already-saved book by scanning its datalake/*/*/ folders for the id-prefixed
files SPEC 4.1 describes (the scan is what SPEC 11 benchmarks as
lookup_scan_mean, unlike the O(1) lookup of the book and batch layouts).
"""

from datetime import datetime, timezone
from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.datalake.safe_write import write_text_safely

_ROOT_FOLDER = "datalake"


class TimeBasedAdapter:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        """Header is written before body, both via the safe write of SPEC 4.3."""
        moment = datetime.now(timezone.utc)
        folder = f"{_ROOT_FOLDER}/{moment:%Y%m%d}/{moment:%H}"
        paths = StoredPaths(f"{folder}/{book_id}.header.txt", f"{folder}/{book_id}.body.txt")
        write_text_safely(self._data_dir / paths.header, text.header)
        write_text_safely(self._data_dir / paths.body, text.body)
        return paths

    def load(self, book_id: int) -> BookText:
        paths = self.get_paths(book_id)
        header = (self._data_dir / paths.header).read_text(encoding="utf-8")
        body = (self._data_dir / paths.body).read_text(encoding="utf-8")
        return BookText(header, body)

    def get_paths(self, book_id: int) -> StoredPaths:
        """Raises FileNotFoundError if book_id is not in the datalake."""
        header_name = f"{book_id}.header.txt"
        for header_file in self._data_dir.glob(f"{_ROOT_FOLDER}/*/*/{header_name}"):
            relative = header_file.relative_to(self._data_dir).as_posix()
            folder = relative.removesuffix(f"/{header_name}")
            return StoredPaths(relative, f"{folder}/{book_id}.body.txt")
        raise FileNotFoundError(f"Book {book_id} not found in {self._data_dir / _ROOT_FOLDER}")
