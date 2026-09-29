"""
Implementation of BookDownloader that reads the local corpus, corpus_raw/N.txt,
instead of requesting Project Gutenberg (SPEC 3.6). It never waits.
"""

from pathlib import Path

from src.domain.model import BookText, DownloadException, FailureReason
from src.domain.text_processing.gutenberg_text import decode_gutenberg_bytes, split_header_body

_CORPUS_FILE_SUFFIX = ".txt"


class LocalCorpusDownloader:
    """Reads corpus_dir/N.txt once and splits it like the HTTP downloader does (SPEC 3.3, 3.4)."""

    def __init__(self, corpus_dir: Path) -> None:
        self._corpus_dir = corpus_dir

    def download(self, book_id: int) -> BookText:
        """Raises DownloadException: HTTP_ERROR if the file does not exist, NO_MARKERS or EMPTY_BODY."""
        try:
            data = (self._corpus_dir / f"{book_id}{_CORPUS_FILE_SUFFIX}").read_bytes()
        except FileNotFoundError as error:
            raise DownloadException(FailureReason.HTTP_ERROR) from error
        return split_header_body(decode_gutenberg_bytes(data))
