"""
The commands of SPEC 10: each one builds what it needs, runs it and prints the
outcome. Returns the exit code; the lock is handled by the caller.
"""

import json
import random
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO

from src.application.control_pipeline import (
    ControlPipeline,
    DownloadNext,
    IndexNext,
    NextStep,
    NothingToDo,
    random_candidates,
)
from src.application.use_cases.index_book_use_case import BookIndexed, BookSkipped, IndexBookUseCase, IndexResult
from src.application.use_cases.ingest_book_use_case import (
    BookDownloaded,
    DownloadFailed,
    IngestBookUseCase,
    IngestResult,
)
from src.application.use_cases.search_use_case import SearchResult
from src.infrastructure.control.file_control_state_store import FileControlStateStore
from src.infrastructure.entrypoints.settings import Settings
from src.infrastructure.entrypoints.wiring.composition import (
    build_index_use_case,
    build_ingest_use_case,
    build_search_use_case,
)
from src.infrastructure.stopwords.file_stopwords_loader import load_stopwords

EXIT_OK = 0
EXIT_USAGE_ERROR = 1
EXIT_RUNTIME_ERROR = 2

_CANONICAL_SEPARATORS = (",", ":")
_DISPLAYED_SCORE_DECIMALS = 6


def download(settings: Settings, book_id: int) -> int:
    """Downloads and stores one book; a failed download is a runtime error."""
    with ExitStack() as resources:
        result = build_ingest_use_case(settings, resources).execute(book_id)
    print(_describe_ingest(result))
    return EXIT_OK if isinstance(result, BookDownloaded) else EXIT_RUNTIME_ERROR


def index(settings: Settings, book_id: int) -> int:
    """Indexes one book already stored in the datalake."""
    with ExitStack() as resources:
        use_case = build_index_use_case(settings, resources, load_stopwords(settings.shared_dir))
        print(_describe_index(use_case.execute(book_id)))
    return EXIT_OK


def run_steps(settings: Settings, steps: int, ids_path: Path | None) -> int:
    """Runs the control steps of SPEC 8.1 one after another; failed downloads are recorded, not fatal."""
    with ExitStack() as resources:
        pipeline = ControlPipeline(FileControlStateStore(settings.data_dir))
        ingest_use_case = build_ingest_use_case(settings, resources)
        index_use_case = build_index_use_case(settings, resources, load_stopwords(settings.shared_dir))
        rng = random.Random()
        for _ in range(steps):
            next_step = _next_step(pipeline, ids_path, rng)
            print(_run_step(next_step, ingest_use_case, index_use_case))
    return EXIT_OK


def search(settings: Settings, query: str, as_json: bool) -> int:
    """Prints the results of a query: canonical JSON on one line, or a human-readable list."""
    with ExitStack() as resources:
        results = build_search_use_case(settings, resources).execute(query)
    print(_json_output(query, results) if as_json else _human_output(query, results))
    return EXIT_OK


def _next_step(pipeline: ControlPipeline, ids_path: Path | None, rng: random.Random) -> NextStep:
    """With --ids the file is read lazily, in its order; without it, 10 random candidates (SPEC 8.1)."""
    if ids_path is None:
        return pipeline.next_book_to_process(random_candidates(rng))
    with ids_path.open(encoding="utf-8", newline="") as ids_file:
        return pipeline.next_book_to_process(_read_ids(ids_file))


def _read_ids(ids_file: TextIO) -> Iterator[int]:
    for line in ids_file:
        content = line.rstrip("\n")
        if content:
            yield int(content)


def _run_step(next_step: NextStep, ingest_use_case: IngestBookUseCase, index_use_case: IndexBookUseCase) -> str:
    match next_step:
        case IndexNext(book_id):
            return _describe_index(index_use_case.execute(book_id))
        case DownloadNext(book_id):
            return _describe_ingest(ingest_use_case.execute(book_id))
        case NothingToDo():
            return "Nothing to do: no book is pending indexing and no candidate is valid"


def _describe_ingest(result: IngestResult) -> str:
    match result:
        case BookDownloaded(book_id, paths):
            return f"Downloaded book {book_id} to {paths.header} and {paths.body}"
        case DownloadFailed(book_id, reason):
            return f"Download of book {book_id} failed: {reason.value}"


def _describe_index(result: IndexResult) -> str:
    match result:
        case BookIndexed(book_id, terms_count):
            return f"Indexed book {book_id}: {terms_count} terms"
        case BookSkipped(book_id, language):
            return f"Book {book_id} recorded in the metadata but not indexed: language {language!r}"


def _json_output(query: str, results: tuple[SearchResult, ...]) -> str:
    """One canonical line: sorted keys, no spaces, score rounded to 6 decimals (SPEC 10, 13.2)."""
    payload = {"query": query, "results": [_json_result(result) for result in results], "total": len(results)}
    return json.dumps(payload, separators=_CANONICAL_SEPARATORS, sort_keys=True, ensure_ascii=False)


def _json_result(result: SearchResult) -> dict[str, str | int | float]:
    return {
        "author": result.book.author,
        "book_id": result.book.book_id,
        "language": result.book.language,
        "score": round(result.score, _DISPLAYED_SCORE_DECIMALS),
        "title": result.book.title,
    }


def _human_output(query: str, results: tuple[SearchResult, ...]) -> str:
    lines = [f"{len(results)} results for {query!r}"]
    lines.extend(
        f"{result.score:.6f}  {result.book.book_id}  {result.book.title} / {result.book.author}" for result in results
    )
    return "\n".join(lines)
