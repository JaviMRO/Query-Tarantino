from src.domain.model import Book, BookText, StoredPaths, TermOccurrences
from src.infrastructure.entrypoints.bench.experiments.index.timed_ports import (
    TimeAccumulator,
    TimedDatalake,
    TimedIndexStorage,
    TimedMetadataStorage,
)
from tests.application.fakes import CallLog, FakeDatalake, FakeIndexStorage, FakeMetadataStorage
from tests.infrastructure.entrypoints.bench.conftest import millisecond_clock

BOOK = Book(7, "Title", "Author", "en", "")
TEXT = BookText("header", "body")


def test_only_load_is_timed_in_the_datalake() -> None:
    accumulator = TimeAccumulator(millisecond_clock())
    datalake = TimedDatalake(FakeDatalake(CallLog(), {7: TEXT}), accumulator)

    paths = datalake.save(8, TEXT)
    datalake.get_paths(8)
    loaded = datalake.load(7)

    assert (loaded, accumulator.total_ns) == (TEXT, 1_000_000)
    assert isinstance(paths, StoredPaths)


def test_both_metadata_writes_add_up() -> None:
    accumulator = TimeAccumulator(millisecond_clock())
    log = CallLog()
    metadata = TimedMetadataStorage(FakeMetadataStorage(log), accumulator)

    metadata.save(BOOK, StoredPaths("h", "b"))
    metadata.update_indexed_at(7, "2026-01-01T00:00:00Z")

    assert accumulator.total_ns == 2_000_000
    assert log.methods() == ["save_metadata", "update_indexed_at"]


def test_index_writes_are_timed_and_forwarded() -> None:
    accumulator = TimeAccumulator(millisecond_clock())
    log = CallLog()

    TimedIndexStorage(FakeIndexStorage(log), accumulator).write_book_terms(7, {"whale": TermOccurrences(1, (0,))})

    assert accumulator.total_ns == 1_000_000
    assert log.methods() == ["write_book_terms"]
