from pathlib import Path

import pytest

from src.infrastructure.stopwords.file_stopwords_loader import load_stopwords
from tests.conftest import SHARED_DIR


def test_loads_official_english_list() -> None:
    stopwords = load_stopwords(SHARED_DIR)

    assert len(stopwords) == 153
    assert {"the", "it", "was", "ve", "don"} <= stopwords


def test_official_list_follows_spec_format() -> None:
    lines = (SHARED_DIR / "stopwords_en.txt").read_text(encoding="utf-8").split("\n")

    assert lines[-1] == ""
    words = lines[:-1]
    assert words == sorted(words)
    assert all(word.isascii() and word.isalpha() and word.islower() for word in words)


def test_loads_other_languages_by_file_name(tmp_path: Path) -> None:
    (tmp_path / "stopwords_xx.txt").write_text("foo\nbar\n", encoding="utf-8")

    assert load_stopwords(tmp_path, "xx") == frozenset({"foo", "bar"})


def test_unknown_language_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_stopwords(tmp_path, "xx")
