"""SPEC 3.3, 3.4 and 14.2."""

import pytest

from src.domain.gutenberg_text import decode_gutenberg_bytes, split_header_body
from src.domain.model import DownloadException, FailureReason

START = "*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***"
END = "*** END OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***"


def test_spec_example_with_bom_and_crlf():
    raw = f"﻿Title: Moby Dick\r\n\r\n{START}\r\n\r\nCall me Ishmael.\r\n\r\n{END}\r\n\r\nLicense text".encode("utf-8")

    header, body = split_header_body(decode_gutenberg_bytes(raw))

    assert header == "Title: Moby Dick"
    assert body == "Call me Ishmael."


def test_invalid_utf8_falls_back_to_latin1():
    assert decode_gutenberg_bytes("café".encode("latin-1")) == "café"


def test_lone_cr_becomes_lf():
    assert decode_gutenberg_bytes(b"a\rb") == "a\nb"


def test_lowercase_marker_is_recognized():
    text = "header\n*** start of this project gutenberg ebook x ***\nbody\n*** end of this project gutenberg ebook x ***"

    assert split_header_body(text) == ("header", "body")


def test_end_marker_must_come_after_start():
    text = f"{END}\nheader\n{START}\nbody"

    with pytest.raises(DownloadException) as error:
        split_header_body(text)
    assert error.value.reason is FailureReason.NO_MARKERS


def test_missing_start_marker():
    with pytest.raises(DownloadException) as error:
        split_header_body(f"no start\n{END}")
    assert error.value.reason is FailureReason.NO_MARKERS


def test_only_whitespace_between_markers():
    with pytest.raises(DownloadException) as error:
        split_header_body(f"header\n{START}\n \t\n{END}")
    assert error.value.reason is FailureReason.EMPTY_BODY
