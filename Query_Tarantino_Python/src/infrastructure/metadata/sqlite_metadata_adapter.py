import sqlite3
from pathlib import Path

from src.domain.model import Book, StoredPaths

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
"""


class SqliteMetadataAdapter:
    """
    Implementation of MetadataStorage using SQLite (SPEC 5.4).
    """

    def __init__(self, data_dir: Path) -> None:
        self._db_path = data_dir / "datamarts" / "metadata.sqlite"
        self._init_db()

    def save(self, book: Book, paths: StoredPaths) -> None:
        query = """
            INSERT OR REPLACE INTO books
            (book_id, title, author, language, release_date, header_path, body_path, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                query,
                (
                    book.book_id,
                    book.title,
                    book.author,
                    book.language,
                    book.release_date,
                    paths.header,
                    paths.body,
                ),
            )

    def update_indexed_at(self, book_id: int, timestamp: str) -> None:
        query = "UPDATE books SET indexed_at = ? WHERE book_id = ?"
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(query, (timestamp, book_id))

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_SCHEMA)
