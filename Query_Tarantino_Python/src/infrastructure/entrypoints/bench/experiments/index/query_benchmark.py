"""Opening the index and timing the benchmark queries (SPEC 11.5.3 steps 5 and 6)."""

import statistics
from contextlib import ExitStack
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from pymongo.collection import Collection

from src.domain.ports import PostingsReader
from src.domain.search import SearchHit, query_terms, rank_books
from src.infrastructure.entrypoints.bench.bench_area import BENCH_DATABASE, BenchContext, check
from src.infrastructure.entrypoints.bench.measurement.timing import (
    Measurement,
    NanoClock,
    Timed,
    Unit,
    milliseconds,
    nearest_rank,
    timed,
)
from src.infrastructure.entrypoints.settings import IndexLayout
from src.infrastructure.entrypoints.wiring.composition import (
    build_postings_reader,
    open_metadata_database,
    open_mongo_client,
)
from src.infrastructure.index.mongodb_index_adapter import POSTINGS_COLLECTION, PostingDocument
from src.infrastructure.metadata.sqlite_metadata_adapter import SqliteBookCatalog, metadata_database_path

MEASURED_PASSES = 5
QUERY_PERCENTILES = (50, 95, 99)
QUERY_TERM_COUNTS = (1, 2, 3)


@dataclass(frozen=True, slots=True)
class OpenedIndex:
    """An index ready for queries: its reader and N, read once when it was opened (SPEC 9.3)."""

    reader: PostingsReader
    total_books: int


@dataclass(frozen=True, slots=True)
class _Queries:
    texts: list[str]
    stopwords: frozenset[str]


def open_index(context: BenchContext, layout: IndexLayout, mongo_url: str, resources: ExitStack) -> Timed[OpenedIndex]:
    """
    SQLite opened and N read; json also parses the whole file and mongo also creates a client and pings the
    server; folders does nothing else (SPEC 11.5.3 step 5).
    """
    return timed(context.clock, partial(_open, context.bench_dir, layout, mongo_url, resources))


def query_measurements(
    clock: NanoClock, opened: OpenedIndex, queries: list[str], stopwords: frozenset[str]
) -> list[Measurement]:
    """A warm-up pass, then 5 measured passes with each query timed on its own: 500 samples (SPEC 11.5.3 step 6)."""
    batch = _Queries(queries, stopwords)
    _timed_pass(clock, opened, batch)
    passes = [_timed_pass(clock, opened, batch) for _ in range(MEASURED_PASSES)]
    samples_ms = [milliseconds(query.elapsed_ns) for measured_pass in passes for query in measured_pass]
    results_total = sum(len(query.result) for query in passes[0])
    return [
        *_latency(samples_ms),
        *_latency_by_term_count(samples_ms, batch),
        Measurement("query_results_total", results_total, Unit.COUNT),
    ]


def _open(data_dir: Path, layout: IndexLayout, mongo_url: str, resources: ExitStack) -> OpenedIndex:
    connection = open_metadata_database(metadata_database_path(data_dir), resources)
    reader = build_postings_reader(layout, data_dir, partial(_pinged_bench_postings, mongo_url, resources))
    return OpenedIndex(reader, SqliteBookCatalog(connection).count_indexed_books())


def _pinged_bench_postings(mongo_url: str, resources: ExitStack) -> Collection[PostingDocument]:
    client = open_mongo_client(mongo_url, resources)
    client.admin.command("ping")
    return client[BENCH_DATABASE][POSTINGS_COLLECTION]


def _timed_pass(clock: NanoClock, opened: OpenedIndex, batch: _Queries) -> list[Timed[list[SearchHit]]]:
    return [timed(clock, partial(_rank, opened, query, batch.stopwords)) for query in batch.texts]


def _rank(opened: OpenedIndex, query: str, stopwords: frozenset[str]) -> list[SearchHit]:
    """SPEC 9.1 to 9.4 up to the ordered (book_id, score) list; titles, authors and printing are excluded."""
    terms = query_terms(query, stopwords)
    if not terms:
        return []
    return rank_books(terms, opened.reader.read_postings(terms), opened.total_books)


def _latency(samples_ms: list[float]) -> list[Measurement]:
    ascending = sorted(samples_ms)
    percentiles = [
        Measurement(f"query_p{percentile}", nearest_rank(ascending, percentile), Unit.MS)
        for percentile in QUERY_PERCENTILES
    ]
    return [Measurement("query_mean", statistics.fmean(samples_ms), Unit.MS), *percentiles]


def _latency_by_term_count(samples_ms: list[float], batch: _Queries) -> list[Measurement]:
    """Mean over the samples of the queries with 1, 2 and 3 distinct terms after tokenization."""
    term_counts = [len(query_terms(query, batch.stopwords)) for query in batch.texts]
    measurements = []
    for term_count in QUERY_TERM_COUNTS:
        group = [ms for position, ms in enumerate(samples_ms) if term_counts[position % len(term_counts)] == term_count]
        check(bool(group), f"no benchmark query has {term_count} distinct terms")
        measurements.append(Measurement(f"query_mean_t{term_count}", statistics.fmean(group), Unit.MS))
    return measurements
