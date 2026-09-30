"""
Implementation of DatalakeStorage that organizes the books downloaded from
Project Gutenberg by download date and hour, in UTC (SPEC 4.1 "time").

A book's folder depends on when it was downloaded, so get_paths() and load()
walk the YYYYMMDD/HH folders from the most recent to the oldest and keep the
first one holding both final files: older copies are ignored (SPEC 4.1, 14.8).
"""

from collections import Counter
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.data_layout import TIME_LAKE_FOLDER
from src.infrastructure.datalake.book_files import (
    complete_book_ids_in,
    has_book_files,
    paths_in_folder,
    read_book_files,
    write_book_files,
)


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
        for hour_folder in _hour_folders_newest_first(self._lake_dir):
            paths = _paths_in(hour_folder, book_id)
            if has_book_files(self._data_dir, paths):
                return paths
        raise FileNotFoundError(f"Book {book_id} not found in {self._lake_dir}")


def hour_folder_of(paths: StoredPaths) -> str:
    """The YYYYMMDD/HH folder of a book stored in the time lake, taken from its paths."""
    return paths.header.removeprefix(f"{TIME_LAKE_FOLDER}/").rsplit("/", 1)[0]


def stored_time_book_ids(data_dir: Path, checkpoint: str) -> set[int]:
    """
    Ids of the complete books in the hour folders whose YYYYMMDD/HH is greater than or equal, as text, to the
    checkpoint; an empty checkpoint lists the whole lake (SPEC 11.5.1 detect_new_scan).
    """
    lake_dir = data_dir / TIME_LAKE_FOLDER
    recent_folders = [folder for folder in _hour_folders_newest_first(lake_dir) if folder >= checkpoint]
    return set(_complete_copies(lake_dir, recent_folders))


def count_stale_copies(data_dir: Path) -> int:
    """Number of books with a complete copy in more than one hour folder (SPEC 4.1, 11.5.2)."""
    lake_dir = data_dir / TIME_LAKE_FOLDER
    copies = Counter(_complete_copies(lake_dir, list(_hour_folders_newest_first(lake_dir))))
    return sum(1 for count in copies.values() if count > 1)


def _complete_copies(lake_dir: Path, hour_folders: list[str]) -> Iterator[int]:
    """The id of every complete copy in the given hour folders; a book stored twice is yielded twice."""
    for folder in hour_folders:
        yield from complete_book_ids_in(lake_dir / folder)


def _paths_in(hour_folder: str, book_id: int) -> StoredPaths:
    return paths_in_folder(f"{TIME_LAKE_FOLDER}/{hour_folder}", book_id)


def _hour_folders_newest_first(lake_dir: Path) -> Iterator[str]:
    for day in _folder_names_descending(lake_dir):
        for hour in _folder_names_descending(lake_dir / day):
            yield f"{day}/{hour}"


def _folder_names_descending(parent: Path) -> list[str]:
    """Only folder names are listed, never their files; the text order of YYYYMMDD and HH is chronological."""
    if not parent.is_dir():
        return []
    return sorted((entry.name for entry in parent.iterdir() if entry.is_dir()), reverse=True)
