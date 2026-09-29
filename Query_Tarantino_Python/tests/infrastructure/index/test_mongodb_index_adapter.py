import uuid
from collections.abc import Iterator

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from src.domain.model import TermOccurrences
from src.infrastructure.index.mongodb_index_adapter import MongodbIndexAdapter, MongoPostingsReader, PostingDocument

MONGO_URL = "mongodb://localhost:27017"
SERVER_TIMEOUT_MS = 500


@pytest.fixture
def collection() -> Iterator[Collection[PostingDocument]]:
    client: MongoClient[PostingDocument] = MongoClient(MONGO_URL, serverSelectionTimeoutMS=SERVER_TIMEOUT_MS)
    try:
        client.admin.command("ping")
    except PyMongoError:
        client.close()
        pytest.skip("MongoDB server not reachable")
    database_name = f"query_tarantino_test_{uuid.uuid4().hex}"
    yield client[database_name]["postings"]
    client.drop_database(database_name)
    client.close()


def test_one_document_per_term_book_pair_with_int_tf_and_sorted_positions(
    collection: Collection[PostingDocument],
) -> None:
    MongodbIndexAdapter(collection).write_book_terms(7, {"whale": TermOccurrences(3, (1, 4, 9))})

    documents = list(collection.find({}, {"_id": 0}))

    assert documents == [{"term": "whale", "book_id": 7, "tf": 3, "pos": [1, 4, 9]}]


def test_reindexing_a_book_does_not_duplicate_documents(collection: Collection[PostingDocument]) -> None:
    adapter = MongodbIndexAdapter(collection)
    adapter.write_book_terms(7, {"whale": TermOccurrences(1, (1,))})

    adapter.write_book_terms(7, {"whale": TermOccurrences(2, (1, 5))})

    assert list(collection.find({}, {"_id": 0})) == [{"term": "whale", "book_id": 7, "tf": 2, "pos": [1, 5]}]


def test_construction_creates_the_spec_7_2_indexes(collection: Collection[PostingDocument]) -> None:
    MongodbIndexAdapter(collection)

    keys = {tuple(index["key"].items()): index.get("unique", False) for index in collection.list_indexes()}

    assert keys[(("term", 1), ("book_id", 1))] is True
    assert (("book_id", 1),) in keys


def test_reader_returns_the_postings_of_each_term(collection: Collection[PostingDocument]) -> None:
    adapter = MongodbIndexAdapter(collection)
    adapter.write_book_terms(1, {"whale": TermOccurrences(2, (0, 4)), "ship": TermOccurrences(1, (2,))})
    adapter.write_book_terms(2, {"whale": TermOccurrences(1, (7,))})

    postings = MongoPostingsReader(collection).read_postings(["whale", "ahab"])

    assert postings == {"whale": {1: 2, 2: 1}, "ahab": {}}
