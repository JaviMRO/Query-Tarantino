from typing import Any

from pymongo import MongoClient, ReplaceOne

from src.domain.model import TermOccurrences


class MongodbIndexAdapter:
    """
    Implementation of InvertedIndexStorage using MongoDB (SPEC 7.2).
    Stores one document per term-book pair including the term positions.
    """

    def __init__(self, connection_url: str) -> None:
        self._client: MongoClient[dict[str, Any]] = MongoClient(connection_url)
        self._collection = self._client["query_tarantino"]["postings"]
        self._init_indexes()

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        if not terms:
            return

        operations = [
            ReplaceOne(
                {"term": term, "book_id": book_id},
                {
                    "term": term,
                    "book_id": book_id,
                    "tf": occurrences.tf,
                    "pos": list(occurrences.positions),
                },
                upsert=True,
            )
            for term, occurrences in terms.items()
        ]

        self._collection.bulk_write(operations)

    def _init_indexes(self) -> None:
        self._collection.create_index([("term", 1), ("book_id", 1)], unique=True)
        self._collection.create_index([("book_id", 1)])
