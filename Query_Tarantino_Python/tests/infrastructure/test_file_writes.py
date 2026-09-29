from pathlib import Path

import pytest

from src.infrastructure.file_writes import append_line, atomic_text_writer


def test_atomic_text_writer_creates_parents_and_writes_exact_bytes(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "file.txt"

    with atomic_text_writer(target) as file:
        file.write("línea\nsecond")

    assert target.read_bytes() == "línea\nsecond".encode()
    assert list(tmp_path.rglob("*.tmp")) == []


def test_atomic_text_writer_replaces_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("old", encoding="utf-8")

    with atomic_text_writer(target) as file:
        file.write("new")

    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_text_writer_keeps_the_old_file_if_writing_fails(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("old", encoding="utf-8")

    with pytest.raises(RuntimeError), atomic_text_writer(target) as file:
        file.write("partial")
        raise RuntimeError("interrupted")

    assert target.read_text(encoding="utf-8") == "old"


def test_append_line_adds_a_terminated_line_without_rewriting(tmp_path: Path) -> None:
    path = tmp_path / "log.txt"

    append_line(path, "1")
    append_line(path, "2")

    assert path.read_bytes() == b"1\n2\n"
