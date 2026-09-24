import random
from collections.abc import Iterable
from dataclasses import dataclass

from src.domain.model import MAX_FAILED_ATTEMPTS
from src.domain.ports import ControlStateStore

RANDOM_CANDIDATES_PER_STEP = 10
MAX_GUTENBERG_ID = 75_000


@dataclass(frozen=True, slots=True)
class IndexNext:
    book_id: int


@dataclass(frozen=True, slots=True)
class DownloadNext:
    book_id: int


@dataclass(frozen=True, slots=True)
class NothingToDo:
    """No book is pending to index and no candidate is valid."""


NextStep = IndexNext | DownloadNext | NothingToDo


def random_candidates(rng: random.Random) -> list[int]:
    """
    Candidates for a step without --ids (SPEC 8.1 step 3): exactly
    RANDOM_CANDIDATES_PER_STEP random IDs in [1, MAX_GUTENBERG_ID].
    Inject a seeded Random in tests.
    """
    return [rng.randint(1, MAX_GUTENBERG_ID) for _ in range(RANDOM_CANDIDATES_PER_STEP)]


class ControlPipeline:
    """
    Decides what one control step does (SPEC 8.1 steps 1-3): books waiting
    to be indexed go first, lowest ID; otherwise the first valid candidate
    (not downloaded, fewer than MAX_FAILED_ATTEMPTS failures) is downloaded;
    if none is valid, the step does nothing.
    """

    def __init__(self, control_store: ControlStateStore):
        self.control_store = control_store

    def next_book_to_process(self, candidates: Iterable[int]) -> NextStep:
        """
        candidates: the whole --ids file in its order (no limit), or
        random_candidates() when there is no --ids file.
        """
        downloaded = self.control_store.get_downloaded_books()

        pending_to_index = downloaded - self.control_store.get_indexed_books()
        if pending_to_index:
            return IndexNext(min(pending_to_index))

        book_to_download = self._first_downloadable(candidates, downloaded)
        return NothingToDo() if book_to_download is None else DownloadNext(book_to_download)

    def _first_downloadable(self, candidates: Iterable[int], downloaded: set[int]) -> int | None:
        failures = self.control_store.get_failure_counts()
        return next(
            (
                book_id
                for book_id in candidates
                if book_id not in downloaded and failures.get(book_id, 0) < MAX_FAILED_ATTEMPTS
            ),
            None,
        )
