"""The index experiment: build, update, breakdown, storage, counts, opening and queries (SPEC 11.5.3)."""

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from pymongo import MongoClient
from pymongo.collection import Collection

from src.application.use_cases.index_book_use_case import IndexBookUseCase
from src.application.use_cases.ingest_book_use_case import IngestBookUseCase
from src.domain.ports import InvertedIndexStorage
from src.infrastructure.control.file_control_state_store import FileControlStateStore
from src.infrastructure.corpus.file_corpus_store import QUERIES_FILE
from src.infrastructure.datalake.layouts.book_based_adapter import BookBasedAdapter
from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader
from src.infrastructure.entrypoints.bench.bench_area import (
    BENCH_DATABASE,
    NEW_BOOKS,
    BenchContext,
    index_books,
    ingest_books,
)
from src.infrastructure.entrypoints.bench.experiments.index.query_benchmark import open_index, query_measurements
from src.infrastructure.entrypoints.bench.experiments.index.timed_ports import (
    TimeAccumulator,
    TimedDatalake,
    TimedIndexStorage,
    TimedMetadataStorage,
)
from src.infrastructure.entrypoints.bench.measurement.storage import DISK_BYTES, file_storage, tree_storage
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit, milliseconds, timed
from src.infrastructure.entrypoints.settings import IndexLayout
from src.infrastructure.entrypoints.wiring.composition import open_metadata_database, open_mongo_client
from src.infrastructure.index.hierarchical_folder_adapter import (
    HierarchicalFolderAdapter,
    count_folder_index,
    folder_index_dir,
)
from src.infrastructure.index.index_counts import IndexCounts
from src.infrastructure.index.mongodb_index_adapter import (
    POSTINGS_COLLECTION,
    MongodbIndexAdapter,
    PostingDocument,
    count_mongo_index,
    mongo_disk_bytes,
)
from src.infrastructure.index.monolithic_json_adapter import MonolithicJsonAdapter, count_json_index, json_index_path
from src.infrastructure.metadata.sqlite_metadata_adapter import SqliteMetadataAdapter, metadata_database_path


@dataclass(frozen=True, slots=True)
class _IndexUnderTest:
    """The writer of the structure, and how to measure its storage and its counts once it is built."""

    writer: InvertedIndexStorage
    storage: Callable[[], list[Measurement]]
    counts: Callable[[], IndexCounts]


@dataclass(frozen=True, slots=True)
class _BuildPorts:
    """The index writer under test and the accumulators of the build_time breakdown."""

    writer: InvertedIndexStorage
    lake_read: TimeAccumulator
    metadata_write: TimeAccumulator
    index_write: TimeAccumulator


def run_index(
    context: BenchContext, layout: IndexLayout, stopwords: frozenset[str], mongo_url: str
) -> list[Measurement]:
    """Runs the six steps of SPEC 11.5.3 in order over a book datalake filled beforehand."""
    with ExitStack() as resources:
        index = _index_under_test(context.bench_dir, layout, mongo_url, resources)
        ingest = IngestBookUseCase(
            LocalCorpusDownloader(context.corpus_dir), BookBasedAdapter(context.bench_dir), _control(context)
        )
        ingest_books(ingest, context.book_ids)
        build = _build(context, index.writer, stopwords)
        counts = index.counts()
        opened = open_index(context, layout, mongo_url, resources)
        queries = query_measurements(context.clock, opened.result, _read_queries(context.shared_dir), stopwords)
        return [
            *build,
            *index.storage(),
            Measurement("index_terms", counts.terms, Unit.COUNT),
            Measurement("index_postings", counts.postings, Unit.COUNT),
            Measurement("open_time", milliseconds(opened.elapsed_ns), Unit.MS),
            *queries,
        ]


def _index_under_test(data_dir: Path, layout: IndexLayout, mongo_url: str, resources: ExitStack) -> _IndexUnderTest:
    match layout:
        case IndexLayout.JSON:
            json_path = json_index_path(data_dir)
            return _IndexUnderTest(
                MonolithicJsonAdapter(data_dir), partial(file_storage, json_path), partial(count_json_index, data_dir)
            )
        case IndexLayout.FOLDERS:
            return _IndexUnderTest(
                HierarchicalFolderAdapter(data_dir),
                partial(tree_storage, folder_index_dir(data_dir)),
                partial(count_folder_index, data_dir),
            )
        case IndexLayout.MONGO:
            return _mongo_under_test(open_mongo_client(mongo_url, resources))


def _mongo_under_test(client: MongoClient[PostingDocument]) -> _IndexUnderTest:
    """The bench database is dropped first, never query_tarantino (SPEC 11.2)."""
    client.drop_database(BENCH_DATABASE)
    collection: Collection[PostingDocument] = client[BENCH_DATABASE][POSTINGS_COLLECTION]
    return _IndexUnderTest(
        MongodbIndexAdapter(collection),
        partial(_mongo_storage, client, collection),
        partial(count_mongo_index, collection),
    )


def _mongo_storage(client: MongoClient[PostingDocument], collection: Collection[PostingDocument]) -> list[Measurement]:
    return [Measurement(DISK_BYTES, mongo_disk_bytes(client, collection), Unit.BYTES)]


def _control(context: BenchContext) -> FileControlStateStore:
    return FileControlStateStore(context.bench_dir)


def _build(context: BenchContext, writer: InvertedIndexStorage, stopwords: frozenset[str]) -> list[Measurement]:
    """The first N - 50 books and the last 50 are timed as two regions (SPEC 11.5.3 steps 1 and 2)."""
    times = _BuildPorts(
        writer, TimeAccumulator(context.clock), TimeAccumulator(context.clock), TimeAccumulator(context.clock)
    )
    with ExitStack() as resources:
        use_case = _timed_index_use_case(context, times, stopwords, resources)
        first = timed(context.clock, partial(index_books, use_case, context.book_ids[:-NEW_BOOKS])).elapsed_ns
        last = timed(context.clock, partial(index_books, use_case, context.book_ids[-NEW_BOOKS:])).elapsed_ns
    return [
        Measurement("build_time", milliseconds(first + last), Unit.MS),
        Measurement("update_50_time", milliseconds(last), Unit.MS),
        Measurement("index_write_time", milliseconds(times.index_write.total_ns), Unit.MS),
        Measurement("metadata_write_time", milliseconds(times.metadata_write.total_ns), Unit.MS),
        Measurement("lake_read_time", milliseconds(times.lake_read.total_ns), Unit.MS),
    ]


def _timed_index_use_case(
    context: BenchContext, times: _BuildPorts, stopwords: frozenset[str], resources: ExitStack
) -> IndexBookUseCase:
    """The real clock sets indexed_at, which is never compared (SPEC 11.5.3 step 1)."""
    connection = open_metadata_database(metadata_database_path(context.bench_dir), resources)
    return IndexBookUseCase(
        TimedDatalake(BookBasedAdapter(context.bench_dir), times.lake_read),
        TimedMetadataStorage(SqliteMetadataAdapter(connection), times.metadata_write),
        TimedIndexStorage(times.writer, times.index_write),
        _control(context),
        stopwords,
    )


def _read_queries(shared_dir: Path) -> list[str]:
    """The 100 lines of shared/queries.txt, in file order (SPEC 11.1)."""
    with (shared_dir / QUERIES_FILE).open(encoding="utf-8", newline="") as file:
        return [content for line in file if (content := line.rstrip("\n"))]
