"""
Checks that every results CSV follows SPEC 11.8 exactly: header, columns, the combinations of SPEC 11.1, the
metric-unit pairs and the six-decimal values.

Usage: validate_csv.py RESULTS_DIR
"""

import csv
import re
import sys
from pathlib import Path

HEADER = ["language", "experiment", "structure", "n_books", "metric", "value", "unit", "run"]
LANGUAGES = {"java", "python", "cpp"}
VALUE_PATTERN = re.compile(r"^-?[0-9]+\.[0-9]{6}$")
OK_VALUES = {"0.000000", "1.000000"}
NOT_RESULTS = {"json_index_sha256.csv"}
CORPUS_SIZES = {100, 250, 500, 1000}
GRID = {
    "datalake": ({"time", "book", "batch"}, CORPUS_SIZES),
    "recovery": ({"time", "book", "batch"}, CORPUS_SIZES),
    "index": ({"json", "mongo", "folders"}, CORPUS_SIZES),
    "metadata": ({"sqlite"}, {1000, 10000, 50000}),
    "download": ({"none"}, {50}),
    "baseline": ({"none"}, {0}),
}
RECOVERY_METRICS = {
    f"{metric}_{scenario}": unit
    for scenario in ("tmp_leftover", "data_without_control")
    for metric, unit in (("recovery_time", "ms"), ("recovery_correct", "ok"), ("recovery_stale_copies", "count"))
}
METRICS = {
    "datalake": {
        "write_throughput": "books_per_s",
        "lookup_scan_mean": "ms",
        "lookup_metadata_mean": "ms",
        "detect_new_control": "ms",
        "detect_new_scan": "ms",
        "disk_bytes": "bytes",
        "disk_bytes_allocated": "bytes",
        "file_count": "files",
        "dir_count": "dirs",
    },
    "recovery": RECOVERY_METRICS,
    "index": {
        **{metric: "ms" for metric in ("build_time", "update_50_time", "index_write_time", "metadata_write_time")},
        **{metric: "ms" for metric in ("lake_read_time", "open_time", "query_mean", "query_p50", "query_p95")},
        **{metric: "ms" for metric in ("query_p99", "query_mean_t1", "query_mean_t2", "query_mean_t3")},
        **{metric: "count" for metric in ("index_terms", "index_postings", "query_results_total")},
        "disk_bytes": "bytes",
        "disk_bytes_allocated": "bytes",
        "file_count": "files",
        "dir_count": "dirs",
    },
    "metadata": {
        "insert_throughput": "rows_per_s",
        "bulk_insert_throughput": "rows_per_s",
        "query_author_mean": "ms",
        "lookup_title_mean": "ms",
        "lookup_id_mean": "ms",
        "disk_bytes": "bytes",
    },
    "download": {"http_throughput": "books_per_s"},
    "baseline": {},
}
ONLY_FOLDERS = {"file_count", "dir_count"}
NOT_IN_MONGO = {"disk_bytes_allocated"}


def row_errors(row: dict[str, str], language: str, experiment: str) -> list[str]:
    """Everything wrong with one row of the file of that language and experiment."""
    if row["language"] != language or row["experiment"] != experiment:
        return [f"row of {row['language']}/{row['experiment']} in the file of {language}/{experiment}"]
    structures, sizes = GRID[experiment]
    metric, unit, value = row["metric"], row["unit"], row["value"]
    expected_unit = "bytes" if metric == "peak_rss" else METRICS[experiment].get(metric)
    checks = [
        (row["structure"] in structures, f"structure {row['structure']!r}"),
        (row["n_books"].isdecimal() and int(row["n_books"]) in sizes, f"n_books {row['n_books']!r}"),
        (row["run"].isdecimal(), f"run {row['run']!r}"),
        (expected_unit is not None, f"metric {metric!r}"),
        (unit == expected_unit, f"unit {unit!r} for {metric}"),
        (VALUE_PATTERN.match(value) is not None, f"value {value!r} without six decimals"),
        (unit != "ok" or value in OK_VALUES, f"ok value {value!r}"),
        (
            metric not in ONLY_FOLDERS or experiment != "index" or row["structure"] == "folders",
            f"{metric} outside folders",
        ),
        (metric not in NOT_IN_MONGO or row["structure"] != "mongo", f"{metric} in mongo"),
    ]
    return [message for is_valid, message in checks if not is_valid]


def file_errors(path: Path) -> list[str]:
    """Errors of one results file, named {language}_{experiment}.csv (SPEC 11.8)."""
    language, _, experiment = path.stem.partition("_")
    if language not in LANGUAGES or experiment not in GRID:
        return [f"{path.name}: not a {{language}}_{{experiment}}.csv name"]
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != HEADER:
            return [f"{path.name}: header {reader.fieldnames}"]
        return [
            f"{path.name}:{line}: {error}"
            for line, row in enumerate(reader, start=2)
            for error in row_errors(row, language, experiment)
        ]


def main(results_dir: Path) -> int:
    paths = sorted(path for path in results_dir.glob("*.csv") if path.name not in NOT_RESULTS)
    errors = [error for path in paths for error in file_errors(path)]
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"{len(paths)} results files checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(Path(sys.argv[1])))
