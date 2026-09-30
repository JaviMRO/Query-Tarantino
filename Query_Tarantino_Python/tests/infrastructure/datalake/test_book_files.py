from pathlib import Path

from src.infrastructure.datalake.book_files import complete_book_ids_in


def write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_only_complete_books_with_numeric_ids_are_listed(tmp_path: Path) -> None:
    write(tmp_path / "7.header.txt")
    write(tmp_path / "7.body.txt")
    write(tmp_path / "8.header.txt")
    write(tmp_path / "notes.header.txt")
    write(tmp_path / "notes.body.txt")
    write(tmp_path / "9.header.txt.tmp")

    assert set(complete_book_ids_in(tmp_path)) == {7}


def test_a_missing_folder_lists_nothing(tmp_path: Path) -> None:
    assert list(complete_book_ids_in(tmp_path / "missing")) == []
