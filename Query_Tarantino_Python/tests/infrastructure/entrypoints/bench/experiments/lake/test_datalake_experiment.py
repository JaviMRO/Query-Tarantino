import pytest

from src.infrastructure.entrypoints.bench.bench_area import BenchValidityError
from src.infrastructure.entrypoints.bench.experiments.lake.datalake_experiment import run_datalake
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit
from src.infrastructure.entrypoints.settings import LakeLayout
from tests.infrastructure.entrypoints.bench.conftest import Workspace, bench_context

DIRECTORIES = {LakeLayout.TIME: 3, LakeLayout.BOOK: 100, LakeLayout.BATCH: 1}


@pytest.mark.parametrize("layout", list(LakeLayout))
def test_datalake_writes_the_eight_metrics_in_spec_order(workspace: Workspace, layout: LakeLayout) -> None:
    measurements = run_datalake(bench_context(workspace), layout)

    assert [(measurement.metric, measurement.unit) for measurement in measurements] == [
        ("write_throughput", Unit.BOOKS_PER_S),
        ("disk_bytes", Unit.BYTES),
        ("file_count", Unit.FILES),
        ("dir_count", Unit.DIRS),
        ("lookup_scan_mean", Unit.MS),
        ("lookup_metadata_mean", Unit.MS),
        ("detect_new_control", Unit.MS),
        ("detect_new_scan", Unit.MS),
    ]


@pytest.mark.parametrize("layout", list(LakeLayout))
def test_each_metric_divides_its_timed_region_as_spec_11_5_1_says(workspace: Workspace, layout: LakeLayout) -> None:
    measurements = {measurement.metric: measurement for measurement in run_datalake(bench_context(workspace), layout)}

    assert measurements["write_throughput"] == Measurement("write_throughput", 100_000.0, Unit.BOOKS_PER_S)
    assert measurements["lookup_scan_mean"].value == 0.001
    assert measurements["lookup_metadata_mean"].value == 0.001
    assert measurements["detect_new_control"].value == 0.05
    assert measurements["detect_new_scan"].value == 0.05


@pytest.mark.parametrize("layout", list(LakeLayout))
def test_storage_counts_the_files_and_folders_of_the_lake_root(workspace: Workspace, layout: LakeLayout) -> None:
    measurements = {
        measurement.metric: measurement.value for measurement in run_datalake(bench_context(workspace), layout)
    }

    assert measurements["file_count"] == 200
    assert measurements["dir_count"] == DIRECTORIES[layout]


def test_a_book_missing_from_the_corpus_makes_the_run_invalid(workspace: Workspace) -> None:
    (workspace.corpus_dir / "7.txt").unlink()

    with pytest.raises(BenchValidityError):
        run_datalake(bench_context(workspace), LakeLayout.BOOK)
