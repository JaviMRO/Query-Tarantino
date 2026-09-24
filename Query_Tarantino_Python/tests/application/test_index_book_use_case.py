from datetime import datetime, timezone

from src.application.index_book_use_case import BookIndexed, BookSkipped, IndexBookUseCase
from src.domain.model import Book, BookText
from tests.application.fakes import (
    CallLog,
    FakeControlStateStore,
    FakeDatalake,
    FakeIndexStorage,
    FakeMetadataStorage,
    paths_for,
)

BOOK_ID = 2701
ENGLISH_HEADER = "Title: Moby Dick\nLanguage: English"
SPANISH_HEADER = "Title: Don Quijote\nLanguage: Spanish"
FIXED_NOW = datetime(2026, 9, 24, 8, 5, 3, tzinfo=timezone.utc)


def build(header: str, log: CallLog) -> IndexBookUseCase:
    return IndexBookUseCase(
        datalake=FakeDatalake(log, {BOOK_ID: BookText(header, "whale whale ship")}),
        metadata_store=FakeMetadataStorage(log),
        index_store=FakeIndexStorage(log),
        control=FakeControlStateStore(log),
        stopwords=frozenset({"the"}),
        clock=lambda: FIXED_NOW,
    )


def test_english_book_is_indexed_in_spec_order() -> None:
    log = CallLog()

    result = build(ENGLISH_HEADER, log).execute(BOOK_ID)

    assert log.methods() == ["save_metadata", "write_book_terms", "update_indexed_at", "record_indexing"]
    assert result == BookIndexed(BOOK_ID, terms_count=2)


def test_metadata_is_saved_with_datalake_paths() -> None:
    log = CallLog()

    build(ENGLISH_HEADER, log).execute(BOOK_ID)

    expected_book = Book(BOOK_ID, "Moby Dick", "", "en", "")
    assert log.calls[0] == ("save_metadata", expected_book, paths_for(BOOK_ID))


def test_indexed_at_uses_spec_format() -> None:
    log = CallLog()

    build(ENGLISH_HEADER, log).execute(BOOK_ID)

    assert ("update_indexed_at", BOOK_ID, "2026-09-24T08:05:03Z") in log.calls


def test_non_english_book_only_saves_metadata() -> None:
    log = CallLog()

    result = build(SPANISH_HEADER, log).execute(BOOK_ID)

    assert log.methods() == ["save_metadata", "record_indexing"]
    assert result == BookSkipped(BOOK_ID, language="es")
