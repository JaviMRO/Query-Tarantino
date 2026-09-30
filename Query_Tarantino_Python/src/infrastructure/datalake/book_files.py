"""Reads and writes the header and body files of one book, shared by every datalake layout (SPEC 4.2, 4.3)."""

from collections.abc import Iterator
from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.file_writes import atomic_text_writer

HEADER_FILE_SUFFIX = ".header.txt"
BODY_FILE_SUFFIX = ".body.txt"


def write_book_files(data_dir: Path, paths: StoredPaths, text: BookText) -> None:
    """Writes the exact header, then the exact body, each with a safe write and no trailing newline (SPEC 4.3)."""
    with atomic_text_writer(data_dir / paths.header) as file:
        file.write(text.header)
    with atomic_text_writer(data_dir / paths.body) as file:
        file.write(text.body)


def read_book_files(data_dir: Path, paths: StoredPaths) -> BookText:
    """Reads the header and body files of a stored book."""
    return BookText(_read_exact_text(data_dir / paths.header), _read_exact_text(data_dir / paths.body))


def has_book_files(data_dir: Path, paths: StoredPaths) -> bool:
    """A book exists only if both final files exist; a .tmp file never counts (SPEC 4.3)."""
    return (data_dir / paths.header).is_file() and (data_dir / paths.body).is_file()


def paths_in_folder(folder: str, book_id: int) -> StoredPaths:
    """N.header.txt and N.body.txt inside a folder, as the time and batch layouts name them (SPEC 4.1)."""
    return StoredPaths(f"{folder}/{book_id}{HEADER_FILE_SUFFIX}", f"{folder}/{book_id}{BODY_FILE_SUFFIX}")


def complete_book_ids_in(folder: Path) -> Iterator[int]:
    """
    Ids of the books with both N.header.txt and N.body.txt in the folder (time and batch layouts). A .tmp file
    never ends with a final suffix, so it is never listed (SPEC 4.3).
    """
    if not folder.is_dir():
        return
    for entry in folder.iterdir():
        book_id_text = entry.name.removesuffix(HEADER_FILE_SUFFIX)
        if book_id_text != entry.name and (folder / f"{book_id_text}{BODY_FILE_SUFFIX}").is_file():
            yield int(book_id_text)


def _read_exact_text(path: Path) -> str:
    """Reads the file without line-ending translation, so the text is returned byte for byte."""
    with path.open(encoding="utf-8", newline="") as file:
        return file.read()
