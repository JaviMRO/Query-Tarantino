"""
The bench command of SPEC 10 and 11: runs one configuration inside the bench
area and appends its rows to --out, only if every validity check passed.
"""

import sys
import time
from contextlib import ExitStack
from pathlib import Path

import requests

from src.infrastructure.corpus.file_corpus_store import BENCHMARK_BOOK_COUNT, BENCHMARK_IDS_FILE, FileCorpusStore
from src.infrastructure.downloader.gutenberg_http_downloader import (
    AUTOMATED_CLIENT_SECONDS_BETWEEN_REQUESTS,
    GUTENBERG_BASE_URL,
    GutenbergHttpDownloader,
)
from src.infrastructure.entrypoints.bench.bench_area import (
    BENCH_DATABASE,
    BENCH_FOLDER,
    BenchContext,
    BenchValidityError,
    MongoTarget,
    check,
    reset_bench_area,
)
from src.infrastructure.entrypoints.bench.configuration import Configuration, Experiment
from src.infrastructure.entrypoints.bench.experiments.download_experiment import run_download
from src.infrastructure.entrypoints.bench.experiments.index.index_experiment import run_index
from src.infrastructure.entrypoints.bench.experiments.lake.datalake_experiment import run_datalake
from src.infrastructure.entrypoints.bench.experiments.lake.recovery_experiment import run_recovery
from src.infrastructure.entrypoints.bench.experiments.metadata_experiment import run_metadata
from src.infrastructure.entrypoints.bench.measurement.csv_output import append_measurements
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement
from src.infrastructure.entrypoints.settings import IndexLayout, LakeLayout, Settings
from src.infrastructure.entrypoints.wiring.commands import EXIT_OK, EXIT_RUNTIME_ERROR
from src.infrastructure.stopwords.file_stopwords_loader import load_stopwords


def bench(settings: Settings, configuration: Configuration, out: Path) -> int:
    """Empties the bench area, runs the configuration and appends its rows; 2 if a validity check failed."""
    try:
        measurements = _run(settings, configuration, _context(settings, configuration))
    except BenchValidityError as error:
        print(f"tarantino bench: invalid run, no rows written: {error}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    append_measurements(out, configuration, measurements)
    print(_outcome(configuration, len(measurements), out))
    return EXIT_OK


def _outcome(configuration: Configuration, rows: int, out: Path) -> str:
    """What the run wrote; baseline writes no rows, run_all.sh only records its peak_rss (SPEC 11.5.6)."""
    name = (
        f"{configuration.experiment.value} {configuration.structure} n={configuration.n_books} run={configuration.run}"
    )
    if rows == 0:
        return f"{name}: no rows written, as expected"
    return f"{name}: {rows} rows appended to {out}"


def _context(settings: Settings, configuration: Configuration) -> BenchContext:
    """The bench area is emptied right after the lock; the books are the first N of the list (SPEC 11.1, 11.2)."""
    bench_dir = settings.data_dir / BENCH_FOLDER
    reset_bench_area(bench_dir)
    return BenchContext(
        bench_dir, settings.corpus_dir, settings.shared_dir, _books_of(settings, configuration), time.perf_counter_ns
    )


def _books_of(settings: Settings, configuration: Configuration) -> tuple[int, ...]:
    """
    The whole list of 1,000 books for metadata, whose n_books counts rows; the first N ids otherwise (SPEC 11.1,
    11.5.4).
    """
    listed = FileCorpusStore(settings.corpus_dir, settings.shared_dir / BENCHMARK_IDS_FILE).get_selected_books()
    if configuration.experiment is Experiment.METADATA:
        check(len(listed) == BENCHMARK_BOOK_COUNT, f"{BENCHMARK_IDS_FILE} lists {len(listed)} books, not 1000")
        return tuple(listed)
    check(len(listed) >= configuration.n_books, f"{BENCHMARK_IDS_FILE} lists only {len(listed)} books")
    return tuple(listed[: configuration.n_books])


def _run(settings: Settings, configuration: Configuration, context: BenchContext) -> list[Measurement]:
    match configuration.experiment:
        case Experiment.DATALAKE:
            return run_datalake(context, LakeLayout(configuration.structure))
        case Experiment.RECOVERY:
            return run_recovery(context, LakeLayout(configuration.structure))
        case Experiment.INDEX:
            stopwords = load_stopwords(settings.shared_dir)
            mongo = MongoTarget(settings.mongo_url, BENCH_DATABASE)
            return run_index(context, IndexLayout(configuration.structure), stopwords, mongo)
        case Experiment.METADATA:
            return run_metadata(context, configuration.n_books)
        case Experiment.DOWNLOAD:
            return _run_download(context)
        case Experiment.BASELINE:
            load_stopwords(settings.shared_dir)
            return []


def _run_download(context: BenchContext) -> list[Measurement]:
    """An automated client, so it waits 2 seconds between requests, like the corpus selection (SPEC 11.5.5)."""
    with ExitStack() as resources:
        session = resources.enter_context(requests.Session())
        downloader = GutenbergHttpDownloader(
            session, GUTENBERG_BASE_URL, time.monotonic, time.sleep, AUTOMATED_CLIENT_SECONDS_BETWEEN_REQUESTS
        )
        return run_download(context, downloader)
