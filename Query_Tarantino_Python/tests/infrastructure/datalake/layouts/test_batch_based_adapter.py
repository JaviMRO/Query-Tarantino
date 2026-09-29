from pathlib import Path

import pytest

from src.domain.model import BookText, StoredPaths
from src.infrastructure.datalake.layouts.batch_based_adapter import BatchBasedAdapter

TEXT = BookText(header="Title: Moby Dick", body="Call me Ishmael.")


@pytest.mark.parametrize(
    ("book_id", "range_folder"),
    [
        (5, "000000-000999"),
        (999, "000000-000999"),
        (1000, "001000-001999"),
        (1342, "001000-001999"),
        (70001, "070000-070999"),
    ],
)
def test_get_paths_follows_the_spec_batch_ranges(book_id: int, range_folder: str) -> None:
    adapter = BatchBasedAdapter(Path("/data"))

    paths = adapter.get_paths(book_id)

    assert paths == StoredPaths(
        f"datalake_batch/{range_folder}/{book_id}.header.txt",
        f"datalake_batch/{range_folder}/{book_id}.body.txt",
    )


def test_save_writes_exact_header_and_body_with_no_trailing_newline(tmp_path: Path) -> None:
    adapter = BatchBasedAdapter(tmp_path)

    paths = adapter.save(1342, TEXT)

    assert paths == adapter.get_paths(1342)
    assert (tmp_path / paths.header).read_bytes() == TEXT.header.encode("utf-8")
    assert (tmp_path / paths.body).read_bytes() == TEXT.body.encode("utf-8")


def test_save_leaves_no_tmp_files_behind(tmp_path: Path) -> None:
    adapter = BatchBasedAdapter(tmp_path)

    adapter.save(1342, TEXT)

    assert list(tmp_path.rglob("*.tmp")) == []


def test_load_returns_exactly_what_was_saved(tmp_path: Path) -> None:
    adapter = BatchBasedAdapter(tmp_path)
    adapter.save(1342, TEXT)

    assert adapter.load(1342) == TEXT


def test_books_in_different_ranges_do_not_collide(tmp_path: Path) -> None:
    adapter = BatchBasedAdapter(tmp_path)
    other_text = BookText(header="Title: Other", body="Other body.")

    adapter.save(5, TEXT)
    adapter.save(1000, other_text)

    assert adapter.load(5) == TEXT
    assert adapter.load(1000) == other_text


def test_an_orphan_tmp_file_is_not_a_book(tmp_path: Path) -> None:
    folder = tmp_path / "datalake_batch" / "000000-000999"
    folder.mkdir(parents=True)
    (folder / "7.header.txt.tmp").write_text("partial", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        BatchBasedAdapter(tmp_path).load(7)


def test_save_writes_utf8_with_lf_line_endings(tmp_path: Path) -> None:
    adapter = BatchBasedAdapter(tmp_path)
    text = BookText(header="Title: Café", body="naïve\nline two")

    paths = adapter.save(1342, text)

    assert (tmp_path / paths.body).read_bytes() == "naïve\nline two".encode()
