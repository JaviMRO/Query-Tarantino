from pathlib import Path

from src.domain.model import TermOccurrences


class HierarchicalFolderAdapter:
    """
    Implementation of InvertedIndexStorage that stores each term in its own
    text file, grouped in folders by the first letter (SPEC 7.3).
    """

    def __init__(self, data_dir: Path) -> None:
        self._index_dir = data_dir / "datamarts" / "inverted_index"

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        for term, occurrences in terms.items():
            term_folder = self._index_dir / term[0].upper()
            term_folder.mkdir(parents=True, exist_ok=True)

            file_path = term_folder / f"{term}.txt"
            self._append_term_data(file_path, book_id, occurrences.tf)

    def _append_term_data(self, file_path: Path, book_id: int, tf: int) -> None:
        with file_path.open("a", encoding="utf-8", newline="") as file:
            file.write(f"{book_id} {tf}\n")