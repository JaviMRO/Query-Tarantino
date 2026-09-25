import json
from pathlib import Path

from src.domain.model import TermOccurrences
from src.infrastructure.datalake.safe_write import write_text_safely


class MonolithicJsonAdapter:
    """
    Implementation of InvertedIndexStorage that stores the entire index in a
    single JSON file in canonical form (SPEC 7.1).
    """

    def __init__(self, data_dir: Path) -> None:
        self._index_path = data_dir / "datamarts" / "inverted_index.json"

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        index_data = self._load_existing_data()
        book_id_str = str(book_id)

        for term, occurrences in terms.items():
            if term not in index_data:
                index_data[term] = {}
            index_data[term][book_id_str] = occurrences.tf

        canonical_json = json.dumps(index_data, separators=(",", ":"), sort_keys=True)
        write_text_safely(self._index_path, f"{canonical_json}\n")

    def _load_existing_data(self) -> dict[str, dict[str, int]]:
        if not self._index_path.exists():
            return {}

        data: dict[str, dict[str, int]] = json.loads(self._index_path.read_text(encoding="utf-8"))
        return data
