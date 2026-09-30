"""
Inverted index stored as a single JSON file in canonical form (SPEC 7.1):
MonolithicJsonAdapter writes it and JsonPostingsReader reads it for searches.
"""

import json
from pathlib import Path

from src.domain.model import TermOccurrences
from src.infrastructure.data_layout import DATAMARTS_FOLDER
from src.infrastructure.file_writes import atomic_text_writer
from src.infrastructure.index.index_counts import IndexCounts

INDEX_FILE = "inverted_index.json"

_CANONICAL_SEPARATORS = (",", ":")


def json_index_path(data_dir: Path) -> Path:
    """Location of the index: datamarts/inverted_index.json (SPEC 7.1)."""
    return data_dir / DATAMARTS_FOLDER / INDEX_FILE


def _read_index(index_path: Path) -> dict[str, dict[str, int]]:
    """The whole index, with str book ids as json.load returns them; a missing file is an empty index."""
    if not index_path.is_file():
        return {}
    with index_path.open(encoding="utf-8") as file:
        index: dict[str, dict[str, int]] = json.load(file)
    return index


class MonolithicJsonAdapter:
    """Implementation of InvertedIndexStorage: read, update and rewrite the whole file for each book (SPEC 7.1)."""

    def __init__(self, data_dir: Path) -> None:
        self._index_path = json_index_path(data_dir)

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        """
        Writes or overwrites the book's tf values with str ids, then rewrites the file with a safe write.
        json.dumps plus a single write is ~3 times faster than json.dump and produces the same bytes.
        """
        index = _read_index(self._index_path)
        book_key = str(book_id)
        for term, occurrences in terms.items():
            index.setdefault(term, {})[book_key] = occurrences.tf
        with atomic_text_writer(self._index_path) as file:
            file.write(json.dumps(index, separators=_CANONICAL_SEPARATORS, sort_keys=True))
            file.write("\n")


class JsonPostingsReader:
    """
    Implementation of PostingsReader and TermStatistics: the whole file is parsed once, when the reader is
    opened (SPEC 11.5.3).
    """

    def __init__(self, data_dir: Path) -> None:
        self._index = _read_index(json_index_path(data_dir))

    def read_postings(self, terms: list[str]) -> dict[str, dict[int, int]]:
        """book_id -> tf for each requested term."""
        return {term: _with_int_ids(self._index.get(term, {})) for term in terms}

    def document_frequencies(self) -> dict[str, int]:
        """Implementation of TermStatistics: the number of books of every term (SPEC 1.2)."""
        return {term: len(postings) for term, postings in self._index.items()}


def count_json_index(data_dir: Path) -> IndexCounts:
    """Distinct terms and term-book pairs of the whole file (SPEC 11.5.3 step 4)."""
    index = _read_index(json_index_path(data_dir))
    return IndexCounts(len(index), sum(len(postings) for postings in index.values()))


def _with_int_ids(postings: dict[str, int]) -> dict[int, int]:
    return {int(book_key): tf for book_key, tf in postings.items()}
