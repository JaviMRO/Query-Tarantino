"""
Inverted index stored as one text file per term, grouped in folders by the
term's first letter in uppercase (SPEC 7.3): HierarchicalFolderAdapter appends
to it and FolderPostingsReader reads it for searches.
"""

from pathlib import Path

from src.domain.model import TermOccurrences
from src.infrastructure.data_layout import DATAMARTS_FOLDER
from src.infrastructure.file_writes import append_line
from src.infrastructure.index.index_counts import IndexCounts

INDEX_FOLDER = "inverted_index"

_TERM_FILE_SUFFIX = ".txt"
_FIELD_SEPARATOR = " "


def folder_index_dir(data_dir: Path) -> Path:
    """Root of the index: datamarts/inverted_index/ (SPEC 7.3)."""
    return data_dir / DATAMARTS_FOLDER / INDEX_FOLDER


def count_folder_index(data_dir: Path) -> IndexCounts:
    """One term per file; the distinct books of each file are its postings, the last line counting (SPEC 7.3)."""
    term_files = list(folder_index_dir(data_dir).glob(f"*/*{_TERM_FILE_SUFFIX}"))
    return IndexCounts(len(term_files), sum(len(_read_term_file(path)) for path in term_files))


def _term_file(index_dir: Path, term: str) -> Path:
    return index_dir / term[0].upper() / f"{term}{_TERM_FILE_SUFFIX}"


class HierarchicalFolderAdapter:
    """Implementation of InvertedIndexStorage: appends one "book_id tf" line per term (SPEC 7.3)."""

    def __init__(self, data_dir: Path) -> None:
        self._index_dir = folder_index_dir(data_dir)

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        """Letter folders are created once per call, before the terms are appended."""
        for letter in {term[0].upper() for term in terms}:
            (self._index_dir / letter).mkdir(parents=True, exist_ok=True)
        for term, occurrences in terms.items():
            append_line(_term_file(self._index_dir, term), f"{book_id}{_FIELD_SEPARATOR}{occurrences.tf}")


class FolderPostingsReader:
    """Implementation of PostingsReader: one file per requested term; the last line of a book counts (SPEC 7.3)."""

    def __init__(self, data_dir: Path) -> None:
        self._index_dir = folder_index_dir(data_dir)

    def read_postings(self, terms: list[str]) -> dict[str, dict[int, int]]:
        """book_id -> tf for each requested term; a term without a file has no postings."""
        return {term: _read_term_file(_term_file(self._index_dir, term)) for term in terms}


def _read_term_file(path: Path) -> dict[int, int]:
    postings: dict[int, int] = {}
    if not path.is_file():
        return postings
    with path.open(encoding="utf-8", newline="") as file:
        for line in file:
            book_id_text, tf_text = line.rstrip("\n").split(_FIELD_SEPARATOR)
            postings[int(book_id_text)] = int(tf_text)
    return postings
