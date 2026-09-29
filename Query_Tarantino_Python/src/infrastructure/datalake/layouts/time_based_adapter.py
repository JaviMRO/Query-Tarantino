"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg by download date and hour, in UTC (SPEC 4.1 "time").

A book's folder depends on when it was downloaded, so get_paths() and load()
walk the YYYYMMDD/HH folders from the most recent to the oldest and keep the
first one holding both final files: older copies are ignored (SPEC 4.1, 14.8).
"""

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.data_layout import TIME_LAKE_FOLDER
from src.infrastructure.datalake.book_files import has_book_files, read_book_files, write_book_files


class TimeBasedAdapter:
    """Stores each book in datalake/YYYYMMDD/HH/, the UTC hour given by the injected clock (SPEC 4.1)."""

    def __init__(self, data_dir: Path, clock: Callable[[], datetime]) -> None:
        self._data_dir = data_dir
        self._lake_dir = data_dir / TIME_LAKE_FOLDER
        self._clock = clock

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        """Calls the clock exactly once; header is written before body, via the safe write of SPEC 4.3."""
        moment = self._clock().astimezone(timezone.utc)
        paths = _paths_in(f"{moment:%Y%m%d}/{moment:%H}", book_id)
        write_book_files(self._data_dir, paths, text)
        return paths

    def load(self, book_id: int) -> BookText:
        """Reads the most recent complete copy of a book; raises FileNotFoundError if there is none."""
        return read_book_files(self._data_dir, self.get_paths(book_id))

    def get_paths(self, book_id: int) -> StoredPaths:
        """Paths of the most recent complete copy; raises FileNotFoundError if there is none (SPEC 14.8)."""
        for hour_folder in self._hour_folders_newest_first():
            paths = _paths_in(hour_folder, book_id)
            if has_book_files(self._data_dir, paths):
                return paths
        raise FileNotFoundError(f"Book {book_id} not found in {self._lake_dir}")

    def _hour_folders_newest_first(self) -> Iterator[str]:
        for day in _folder_names_descending(self._lake_dir):
            for hour in _folder_names_descending(self._lake_dir / day):
                yield f"{day}/{hour}"


def _paths_in(hour_folder: str, book_id: int) -> StoredPaths:
    folder = f"{TIME_LAKE_FOLDER}/{hour_folder}"
    return StoredPaths(f"{folder}/{book_id}.header.txt", f"{folder}/{book_id}.body.txt")


def _folder_names_descending(parent: Path) -> list[str]:
    """Only folder names are listed, never their files; the text order of YYYYMMDD and HH is chronological."""
    if not parent.is_dir():
        return []
    return sorted((entry.name for entry in parent.iterdir() if entry.is_dir()), reverse=True)
