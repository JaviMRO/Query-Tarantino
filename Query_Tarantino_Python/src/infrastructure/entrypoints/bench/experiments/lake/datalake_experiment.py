"""The datalake experiment: writing, storage, lookups and incremental detection (SPEC 11.5.1)."""

import sqlite3
from contextlib import ExitStack
from functools import partial
from pathlib import Path

from src.application.use_cases.ingest_book_use_case import IngestBookUseCase
from src.domain.ports import DatalakeStorage, MetadataStorage
from src.domain.text_processing.header_parser import parse_header
from src.infrastructure.control.file_control_state_store import FileControlStateStore
from src.infrastructure.datalake.book_files import has_book_files
from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader
from src.infrastructure.entrypoints.bench.bench_area import NEW_BOOKS, BenchContext, check, ingest_books
from src.infrastructure.entrypoints.bench.experiments.bench_sql import SELECT_PATHS_BY_ID
from src.infrastructure.entrypoints.bench.experiments.lake.lake_scans import (
    WHOLE_LAKE,
    checkpoint_of,
    lake_root,
    stored_book_ids,
)
from src.infrastructure.entrypoints.bench.measurement.storage import has_tmp_files, tree_storage
from src.infrastructure.entrypoints.bench.measurement.timing import (
    SIMULATED_CLOCK_START,
    Measurement,
    Unit,
    per_second,
    sample_positions,
    simulated_clock,
    timed,
    warm_mean,
)
from src.infrastructure.entrypoints.settings import LakeLayout
from src.infrastructure.entrypoints.wiring.composition import build_datalake, open_metadata_database
from src.infrastructure.metadata.sqlite_metadata_adapter import SqliteMetadataAdapter, metadata_database_path

LOOKUP_PASSES = 20
DETECT_REPETITIONS = 20


def run_datalake(context: BenchContext, layout: LakeLayout) -> list[Measurement]:
    """Runs the seven steps of SPEC 11.5.1 in order; raises BenchValidityError if a check of SPEC 11.7 fails."""
    datalake = build_datalake(layout, context.bench_dir, simulated_clock(SIMULATED_CLOCK_START))
    control = FileControlStateStore(context.bench_dir)
    write_throughput = _write_throughput(context, datalake, control)
    storage = tree_storage(lake_root(layout, context.bench_dir))
    _check_lake_holds_the_books(context, layout)
    sample = [context.book_ids[position] for position in sample_positions(len(context.book_ids))]
    lookups = [_lookup_scan_mean(context, datalake, sample), _lookup_metadata_mean(context, datalake, sample)]
    for book_id in context.book_ids[:-NEW_BOOKS]:
        control.record_indexing(book_id)
    detections = [_detect_new_control(context, control), _detect_new_scan(context, layout, datalake, control)]
    return [write_throughput, *storage, *lookups, *detections]


def _write_throughput(context: BenchContext, datalake: DatalakeStorage, control: FileControlStateStore) -> Measurement:
    ingest = IngestBookUseCase(LocalCorpusDownloader(context.corpus_dir), datalake, control)
    elapsed_ns = timed(context.clock, partial(ingest_books, ingest, context.book_ids)).elapsed_ns
    return Measurement("write_throughput", per_second(len(context.book_ids), elapsed_ns), Unit.BOOKS_PER_S)


def _check_lake_holds_the_books(context: BenchContext, layout: LakeLayout) -> None:
    stored = stored_book_ids(layout, context.bench_dir, WHOLE_LAKE)
    check(stored == set(context.book_ids), f"the lake holds {len(stored)} complete books, not the N expected")
    check(not has_tmp_files(lake_root(layout, context.bench_dir)), "the lake holds .tmp files")


def _lookup_scan_mean(context: BenchContext, datalake: DatalakeStorage, sample: list[int]) -> Measurement:
    """get_paths of the structure, then both files checked; neither control nor SQLite (SPEC 11.5.1 step 3)."""
    lookup_pass = partial(_count_found_by_structure, context.bench_dir, datalake, sample)
    measured = warm_mean(context.clock, lookup_pass, LOOKUP_PASSES, LOOKUP_PASSES * len(sample))
    check(all(found == len(sample) for found in measured.results), "a structure lookup did not find both files")
    return Measurement("lookup_scan_mean", measured.mean_ms, Unit.MS)


def _count_found_by_structure(data_dir: Path, datalake: DatalakeStorage, sample: list[int]) -> int:
    return sum(has_book_files(data_dir, datalake.get_paths(book_id)) for book_id in sample)


def _lookup_metadata_mean(context: BenchContext, datalake: DatalakeStorage, sample: list[int]) -> Measurement:
    """The paths come from SQLite, filled beforehand from the lake (SPEC 11.5.1 step 4)."""
    with ExitStack() as resources:
        connection = open_metadata_database(metadata_database_path(context.bench_dir), resources)
        _save_metadata(context.book_ids, datalake, SqliteMetadataAdapter(connection))
        lookup_pass = partial(_count_found_by_metadata, context.bench_dir, connection, sample)
        measured = warm_mean(context.clock, lookup_pass, LOOKUP_PASSES, LOOKUP_PASSES * len(sample))
    check(all(found == len(sample) for found in measured.results), "a metadata lookup did not find both files")
    return Measurement("lookup_metadata_mean", measured.mean_ms, Unit.MS)


def _save_metadata(book_ids: tuple[int, ...], datalake: DatalakeStorage, metadata: MetadataStorage) -> None:
    for book_id in book_ids:
        metadata.save(parse_header(book_id, datalake.load(book_id).header), datalake.get_paths(book_id))


def _count_found_by_metadata(data_dir: Path, connection: sqlite3.Connection, sample: list[int]) -> int:
    found = 0
    for book_id in sample:
        header_path, body_path = connection.execute(SELECT_PATHS_BY_ID, (book_id,)).fetchone()
        found += (data_dir / header_path).is_file() and (data_dir / body_path).is_file()
    return found


def _detect_new_control(context: BenchContext, control: FileControlStateStore) -> Measurement:
    """Downloaded minus indexed, read from the control files (SPEC 11.5.1 step 6)."""
    detection = partial(_pending_by_control, control)
    measured = warm_mean(context.clock, detection, DETECT_REPETITIONS, DETECT_REPETITIONS)
    check(_all_return_the_new_books(context, measured.results), "detect_new_control did not return the last 50 books")
    return Measurement("detect_new_control", measured.mean_ms, Unit.MS)


def _pending_by_control(control: FileControlStateStore) -> set[int]:
    return control.get_downloaded_books() - control.get_indexed_books()


def _detect_new_scan(
    context: BenchContext, layout: LakeLayout, datalake: DatalakeStorage, control: FileControlStateStore
) -> Measurement:
    """The lake listed from the checkpoint minus the indexed set, read once before timing (SPEC 11.5.1 step 7)."""
    indexed = control.get_indexed_books()
    checkpoint = checkpoint_of(layout, datalake, context.book_ids[-NEW_BOOKS - 1])
    detection = partial(_pending_by_scan, layout, context.bench_dir, checkpoint, indexed)
    measured = warm_mean(context.clock, detection, DETECT_REPETITIONS, DETECT_REPETITIONS)
    check(_all_return_the_new_books(context, measured.results), "detect_new_scan did not return the last 50 books")
    return Measurement("detect_new_scan", measured.mean_ms, Unit.MS)


def _all_return_the_new_books(context: BenchContext, detections: list[set[int]]) -> bool:
    """Every measured detection returned exactly the last 50 books of the configuration (SPEC 11.7)."""
    new_books = set(context.book_ids[-NEW_BOOKS:])
    return all(detected == new_books for detected in detections)


def _pending_by_scan(layout: LakeLayout, data_dir: Path, checkpoint: str, indexed: set[int]) -> set[int]:
    return stored_book_ids(layout, data_dir, checkpoint) - indexed
