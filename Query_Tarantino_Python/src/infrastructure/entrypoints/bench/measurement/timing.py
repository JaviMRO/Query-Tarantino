"""Clock, sample and statistics rules shared by every experiment (SPEC 11.3, 11.4, 11.5)."""

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Generic, TypeVar

NanoClock = Callable[[], int]

SAMPLE_SIZE = 50
SIMULATED_CLOCK_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
BOOKS_PER_SIMULATED_HOUR = 50

_NANOSECONDS_PER_MILLISECOND = 1_000_000
_NANOSECONDS_PER_SECOND = 1_000_000_000
_PERCENT = 100

_Result = TypeVar("_Result")


class Unit(Enum):
    """Units of the CSV (SPEC 11.8)."""

    BOOKS_PER_S = "books_per_s"
    ROWS_PER_S = "rows_per_s"
    MS = "ms"
    BYTES = "bytes"
    FILES = "files"
    DIRS = "dirs"
    OK = "ok"
    COUNT = "count"


@dataclass(frozen=True, slots=True)
class Measurement:
    """One metric of a run, written as one CSV row (SPEC 11.8)."""

    metric: str
    value: float
    unit: Unit


@dataclass(frozen=True, slots=True)
class Timed(Generic[_Result]):
    """What a timed operation returned and how long it took."""

    result: _Result
    elapsed_ns: int


def timed(clock: NanoClock, operation: Callable[[], _Result]) -> Timed[_Result]:
    """Runs the operation inside a single timed region (SPEC 11.3 rule 2)."""
    start = clock()
    result = operation()
    return Timed(result, clock() - start)


@dataclass(frozen=True, slots=True)
class WarmMean(Generic[_Result]):
    """Mean time per operation of the measured passes, and what each measured pass returned."""

    mean_ms: float
    results: list[_Result]


def warm_mean(clock: NanoClock, one_pass: Callable[[], _Result], passes: int, operations: int) -> WarmMean[_Result]:
    """
    One unmeasured warm-up pass, then `passes` passes timed as a single region; the total, in milliseconds,
    divided by the number of operations (SPEC 11.3 rules 3 and 4). The results let the validity checks of
    SPEC 11.7 look at the measured passes themselves.
    """
    one_pass()
    results = []
    start = clock()
    for _ in range(passes):
        results.append(one_pass())
    return WarmMean(milliseconds(clock() - start) / operations, results)


def milliseconds(elapsed_ns: int) -> float:
    """Nanoseconds as milliseconds (SPEC 11.3 rule 9)."""
    return elapsed_ns / _NANOSECONDS_PER_MILLISECOND


def per_second(items: int, elapsed_ns: int) -> float:
    """Items per second, with the elapsed time in seconds (SPEC 11.3 rule 9)."""
    return items * _NANOSECONDS_PER_SECOND / elapsed_ns


def nearest_rank(ascending_samples: Sequence[float], percentile: int) -> float:
    """The sample at 1-based position (p x n + 99) div 100, without interpolation (SPEC 11.3 rule 5)."""
    return ascending_samples[(percentile * len(ascending_samples) + _PERCENT - 1) // _PERCENT - 1]


def sample_positions(n_books: int) -> list[int]:
    """The 50 positions floor(j x N / 50), for j = 0...49 (SPEC 11.5.1)."""
    return [position * n_books // SAMPLE_SIZE for position in range(SAMPLE_SIZE)]


def simulated_clock(start: datetime) -> Callable[[], datetime]:
    """On its i-th call (from 0) it returns start + floor(i / 50) hours (SPEC 11.4)."""
    calls = itertools.count()
    return lambda: start + timedelta(hours=next(calls) // BOOKS_PER_SIMULATED_HOUR)
