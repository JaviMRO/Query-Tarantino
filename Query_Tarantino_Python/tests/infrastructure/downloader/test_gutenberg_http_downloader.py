from typing import cast
from unittest.mock import MagicMock

import pytest
import requests

from src.domain.model import BookText, DownloadException, FailureReason
from src.infrastructure.downloader.gutenberg_http_downloader import GutenbergHttpDownloader

BOOK_ID = 2701
RAW_TEXT = (
    "Title: Moby Dick\n"
    "\n"
    "*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK ***\n"
    "Call me Ishmael.\n"
    "*** END OF THE PROJECT GUTENBERG EBOOK MOBY DICK ***\n"
    "License text"
)


def _response(status_code: int, content: bytes = b"") -> requests.Response:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.content = content
    return cast(requests.Response, response)


def build(session: MagicMock) -> GutenbergHttpDownloader:
    return GutenbergHttpDownloader(cast(requests.Session, session))


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests are about URL fallback and error handling, not timing (SPEC 3.2 is tested separately)."""
    monkeypatch.setattr("src.infrastructure.downloader.gutenberg_http_downloader.time.sleep", lambda _seconds: None)


def test_first_url_success_downloads_and_splits() -> None:
    session = MagicMock()
    session.get.return_value = _response(200, RAW_TEXT.encode("utf-8"))

    result = build(session).download(BOOK_ID)

    assert result == BookText("Title: Moby Dick", "Call me Ishmael.")
    url = session.get.call_args.args[0]
    assert url == f"https://www.gutenberg.org/cache/epub/{BOOK_ID}/pg{BOOK_ID}.txt"


def test_falls_back_to_next_url_on_non_200() -> None:
    session = MagicMock()
    session.get.side_effect = [_response(404), _response(200, RAW_TEXT.encode("utf-8"))]

    result = build(session).download(BOOK_ID)

    assert result.body == "Call me Ishmael."
    assert session.get.call_count == 2
    second_url = session.get.call_args_list[1].args[0]
    assert second_url == f"https://www.gutenberg.org/files/{BOOK_ID}/{BOOK_ID}-0.txt"


def test_network_error_is_treated_as_a_failed_url_and_the_next_one_is_tried() -> None:
    session = MagicMock()
    session.get.side_effect = [requests.ConnectionError(), _response(200, RAW_TEXT.encode("utf-8"))]

    result = build(session).download(BOOK_ID)

    assert result.body == "Call me Ishmael."
    assert session.get.call_count == 2


def test_all_three_urls_failing_raises_http_error() -> None:
    session = MagicMock()
    session.get.return_value = _response(404)

    with pytest.raises(DownloadException) as excinfo:
        build(session).download(BOOK_ID)

    assert excinfo.value.reason == FailureReason.HTTP_ERROR
    assert session.get.call_count == 3


def test_request_uses_the_spec_user_agent_timeout_and_redirects() -> None:
    session = MagicMock()
    session.get.return_value = _response(200, RAW_TEXT.encode("utf-8"))

    build(session).download(BOOK_ID)

    _, kwargs = session.get.call_args
    assert kwargs["headers"]["User-Agent"] == "QueryTarantino/1.0 (ULPGC Big Data student project)"
    assert kwargs["timeout"] == 30
    assert kwargs["allow_redirects"] is True


def test_missing_markers_propagates_as_no_markers() -> None:
    session = MagicMock()
    session.get.return_value = _response(200, b"no markers in this text")

    with pytest.raises(DownloadException) as excinfo:
        build(session).download(BOOK_ID)

    assert excinfo.value.reason == FailureReason.NO_MARKERS


def test_empty_body_propagates_as_empty_body() -> None:
    session = MagicMock()
    text = "*** START OF THE PROJECT GUTENBERG EBOOK X ***\n*** END OF THE PROJECT GUTENBERG EBOOK X ***"
    session.get.return_value = _response(200, text.encode("utf-8"))

    with pytest.raises(DownloadException) as excinfo:
        build(session).download(BOOK_ID)

    assert excinfo.value.reason == FailureReason.EMPTY_BODY


def test_waits_at_least_one_second_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "src.infrastructure.downloader.gutenberg_http_downloader.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    times = iter([0.0, 0.2, 0.2])
    monkeypatch.setattr(
        "src.infrastructure.downloader.gutenberg_http_downloader.time.monotonic",
        lambda: next(times),
    )
    session = MagicMock()
    session.get.side_effect = [_response(404), _response(200, RAW_TEXT.encode("utf-8"))]

    build(session).download(BOOK_ID)

    assert sleeps == [pytest.approx(0.8)]
