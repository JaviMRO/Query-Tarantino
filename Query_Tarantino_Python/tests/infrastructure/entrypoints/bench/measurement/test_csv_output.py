from pathlib import Path

from src.infrastructure.entrypoints.bench.configuration import Configuration, Experiment
from src.infrastructure.entrypoints.bench.measurement.csv_output import append_measurements, format_value
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit

CONFIGURATION = Configuration(Experiment.DATALAKE, "book", 100, 2)


def test_the_header_is_written_once_and_each_run_appends_its_rows(tmp_path: Path) -> None:
    out = tmp_path / "results" / "python_datalake.csv"

    append_measurements(out, CONFIGURATION, [Measurement("write_throughput", 1000, Unit.BOOKS_PER_S)])
    append_measurements(out, CONFIGURATION, [Measurement("lookup_scan_mean", 0.0042131, Unit.MS)])

    assert out.read_bytes() == (
        b"language,experiment,structure,n_books,metric,value,unit,run\n"
        b"python,datalake,book,100,write_throughput,1000.000000,books_per_s,2\n"
        b"python,datalake,book,100,lookup_scan_mean,0.004213,ms,2\n"
    )


def test_a_run_without_measurements_creates_no_file(tmp_path: Path) -> None:
    out = tmp_path / "python_baseline.csv"

    append_measurements(out, CONFIGURATION, [])

    assert not out.exists()


def test_values_have_six_decimals_and_no_thousands_separator() -> None:
    assert format_value(1234567.5) == "1234567.500000"
