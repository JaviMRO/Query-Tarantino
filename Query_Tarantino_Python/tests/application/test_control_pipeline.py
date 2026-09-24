import random
from collections.abc import Iterable

from src.application.control_pipeline import (
    MAX_GUTENBERG_ID,
    RANDOM_CANDIDATES_PER_STEP,
    ControlPipeline,
    DownloadNext,
    IndexNext,
    NextStep,
    NothingToDo,
    random_candidates,
)
from src.domain.model import MAX_FAILED_ATTEMPTS
from tests.application.fakes import FakeControlStateStore


def next_step(
    candidates: Iterable[int],
    downloaded: set[int] | None = None,
    indexed: set[int] | None = None,
    failures: dict[int, int] | None = None,
) -> NextStep:
    store = FakeControlStateStore(downloaded=downloaded, indexed=indexed, failures=failures)
    return ControlPipeline(store).next_book_to_process(candidates)


def test_pending_indexing_goes_first_lowest_id() -> None:
    assert next_step([1], downloaded={5, 3, 9}, indexed={9}) == IndexNext(3)


def test_downloads_first_candidate_not_downloaded() -> None:
    assert next_step([3, 7, 8], downloaded={3}, indexed={3}) == DownloadNext(7)


def test_skips_candidates_with_max_failures() -> None:
    failures = {7: MAX_FAILED_ATTEMPTS, 8: MAX_FAILED_ATTEMPTS - 1}

    assert next_step([7, 8], failures=failures) == DownloadNext(8)


def test_nothing_to_do_when_no_candidate_is_valid() -> None:
    assert next_step([3], downloaded={3}, indexed={3}) == NothingToDo()


def test_ids_list_is_traversed_beyond_ten_candidates() -> None:
    already_downloaded = set(range(1, 21))

    step = next_step(range(1, 22), downloaded=already_downloaded, indexed=already_downloaded)

    assert step == DownloadNext(21)


def test_random_candidates_are_bounded_and_reproducible() -> None:
    candidates = random_candidates(random.Random(42))

    assert len(candidates) == RANDOM_CANDIDATES_PER_STEP
    assert all(1 <= book_id <= MAX_GUTENBERG_ID for book_id in candidates)
    assert candidates == random_candidates(random.Random(42))
