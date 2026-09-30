"""The download experiment: real downloads from Project Gutenberg, waits included (SPEC 11.5.5)."""

from functools import partial

from src.application.use_cases.ingest_book_use_case import IngestBookUseCase
from src.domain.ports import BookDownloader
from src.infrastructure.control.file_control_state_store import FileControlStateStore
from src.infrastructure.datalake.layouts.book_based_adapter import BookBasedAdapter
from src.infrastructure.entrypoints.bench.bench_area import BenchContext, ingest_books
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit, per_second, timed


def run_download(context: BenchContext, downloader: BookDownloader) -> list[Measurement]:
    """IngestBookUseCase with a book datalake for the books of the configuration; a failed download is recorded."""
    control = FileControlStateStore(context.bench_dir)
    ingest = IngestBookUseCase(downloader, BookBasedAdapter(context.bench_dir), control)
    elapsed_ns = timed(context.clock, partial(ingest_books, ingest, context.book_ids)).elapsed_ns
    return [Measurement("http_throughput", per_second(len(context.book_ids), elapsed_ns), Unit.BOOKS_PER_S)]
