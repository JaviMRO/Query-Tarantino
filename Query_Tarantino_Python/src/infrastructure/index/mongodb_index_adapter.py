"""
Inverted index stored in MongoDB, one document per term-book pair with the
term positions (SPEC 7.2): MongodbIndexAdapter writes it and
MongoPostingsReader reads it for searches. The collection is injected, so the
pipeline and the benchmark can use different databases.
"""

from typing import TypedDict

from pymongo import ASCENDING, ReplaceOne
from pymongo.collection import Collection

from src.domain.model import TermOccurrences

POSTINGS_COLLECTION = "postings"


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
