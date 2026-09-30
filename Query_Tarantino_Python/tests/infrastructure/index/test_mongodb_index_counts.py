import uuid
from collections.abc import Iterator

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from src.domain.model import TermOccurrences
from src.infrastructure.index.index_counts import IndexCounts
from src.infrastructure.index.mongodb_index_adapter import (
    MongodbIndexAdapter,
    PostingDocument,
    count_mongo_index,
    mongo_disk_bytes,
)

MONGO_URL = "mongodb://localhost:27017"
SERVER_TIMEOUT_MS = 500


@pytest.fixture
def client() -> Iterator[MongoClient[PostingDocument]]:
    mongo: MongoClient[PostingDocument] = MongoClient(MONGO_URL, serverSelectionTimeoutMS=SERVER_TIMEOUT_MS)
    try:
        mongo.admin.command("ping")
    except PyMongoError:
        mongo.close()
        pytest.skip("MongoDB server not reachable")
    yield mongo
    mongo.close()


@pytest.fixture
def collection(client: MongoClient[PostingDocument]) -> Iterator[Collection[PostingDocument]]:
    database_name = f"query_tarantino_test_{uuid.uuid4().hex}"
    yield client[database_name]["postings"]
    client.drop_database(database_name)


def test_mongo_counts_distinct_terms_and_documents(collection: Collection[PostingDocument]) -> None:
    index = MongodbIndexAdapter(collection)
    index.write_book_terms(1, {"whale": TermOccurrences(1, (0,)), "ship": TermOccurrences(1, (1,))})
    index.write_book_terms(2, {"whale": TermOccurrences(1, (0,))})

    assert count_mongo_index(collection) == IndexCounts(2, 3)


def test_an_empty_collection_has_no_terms(collection: Collection[PostingDocument]) -> None:
    MongodbIndexAdapter(collection)

    assert count_mongo_index(collection) == IndexCounts(0, 0)


def test_disk_bytes_are_positive_once_something_is_stored(
    client: MongoClient[PostingDocument], collection: Collection[PostingDocument]
) -> None:
    MongodbIndexAdapter(collection).write_book_terms(1, {"whale": TermOccurrences(1, (0,))})

    assert mongo_disk_bytes(client, collection) > 0
