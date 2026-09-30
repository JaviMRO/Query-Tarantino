"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg into fixed-size id ranges of 1,000 (SPEC 4.1 "batch").
"""

from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.data_layout import BATCH_LAKE_FOLDER
from src.infrastructure.datalake.book_files import (
    complete_book_ids_in,
    paths_in_folder,
    read_book_files,
    write_book_files,
)

_BATCH_SIZE = 1000


class BatchBasedAdapter:
    """Stores each book in datalake_batch/AAAAAA-BBBBBB/, the range of 1,000 ids it belongs to (SPEC 4.1)."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        """Header is written before body, both via the safe write of SPEC 4.3."""
        paths = self.get_paths(book_id)
        write_book_files(self._data_dir, paths, text)
        return paths

    def load(self, book_id: int) -> BookText:
        """Reads a stored book; raises FileNotFoundError if it is not complete in the datalake."""
        return read_book_files(self._data_dir, self.get_paths(book_id))

    def get_paths(self, book_id: int) -> StoredPaths:
        """Derived from the id alone, without touching the disk (SPEC 14.4)."""
        range_start = (book_id // _BATCH_SIZE) * _BATCH_SIZE
        range_end = range_start + _BATCH_SIZE - 1
        return paths_in_folder(f"{BATCH_LAKE_FOLDER}/{range_start:06d}-{range_end:06d}", book_id)


def stored_batch_book_ids(data_dir: Path) -> set[int]:
    """Ids of every complete book in the batch lake, found by listing it (SPEC 11.5.1 detect_new_scan)."""
    lake_dir = data_dir / BATCH_LAKE_FOLDER
    if not lake_dir.is_dir():
        return set()
    return {book_id for batch in lake_dir.iterdir() for book_id in complete_book_ids_in(batch)}
