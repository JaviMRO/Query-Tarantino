from datetime import datetime, timezone

import pytest

from src.infrastructure.entrypoints.bench.measurement.timing import (
    SIMULATED_CLOCK_START,
    milliseconds,
    nearest_rank,
    per_second,
    sample_positions,
    simulated_clock,
    timed,
    warm_mean,
)
from tests.infrastructure.entrypoints.bench.conftest import millisecond_clock

SPEC_14_9_SAMPLES = [5.0, 1.0, 4.0, 2.0, 3.0, 10.0, 9.0, 8.0, 7.0, 6.0]


@pytest.mark.parametrize(("percentile", "expected"), [(25, 3.0), (50, 5.0), (75, 8.0), (95, 10.0), (99, 10.0)])
def test_nearest_rank_gives_the_spec_14_9_percentiles(percentile: int, expected: float) -> None:
    assert nearest_rank(sorted(SPEC_14_9_SAMPLES), percentile) == expected


@pytest.mark.parametrize(("call", "hour"), [(0, 0), (49, 0), (50, 1), (999, 19)])
def test_simulated_clock_advances_one_hour_every_50_calls(call: int, hour: int) -> None:
    clock = simulated_clock(SIMULATED_CLOCK_START)

    instants = [clock() for _ in range(call + 1)]

    assert instants[call] == datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("n_books", "first_positions", "last_position"),
    [(100, [0, 2, 4], 98), (250, [0, 5, 10], 245), (500, [0, 10, 20], 490), (1000, [0, 20, 40], 980)],
)
def test_sample_positions_follow_spec_14_9(n_books: int, first_positions: list[int], last_position: int) -> None:
    positions = sample_positions(n_books)

    assert len(positions) == 50
    assert positions[:3] == first_positions
    assert positions[-1] == last_position


def test_timed_returns_the_result_and_the_time_between_two_clock_reads() -> None:
    measured = timed(millisecond_clock(), lambda: "done")

    assert (measured.result, measured.elapsed_ns) == ("done", 1_000_000)


def test_warm_mean_runs_a_warm_up_pass_and_divides_the_measured_region_by_the_operations() -> None:
    passes: list[int] = []

    measured = warm_mean(millisecond_clock(), lambda: passes.append(1), 20, 1000)

    assert len(passes) == 21
    assert measured.mean_ms == 0.001


def test_warm_mean_keeps_what_each_measured_pass_returned_but_not_the_warm_up() -> None:
    calls = iter(range(10))

    measured = warm_mean(millisecond_clock(), lambda: next(calls), 3, 3)

    assert measured.results == [1, 2, 3]


def test_times_and_throughputs_use_milliseconds_and_seconds() -> None:
    assert milliseconds(2_500_000) == 2.5
    assert per_second(50, 2_000_000_000) == 25.0
