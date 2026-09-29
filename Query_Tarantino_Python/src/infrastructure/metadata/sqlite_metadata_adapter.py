"""
Book metadata in SQLite (SPEC 5.4): SqliteMetadataAdapter writes it while
indexing and SqliteBookCatalog reads it for searches (SPEC 9.3, 9.4). Both use
a connection created once by the entrypoint.
"""

import sqlite3
from pathlib import Path

from src.domain.model import Book, StoredPaths
from src.infrastructure.data_layout import DATAMARTS_FOLDER

METADATA_FILE = "metadata.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  book_id      INTEGER PRIMARY KEY,
  title        TEXT NOT NULL,
  author       TEXT NOT NULL,
  language     TEXT NOT NULL,
  release_date TEXT NOT NULL,
  header_path  TEXT NOT NULL,
  body_path    TEXT NOT NULL,
  indexed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_books_author   ON books(lower(author));
CREATE INDEX IF NOT EXISTS idx_books_language ON books(language);
CREATE INDEX IF NOT EXISTS idx_books_title    ON books(title);
"""

_SAVE_BOOK = """
INSERT OR REPLACE INTO books
(book_id, title, author, language, release_date, header_path, body_path, indexed_at)
VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
"""
_UPDATE_INDEXED_AT = "UPDATE books SET indexed_at = ? WHERE book_id = ?"
_COUNT_INDEXED_BOOKS = "SELECT COUNT(*) FROM books WHERE indexed_at IS NOT NULL"
_SELECT_BOOK = "SELECT title, author, language, release_date FROM books WHERE book_id = ?"


def metadata_database_path(data_dir: Path) -> Path:
    """Location of the metadata database: datamarts/metadata.sqlite (SPEC 5.4)."""
    return data_dir / DATAMARTS_FOLDER / METADATA_FILE


class SqliteMetadataAdapter:
    """Implementation of MetadataStorage; ensures the exact SPEC 5.4 schema, indexes included, on construction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.executescript(_SCHEMA)

    def save(self, book: Book, paths: StoredPaths) -> None:
        """INSERT OR REPLACE with indexed_at NULL and the relative datalake paths, in one transaction."""
        row = (book.book_id, book.title, book.author, book.language, book.release_date, paths.header, paths.body)
        with self._connection:
            self._connection.execute(_SAVE_BOOK, row)

    def update_indexed_at(self, book_id: int, timestamp: str) -> None:
        """Sets the YYYY-MM-DDTHH:MM:SSZ timestamp given by the use case, in one transaction."""
        with self._connection:
            self._connection.execute(_UPDATE_INDEXED_AT, (timestamp, book_id))


class SqliteBookCatalog:
    """Implementation of BookCatalog: reads N and the metadata of the result books (SPEC 9.3, 9.4)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def count_indexed_books(self) -> int:
        """N of the TF-IDF formula: books with indexed_at set (SPEC 9.3)."""
        (count,) = self._connection.execute(_COUNT_INDEXED_BOOKS).fetchone()
        return int(count)

    def get_books(self, book_ids: list[int]) -> dict[int, Book]:
        """Metadata of each requested book; raises KeyError if one is not in the database."""
        return {book_id: self._get_book(book_id) for book_id in book_ids}

    def _get_book(self, book_id: int) -> Book:
        row = self._connection.execute(_SELECT_BOOK, (book_id,)).fetchone()
        if row is None:
            raise KeyError(f"Book {book_id} is not in the metadata database")
        title, author, language, release_date = row
        return Book(book_id, title, author, language, release_date)
