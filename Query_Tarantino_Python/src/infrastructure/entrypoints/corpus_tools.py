"""
One-off tools that create the shared benchmark data (SPEC 1.1, 1.2), run once by one person:
python -m src.infrastructure.entrypoints.corpus_tools build-corpus | build-queries.
They are not part of the SPEC 10 command line, which is the same in the three languages.
"""

import argparse
import os
import random
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import ExitStack

import requests

from src.application.corpus.build_benchmark_corpus_use_case import BuildBenchmarkCorpusUseCase
from src.application.corpus.generate_queries_use_case import QUERY_SEED, GenerateQueriesUseCase
from src.infrastructure.corpus.file_corpus_store import (
    BENCHMARK_IDS_FILE,
    QUERIES_FILE,
    SAMPLE_DATASET_FOLDER,
    FileCorpusStore,
    copy_sample_dataset,
)
from src.infrastructure.downloader.gutenberg_http_downloader import (
    AUTOMATED_CLIENT_SECONDS_BETWEEN_REQUESTS,
    GUTENBERG_BASE_URL,
    GutenbergHttpDownloader,
)
from src.infrastructure.entrypoints.settings import SETTING_NAMES, Settings, option_flag, resolve_settings
from src.infrastructure.entrypoints.wiring.commands import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR
from src.infrastructure.entrypoints.wiring.composition import open_metadata_database_read_only
from src.infrastructure.file_writes import atomic_text_writer
from src.infrastructure.index.monolithic_json_adapter import JsonPostingsReader
from src.infrastructure.metadata.sqlite_metadata_adapter import SqliteBookCatalog

PROGRAM_NAME = "corpus_tools"
BENCHMARK_BOOK_COUNT = 1000


def main(argv: Sequence[str], environ: Mapping[str, str]) -> int:
    """Runs one tool and returns its exit code: 0 success, 1 usage error, 2 runtime error."""
    try:
        arguments = _build_parser().parse_args(argv)
        settings = resolve_settings(vars(arguments), environ)
    except SystemExit as parser_exit:
        return EXIT_OK if parser_exit.code == EXIT_OK else EXIT_USAGE_ERROR
    except ValueError as error:
        _print_error(str(error))
        return EXIT_USAGE_ERROR
    try:
        return build_corpus(settings) if arguments.tool == "build-corpus" else build_queries(settings)
    except Exception as error:
        _print_error(f"{type(error).__name__}: {error}")
        return EXIT_RUNTIME_ERROR


def build_corpus(settings: Settings) -> int:
    """
    Selects the first 1,000 valid English books from Gutenberg into corpus_dir and shared/book_ids_benchmark.txt,
    then copies the first 20 to shared/sample_dataset/. Waits 2 s between requests, as Gutenberg asks of robots.
    """
    with requests.Session() as session:
        source = GutenbergHttpDownloader(
            session, GUTENBERG_BASE_URL, time.monotonic, time.sleep, AUTOMATED_CLIENT_SECONDS_BETWEEN_REQUESTS
        )
        store = FileCorpusStore(settings.corpus_dir, settings.shared_dir / BENCHMARK_IDS_FILE)
        selected = BuildBenchmarkCorpusUseCase(source, store, BENCHMARK_BOOK_COUNT, _print_progress).execute()
    copy_sample_dataset(settings.corpus_dir, settings.shared_dir / SAMPLE_DATASET_FOLDER, selected)
    print(f"Selected {len(selected)} books; sample dataset copied to {settings.shared_dir / SAMPLE_DATASET_FOLDER}")
    return EXIT_OK


def build_queries(settings: Settings) -> int:
    """Writes shared/queries.txt from the json index of the data dir; refuses to overwrite it (SPEC 1.2)."""
    queries_path = settings.shared_dir / QUERIES_FILE
    if queries_path.exists():
        _print_error(f"{queries_path} already exists and is never regenerated (SPEC 1.2)")
        return EXIT_RUNTIME_ERROR
    with ExitStack() as resources:
        catalog = SqliteBookCatalog(open_metadata_database_read_only(settings, resources))
        queries = GenerateQueriesUseCase(JsonPostingsReader(settings.data_dir), catalog, random.Random(QUERY_SEED))
        lines = queries.execute()
    with atomic_text_writer(queries_path) as file:
        file.writelines(f"{line}\n" for line in lines)
    print(f"Wrote {len(lines)} queries to {queries_path}")
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME)
    for name in SETTING_NAMES:
        parser.add_argument(option_flag(name), dest=name, default=argparse.SUPPRESS)
    parser.add_argument("tool", choices=("build-corpus", "build-queries"))
    return parser


def _print_progress(book_id: int, is_selected: bool) -> None:
    print(f"{book_id}: {'selected' if is_selected else 'skipped'}", flush=True)


def _print_error(message: str) -> None:
    print(f"{PROGRAM_NAME}: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ))
