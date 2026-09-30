from pathlib import Path

from src.infrastructure.entrypoints.bench.measurement.storage import file_storage, has_tmp_files, tree_storage
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit


def test_tree_storage_counts_files_bytes_and_directories_below_the_root(tmp_path: Path) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "one.txt").write_bytes(b"123")
    (tmp_path / "a" / "b" / "two.txt").write_bytes(b"4567")

    assert tree_storage(tmp_path) == [
        Measurement("disk_bytes", 7, Unit.BYTES),
        Measurement("file_count", 2, Unit.FILES),
        Measurement("dir_count", 2, Unit.DIRS),
    ]


def test_file_storage_is_the_size_of_the_file(tmp_path: Path) -> None:
    index = tmp_path / "inverted_index.json"
    index.write_bytes(b"{}\n")

    assert file_storage(index) == [Measurement("disk_bytes", 3, Unit.BYTES)]


def test_a_tmp_leftover_anywhere_below_the_root_is_detected(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "7.body.txt").write_text("", encoding="utf-8")
    assert not has_tmp_files(tmp_path)

    (tmp_path / "x" / "7.header.txt.tmp").write_text("", encoding="utf-8")

    assert has_tmp_files(tmp_path)
