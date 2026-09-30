from datetime import datetime, timezone

import pytest

from src.infrastructure.entrypoints.bench.experiments.lake.recovery_experiment import (
    restart_clock_start,
    run_recovery,
)
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit
from src.infrastructure.entrypoints.settings import LakeLayout
from tests.infrastructure.entrypoints.bench.conftest import Workspace, bench_context

STALE_COPIES_AFTER_DATA_WITHOUT_CONTROL = {LakeLayout.TIME: 1, LakeLayout.BOOK: 0, LakeLayout.BATCH: 0}


@pytest.mark.parametrize("layout", list(LakeLayout))
def test_both_scenarios_recover_every_book_exactly_once(workspace: Workspace, layout: LakeLayout) -> None:
    measurements = run_recovery(bench_context(workspace), layout)

    assert measurements == [
        Measurement("recovery_time_tmp_leftover", 1.0, Unit.MS),
        Measurement("recovery_correct_tmp_leftover", 1.0, Unit.OK),
        Measurement("recovery_stale_copies_tmp_leftover", 0, Unit.COUNT),
        Measurement("recovery_time_data_without_control", 1.0, Unit.MS),
        Measurement("recovery_correct_data_without_control", 1.0, Unit.OK),
        Measurement(
            "recovery_stale_copies_data_without_control", STALE_COPIES_AFTER_DATA_WITHOUT_CONTROL[layout], Unit.COUNT
        ),
    ]


@pytest.mark.parametrize(("interrupted_position", "hour"), [(50, 2), (125, 3), (250, 6), (500, 11)])
def test_the_restart_clock_starts_as_spec_14_9_says(interrupted_position: int, hour: int) -> None:
    assert restart_clock_start(interrupted_position) == datetime(2026, 1, 1, hour, tzinfo=timezone.utc)
