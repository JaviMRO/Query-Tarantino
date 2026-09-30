"""
Decorators that implement the ports used by IndexBookUseCase and add up the time
spent inside the wrapped calls, for the breakdown of build_time (SPEC 11.5.3 step 2).
"""

from collections.abc import Callable
from typing import TypeVar

from src.domain.model import Book, BookText, StoredPaths, TermOccurrences
from src.domain.ports import DatalakeStorage, InvertedIndexStorage, MetadataStorage
from src.infrastructure.entrypoints.bench.measurement.timing import NanoClock

_Result = TypeVar("_Result")


class TimeAccumulator:
    """Total nanoseconds spent inside the calls it measured; its total is the only state it keeps."""

    def __init__(self, clock: NanoClock) -> None:
        self._clock = clock
        self._total_ns = 0

    @property
    def total_ns(self) -> int:
        """Nanoseconds added up so far."""
        return self._total_ns

    def measure(self, call: Callable[[], _Result]) -> _Result:
        """Runs the call and adds its duration to the total."""
        start = self._clock()
        result = call()
        self._total_ns += self._clock() - start
        return result


class TimedDatalake:
    """DatalakeStorage whose load() is timed (lake_read_time)."""

    def __init__(self, datalake: DatalakeStorage, accumulator: TimeAccumulator) -> None:
        self._datalake = datalake
        self._accumulator = accumulator

    def save(self, book_id: int, text: BookText) -> StoredPaths:
        """Not timed: indexing never saves to the lake."""
        return self._datalake.save(book_id, text)

    def load(self, book_id: int) -> BookText:
        """Timed."""
        return self._accumulator.measure(lambda: self._datalake.load(book_id))

    def get_paths(self, book_id: int) -> StoredPaths:
        """Not timed: SPEC 11.5.3 only times load()."""
        return self._datalake.get_paths(book_id)


class TimedMetadataStorage:
    """MetadataStorage whose two writes are timed (metadata_write_time)."""

    def __init__(self, metadata: MetadataStorage, accumulator: TimeAccumulator) -> None:
        self._metadata = metadata
        self._accumulator = accumulator

    def save(self, book: Book, paths: StoredPaths) -> None:
        """Timed."""
        self._accumulator.measure(lambda: self._metadata.save(book, paths))

    def update_indexed_at(self, book_id: int, timestamp: str) -> None:
        """Timed."""
        self._accumulator.measure(lambda: self._metadata.update_indexed_at(book_id, timestamp))


class TimedIndexStorage:
    """InvertedIndexStorage whose write is timed (index_write_time)."""

    def __init__(self, index: InvertedIndexStorage, accumulator: TimeAccumulator) -> None:
        self._index = index
        self._accumulator = accumulator

    def write_book_terms(self, book_id: int, terms: dict[str, TermOccurrences]) -> None:
        """Timed."""
        self._accumulator.measure(lambda: self._index.write_book_terms(book_id, terms))
