"""
Inverted index stored in MongoDB, one document per term-book pair with the
term positions (SPEC 7.2): MongodbIndexAdapter writes it and
MongoPostingsReader reads it for searches. The collection is injected, so the
pipeline and the benchmark can use different databases.
"""

from typing import TypedDict

from pymongo import ASCENDING, MongoClient, ReplaceOne
from pymongo.collection import Collection

from src.domain.model import TermOccurrences
from src.infrastructure.index.index_counts import IndexCounts

POSTINGS_COLLECTION = "postings"

_TERMS_FIELD = "terms"
_COUNT_TERMS_PIPELINE: list[dict[str, object]] = [{"$group": {"_id": "$term"}}, {"$count": _TERMS_FIELD}]
_STORAGE_STATS_PIPELINE: list[dict[str, object]] = [{"$collStats": {"storageStats": {}}}]


class PostingDocument(TypedDict):
    """One document of the postings collection (SPEC 7.2)."""

    term: str
    book_id: int
    tf: int
    pos: list[int]


class MongodbIndexAdapter:
    """Implementation of InvertedIndexStorage; creates the SPEC 7.2 indexes on construction if missing."""

    def __init__(self, collection: Collection[PostingDocument]) -> None:
        self._collection = collection
        self._collection.create_index([("term", ASCENDING), ("book_id", ASCENDING)], unique=True)
        self._collection.create_index([("book_id", ASCENDING)])

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        """A single bulk write with one upserting replaceOne per term, so reindexing never duplicates."""
        if not terms:
            return
        operations = [
            ReplaceOne(
                {"term": term, "book_id": book_id},
                PostingDocument(term=term, book_id=book_id, tf=occurrences.tf, pos=list(occurrences.positions)),
                upsert=True,
            )
            for term, occurrences in terms.items()
        ]
        self._collection.bulk_write(operations)


class MongoPostingsReader:
    """Implementation of PostingsReader: a single $in query for all the terms (SPEC 7.2)."""

    def __init__(self, collection: Collection[PostingDocument]) -> None:
        self._collection = collection

    def read_postings(self, terms: list[str]) -> dict[str, dict[int, int]]:
        """book_id -> tf for each requested term."""
        postings: dict[str, dict[int, int]] = {term: {} for term in terms}
        for document in self._collection.find({"term": {"$in": terms}}, {"_id": 0, "term": 1, "book_id": 1, "tf": 1}):
            postings[document["term"]][document["book_id"]] = document["tf"]
        return postings


def count_mongo_index(collection: Collection[PostingDocument]) -> IndexCounts:
    """Distinct terms, grouped by the server, and documents, one per term-book pair (SPEC 7.2, 11.5.3 step 4)."""
    reply = collection.database.command("aggregate", collection.name, pipeline=_COUNT_TERMS_PIPELINE, cursor={})
    first_batch = reply["cursor"]["firstBatch"]
    terms = int(first_batch[0][_TERMS_FIELD]) if first_batch else 0
    return IndexCounts(terms, collection.count_documents({}))


def mongo_disk_bytes(client: MongoClient[PostingDocument], collection: Collection[PostingDocument]) -> int:
    """
    storageSize + totalIndexSize of the collection, after the fsync admin command so that the data has reached
    the disk; the size is compressed by MongoDB (SPEC 11.5.3 step 3).
    """
    client.admin.command("fsync")
    reply = collection.database.command("aggregate", collection.name, pipeline=_STORAGE_STATS_PIPELINE, cursor={})
    storage_stats = reply["cursor"]["firstBatch"][0]["storageStats"]
    return int(storage_stats["storageSize"]) + int(storage_stats["totalIndexSize"])
