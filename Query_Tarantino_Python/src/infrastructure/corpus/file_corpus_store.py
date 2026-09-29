"""
Implementation of CorpusStore: corpus_raw/N.txt files written with the safe
write of SPEC 4.3, and the selected ids appended to book_ids_benchmark.txt
(SPEC 1, 1.1, 3.6). Also copies the sample dataset.
"""

import shutil
from pathlib import Path

from src.infrastructure.file_writes import append_line, atomic_text_writer

BENCHMARK_IDS_FILE = "book_ids_benchmark.txt"
SAMPLE_DATASET_FOLDER = "sample_dataset"
SAMPLE_SIZE = 20

_CORPUS_FILE_SUFFIX = ".txt"


def corpus_file(corpus_dir: Path, book_id: int) -> Path:
    """Location of a book in the local corpus: corpus_raw/N.txt (SPEC 3.6)."""
    return corpus_dir / f"{book_id}{_CORPUS_FILE_SUFFIX}"


class FileCorpusStore:
    """The id list is append-only, so an interrupted selection resumes where it stopped."""

    def __init__(self, corpus_dir: Path, ids_path: Path) -> None:
        self._corpus_dir = corpus_dir
        self._ids_path = ids_path
        self._ids_path.parent.mkdir(parents=True, exist_ok=True)

    def save_text(self, book_id: int, text: str) -> None:
        """Writes the normalized text exactly, with UTF-8 and \\n line endings."""
        with atomic_text_writer(corpus_file(self._corpus_dir, book_id)) as file:
            file.write(text)

    def record_selected(self, book_id: int) -> None:
        """Appends the id to the benchmark list."""
        append_line(self._ids_path, str(book_id))

    def get_selected_books(self) -> list[int]:
        """Ids already in the benchmark list, in file order."""
        if not self._ids_path.is_file():
            return []
        with self._ids_path.open(encoding="utf-8", newline="") as file:
            return [int(content) for line in file if (content := line.rstrip("\n"))]


def copy_sample_dataset(corpus_dir: Path, sample_dir: Path, book_ids: list[int]) -> None:
    """Copies the corpus files of the first SAMPLE_SIZE selected books, byte for byte (SPEC 1.1)."""
    sample_dir.mkdir(parents=True, exist_ok=True)
    for book_id in book_ids[:SAMPLE_SIZE]:
        shutil.copyfile(corpus_file(corpus_dir, book_id), corpus_file(sample_dir, book_id))
