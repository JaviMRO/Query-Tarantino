"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg by individual book id (SPEC 4.1 "book").
"""

from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.datalake.safe_write import write_text_safely

_ROOT_FOLDER = "datalake_book"


class BookBasedAdapter:
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
        folder = f"{_ROOT_FOLDER}/{book_id}"
        return StoredPaths(f"{folder}/header.txt", f"{folder}/body.txt")
