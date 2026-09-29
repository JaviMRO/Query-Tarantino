from pathlib import Path

from src.domain.model import TermOccurrences
from src.infrastructure.index.hierarchical_folder_adapter import FolderPostingsReader, HierarchicalFolderAdapter

CAR = {"car": TermOccurrences(1, (1,))}
CAR_FILE = Path("datamarts/inverted_index/C/car.txt")


def test_a_book_indexed_again_appends_a_line_as_in_spec_14_5(tmp_path: Path) -> None:
    adapter = HierarchicalFolderAdapter(tmp_path)

    adapter.write_book_terms(1, CAR)
    adapter.write_book_terms(2, CAR)
    adapter.write_book_terms(1, CAR)

    assert (tmp_path / CAR_FILE).read_bytes() == b"1 1\n2 1\n1 1\n"


def test_reading_the_spec_14_5_file_keeps_the_last_line_of_each_book(tmp_path: Path) -> None:
    adapter = HierarchicalFolderAdapter(tmp_path)
    adapter.write_book_terms(1, CAR)
    adapter.write_book_terms(2, CAR)
    adapter.write_book_terms(1, {"car": TermOccurrences(3, (1, 2, 3))})

    assert FolderPostingsReader(tmp_path).read_postings(["car"]) == {"car": {1: 3, 2: 1}}


def test_each_term_goes_to_the_uppercase_folder_of_its_first_letter(tmp_path: Path) -> None:
    HierarchicalFolderAdapter(tmp_path).write_book_terms(
        7, {"whale": TermOccurrences(2, (0, 5)), "ahab": TermOccurrences(1, (3,))}
    )

    assert (tmp_path / "datamarts/inverted_index/W/whale.txt").read_bytes() == b"7 2\n"
    assert (tmp_path / "datamarts/inverted_index/A/ahab.txt").read_bytes() == b"7 1\n"


def test_writing_appends_without_rewriting_previous_lines(tmp_path: Path) -> None:
    adapter = HierarchicalFolderAdapter(tmp_path)
    adapter.write_book_terms(1, CAR)
    first_write = (tmp_path / CAR_FILE).read_bytes()

    adapter.write_book_terms(2, CAR)

    assert (tmp_path / CAR_FILE).read_bytes().startswith(first_write)


def test_a_term_without_a_file_has_no_postings(tmp_path: Path) -> None:
    assert FolderPostingsReader(tmp_path).read_postings(["whale"]) == {"whale": {}}
