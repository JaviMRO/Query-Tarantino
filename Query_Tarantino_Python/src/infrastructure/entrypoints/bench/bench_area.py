"""
The bench area, <data dir>/bench/, where every run works from scratch, and what
every experiment receives (SPEC 11.2, 11.7).
"""

import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.application.use_cases.index_book_use_case import IndexBookUseCase
from src.application.use_cases.ingest_book_use_case import IngestBookUseCase
from src.infrastructure.entrypoints.bench.measurement.timing import NanoClock

BENCH_FOLDER = "bench"
BENCH_DATABASE = "query_tarantino_bench"
NEW_BOOKS = 50


@dataclass(frozen=True, slots=True)
class MongoTarget:
    """The server and the database the bench writes to: query_tarantino_bench in every measured run (SPEC 11.2)."""

    url: str
    database: str


class BenchValidityError(Exception):
    """A validity check failed: the run writes no rows and exits with code 2 (SPEC 11.7)."""


@dataclass(frozen=True, slots=True)
class BenchContext:
    """The bench area, the local corpus, the shared files, the books of the configuration and the timing clock."""

    bench_dir: Path
    corpus_dir: Path
    shared_dir: Path
    book_ids: tuple[int, ...]
    clock: NanoClock


def reset_bench_area(bench_dir: Path) -> None:
    """Empties the bench area; nothing outside it is ever touched (SPEC 11.2). A failed deletion is raised."""
    if bench_dir.exists():
        shutil.rmtree(bench_dir)
    bench_dir.mkdir(parents=True)


def check(is_valid: bool, message: str) -> None:
    """Raises BenchValidityError with the message if the check failed (SPEC 11.7)."""
    if not is_valid:
        raise BenchValidityError(message)


def ingest_books(ingest: IngestBookUseCase, book_ids: Iterable[int]) -> None:
    """Downloads and stores the books in order, as the pipeline does."""
    for book_id in book_ids:
        ingest.execute(book_id)


def index_books(index: IndexBookUseCase, book_ids: Iterable[int]) -> None:
    """Indexes the books in order, as the pipeline does."""
    for book_id in book_ids:
        index.execute(book_id)
