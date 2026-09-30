"""Rows of a run in the exact CSV format of SPEC 11.8."""

from pathlib import Path

from src.infrastructure.entrypoints.bench.configuration import Configuration
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement

CSV_HEADER = "language,experiment,structure,n_books,metric,value,unit,run"
LANGUAGE = "python"

_FIELD_SEPARATOR = ","


def append_measurements(out: Path, configuration: Configuration, measurements: list[Measurement]) -> None:
    """Appends one row per measurement, writing the header only if the file does not exist yet (SPEC 11.2)."""
    if not measurements:
        return
    is_new_file = not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8", newline="") as file:
        if is_new_file:
            file.write(CSV_HEADER + "\n")
        file.writelines(_row(configuration, measurement) + "\n" for measurement in measurements)


def format_value(value: float) -> str:
    """Six decimals, a decimal point and no thousands separator, independent of the locale (SPEC 11.8)."""
    return f"{value:.6f}"


def _row(configuration: Configuration, measurement: Measurement) -> str:
    fields = (
        LANGUAGE,
        configuration.experiment.value,
        configuration.structure,
        str(configuration.n_books),
        measurement.metric,
        format_value(measurement.value),
        measurement.unit.value,
        str(configuration.run),
    )
    return _FIELD_SEPARATOR.join(fields)
