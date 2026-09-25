"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg into fixed-size id ranges of 1,000 (SPEC 4.1 "batch").
"""

from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.datalake.safe_write import write_text_safely

_ROOT_FOLDER = "datalake_batch"
_BATCH_SIZE = 1000


class BatchBasedAdapter:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        """Header is written before body, both via the safe write of SPEC 4.3."""
        paths = self.get_paths(book_id)
        write_text_safely(self._data_dir / paths.header, text.header)
        write_text_safely(self._data_dir / paths.body, text.body)
        return paths

    def load(self, book_id: int) -> BookText:
        paths = self.get_paths(book_id)
        header = (self._data_dir / paths.header).read_text(encoding="utf-8")
        body = (self._data_dir / paths.body).read_text(encoding="utf-8")
        return BookText(header, body)

    def get_paths(self, book_id: int) -> StoredPaths:
        range_start = (book_id // _BATCH_SIZE) * _BATCH_SIZE
        range_end = range_start + _BATCH_SIZE - 1
        folder = f"{_ROOT_FOLDER}/{range_start:06d}-{range_end:06d}"
        return StoredPaths(f"{folder}/{book_id}.header.txt", f"{folder}/{book_id}.body.txt")
