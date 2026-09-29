import sqlite3
from collections.abc import Iterator

import pytest

from src.domain.model import Book, StoredPaths
from src.infrastructure.metadata.sqlite_metadata_adapter import SqliteBookCatalog, SqliteMetadataAdapter

BOOK = Book(2701, "Moby Dick; Or, The Whale", "Herman Melville", "en", "July 1, 2001")
PATHS = StoredPaths("datalake_book/2701/header.txt", "datalake_book/2701/body.txt")
INDEXED_AT = "2026-09-28T10:15:00Z"


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    database = sqlite3.connect(":memory:")
    yield database
    database.close()


def rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    return connection.execute("SELECT * FROM books ORDER BY book_id").fetchall()


def test_construction_creates_the_books_table_and_its_three_indexes(connection: sqlite3.Connection) -> None:
    SqliteMetadataAdapter(connection)

    names = {name for (name,) in connection.execute("SELECT name FROM sqlite_master")}

    assert {"books", "idx_books_author", "idx_books_language", "idx_books_title"} <= names


def test_construction_twice_keeps_existing_rows(connection: sqlite3.Connection) -> None:
    SqliteMetadataAdapter(connection).save(BOOK, PATHS)

    SqliteMetadataAdapter(connection)

    assert len(rows(connection)) == 1


def test_save_stores_every_field_with_relative_paths_and_null_indexed_at(connection: sqlite3.Connection) -> None:
    SqliteMetadataAdapter(connection).save(BOOK, PATHS)

    assert rows(connection) == [
        (
            2701,
            "Moby Dick; Or, The Whale",
            "Herman Melville",
            "en",
            "July 1, 2001",
            "datalake_book/2701/header.txt",
            "datalake_book/2701/body.txt",
            None,
        )
    ]


def test_saving_the_same_book_again_replaces_it_and_clears_indexed_at(connection: sqlite3.Connection) -> None:
    adapter = SqliteMetadataAdapter(connection)
    adapter.save(BOOK, PATHS)
    adapter.update_indexed_at(BOOK.book_id, INDEXED_AT)

    adapter.save(Book(2701, "New title", "Herman Melville", "en", ""), PATHS)

    assert [(row[1], row[7]) for row in rows(connection)] == [("New title", None)]


def test_update_indexed_at_sets_the_timestamp(connection: sqlite3.Connection) -> None:
    adapter = SqliteMetadataAdapter(connection)
    adapter.save(BOOK, PATHS)

    adapter.update_indexed_at(BOOK.book_id, INDEXED_AT)

    assert rows(connection)[0][7] == INDEXED_AT


def test_catalog_counts_only_indexed_books(connection: sqlite3.Connection) -> None:
    adapter = SqliteMetadataAdapter(connection)
    adapter.save(BOOK, PATHS)
    adapter.save(Book(5, "Other", "", "fr", ""), PATHS)
    adapter.update_indexed_at(BOOK.book_id, INDEXED_AT)

    assert SqliteBookCatalog(connection).count_indexed_books() == 1


def test_catalog_returns_the_metadata_of_the_requested_books(connection: sqlite3.Connection) -> None:
    SqliteMetadataAdapter(connection).save(BOOK, PATHS)

    assert SqliteBookCatalog(connection).get_books([2701]) == {2701: BOOK}


def test_catalog_raises_for_an_unknown_book(connection: sqlite3.Connection) -> None:
    SqliteMetadataAdapter(connection)

    with pytest.raises(KeyError):
        SqliteBookCatalog(connection).get_books([1])
