"""The experiments, structures and sizes that the bench command accepts (SPEC 10, 11.1)."""

from dataclasses import dataclass
from enum import Enum

NO_STRUCTURE = "none"

_LAKE_STRUCTURES = ("time", "book", "batch")
_INDEX_STRUCTURES = ("json", "mongo", "folders")
_METADATA_STRUCTURES = ("sqlite",)
_CORPUS_SIZES = (100, 250, 500, 1000)
_METADATA_SIZES = (1000, 10000, 50000)
_DOWNLOAD_SIZES = (50,)
_BASELINE_SIZES = (0,)


class Experiment(Enum):
    """What a run measures (SPEC 11.1)."""

    DATALAKE = "datalake"
    RECOVERY = "recovery"
    INDEX = "index"
    METADATA = "metadata"
    DOWNLOAD = "download"
    BASELINE = "baseline"


@dataclass(frozen=True, slots=True)
class _Grid:
    structures: tuple[str, ...]
    sizes: tuple[int, ...]


_GRIDS = {
    Experiment.DATALAKE: _Grid(_LAKE_STRUCTURES, _CORPUS_SIZES),
    Experiment.RECOVERY: _Grid(_LAKE_STRUCTURES, _CORPUS_SIZES),
    Experiment.INDEX: _Grid(_INDEX_STRUCTURES, _CORPUS_SIZES),
    Experiment.METADATA: _Grid(_METADATA_STRUCTURES, _METADATA_SIZES),
    Experiment.DOWNLOAD: _Grid((NO_STRUCTURE,), _DOWNLOAD_SIZES),
    Experiment.BASELINE: _Grid((NO_STRUCTURE,), _BASELINE_SIZES),
}


@dataclass(frozen=True, slots=True)
class Configuration:
    """One combination of experiment, structure and n_books, measured in round `run` (SPEC 11.1, 11.6)."""

    experiment: Experiment
    structure: str
    n_books: int
    run: int


def parse_configuration(experiment: str, structure: str, n_books: int, run: int) -> Configuration:
    """Raises ValueError for a combination outside the table of SPEC 11.1 or a negative run (a usage error)."""
    chosen = Experiment(experiment)
    grid = _GRIDS[chosen]
    if structure not in grid.structures:
        raise ValueError(f"Invalid --structure {structure!r} for {experiment}; allowed: {', '.join(grid.structures)}")
    if n_books not in grid.sizes:
        raise ValueError(f"Invalid --n {n_books} for {experiment}; allowed: {', '.join(map(str, grid.sizes))}")
    if run < 0:
        raise ValueError(f"Invalid --run {run}; it must be 0 or greater")
    return Configuration(chosen, structure, n_books, run)
