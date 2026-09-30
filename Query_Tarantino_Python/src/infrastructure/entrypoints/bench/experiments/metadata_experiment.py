"""The metadata experiment: the SQLite store of SPEC 5.4 from 1,000 to 50,000 rows (SPEC 11.5.4)."""

import sqlite3
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path

from src.domain.model import Book, StoredPaths
from src.domain.text_processing.header_parser import parse_header
from src.infrastructure.data_layout import DATAMARTS_FOLDER
from src.infrastructure.datalake.layouts.book_based_adapter import BookBasedAdapter
from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader
from src.infrastructure.entrypoints.bench.bench_area import BenchContext, check
from src.infrastructure.entrypoints.bench.experiments.bench_sql import (
    COUNT_ROWS,
    INSERT_ROW,
    SELECT_IDS_BY_AUTHOR,
    SELECT_PATHS_BY_ID,
    SELECT_PATHS_BY_TITLE,
)
from src.infrastructure.entrypoints.bench.measurement.storage import file_storage
from src.infrastructure.entrypoints.bench.measurement.timing import (
    Measurement,
    Unit,
    per_second,
    sample_positions,
    timed,
    warm_mean_ms,
)
from src.infrastructure.entrypoints.wiring.composition import open_metadata_database
from src.infrastructure.metadata.sqlite_metadata_adapter import SqliteMetadataAdapter

METADATA_BENCH_FILE = "metadata_bench.sqlite"
COPY_ID_OFFSET = 1_000_000
SOURCE_INDEXED_AT = "2026-01-01T00:00:00Z"
LOOKUP_PASSES = 20

SqlValue = int | str


@dataclass(frozen=True, slots=True)
class MetadataRow:
    """One row of the books table: the metadata of a book and its book-layout paths (SPEC 11.5.4 step 1)."""

    book: Book
    paths: StoredPaths


@dataclass(frozen=True, slots=True)
class _Lookup:
    metric: str
    statement: str
    key: Callable[[Book], SqlValue]


_LOOKUPS = (
    _Lookup("query_author_mean", SELECT_IDS_BY_AUTHOR, lambda book: book.author),
    _Lookup("lookup_title_mean", SELECT_PATHS_BY_TITLE, lambda book: book.title),
    _Lookup("lookup_id_mean", SELECT_PATHS_BY_ID, lambda book: book.book_id),
)


def run_metadata(context: BenchContext, rows_count: int) -> list[Measurement]:
    """Runs the seven steps of SPEC 11.5.4 with K = rows_count rows; the books are the whole benchmark list."""
    source = _source_rows(context)
    parameters = [_parameters(row) for row in scaled_rows(source, rows_count)]
    database = context.bench_dir / DATAMARTS_FOLDER / METADATA_BENCH_FILE
    insert = _insert_throughput(context, database, parameters)
    with ExitStack() as resources:
        connection = _fresh_database(database, resources)
        bulk = _bulk_insert_throughput(context, connection, parameters)
        sample = [source[position].book for position in sample_positions(len(source))]
        lookups = [_lookup_mean(context, connection, sample, lookup) for lookup in _LOOKUPS]
    return [insert, bulk, *lookups, *file_storage(database)]


def scaled_rows(source: list[MetadataRow], rows_count: int) -> list[MetadataRow]:
    """K / 1000 copies; copy c replaces book_id with book_id + 1,000,000 x c, in order of copy then of id (step 2)."""
    check(rows_count % len(source) == 0, f"{rows_count} rows are not a whole number of copies of {len(source)}")
    return [
        MetadataRow(replace(row.book, book_id=row.book.book_id + COPY_ID_OFFSET * copy), row.paths)
        for copy in range(rows_count // len(source))
        for row in source
    ]


def _source_rows(context: BenchContext) -> list[MetadataRow]:
    """Every book read with the local downloader and parsed, with book-layout paths; nothing is written (step 1)."""
    downloader = LocalCorpusDownloader(context.corpus_dir)
    book_layout = BookBasedAdapter(context.bench_dir)
    return [
        MetadataRow(parse_header(book_id, downloader.download(book_id).header), book_layout.get_paths(book_id))
        for book_id in sorted(context.book_ids)
    ]


def _parameters(row: MetadataRow) -> tuple[SqlValue, ...]:
    book = row.book
    return (
        book.book_id,
        book.title,
        book.author,
        book.language,
        book.release_date,
        row.paths.header,
        row.paths.body,
        SOURCE_INDEXED_AT,
    )


def _fresh_database(database: Path, resources: ExitStack) -> sqlite3.Connection:
    """Deleted and created again with the SPEC 5.4 schema before each insertion step (step 3)."""
    database.unlink(missing_ok=True)
    connection = open_metadata_database(database, resources)
    SqliteMetadataAdapter(connection)
    return connection


def _insert_throughput(context: BenchContext, database: Path, rows: list[tuple[SqlValue, ...]]) -> Measurement:
    """Each row with its own INSERT OR REPLACE in its own transaction, as the pipeline does (step 4)."""
    with ExitStack() as resources:
        connection = _fresh_database(database, resources)
        elapsed_ns = timed(context.clock, partial(_insert_one_by_one, connection, rows)).elapsed_ns
        _check_row_count(connection, len(rows))
    return Measurement("insert_throughput", per_second(len(rows), elapsed_ns), Unit.ROWS_PER_S)


def _insert_one_by_one(connection: sqlite3.Connection, rows: list[tuple[SqlValue, ...]]) -> None:
    for row in rows:
        with connection:
            connection.execute(INSERT_ROW, row)


def _bulk_insert_throughput(
    context: BenchContext, connection: sqlite3.Connection, rows: list[tuple[SqlValue, ...]]
) -> Measurement:
    """The same rows in a single transaction with a single prepared statement (step 5)."""
    elapsed_ns = timed(context.clock, partial(_insert_in_bulk, connection, rows)).elapsed_ns
    _check_row_count(connection, len(rows))
    return Measurement("bulk_insert_throughput", per_second(len(rows), elapsed_ns), Unit.ROWS_PER_S)


def _insert_in_bulk(connection: sqlite3.Connection, rows: list[tuple[SqlValue, ...]]) -> None:
    with connection:
        connection.executemany(INSERT_ROW, rows)


def _check_row_count(connection: sqlite3.Connection, rows_count: int) -> None:
    (stored,) = connection.execute(COUNT_ROWS).fetchone()
    check(stored == rows_count, f"the table has {stored} rows, not {rows_count}")


def _lookup_mean(
    context: BenchContext, connection: sqlite3.Connection, sample: list[Book], lookup: _Lookup
) -> Measurement:
    """A warm-up pass, then 20 passes over the 50 sample rows timed as one region (step 6)."""
    values = [lookup.key(book) for book in sample]
    lookup_pass = partial(_count_answered, connection, lookup.statement, values)
    mean_ms = warm_mean_ms(context.clock, lookup_pass, LOOKUP_PASSES, LOOKUP_PASSES * len(values))
    check(lookup_pass() == len(values), f"a {lookup.metric} lookup returned no rows")
    return Measurement(lookup.metric, mean_ms, Unit.MS)


def _count_answered(connection: sqlite3.Connection, statement: str, values: list[SqlValue]) -> int:
    """Every execution reads all the rows it returns."""
    return sum(bool(connection.execute(statement, (value,)).fetchall()) for value in values)
