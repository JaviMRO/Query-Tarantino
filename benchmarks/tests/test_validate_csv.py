from pathlib import Path

from validate_csv import METRICS, expected_metrics, file_errors, main, row_errors, run_errors

HEADER_LINE = "language,experiment,structure,n_books,metric,value,unit,run\n"
DOWNLOAD_RUN = (("http_throughput", "books_per_s"), ("peak_rss", "bytes"))


def row(**changes: str) -> dict[str, str]:
    valid = {
        "language": "python",
        "experiment": "index",
        "structure": "json",
        "n_books": "100",
        "metric": "build_time",
        "value": "12.345678",
        "unit": "ms",
        "run": "1",
    }
    return {**valid, **changes}


def test_a_valid_row_has_no_errors() -> None:
    assert row_errors(row(), "python", "index") == []


def test_peak_rss_is_accepted_in_every_experiment() -> None:
    assert row_errors(row(metric="peak_rss", unit="bytes"), "python", "index") == []


def test_a_value_without_six_decimals_is_an_error() -> None:
    assert row_errors(row(value="12.35"), "python", "index") != []


def test_a_wrong_unit_is_an_error() -> None:
    assert row_errors(row(unit="bytes"), "python", "index") != []


def test_a_combination_outside_spec_11_1_is_an_error() -> None:
    assert row_errors(row(n_books="200"), "python", "index") != []
    assert row_errors(row(structure="time"), "python", "index") != []


def test_folder_counts_only_in_the_folders_index() -> None:
    assert row_errors(row(metric="file_count", unit="files", value="3.000000"), "python", "index") != []
    folders = row(structure="folders", metric="file_count", unit="files", value="3.000000")
    assert row_errors(folders, "python", "index") == []


def test_disk_bytes_allocated_never_in_mongo() -> None:
    mongo = row(structure="mongo", metric="disk_bytes_allocated", unit="bytes", value="1.000000")
    assert row_errors(mongo, "python", "index") != []


def test_ok_values_are_only_0_or_1() -> None:
    recovery = row(experiment="recovery", structure="time", metric="recovery_correct_tmp_leftover", unit="ok")
    assert row_errors({**recovery, "value": "1.000000"}, "python", "recovery") == []
    assert row_errors({**recovery, "value": "0.500000"}, "python", "recovery") != []


def test_a_file_with_a_wrong_name_or_header_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "rust_index.csv").write_text(HEADER_LINE, encoding="utf-8")
    (tmp_path / "python_index.csv").write_text("language,value\n", encoding="utf-8")

    assert file_errors(tmp_path / "rust_index.csv") != []
    assert file_errors(tmp_path / "python_index.csv") != []


def test_main_checks_every_results_file_but_the_fingerprints(tmp_path: Path) -> None:
    lines = [f"python,download,none,50,{metric},1.000000,{unit},1\n" for metric, unit in DOWNLOAD_RUN]
    (tmp_path / "python_download.csv").write_text(HEADER_LINE + "".join(lines), encoding="utf-8")
    (tmp_path / "json_index_sha256.csv").write_text("language,n_books,run,sha256\n", encoding="utf-8")

    assert main(tmp_path) == 0


def run_rows(experiment: str, structure: str, n_books: str = "100") -> list[dict[str, str]]:
    units = {**METRICS[experiment], "peak_rss": "bytes"}
    return [
        row(experiment=experiment, structure=structure, n_books=n_books, metric=metric, unit=units[metric])
        for metric in sorted(expected_metrics(experiment, structure))
    ]


def test_a_complete_run_has_no_run_errors() -> None:
    assert run_errors(run_rows("index", "folders"), "index") == []
    assert run_errors(run_rows("index", "mongo"), "index") == []


def test_a_run_without_peak_rss_is_an_error() -> None:
    rows = [line for line in run_rows("index", "json") if line["metric"] != "peak_rss"]

    assert run_errors(rows, "index") == ["json n_books=100 run=1: missing peak_rss"]


def test_a_folders_run_without_file_count_is_an_error() -> None:
    rows = [line for line in run_rows("index", "folders") if line["metric"] != "file_count"]

    assert run_errors(rows, "index") == ["folders n_books=100 run=1: missing file_count"]


def test_a_repeated_metric_is_an_error() -> None:
    rows = run_rows("index", "json")

    assert run_errors([*rows, rows[0]], "index") == [
        f"json n_books=100 run=1: {rows[0]['metric']} appears more than once"
    ]


def test_the_baseline_run_only_has_peak_rss() -> None:
    assert expected_metrics("baseline", "none") == {"peak_rss"}


def test_a_row_with_missing_or_extra_fields_is_reported_instead_of_crashing(tmp_path: Path) -> None:
    lines = [f"python,download,none,50,{metric},1.000000,{unit},1\n" for metric, unit in DOWNLOAD_RUN]
    broken = HEADER_LINE + "".join(lines) + "python,download,none,50\n" + "python,download,none,50,a,b,c,d,e\n"
    (tmp_path / "python_download.csv").write_text(broken, encoding="utf-8")

    errors = file_errors(tmp_path / "python_download.csv")

    assert errors == [
        "python_download.csv:4: 4 fields instead of 8",
        "python_download.csv:5: 9 fields instead of 8",
    ]
