from pathlib import Path

from src.domain.model import BookText, StoredPaths
from src.infrastructure.datalake.book_based_adapter import BookBasedAdapter

BOOK_ID = 2701
TEXT = BookText(header="Title: Moby Dick", body="Call me Ishmael.")


def test_get_paths_follows_the_book_layout() -> None:
    adapter = BookBasedAdapter(Path("/data"))

    paths = adapter.get_paths(BOOK_ID)

    assert paths == StoredPaths("datalake_book/2701/header.txt", "datalake_book/2701/body.txt")


def test_save_returns_the_same_paths_as_get_paths(tmp_path: Path) -> None:
    adapter = BookBasedAdapter(tmp_path)

    assert adapter.save(BOOK_ID, TEXT) == adapter.get_paths(BOOK_ID)


def test_save_writes_exact_header_and_body_with_no_trailing_newline(tmp_path: Path) -> None:
    adapter = BookBasedAdapter(tmp_path)

    paths = adapter.save(BOOK_ID, TEXT)

    assert (tmp_path / paths.header).read_bytes() == TEXT.header.encode("utf-8")
    assert (tmp_path / paths.body).read_bytes() == TEXT.body.encode("utf-8")


def test_save_leaves_no_tmp_files_behind(tmp_path: Path) -> None:
    adapter = BookBasedAdapter(tmp_path)

    adapter.save(BOOK_ID, TEXT)

    assert list(tmp_path.rglob("*.tmp")) == []


def test_save_creates_missing_parent_folders(tmp_path: Path) -> None:
    adapter = BookBasedAdapter(tmp_path / "nested" / "data")

    adapter.save(BOOK_ID, TEXT)

    assert (tmp_path / "nested" / "data" / "datalake_book" / "2701" / "header.txt").exists()


def test_load_returns_exactly_what_was_saved(tmp_path: Path) -> None:
    adapter = BookBasedAdapter(tmp_path)
    adapter.save(BOOK_ID, TEXT)

    assert adapter.load(BOOK_ID) == TEXT


def test_different_books_do_not_collide(tmp_path: Path) -> None:
    adapter = BookBasedAdapter(tmp_path)
    other_text = BookText(header="Title: Other", body="Other body.")

    adapter.save(BOOK_ID, TEXT)
    adapter.save(2702, other_text)

    assert adapter.load(BOOK_ID) == TEXT
    assert adapter.load(2702) == other_text
