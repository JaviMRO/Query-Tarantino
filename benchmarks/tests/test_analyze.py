import math
from pathlib import Path

import pandas as pd
import pytest

from analyze import (
    aggregate,
    coefficient_of_variation,
    least_squares_slope,
    nearest_rank,
    speedup,
    validity_problems,
    write_extra_rounds,
    write_rerun_configurations,
)

SPEC_14_9_SAMPLES = [5, 1, 4, 2, 3, 10, 9, 8, 7, 6]
COLUMNS = ["language", "experiment", "structure", "n_books", "metric", "value", "unit", "run"]


def results(*rows: tuple[str, str, str, int, str, float, str, int]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=COLUMNS)


@pytest.mark.parametrize(("percentile", "expected"), [(25, 3), (50, 5), (75, 8), (95, 10), (99, 10)])
def test_nearest_rank_matches_spec_14_9(percentile: int, expected: float) -> None:
    assert nearest_rank(SPEC_14_9_SAMPLES, percentile) == expected


def test_coefficient_of_variation_is_the_sample_deviation_over_the_mean() -> None:
    assert coefficient_of_variation([2.0, 2.0]) == 0.0
    assert coefficient_of_variation([1.0, 3.0]) == pytest.approx(math.sqrt(2) / 2)


def test_the_log_log_slope_is_1_for_linear_and_2_for_quadratic_growth() -> None:
    sizes = [100.0, 250.0, 500.0, 1000.0]

    assert least_squares_slope(sizes, [3 * size for size in sizes]) == pytest.approx(1.0)
    assert least_squares_slope(sizes, [size * size for size in sizes]) == pytest.approx(2.0)


def test_the_slope_ignores_non_positive_values() -> None:
    assert math.isnan(least_squares_slope([100.0, 1000.0], [0.0, 5.0]))


def test_speedup_is_above_1_when_the_candidate_is_better() -> None:
    assert speedup(10.0, 5.0, "ms") == 2.0
    assert speedup(100.0, 200.0, "books_per_s") == 2.0


def test_aggregate_ignores_the_warm_up_round_and_flags_noisy_timings() -> None:
    measured = results(
        ("python", "index", "json", 100, "build_time", 1000.0, "ms", 0),
        ("python", "index", "json", 100, "build_time", 10.0, "ms", 1),
        ("python", "index", "json", 100, "build_time", 20.0, "ms", 2),
        ("python", "index", "json", 100, "index_terms", 7.0, "count", 1),
        ("python", "index", "json", 100, "index_terms", 9.0, "count", 2),
    )

    aggregated = aggregate(measured).set_index("metric")

    assert aggregated.at["build_time", "runs"] == 2
    assert aggregated.at["build_time", "median"] == 15.0
    assert bool(aggregated.at["build_time", "flagged"])
    assert not bool(aggregated.at["index_terms", "flagged"])


def test_validity_reports_different_counts_failed_recoveries_and_fingerprints(tmp_path: Path) -> None:
    measured = results(
        ("python", "index", "json", 100, "index_terms", 7.0, "count", 1),
        ("java", "index", "json", 100, "index_terms", 8.0, "count", 1),
        ("python", "recovery", "time", 100, "recovery_correct_tmp_leftover", 0.0, "ok", 1),
    )
    (tmp_path / "json_index_sha256.csv").write_text(
        "language,n_books,run,sha256\npython,100,1,aa\njava,100,1,bb\n", encoding="utf-8"
    )

    assert len(validity_problems(measured, tmp_path)) == 3


def test_consistent_results_have_no_validity_problems(tmp_path: Path) -> None:
    measured = results(
        ("python", "index", "json", 100, "index_terms", 7.0, "count", 1),
        ("java", "index", "mongo", 100, "index_terms", 7.0, "count", 1),
        ("python", "recovery", "time", 100, "recovery_correct_tmp_leftover", 1.0, "ok", 1),
    )

    assert validity_problems(measured, tmp_path) == []


def test_flagged_configurations_are_written_for_run_all(tmp_path: Path) -> None:
    measured = results(
        ("cpp", "index", "json", 100, "build_time", 10.0, "ms", 1),
        ("cpp", "index", "json", 100, "build_time", 20.0, "ms", 2),
    )

    assert write_rerun_configurations(aggregate(measured), tmp_path) == 1
    assert (tmp_path / "rerun_configurations.txt").read_text(encoding="utf-8") == "cpp index json 100\n"


def test_the_report_lists_the_configurations_measured_in_extra_rounds(tmp_path: Path) -> None:
    measured = results(
        ("java", "index", "json", 100, "build_time", 10.0, "ms", 5),
        ("java", "index", "json", 100, "build_time", 11.0, "ms", 6),
        ("java", "index", "json", 100, "build_time", 12.0, "ms", 7),
        ("cpp", "datalake", "book", 100, "write_throughput", 1.0, "books_per_s", 3),
    )

    assert write_extra_rounds(measured, tmp_path) == 1
    report = (tmp_path / "extra_rounds.md").read_text(encoding="utf-8")
    assert "- java index json 100: rounds 6, 7" in report
    assert "cpp" not in report


def test_the_report_says_when_no_extra_round_was_needed(tmp_path: Path) -> None:
    measured = results(("cpp", "datalake", "book", 100, "write_throughput", 1.0, "books_per_s", 1))

    assert write_extra_rounds(measured, tmp_path) == 0
    assert "None" in (tmp_path / "extra_rounds.md").read_text(encoding="utf-8")
