import sqlite3

import pytest

from src.domain.model import Book, StoredPaths
from src.infrastructure.entrypoints.bench.bench_area import BenchValidityError
from src.infrastructure.entrypoints.bench.experiments.metadata_experiment import (
    METADATA_BENCH_FILE,
    MetadataRow,
    run_metadata,
    scaled_rows,
)
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit
from tests.infrastructure.entrypoints.bench.conftest import Workspace, bench_context

SOURCE_BOOKS = tuple(range(1, 11))
PATHS = StoredPaths("datalake_book/1342/header.txt", "datalake_book/1342/body.txt")


def test_metadata_writes_the_seven_metrics_with_k_rows(workspace: Workspace) -> None:
    context = bench_context(workspace, SOURCE_BOOKS)

    measurements = run_metadata(context, 20)

    assert [(measurement.metric, measurement.unit) for measurement in measurements] == [
        ("insert_throughput", Unit.ROWS_PER_S),
        ("bulk_insert_throughput", Unit.ROWS_PER_S),
        ("query_author_mean", Unit.MS),
        ("lookup_title_mean", Unit.MS),
        ("lookup_id_mean", Unit.MS),
        ("disk_bytes", Unit.BYTES),
    ]
    assert measurements[0] == Measurement("insert_throughput", 20_000.0, Unit.ROWS_PER_S)


def test_the_database_keeps_the_rows_of_the_bulk_step(workspace: Workspace) -> None:
    context = bench_context(workspace, SOURCE_BOOKS)

    run_metadata(context, 20)

    with sqlite3.connect(context.bench_dir / "datamarts" / METADATA_BENCH_FILE) as connection:
        stored_ids = [book_id for (book_id,) in connection.execute("SELECT book_id FROM books ORDER BY book_id")]
    assert stored_ids == [*SOURCE_BOOKS, *(book_id + 1_000_000 for book_id in SOURCE_BOOKS)]


def test_copies_replace_the_id_and_keep_every_other_column() -> None:
    source = [MetadataRow(Book(1342, "Pride", "Austen", "en", "1998"), PATHS)]

    copies = scaled_rows(source, 4)

    assert [row.book.book_id for row in copies] == [1342, 1001342, 2001342, 3001342]
    assert {(row.book.title, row.paths) for row in copies} == {("Pride", PATHS)}


def test_rows_that_are_not_whole_copies_make_the_run_invalid() -> None:
    source = [MetadataRow(Book(1, "T", "A", "en", ""), PATHS), MetadataRow(Book(2, "T", "A", "en", ""), PATHS)]

    with pytest.raises(BenchValidityError):
        scaled_rows(source, 3)
