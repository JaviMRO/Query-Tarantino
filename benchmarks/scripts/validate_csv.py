import csv
import math
import sys
from pathlib import Path


EXPECTED_HEADER = [
    "language",
    "experiment",
    "structure",
    "n_books",
    "metric",
    "value",
    "unit",
    "run",
]

VALID_LANGUAGES = {"java", "python", "cpp"}

VALID_EXPERIMENTS = {
    "datalake",
    "index",
    "download",
}

VALID_STRUCTURES = {
    "datalake": {
        "time",
        "book",
        "batch",
    },
    "index": {
        "json",
        "mongo",
        "folders",
    },
    "download": {
        "none",
    },
}

VALID_METRICS = {
    "datalake": {
        "write_throughput": "books_per_s",
        "lookup_scan_mean": "ms",
        "lookup_metadata_mean": "ms",
        "detect_new": "ms",
        "recovery_correct": "ok",
        "recovery_time": "ms",
        "disk_bytes": "bytes",
        "file_count": "files",
        "dir_count": "dirs",
        "peak_rss": "bytes",
    },
    "index": {
        "build_time": "ms",
        "query_mean": "ms",
        "query_p95": "ms",
        "update_50_time": "ms",
        "disk_bytes": "bytes",
        "peak_rss": "bytes",
    },
    "download": {
        "http_throughput": "books_per_s",
        "peak_rss": "bytes",
    },
}

VALID_N_BOOKS = {100, 250, 500, 1000}

# run=0 is warm-up.
# Only runs 1, 2 and 3 are official measurements.
VALID_RUNS = {1, 2, 3}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def validate_value(
    value: str,
    metric: str,
    line_number: int,
) -> None:
    if metric == "recovery_correct":
        if value not in {"0.0", "1.0"}:
            fail(
                f"line {line_number}: recovery_correct "
                f"must be 0.0 or 1.0, found '{value}'"
            )
        return

    try:
        numeric_value = float(value)
    except ValueError:
        fail(
            f"line {line_number}: value must be numeric, "
            f"found '{value}'"
        )

    if not math.isfinite(numeric_value):
        fail(
            f"line {line_number}: value must be finite, "
            f"found '{value}'"
        )

    if "." not in value:
        fail(
            f"line {line_number}: value must contain "
            f"a decimal point, found '{value}'"
        )


def validate_file(path: Path) -> None:
    if not path.exists():
        fail(f"file does not exist: {path}")

    if not path.is_file():
        fail(f"not a file: {path}")

    seen_rows = set()
    row_count = 0
    languages = set()
    experiments = set()

    try:
        with path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:

            reader = csv.reader(file)

            try:
                header = next(reader)
            except StopIteration:
                fail("CSV is empty")

            if header != EXPECTED_HEADER:
                fail(
                    "invalid CSV header\n"
                    f"expected: {EXPECTED_HEADER}\n"
                    f"found:    {header}"
                )

            for line_number, row in enumerate(reader, start=2):

                row_count += 1

                if len(row) != len(EXPECTED_HEADER):
                    fail(
                        f"line {line_number}: expected "
                        f"{len(EXPECTED_HEADER)} columns, "
                        f"found {len(row)}"
                    )

                (
                    language,
                    experiment,
                    structure,
                    n_books_text,
                    metric,
                    value,
                    unit,
                    run_text,
                ) = row

                if language not in VALID_LANGUAGES:
                    fail(
                        f"line {line_number}: invalid language "
                        f"'{language}'"
                    )

                if experiment not in VALID_EXPERIMENTS:
                    fail(
                        f"line {line_number}: invalid experiment "
                        f"'{experiment}'"
                    )

                languages.add(language)
                experiments.add(experiment)

                if structure not in VALID_STRUCTURES[experiment]:
                    fail(
                        f"line {line_number}: invalid "
                        f"{experiment} structure "
                        f"'{structure}'"
                    )

                metric_units = VALID_METRICS[experiment]

                if metric not in metric_units:
                    fail(
                        f"line {line_number}: invalid metric "
                        f"'{metric}' for experiment "
                        f"'{experiment}'"
                    )

                expected_unit = metric_units[metric]

                if unit != expected_unit:
                    fail(
                        f"line {line_number}: metric '{metric}' "
                        f"requires unit '{expected_unit}', "
                        f"found '{unit}'"
                    )

                try:
                    n_books = int(n_books_text)
                except ValueError:
                    fail(
                        f"line {line_number}: n_books "
                        f"must be an integer"
                    )

                if n_books not in VALID_N_BOOKS:
                    fail(
                        f"line {line_number}: invalid n_books "
                        f"'{n_books}'"
                    )

                validate_value(
                    value,
                    metric,
                    line_number,
                )

                try:
                    run = int(run_text)
                except ValueError:
                    fail(
                        f"line {line_number}: run must be "
                        f"an integer"
                    )

                if run not in VALID_RUNS:
                    fail(
                        f"line {line_number}: official results "
                        f"must use run 1, 2 or 3; found '{run}'"
                    )

                row_key = (
                    language,
                    experiment,
                    structure,
                    n_books,
                    metric,
                    run,
                )

                if row_key in seen_rows:
                    fail(
                        f"line {line_number}: duplicate result "
                        f"for {row_key}"
                    )

                seen_rows.add(row_key)

            if row_count == 0:
                fail("CSV contains only the header")

    except UnicodeDecodeError as exc:
        fail(f"file is not valid UTF-8: {exc}")

    if len(languages) != 1:
        fail(
            "CSV must contain exactly one language, "
            f"found: {sorted(languages)}"
        )

    if len(experiments) != 1:
        fail(
            "CSV must contain exactly one experiment, "
            f"found: {sorted(experiments)}"
        )

    language = next(iter(languages))
    experiment = next(iter(experiments))

    expected_rows = (
        len(VALID_STRUCTURES[experiment])
        * len(VALID_N_BOOKS)
        * len(VALID_RUNS)
        * len(VALID_METRICS[experiment])
    )

    if row_count != expected_rows:
        fail(
            f"invalid number of result rows: "
            f"expected {expected_rows}, "
            f"found {row_count}"
        )

    for structure in VALID_STRUCTURES[experiment]:
        for n_books in VALID_N_BOOKS:
            for run in VALID_RUNS:
                for metric in VALID_METRICS[experiment]:

                    key = (
                        language,
                        experiment,
                        structure,
                        n_books,
                        metric,
                        run,
                    )

                    if key not in seen_rows:
                        fail(
                            "missing result for "
                            f"language={language}, "
                            f"experiment={experiment}, "
                            f"structure={structure}, "
                            f"n_books={n_books}, "
                            f"metric={metric}, "
                            f"run={run}"
                        )

    print(
        f"OK: {path} "
        f"({row_count} result rows)"
    )


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python validate_csv.py <csv_file>",
            file=sys.stderr,
        )
        sys.exit(1)

    validate_file(Path(sys.argv[1]))


if __name__ == "__main__":
    main()