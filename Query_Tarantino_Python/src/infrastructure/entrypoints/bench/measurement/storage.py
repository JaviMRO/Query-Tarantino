"""Space used by a structure, measured by the program itself (SPEC 11.5.1 step 2, 11.5.3 step 3)."""

from pathlib import Path

from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit
from src.infrastructure.file_writes import TMP_SUFFIX

DISK_BYTES = "disk_bytes"


def tree_storage(root: Path) -> list[Measurement]:
    """disk_bytes and file_count of the regular files under root, and dir_count below it, root excluded."""
    disk_bytes = file_count = dir_count = 0
    for entry in root.rglob("*"):
        if entry.is_dir():
            dir_count += 1
        elif entry.is_file():
            file_count += 1
            disk_bytes += entry.stat().st_size
    return [
        Measurement(DISK_BYTES, disk_bytes, Unit.BYTES),
        Measurement("file_count", file_count, Unit.FILES),
        Measurement("dir_count", dir_count, Unit.DIRS),
    ]


def file_storage(path: Path) -> list[Measurement]:
    """disk_bytes of a single file."""
    return [Measurement(DISK_BYTES, path.stat().st_size, Unit.BYTES)]


def has_tmp_files(root: Path) -> bool:
    """Whether a .tmp leftover of the safe write exists under root (SPEC 4.3)."""
    return any(root.rglob(f"*{TMP_SUFFIX}"))
