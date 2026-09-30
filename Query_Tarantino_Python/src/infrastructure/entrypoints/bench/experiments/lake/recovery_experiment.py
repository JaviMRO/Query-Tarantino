"""The recovery experiment: resuming after an interrupted run, in two scenarios (SPEC 11.5.2)."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import partial
from pathlib import Path

from src.application.use_cases.ingest_book_use_case import IngestBookUseCase
from src.domain.model import StoredPaths
from src.domain.ports import DatalakeStorage
from src.infrastructure.control.file_control_state_store import DOWNLOADED_FILE, FileControlStateStore
from src.infrastructure.data_layout import CONTROL_FOLDER
from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader
from src.infrastructure.entrypoints.bench.bench_area import BenchContext, check, ingest_books, reset_bench_area
from src.infrastructure.entrypoints.bench.experiments.lake.lake_scans import stale_copies
from src.infrastructure.entrypoints.bench.measurement.storage import has_tmp_files
from src.infrastructure.entrypoints.bench.measurement.timing import (
    BOOKS_PER_SIMULATED_HOUR,
    SIMULATED_CLOCK_START,
    Measurement,
    Unit,
    milliseconds,
    simulated_clock,
    timed,
)
from src.infrastructure.entrypoints.settings import LakeLayout
from src.infrastructure.entrypoints.wiring.composition import build_datalake
from src.infrastructure.file_writes import TMP_SUFFIX
from src.infrastructure.startup.tmp_cleanup import delete_tmp_leftovers


class Scenario(Enum):
    """Where the first run was interrupted (SPEC 11.5.2 phase 1)."""

    TMP_LEFTOVER = "tmp_leftover"
    DATA_WITHOUT_CONTROL = "data_without_control"


@dataclass(frozen=True, slots=True)
class _LakeProcess:
    """The adapters of one process: a restart creates new ones (SPEC 11.5.2 phase 2)."""

    datalake: DatalakeStorage
    control: FileControlStateStore
    ingest: IngestBookUseCase


def run_recovery(context: BenchContext, layout: LakeLayout) -> list[Measurement]:
    """Both scenarios, each from an empty bench area and in this order: six metrics (SPEC 11.5.2)."""
    return [measurement for scenario in Scenario for measurement in _run_scenario(context, layout, scenario)]


def restart_clock_start(interrupted_position: int) -> datetime:
    """One hour after the last hour used before the interruption (SPEC 11.5.2 phase 2, 14.9)."""
    return SIMULATED_CLOCK_START + timedelta(hours=interrupted_position // BOOKS_PER_SIMULATED_HOUR + 1)


def _run_scenario(context: BenchContext, layout: LakeLayout, scenario: Scenario) -> list[Measurement]:
    reset_bench_area(context.bench_dir)
    interrupted_position = len(context.book_ids) // 2
    _interrupt(context, layout, scenario, interrupted_position)
    restarted = _lake_process(context, layout, restart_clock_start(interrupted_position))
    recovery = timed(context.clock, partial(_recover, context, restarted))
    check(recovery.result == context.book_ids[interrupted_position], "the first book after the restart was not b")
    ingest_books(restarted.ingest, context.book_ids[interrupted_position + 1 :])
    return [
        Measurement(f"recovery_time_{scenario.value}", milliseconds(recovery.elapsed_ns), Unit.MS),
        Measurement(f"recovery_correct_{scenario.value}", float(_is_correct(context, restarted)), Unit.OK),
        Measurement(f"recovery_stale_copies_{scenario.value}", stale_copies(layout, context.bench_dir), Unit.COUNT),
    ]


def _lake_process(context: BenchContext, layout: LakeLayout, clock_start: datetime) -> _LakeProcess:
    datalake = build_datalake(layout, context.bench_dir, simulated_clock(clock_start))
    control = FileControlStateStore(context.bench_dir)
    return _LakeProcess(
        datalake, control, IngestBookUseCase(LocalCorpusDownloader(context.corpus_dir), datalake, control)
    )


def _interrupt(context: BenchContext, layout: LakeLayout, scenario: Scenario, interrupted_position: int) -> None:
    """Books before c are ingested; b is saved but never recorded in control (SPEC 11.5.2 phase 1)."""
    first_run = _lake_process(context, layout, SIMULATED_CLOCK_START)
    ingest_books(first_run.ingest, context.book_ids[:interrupted_position])
    book_id = context.book_ids[interrupted_position]
    text = LocalCorpusDownloader(context.corpus_dir).download(book_id)
    paths = first_run.datalake.save(book_id, text)
    if scenario is Scenario.TMP_LEFTOVER:
        _leave_half_written_header(context.bench_dir, paths, text.header)


def _leave_half_written_header(data_dir: Path, paths: StoredPaths, header: str) -> None:
    """Interrupted while writing the header: no final file, and the first floor(L / 2) bytes in the .tmp."""
    (data_dir / paths.header).unlink()
    (data_dir / paths.body).unlink()
    header_bytes = header.encode("utf-8")
    (data_dir / f"{paths.header}{TMP_SUFFIX}").write_bytes(header_bytes[: len(header_bytes) // 2])


def _recover(context: BenchContext, restarted: _LakeProcess) -> int:
    """The .tmp cleanup, then the first book of the list not yet downloaded is ingested (SPEC 11.5.2 phase 2)."""
    delete_tmp_leftovers(context.bench_dir)
    downloaded = restarted.control.get_downloaded_books()
    book_id = next(book_id for book_id in context.book_ids if book_id not in downloaded)
    restarted.ingest.execute(book_id)
    return book_id


def _is_correct(context: BenchContext, restarted: _LakeProcess) -> bool:
    """No .tmp left, each book downloaded exactly once and stored exactly as the corpus has it (SPEC 11.5.2)."""
    downloader = LocalCorpusDownloader(context.corpus_dir)
    return (
        not has_tmp_files(context.bench_dir)
        and _downloaded_lines(context.bench_dir) == Counter(context.book_ids)
        and all(restarted.datalake.load(book_id) == downloader.download(book_id) for book_id in context.book_ids)
    )


def _downloaded_lines(data_dir: Path) -> Counter[int]:
    """How many times each id appears in downloaded_books.txt, repeated lines included."""
    with (data_dir / CONTROL_FOLDER / DOWNLOADED_FILE).open(encoding="utf-8", newline="") as file:
        return Counter(int(line) for line in file if line.strip("\n"))
