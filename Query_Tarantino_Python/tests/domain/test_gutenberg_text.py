"""SPEC 3.3, 3.4 and 14.2."""

import pytest

from src.domain.gutenberg_text import decode_gutenberg_bytes, split_header_body
from src.domain.model import BookText, DownloadException, FailureReason

START = "*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***"
END = "*** END OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***"


def test_spec_example_with_bom_and_crlf() -> None:
    text = f"\ufeffTitle: Moby Dick\r\n\r\n{START}\r\n\r\nCall me Ishmael.\r\n\r\n{END}\r\n\r\nLicense text"
    raw = text.encode("utf-8")

    assert split_header_body(decode_gutenberg_bytes(raw)) == BookText("Title: Moby Dick", "Call me Ishmael.")


def test_invalid_utf8_falls_back_to_latin1() -> None:
    assert decode_gutenberg_bytes("café".encode("latin-1")) == "café"


def test_lone_cr_becomes_lf() -> None:
    assert decode_gutenberg_bytes(b"a\rb") == "a\nb"


def test_lowercase_marker_is_recognized() -> None:
    start = "*** start of this project gutenberg ebook x ***"
    end = "*** end of this project gutenberg ebook x ***"
    text = f"header\n{start}\nbody\n{end}"

    assert split_header_body(text) == BookText("header", "body")


def test_end_marker_must_come_after_start() -> None:
    text = f"{END}\nheader\n{START}\nbody"

    with pytest.raises(DownloadException) as error:
        split_header_body(text)
    assert error.value.reason is FailureReason.NO_MARKERS


def test_missing_start_marker() -> None:
    with pytest.raises(DownloadException) as error:
        split_header_body(f"no start\n{END}")
    assert error.value.reason is FailureReason.NO_MARKERS


def test_only_whitespace_between_markers() -> None:
    with pytest.raises(DownloadException) as error:
        split_header_body(f"header\n{START}\n \t\n{END}")
    assert error.value.reason is FailureReason.EMPTY_BODY


def test_marker_does_not_accept_non_ascii_whitespace() -> None:
    text = f"header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nbody\n{END}"

    with pytest.raises(DownloadException) as error:
        split_header_body(text)
    assert error.value.reason is FailureReason.NO_MARKERS
