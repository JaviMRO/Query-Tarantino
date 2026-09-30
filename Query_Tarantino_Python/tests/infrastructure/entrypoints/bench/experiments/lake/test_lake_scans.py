import pytest

from src.domain.model import BookText
from src.infrastructure.entrypoints.bench.experiments.lake.lake_scans import (
    WHOLE_LAKE,
    checkpoint_of,
    lake_root,
    stale_copies,
    stored_book_ids,
)
from src.infrastructure.entrypoints.bench.measurement.timing import SIMULATED_CLOCK_START, simulated_clock
from src.infrastructure.entrypoints.settings import LakeLayout
from src.infrastructure.entrypoints.wiring.composition import build_datalake
from tests.infrastructure.entrypoints.bench.conftest import Workspace, bench_context

TEXT = BookText("header", "body")


@pytest.mark.parametrize("layout", list(LakeLayout))
def test_the_whole_lake_lists_every_saved_book(workspace: Workspace, layout: LakeLayout) -> None:
    context = bench_context(workspace)
    datalake = build_datalake(layout, context.bench_dir, simulated_clock(SIMULATED_CLOCK_START))
    for book_id in (5, 1342, 7):
        datalake.save(book_id, TEXT)

    assert stored_book_ids(layout, context.bench_dir, WHOLE_LAKE) == {5, 1342, 7}
    assert lake_root(layout, context.bench_dir).is_dir()


def test_the_time_checkpoint_skips_older_hour_folders(workspace: Workspace) -> None:
    context = bench_context(workspace)
    datalake = build_datalake(LakeLayout.TIME, context.bench_dir, simulated_clock(SIMULATED_CLOCK_START))
    for book_id in range(1, 121):
        datalake.save(book_id, TEXT)

    checkpoint = checkpoint_of(LakeLayout.TIME, datalake, 60)

    assert checkpoint == "20260101/01"
    assert stored_book_ids(LakeLayout.TIME, context.bench_dir, checkpoint) == set(range(51, 121))


def test_book_and_batch_have_no_checkpoint_nor_stale_copies(workspace: Workspace) -> None:
    context = bench_context(workspace)
    datalake = build_datalake(LakeLayout.BATCH, context.bench_dir, simulated_clock(SIMULATED_CLOCK_START))
    datalake.save(3, TEXT)

    assert checkpoint_of(LakeLayout.BATCH, datalake, 3) == WHOLE_LAKE
    assert stale_copies(LakeLayout.BATCH, context.bench_dir) == 0
