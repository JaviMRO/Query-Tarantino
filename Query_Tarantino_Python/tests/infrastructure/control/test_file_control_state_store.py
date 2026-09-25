from pathlib import Path

from src.domain.model import FailureReason
from src.infrastructure.control.file_control_state_store import FileControlStateStore

BOOK_ID = 2701


def test_empty_store_reports_nothing(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    assert store.get_downloaded_books() == set()
    assert store.get_indexed_books() == set()
    assert store.get_failure_counts() == {}


def test_record_download_is_reflected_in_downloaded_books(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_download(BOOK_ID)

    assert store.get_downloaded_books() == {BOOK_ID}


def test_record_indexing_is_reflected_in_indexed_books(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_indexing(BOOK_ID)

    assert store.get_indexed_books() == {BOOK_ID}


def test_downloaded_books_file_has_one_id_per_line_terminated_by_newline(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_download(BOOK_ID)
    store.record_download(5)

    content = (tmp_path / "control" / "downloaded_books.txt").read_bytes()
    assert content == f"{BOOK_ID}\n5\n".encode()


def test_repeated_download_lines_for_the_same_id_change_nothing(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_download(BOOK_ID)
    store.record_download(BOOK_ID)

    assert store.get_downloaded_books() == {BOOK_ID}


def test_control_files_are_append_only(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)
    store.record_download(BOOK_ID)
    first_write = (tmp_path / "control" / "downloaded_books.txt").read_text(encoding="utf-8")

    store.record_download(5)

    second_write = (tmp_path / "control" / "downloaded_books.txt").read_text(encoding="utf-8")
    assert second_write.startswith(first_write)


def test_first_failure_is_recorded_with_attempts_one(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_failure(BOOK_ID, FailureReason.HTTP_ERROR)

    content = (tmp_path / "control" / "failed_books.txt").read_bytes()
    assert content == f"{BOOK_ID};HTTP_ERROR;1\n".encode()
    assert store.get_failure_counts() == {BOOK_ID: 1}


def test_repeated_failures_accumulate_the_attempt_count(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_failure(BOOK_ID, FailureReason.HTTP_ERROR)
    store.record_failure(BOOK_ID, FailureReason.NO_MARKERS)
    store.record_failure(BOOK_ID, FailureReason.EMPTY_BODY)

    assert store.get_failure_counts() == {BOOK_ID: 3}
    lines = (tmp_path / "control" / "failed_books.txt").read_text(encoding="utf-8").splitlines()
    assert lines == [f"{BOOK_ID};HTTP_ERROR;1", f"{BOOK_ID};NO_MARKERS;2", f"{BOOK_ID};EMPTY_BODY;3"]


def test_failures_are_tracked_independently_per_book(tmp_path: Path) -> None:
    store = FileControlStateStore(tmp_path)

    store.record_failure(BOOK_ID, FailureReason.HTTP_ERROR)
    store.record_failure(5, FailureReason.HTTP_ERROR)
    store.record_failure(5, FailureReason.HTTP_ERROR)

    assert store.get_failure_counts() == {BOOK_ID: 1, 5: 2}


def test_the_line_with_the_highest_attempts_counts_even_if_it_is_not_the_last_one(tmp_path: Path) -> None:
    """Mirrors the SPEC 14.5 rule for the folder index, applied to failed_books.txt (SPEC 8)."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()
    (control_dir / "failed_books.txt").write_text(
        f"{BOOK_ID};HTTP_ERROR;2\n{BOOK_ID};HTTP_ERROR;1\n", encoding="utf-8", newline=""
    )
    store = FileControlStateStore(tmp_path)

    assert store.get_failure_counts() == {BOOK_ID: 2}
