"""
Implementation of BookDownloader and RawTextSource that downloads a book's .txt
from Project Gutenberg via HTTP, trying the fallback URLs of SPEC 3.1 with the
politeness rules of SPEC 3.2, and delegates decoding and splitting to
src.domain.text_processing.gutenberg_text.
"""

from collections.abc import Callable, Iterator

import requests

from src.domain.model import BookText, DownloadException, FailureReason
from src.domain.text_processing.gutenberg_text import decode_gutenberg_bytes, split_header_body

GUTENBERG_BASE_URL = "https://www.gutenberg.org"
USER_AGENT = "QueryTarantino/1.0 (ULPGC Big Data student project)"
REQUEST_TIMEOUT_SECONDS = 30
MIN_SECONDS_BETWEEN_REQUESTS = 1.0

_HTTP_OK = 200
_URL_PATH_TEMPLATES = (
    "/cache/epub/{book_id}/pg{book_id}.txt",
    "/files/{book_id}/{book_id}-0.txt",
    "/files/{book_id}/{book_id}.txt",
)


class GutenbergHttpDownloader:
    """
    Downloads a book following SPEC 3.1-3.4. The session, the base URL, the monotonic clock, the sleep
    function and the wait between request starts (never below the SPEC minimum of one second) are injected;
    the start of the last request is the only state kept between calls.
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
        seconds_between_requests: float,
    ) -> None:
        if seconds_between_requests < MIN_SECONDS_BETWEEN_REQUESTS:
            raise ValueError(f"SPEC 3.2 requires at least {MIN_SECONDS_BETWEEN_REQUESTS} s between requests")
        self._session = session
        self._base_url = base_url
        self._monotonic = monotonic
        self._sleep = sleep
        self._seconds_between_requests = seconds_between_requests
        self._last_request_started_at: float | None = None

    def download(self, book_id: int) -> BookText:
        """Raises DownloadException on HTTP_ERROR, NO_MARKERS, or EMPTY_BODY."""
        return split_header_body(self.fetch_text(book_id))

    def fetch_text(self, book_id: int) -> str:
        """Whole normalized text, not split (SPEC 3.3, 3.6); raises DownloadException with HTTP_ERROR."""
        return decode_gutenberg_bytes(self._fetch_bytes(book_id))

    def _fetch_bytes(self, book_id: int) -> bytes:
        """The first URL answering 200 wins; a non-200 answer or any network error moves on to the next one."""
        for url in self._urls_for(book_id):
            try:
                response = self._request(url)
            except requests.RequestException:
                continue
            if response.status_code == _HTTP_OK:
                return response.content
        raise DownloadException(FailureReason.HTTP_ERROR)

    def _urls_for(self, book_id: int) -> Iterator[str]:
        for template in _URL_PATH_TEMPLATES:
            yield self._base_url + template.format(book_id=book_id)

    def _request(self, url: str) -> requests.Response:
        self._wait_for_politeness()
        return self._session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )

    def _wait_for_politeness(self) -> None:
        """The configured wait between the starts of two requests, fallback URLs included (SPEC 3.2)."""
        if self._last_request_started_at is not None:
            remaining = self._seconds_between_requests - (self._monotonic() - self._last_request_started_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_started_at = self._monotonic()
