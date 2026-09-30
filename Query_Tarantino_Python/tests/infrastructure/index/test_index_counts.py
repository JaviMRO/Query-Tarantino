from pathlib import Path

from src.domain.model import TermOccurrences
from src.infrastructure.index.hierarchical_folder_adapter import HierarchicalFolderAdapter, count_folder_index
from src.infrastructure.index.index_counts import IndexCounts
from src.infrastructure.index.monolithic_json_adapter import MonolithicJsonAdapter, count_json_index

TERMS = {"whale": TermOccurrences(2, (0, 3)), "ship": TermOccurrences(1, (1,))}


def test_json_counts_distinct_terms_and_term_book_pairs(tmp_path: Path) -> None:
    index = MonolithicJsonAdapter(tmp_path)
    index.write_book_terms(1, TERMS)
    index.write_book_terms(2, {"whale": TermOccurrences(1, (0,))})

    assert count_json_index(tmp_path) == IndexCounts(2, 3)


def test_folders_count_a_book_indexed_twice_once(tmp_path: Path) -> None:
    index = HierarchicalFolderAdapter(tmp_path)
    index.write_book_terms(1, TERMS)
    index.write_book_terms(1, TERMS)
    index.write_book_terms(2, {"whale": TermOccurrences(1, (0,))})

    assert count_folder_index(tmp_path) == IndexCounts(2, 3)
