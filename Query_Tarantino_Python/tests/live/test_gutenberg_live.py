import os
import time
from collections.abc import Iterator

import pytest
import requests

from src.domain.model import DownloadException, FailureReason
from src.domain.text_processing.header_parser import parse_header
from src.infrastructure.downloader.gutenberg_http_downloader import (
    GUTENBERG_BASE_URL,
    MIN_SECONDS_BETWEEN_REQUESTS,
    GutenbergHttpDownloader,
)

LIVE_TESTS_VARIABLE = "TARANTINO_LIVE_TESTS"
PRIDE_AND_PREJUDICE = 1342
MISSING_BOOK_ID = 999_999
HTTP_BASE_URL = "http://www.gutenberg.org"

pytestmark = pytest.mark.skipif(
    os.environ.get(LIVE_TESTS_VARIABLE) != "1",
    reason=f"live requests to gutenberg.org run only with {LIVE_TESTS_VARIABLE}=1",
)


@pytest.fixture(scope="module")
def session() -> Iterator[requests.Session]:
    with requests.Session() as http_session:
        yield http_session


@pytest.fixture(scope="module")
def downloader(session: requests.Session) -> GutenbergHttpDownloader:
    return GutenbergHttpDownloader(
        session, GUTENBERG_BASE_URL, time.monotonic, time.sleep, MIN_SECONDS_BETWEEN_REQUESTS
    )


def test_a_real_book_is_downloaded_split_and_parsed(downloader: GutenbergHttpDownloader) -> None:
    text = downloader.download(PRIDE_AND_PREJUDICE)

    book = parse_header(PRIDE_AND_PREJUDICE, text.header)
    assert book.title == "Pride and Prejudice"
    assert book.author == "Jane Austen"
    assert book.language == "en"
    assert "It is a truth universally acknowledged" in text.body


def test_the_real_text_is_normalized_and_keeps_the_markers(downloader: GutenbergHttpDownloader) -> None:
    text = downloader.fetch_text(PRIDE_AND_PREJUDICE)

    assert not text.startswith("﻿")
    assert "\r" not in text
    assert "*** START OF THE PROJECT GUTENBERG EBOOK" in text.upper()


def test_a_missing_book_tries_the_three_urls_one_second_apart(downloader: GutenbergHttpDownloader) -> None:
    started = time.monotonic()

    with pytest.raises(DownloadException) as raised:
        downloader.download(MISSING_BOOK_ID)

    assert raised.value.reason == FailureReason.HTTP_ERROR
    assert time.monotonic() - started >= 2 * MIN_SECONDS_BETWEEN_REQUESTS


def test_the_http_address_redirects_to_https_and_is_followed() -> None:
    responses: list[requests.Response] = []
    with requests.Session() as session:
        session.hooks["response"].append(lambda response, *_args, **_kwargs: responses.append(response))
        downloader = GutenbergHttpDownloader(
            session, HTTP_BASE_URL, time.monotonic, time.sleep, MIN_SECONDS_BETWEEN_REQUESTS
        )

        text = downloader.download(PRIDE_AND_PREJUDICE)

    assert parse_header(PRIDE_AND_PREJUDICE, text.header).language == "en"
    assert any(response.is_redirect for response in responses)
