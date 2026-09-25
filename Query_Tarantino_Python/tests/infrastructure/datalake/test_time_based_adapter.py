from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.model import BookText
from src.infrastructure.datalake.time_based_adapter import TimeBasedAdapter

BOOK_ID = 2701
TEXT = BookText(header="Title: Moby Dick", body="Call me Ishmael.")


def test_save_uses_the_current_utc_date_and_hour_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixed_now = datetime(2026, 9, 24, 13, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "src.infrastructure.datalake.time_based_adapter.datetime",
        type("_FixedDatetime", (), {"now": staticmethod(lambda tz=None: fixed_now)}),
    )
    adapter = TimeBasedAdapter(tmp_path)

    paths = adapter.save(BOOK_ID, TEXT)

    assert paths.header == f"datalake/20260924/13/{BOOK_ID}.header.txt"
    assert paths.body == f"datalake/20260924/13/{BOOK_ID}.body.txt"


def test_save_writes_exact_header_and_body_with_no_trailing_newline(tmp_path: Path) -> None:
    adapter = TimeBasedAdapter(tmp_path)

    paths = adapter.save(BOOK_ID, TEXT)

    assert (tmp_path / paths.header).read_bytes() == TEXT.header.encode("utf-8")
    assert (tmp_path / paths.body).read_bytes() == TEXT.body.encode("utf-8")


def test_save_leaves_no_tmp_files_behind(tmp_path: Path) -> None:
    adapter = TimeBasedAdapter(tmp_path)

    adapter.save(BOOK_ID, TEXT)

    assert list(tmp_path.rglob("*.tmp")) == []


def test_get_paths_finds_a_saved_book_by_scanning(tmp_path: Path) -> None:
    adapter = TimeBasedAdapter(tmp_path)
    saved_paths = adapter.save(BOOK_ID, TEXT)

    assert adapter.get_paths(BOOK_ID) == saved_paths


def test_get_paths_raises_when_the_book_was_never_saved(tmp_path: Path) -> None:
    adapter = TimeBasedAdapter(tmp_path)

    with pytest.raises(FileNotFoundError):
        adapter.get_paths(BOOK_ID)


def test_load_finds_and_returns_a_book_saved_in_an_earlier_run(tmp_path: Path) -> None:
    """A separate TimeBasedAdapter instance simulates indexing happening in a later process (SPEC 8.1)."""
    TimeBasedAdapter(tmp_path).save(BOOK_ID, TEXT)

    assert TimeBasedAdapter(tmp_path).load(BOOK_ID) == TEXT


def test_get_paths_does_not_confuse_ids_with_a_shared_suffix(tmp_path: Path) -> None:
    adapter = TimeBasedAdapter(tmp_path)
    other_text = BookText(header="Title: Other", body="Other body.")
    adapter.save(1, TEXT)
    adapter.save(21, other_text)

    assert adapter.load(1) == TEXT
    assert adapter.load(21) == other_text
