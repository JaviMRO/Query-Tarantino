from pathlib import Path

from src.infrastructure.startup.tmp_cleanup import delete_tmp_leftovers


def create(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    return path


def test_deletes_tmp_files_under_every_lake_and_the_datamarts(tmp_path: Path) -> None:
    leftovers = [
        create(tmp_path / "datalake/20260101/00/7.header.txt.tmp"),
        create(tmp_path / "datalake_book/7/body.txt.tmp"),
        create(tmp_path / "datalake_batch/000000-000999/7.body.txt.tmp"),
        create(tmp_path / "datamarts/inverted_index.json.tmp"),
    ]

    delete_tmp_leftovers(tmp_path)

    assert not any(leftover.exists() for leftover in leftovers)


def test_keeps_final_files_and_tmp_files_outside_the_cleaned_folders(tmp_path: Path) -> None:
    final_file = create(tmp_path / "datalake_book/7/body.txt")
    outside = create(tmp_path / "control/notes.tmp")

    delete_tmp_leftovers(tmp_path)

    assert final_file.exists()
    assert outside.exists()


def test_an_empty_data_folder_is_not_an_error(tmp_path: Path) -> None:
    delete_tmp_leftovers(tmp_path)

    assert list(tmp_path.iterdir()) == []
