"""What the lake experiments read from each datalake structure besides its port (SPEC 11.5.1, 11.5.2)."""

from pathlib import Path

from src.domain.ports import DatalakeStorage
from src.infrastructure.data_layout import BATCH_LAKE_FOLDER, BOOK_LAKE_FOLDER, TIME_LAKE_FOLDER
from src.infrastructure.datalake.layouts.batch_based_adapter import stored_batch_book_ids
from src.infrastructure.datalake.layouts.book_based_adapter import stored_book_book_ids
from src.infrastructure.datalake.layouts.time_based_adapter import (
    count_stale_copies,
    hour_folder_of,
    stored_time_book_ids,
)
from src.infrastructure.entrypoints.settings import LakeLayout

WHOLE_LAKE = ""


def lake_root(layout: LakeLayout, data_dir: Path) -> Path:
    """datalake/, datalake_book/ or datalake_batch/ (SPEC 4.1)."""
    match layout:
        case LakeLayout.TIME:
            return data_dir / TIME_LAKE_FOLDER
        case LakeLayout.BOOK:
            return data_dir / BOOK_LAKE_FOLDER
        case LakeLayout.BATCH:
            return data_dir / BATCH_LAKE_FOLDER


def stored_book_ids(layout: LakeLayout, data_dir: Path, checkpoint: str) -> set[int]:
    """
    Complete books found by listing the lake. Only time can skip the hour folders before the checkpoint; book
    and batch do not record when a book was written, so they list the whole lake (SPEC 11.5.1 step 7).
    """
    match layout:
        case LakeLayout.TIME:
            return stored_time_book_ids(data_dir, checkpoint)
        case LakeLayout.BOOK:
            return stored_book_book_ids(data_dir)
        case LakeLayout.BATCH:
            return stored_batch_book_ids(data_dir)


def checkpoint_of(layout: LakeLayout, datalake: DatalakeStorage, book_id: int) -> str:
    """The hour folder of a book in time; the other structures have no checkpoint (SPEC 11.5.1 step 7)."""
    if layout is LakeLayout.TIME:
        return hour_folder_of(datalake.get_paths(book_id))
    return WHOLE_LAKE


def stale_copies(layout: LakeLayout, data_dir: Path) -> int:
    """Books with a complete copy in more than one place; only time can have them (SPEC 4.1, 11.5.2)."""
    if layout is LakeLayout.TIME:
        return count_stale_copies(data_dir)
    return 0
