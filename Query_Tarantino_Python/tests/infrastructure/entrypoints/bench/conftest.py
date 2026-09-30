import itertools
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.infrastructure.corpus.file_corpus_store import BENCHMARK_IDS_FILE, QUERIES_FILE
from src.infrastructure.entrypoints.bench.bench_area import BENCH_FOLDER, BenchContext, reset_bench_area
from src.infrastructure.entrypoints.bench.measurement.timing import NanoClock
from tests.conftest import SHARED_DIR

BOOK_COUNT = 100
BOOK_IDS = tuple(range(1, BOOK_COUNT + 1))
ONE_MILLISECOND_NS = 1_000_000
QUERIES = ("whale", "harbor ocean", "whale harbor lantern")
STOPWORDS_FILE = "stopwords_en.txt"


@dataclass(frozen=True, slots=True)
class Workspace:
    data_dir: Path
    corpus_dir: Path
    shared_dir: Path


def book_body(book_id: int) -> str:
    words = ["whale", "ocean"]
    if book_id % 2 == 0:
        words.append("harbor")
    if book_id % 3 == 0:
        words.append("lantern")
    return " ".join(words)


def corpus_text(book_id: int) -> str:
    return (
        f"Title: Book {book_id}\n"
        f"Author: Author {book_id % 5}\n"
        "Language: English\n"
        "\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
        f"{book_body(book_id)}\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK X ***\n"
    )


def millisecond_clock() -> NanoClock:
    ticks = itertools.count(0, ONE_MILLISECOND_NS)
    return lambda: next(ticks)


def bench_context(workspace: Workspace, book_ids: tuple[int, ...] = BOOK_IDS) -> BenchContext:
    bench_dir = workspace.data_dir / BENCH_FOLDER
    reset_bench_area(bench_dir)
    return BenchContext(bench_dir, workspace.corpus_dir, workspace.shared_dir, book_ids, millisecond_clock())


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for book_id in BOOK_IDS:
        (corpus_dir / f"{book_id}.txt").write_text(corpus_text(book_id), encoding="utf-8", newline="")
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    shutil.copyfile(SHARED_DIR / STOPWORDS_FILE, shared_dir / STOPWORDS_FILE)
    (shared_dir / BENCHMARK_IDS_FILE).write_text("".join(f"{book_id}\n" for book_id in BOOK_IDS), encoding="utf-8")
    (shared_dir / QUERIES_FILE).write_text("".join(f"{query}\n" for query in QUERIES), encoding="utf-8")
    return Workspace(tmp_path / "data", corpus_dir, shared_dir)
