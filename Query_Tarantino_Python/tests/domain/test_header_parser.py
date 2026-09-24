"""SPEC 5.1, 5.2 and 14.2."""

from src.domain.header_parser import parse_header
from src.domain.model import Book

MOBY_DICK_HEADER = """The Project Gutenberg eBook of Moby Dick; Or, The Whale

Title: Moby Dick;
       Or, The Whale

Author: Herman Melville

Release date: July 1, 2001 [eBook #2701]
                Most recently updated: August 18, 2021

Language: English"""


def test_spec_example() -> None:
    assert parse_header(2701, MOBY_DICK_HEADER) == Book(
        book_id=2701,
        title="Moby Dick; Or, The Whale",
        author="Herman Melville",
        language="en",
        release_date="July 1, 2001",
    )


def test_missing_fields_are_empty_strings() -> None:
    assert parse_header(1, "No metadata here") == Book(1, "", "", "", "")


def test_only_first_matching_line_counts() -> None:
    assert parse_header(1, "Author: First\nAuthor: Second").author == "First"


def test_field_must_start_the_line() -> None:
    assert parse_header(1, "  Title: Indented").title == ""


def test_title_continuation_stops_at_blank_line() -> None:
    assert parse_header(1, "Title: Part one\n   \n  Not appended").title == "Part one"


def test_language_keeps_text_before_first_comma() -> None:
    assert parse_header(1, "Language: French, English").language == "fr"


def test_unknown_language_is_lowercased() -> None:
    assert parse_header(1, "Language: Esperanto").language == "esperanto"


def test_book_is_indexable_only_in_english() -> None:
    assert parse_header(1, "Language: English").is_indexable()
    assert not parse_header(1, "Language: Spanish").is_indexable()


def test_non_ascii_whitespace_is_kept_as_in_java_and_cpp() -> None:
    assert parse_header(1, "Title: Dracula").title == " Dracula"
