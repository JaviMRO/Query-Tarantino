import uuid
from collections.abc import Iterator

import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from src.infrastructure.entrypoints.bench.bench_area import BENCH_DATABASE, MongoTarget
from src.infrastructure.entrypoints.bench.experiments.index.index_experiment import run_index
from src.infrastructure.entrypoints.bench.measurement.timing import Unit
from src.infrastructure.entrypoints.settings import IndexLayout
from src.infrastructure.index.mongodb_index_adapter import PostingDocument
from tests.infrastructure.entrypoints.bench.conftest import Workspace, bench_context

MONGO_URL = "mongodb://localhost:27017"
SERVER_TIMEOUT_MS = 500
EXPECTED_TERMS = 4
EXPECTED_POSTINGS = 100 + 100 + 50 + 33
EXPECTED_RESULTS_TOTAL = 100 + 50 + 16
COMMON_METRICS = [
    ("build_time", Unit.MS),
    ("update_50_time", Unit.MS),
    ("index_write_time", Unit.MS),
    ("metadata_write_time", Unit.MS),
    ("lake_read_time", Unit.MS),
]
QUERY_METRICS = [
    ("index_terms", Unit.COUNT),
    ("index_postings", Unit.COUNT),
    ("open_time", Unit.MS),
    ("query_mean", Unit.MS),
    ("query_p50", Unit.MS),
    ("query_p95", Unit.MS),
    ("query_p99", Unit.MS),
    ("query_mean_t1", Unit.MS),
    ("query_mean_t2", Unit.MS),
    ("query_mean_t3", Unit.MS),
    ("query_results_total", Unit.COUNT),
]
STORAGE_METRICS = {
    IndexLayout.JSON: [("disk_bytes", Unit.BYTES)],
    IndexLayout.FOLDERS: [("disk_bytes", Unit.BYTES), ("file_count", Unit.FILES), ("dir_count", Unit.DIRS)],
    IndexLayout.MONGO: [("disk_bytes", Unit.BYTES)],
}


UNUSED_MONGO = MongoTarget(MONGO_URL, "unused")


@pytest.fixture
def mongo_client() -> Iterator[MongoClient[PostingDocument]]:
    client: MongoClient[PostingDocument] = MongoClient(MONGO_URL, serverSelectionTimeoutMS=SERVER_TIMEOUT_MS)
    try:
        client.admin.command("ping")
    except PyMongoError:
        client.close()
        pytest.skip("MongoDB server not reachable")
    yield client
    client.close()


@pytest.fixture
def mongo_target(mongo_client: MongoClient[PostingDocument]) -> Iterator[MongoTarget]:
    """A database of its own for each test, never the bench one, dropped at the end (CLAUDE.md 14.1)."""
    database = f"query_tarantino_test_{uuid.uuid4().hex}"
    yield MongoTarget(MONGO_URL, database)
    mongo_client.drop_database(database)


@pytest.mark.parametrize("layout", [IndexLayout.JSON, IndexLayout.FOLDERS])
def test_index_writes_its_metrics_in_spec_order(
    workspace: Workspace, layout: IndexLayout, official_stopwords: frozenset[str]
) -> None:
    measurements = run_index(bench_context(workspace), layout, official_stopwords, UNUSED_MONGO)

    assert [(measurement.metric, measurement.unit) for measurement in measurements] == [
        *COMMON_METRICS,
        *STORAGE_METRICS[layout],
        *QUERY_METRICS,
    ]


@pytest.mark.parametrize("layout", [IndexLayout.JSON, IndexLayout.FOLDERS])
def test_counts_and_results_are_the_same_in_every_structure(
    workspace: Workspace, layout: IndexLayout, official_stopwords: frozenset[str]
) -> None:
    measurements = {
        measurement.metric: measurement.value
        for measurement in run_index(bench_context(workspace), layout, official_stopwords, UNUSED_MONGO)
    }

    assert measurements["index_terms"] == EXPECTED_TERMS
    assert measurements["index_postings"] == EXPECTED_POSTINGS
    assert measurements["query_results_total"] == EXPECTED_RESULTS_TOTAL


def test_mongo_gives_the_same_counts_and_results(
    workspace: Workspace, official_stopwords: frozenset[str], mongo_target: MongoTarget
) -> None:
    measurements = run_index(bench_context(workspace), IndexLayout.MONGO, official_stopwords, mongo_target)

    values = {measurement.metric: measurement.value for measurement in measurements}
    assert [(measurement.metric, measurement.unit) for measurement in measurements] == [
        *COMMON_METRICS,
        *STORAGE_METRICS[IndexLayout.MONGO],
        *QUERY_METRICS,
    ]
    assert (values["index_terms"], values["index_postings"]) == (EXPECTED_TERMS, EXPECTED_POSTINGS)
    assert values["query_results_total"] == EXPECTED_RESULTS_TOTAL


def test_mongo_writes_only_to_the_database_it_is_given(
    workspace: Workspace,
    official_stopwords: frozenset[str],
    mongo_target: MongoTarget,
    mongo_client: MongoClient[PostingDocument],
) -> None:
    databases_before = set(mongo_client.list_database_names())

    run_index(bench_context(workspace), IndexLayout.MONGO, official_stopwords, mongo_target)

    assert set(mongo_client.list_database_names()) - databases_before == {mongo_target.database}
    assert BENCH_DATABASE not in set(mongo_client.list_database_names()) - databases_before
