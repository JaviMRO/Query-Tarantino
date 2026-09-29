"""
The control/.lock file that keeps a second writing process out of the same
TARANTINO_DATA_DIR (SPEC 13.1). It holds the owner's PID and start time in UTC.
"""

from datetime import datetime
from pathlib import Path

from src.infrastructure.data_layout import CONTROL_FOLDER

LOCK_FILE = ".lock"

_STARTED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def lock_path(data_dir: Path) -> Path:
    """Location of the lock: control/.lock."""
    return data_dir / CONTROL_FOLDER / LOCK_FILE


def acquire_lock(path: Path, pid: int, started_at: datetime) -> None:
    """Creates the lock in exclusive mode; raises FileExistsError, touching nothing, if it already exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as file:
        file.write(f"{pid}\n{started_at:{_STARTED_AT_FORMAT}}\n")


def read_lock_owner(path: Path) -> str:
    """PID written in an existing lock, to tell the user which process holds it."""
    with path.open(encoding="utf-8", newline="") as file:
        return file.readline().rstrip("\n")


def release_lock(path: Path) -> None:
    """Deletes the lock; only called by the process that acquired it."""
    path.unlink()
