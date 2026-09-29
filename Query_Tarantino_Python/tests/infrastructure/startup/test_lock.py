from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.infrastructure.startup.lock import acquire_lock, lock_path, read_lock_owner, release_lock

STARTED_AT = datetime(2026, 9, 28, 10, 15, 30, tzinfo=timezone.utc)


def test_the_lock_lives_in_the_control_folder(tmp_path: Path) -> None:
    assert lock_path(tmp_path) == tmp_path / "control" / ".lock"


def test_acquire_writes_the_pid_and_the_utc_start_time(tmp_path: Path) -> None:
    lock = lock_path(tmp_path)

    acquire_lock(lock, 1234, STARTED_AT)

    assert lock.read_bytes() == b"1234\n2026-09-28T10:15:30Z\n"
    assert read_lock_owner(lock) == "1234"


def test_acquire_fails_without_touching_an_existing_lock(tmp_path: Path) -> None:
    lock = lock_path(tmp_path)
    acquire_lock(lock, 1234, STARTED_AT)

    with pytest.raises(FileExistsError):
        acquire_lock(lock, 5678, STARTED_AT)

    assert read_lock_owner(lock) == "1234"


def test_release_deletes_the_lock(tmp_path: Path) -> None:
    lock = lock_path(tmp_path)
    acquire_lock(lock, 1234, STARTED_AT)

    release_lock(lock)

    assert not lock.exists()
