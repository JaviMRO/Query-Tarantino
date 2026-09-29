"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg by individual book id (SPEC 4.1 "book").
"""

from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.data_layout import BOOK_LAKE_FOLDER
from src.infrastructure.datalake.book_files import read_book_files, write_book_files


class BookBasedAdapter:
    """Stores each book in datalake_book/N/header.txt and datalake_book/N/body.txt (SPEC 4.1)."""

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
        """Derived from the id alone, without touching the disk."""
        folder = f"{BOOK_LAKE_FOLDER}/{book_id}"
        return StoredPaths(f"{folder}/header.txt", f"{folder}/body.txt")
