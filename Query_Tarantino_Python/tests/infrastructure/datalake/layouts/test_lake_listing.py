from datetime import datetime, timezone
from pathlib import Path

from src.domain.model import BookText
from src.infrastructure.datalake.book_files import complete_book_ids_in
from src.infrastructure.datalake.layouts.batch_based_adapter import BatchBasedAdapter, stored_batch_book_ids
from src.infrastructure.datalake.layouts.book_based_adapter import BookBasedAdapter, stored_book_book_ids
from src.infrastructure.datalake.layouts.time_based_adapter import (
    TimeBasedAdapter,
    count_stale_copies,
    hour_folder_of,
    stored_time_book_ids,
)

TEXT = BookText("header", "body")
EARLY = datetime(2026, 1, 1, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 1, 1, 5, tzinfo=timezone.utc)


def test_only_books_with_both_final_files_are_listed(tmp_path: Path) -> None:
    (tmp_path / "1.header.txt").write_text("h", encoding="utf-8")
    (tmp_path / "1.body.txt").write_text("b", encoding="utf-8")
    (tmp_path / "2.header.txt").write_text("h", encoding="utf-8")
    (tmp_path / "3.header.txt.tmp").write_text("h", encoding="utf-8")
    (tmp_path / "3.body.txt").write_text("b", encoding="utf-8")

    assert set(complete_book_ids_in(tmp_path)) == {1}


def test_book_and_batch_lakes_list_their_complete_books(tmp_path: Path) -> None:
    for book_id in (5, 1342):
        BookBasedAdapter(tmp_path).save(book_id, TEXT)
        BatchBasedAdapter(tmp_path).save(book_id, TEXT)
    (tmp_path / "datalake_book" / "5" / "body.txt").unlink()

    assert stored_book_book_ids(tmp_path) == {1342}
    assert stored_batch_book_ids(tmp_path) == {5, 1342}


def test_an_empty_lake_lists_nothing(tmp_path: Path) -> None:
    assert stored_book_book_ids(tmp_path) == set()
    assert stored_batch_book_ids(tmp_path) == set()
    assert stored_time_book_ids(tmp_path, "") == set()
    assert count_stale_copies(tmp_path) == 0


def test_the_time_lake_lists_from_the_checkpoint_and_counts_stale_copies(tmp_path: Path) -> None:
    TimeBasedAdapter(tmp_path, lambda: EARLY).save(7, TEXT)
    TimeBasedAdapter(tmp_path, lambda: EARLY).save(8, TEXT)
    late_paths = TimeBasedAdapter(tmp_path, lambda: LATE).save(7, TEXT)

    assert hour_folder_of(late_paths) == "20260101/05"
    assert stored_time_book_ids(tmp_path, "20260101/05") == {7}
    assert stored_time_book_ids(tmp_path, "") == {7, 8}
    assert count_stale_copies(tmp_path) == 1
