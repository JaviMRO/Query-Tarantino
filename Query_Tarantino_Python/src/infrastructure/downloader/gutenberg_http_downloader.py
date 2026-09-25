"""
Implementation of BookDownloader that downloads a book's .txt from Project
Gutenberg via HTTP, trying the fallback URLs of SPEC 3.1, and delegates
decoding and splitting to src.domain.gutenberg_text.
"""

import time

import requests

from src.domain.gutenberg_text import decode_gutenberg_bytes, split_header_body
from src.domain.model import BookText, DownloadException, FailureReason

USER_AGENT = "QueryTarantino/1.0 (ULPGC Big Data student project)"
REQUEST_TIMEOUT_SECONDS = 30
MIN_SECONDS_BETWEEN_REQUESTS = 1.0

_URL_TEMPLATES = (
    "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
    "https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt",
    "https://www.gutenberg.org/files/{book_id}/{book_id}.txt",
)


class GutenbergHttpDownloader:
    """Downloads a book from Project Gutenberg, following SPEC 3.1-3.4."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._last_request_at: float | None = None

    def download(self, book_id: int) -> BookText:
        """Raises DownloadException on HTTP_ERROR, NO_MARKERS, or EMPTY_BODY."""
        data = self._fetch_bytes(book_id)
        text = decode_gutenberg_bytes(data)
        return split_header_body(text)

    def _fetch_bytes(self, book_id: int) -> bytes:
        for template in _URL_TEMPLATES:
            url = template.format(book_id=book_id)
            response = self._get(url)
            if response is not None and response.status_code == 200:
                return response.content
        raise DownloadException(FailureReason.HTTP_ERROR)

    def _get(self, url: str) -> requests.Response | None:
        self._respect_rate_limit()
        try:
            return self._session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
        except requests.RequestException:
            return None

    def _respect_rate_limit(self) -> None:
        """At most one request per second (SPEC 3.2), fallback URLs included."""
        if self._last_request_at is not None:
            remaining = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()
