"""Deletes the .tmp leftovers of an interrupted run, right after acquiring the lock (SPEC 4.3, 13.1)."""

from pathlib import Path

from src.infrastructure.data_layout import TMP_CLEANUP_FOLDERS
from src.infrastructure.file_writes import TMP_SUFFIX


def delete_tmp_leftovers(data_dir: Path) -> None:
    """Deletes every .tmp file under datalake/, datalake_book/, datalake_batch/ and datamarts/."""
    for folder in TMP_CLEANUP_FOLDERS:
        for leftover in _tmp_files_under(data_dir / folder):
            leftover.unlink()


def _tmp_files_under(folder: Path) -> list[Path]:
    """Collected before deleting, so the tree is not modified while it is being walked."""
    if not folder.is_dir():
        return []
    return [path for path in folder.rglob(f"*{TMP_SUFFIX}") if path.is_file()]
