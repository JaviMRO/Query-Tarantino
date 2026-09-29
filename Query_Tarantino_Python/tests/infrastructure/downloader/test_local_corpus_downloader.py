from pathlib import Path

import pytest

from src.domain.model import BookText, DownloadException, FailureReason
from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader

BOOK_ID = 2701
CORPUS_TEXT = (
    "Title: Moby Dick\n"
    "\n"
    "*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK ***\n"
    "Call me Ishmael.\n"
    "*** END OF THE PROJECT GUTENBERG EBOOK MOBY DICK ***\n"
    "License text"
)


def test_reads_and_splits_the_corpus_file(tmp_path: Path) -> None:
    (tmp_path / "2701.txt").write_text(CORPUS_TEXT, encoding="utf-8", newline="")

    result = LocalCorpusDownloader(tmp_path).download(BOOK_ID)

    assert result == BookText("Title: Moby Dick", "Call me Ishmael.")


def test_a_missing_corpus_file_fails_with_http_error(tmp_path: Path) -> None:
    with pytest.raises(DownloadException) as raised:
        LocalCorpusDownloader(tmp_path).download(BOOK_ID)

    assert raised.value.reason == FailureReason.HTTP_ERROR


def test_a_corpus_file_without_markers_fails_with_no_markers(tmp_path: Path) -> None:
    (tmp_path / "2701.txt").write_text("no markers", encoding="utf-8", newline="")

    with pytest.raises(DownloadException) as raised:
        LocalCorpusDownloader(tmp_path).download(BOOK_ID)

    assert raised.value.reason == FailureReason.NO_MARKERS
