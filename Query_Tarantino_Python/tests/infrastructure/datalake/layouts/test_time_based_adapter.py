from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.domain.model import BookText, StoredPaths
from src.infrastructure.datalake.layouts.time_based_adapter import TimeBasedAdapter

BOOK_ID = 2701
TEXT = BookText(header="Title: Moby Dick", body="Call me Ishmael.")
FIXED_NOW = datetime(2026, 9, 24, 13, 30, tzinfo=timezone.utc)


class CountingClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.moment


def build(data_dir: Path, moment: datetime = FIXED_NOW) -> TimeBasedAdapter:
    return TimeBasedAdapter(data_dir, CountingClock(moment))


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


def test_save_uses_the_utc_date_and_hour_folder_of_the_injected_clock(tmp_path: Path) -> None:
    adapter = build(tmp_path)

    paths = adapter.save(BOOK_ID, TEXT)

    assert paths == StoredPaths("datalake/20260924/13/2701.header.txt", "datalake/20260924/13/2701.body.txt")


def test_save_converts_the_clock_moment_to_utc(tmp_path: Path) -> None:
    madrid_summer = timezone(timedelta(hours=2))
    adapter = build(tmp_path, datetime(2026, 9, 25, 1, 30, tzinfo=madrid_summer))

    paths = adapter.save(BOOK_ID, TEXT)

    assert paths.header == "datalake/20260924/23/2701.header.txt"


def test_save_calls_the_clock_exactly_once(tmp_path: Path) -> None:
    clock = CountingClock(FIXED_NOW)
    adapter = TimeBasedAdapter(tmp_path, clock)

    adapter.save(BOOK_ID, TEXT)

    assert clock.calls == 1


def test_save_writes_exact_header_and_body_with_no_trailing_newline(tmp_path: Path) -> None:
    adapter = build(tmp_path)

    paths = adapter.save(BOOK_ID, TEXT)

    assert (tmp_path / paths.header).read_bytes() == TEXT.header.encode("utf-8")
    assert (tmp_path / paths.body).read_bytes() == TEXT.body.encode("utf-8")


def test_save_writes_utf8_with_lf_line_endings(tmp_path: Path) -> None:
    adapter = build(tmp_path)
    text = BookText(header="Title: Café\nAuthor: Zoë", body="naïve\nline two")

    paths = adapter.save(BOOK_ID, text)

    assert (tmp_path / paths.body).read_bytes() == "naïve\nline two".encode()
    assert adapter.load(BOOK_ID) == text


def test_save_leaves_no_tmp_files_behind(tmp_path: Path) -> None:
    adapter = build(tmp_path)

    adapter.save(BOOK_ID, TEXT)

    assert list(tmp_path.rglob("*.tmp")) == []


def test_get_paths_matches_what_save_returned(tmp_path: Path) -> None:
    adapter = build(tmp_path)
    saved_paths = adapter.save(BOOK_ID, TEXT)

    assert adapter.get_paths(BOOK_ID) == saved_paths


def test_get_paths_raises_when_the_book_was_never_saved(tmp_path: Path) -> None:
    adapter = build(tmp_path)

    with pytest.raises(FileNotFoundError):
        adapter.get_paths(BOOK_ID)


def test_load_finds_a_book_saved_by_another_instance_at_another_hour(tmp_path: Path) -> None:
    build(tmp_path, datetime(2026, 1, 1, 0, tzinfo=timezone.utc)).save(BOOK_ID, TEXT)

    assert build(tmp_path, datetime(2026, 3, 1, 5, tzinfo=timezone.utc)).load(BOOK_ID) == TEXT


def test_get_paths_does_not_confuse_ids_with_a_shared_suffix(tmp_path: Path) -> None:
    adapter = build(tmp_path)
    other_text = BookText(header="Title: Other", body="Other body.")
    adapter.save(1, TEXT)
    adapter.save(21, other_text)

    assert adapter.load(1) == TEXT
    assert adapter.load(21) == other_text


def test_an_orphan_tmp_file_is_not_a_book(tmp_path: Path) -> None:
    write_file(tmp_path / "datalake/20260101/00/7.header.txt.tmp", "partial")
    write_file(tmp_path / "datalake/20260101/00/7.body.txt.tmp", "partial")

    with pytest.raises(FileNotFoundError):
        build(tmp_path).get_paths(7)


def test_the_most_recent_complete_copy_wins_over_old_and_incomplete_ones(tmp_path: Path) -> None:
    write_file(tmp_path / "datalake/20260101/00/7.header.txt", "old header")
    write_file(tmp_path / "datalake/20260101/00/7.body.txt", "old body")
    write_file(tmp_path / "datalake/20260101/03/7.header.txt", "new header")
    write_file(tmp_path / "datalake/20260101/03/7.body.txt", "new body")
    write_file(tmp_path / "datalake/20260101/05/7.header.txt", "incomplete")
    adapter = build(tmp_path)

    assert adapter.load(7) == BookText("new header", "new body")
    assert adapter.get_paths(7) == StoredPaths("datalake/20260101/03/7.header.txt", "datalake/20260101/03/7.body.txt")


def test_a_later_day_wins_over_a_later_hour_of_an_earlier_day(tmp_path: Path) -> None:
    write_file(tmp_path / "datalake/20260101/23/7.header.txt", "old header")
    write_file(tmp_path / "datalake/20260101/23/7.body.txt", "old body")
    write_file(tmp_path / "datalake/20260102/00/7.header.txt", "new header")
    write_file(tmp_path / "datalake/20260102/00/7.body.txt", "new body")

    assert build(tmp_path).load(7) == BookText("new header", "new body")
