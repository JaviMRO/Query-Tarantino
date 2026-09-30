"""
Composition root: the only place that knows the concrete adapters. Every
connection and client is created once and registered in the caller's
ExitStack, which closes it when the command ends.
"""

import sqlite3
import time
from collections.abc import Callable
from contextlib import ExitStack, closing
from datetime import datetime
from pathlib import Path

import requests
from pymongo import MongoClient
from pymongo.collection import Collection

from src.application.use_cases.index_book_use_case import IndexBookUseCase, utc_now
from src.application.use_cases.ingest_book_use_case import IngestBookUseCase
from src.application.use_cases.search_use_case import SearchUseCase
from src.domain.ports import BookDownloader, DatalakeStorage, InvertedIndexStorage, PostingsReader
from src.infrastructure.control.file_control_state_store import FileControlStateStore
from src.infrastructure.datalake.layouts.batch_based_adapter import BatchBasedAdapter
from src.infrastructure.datalake.layouts.book_based_adapter import BookBasedAdapter
from src.infrastructure.datalake.layouts.time_based_adapter import TimeBasedAdapter
from src.infrastructure.downloader.gutenberg_http_downloader import (
    GUTENBERG_BASE_URL,
    MIN_SECONDS_BETWEEN_REQUESTS,
    GutenbergHttpDownloader,
)
from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader
from src.infrastructure.entrypoints.settings import DownloaderKind, IndexLayout, LakeLayout, Settings
from src.infrastructure.index.hierarchical_folder_adapter import FolderPostingsReader, HierarchicalFolderAdapter
from src.infrastructure.index.mongodb_index_adapter import (
    POSTINGS_COLLECTION,
    MongodbIndexAdapter,
    MongoPostingsReader,
    PostingDocument,
)
from src.infrastructure.index.monolithic_json_adapter import JsonPostingsReader, MonolithicJsonAdapter
from src.infrastructure.metadata.sqlite_metadata_adapter import (
    SqliteBookCatalog,
    SqliteMetadataAdapter,
    metadata_database_path,
)
from src.infrastructure.stopwords.file_stopwords_loader import load_stopwords

PIPELINE_DATABASE = "query_tarantino"

_READ_ONLY_QUERY = "?mode=ro"

PostingsOpener = Callable[[], Collection[PostingDocument]]


def build_ingest_use_case(settings: Settings, resources: ExitStack) -> IngestBookUseCase:
    """Download and storage of one book, with the configured downloader and datalake."""
    downloader = _build_downloader(settings, resources)
    datalake = build_datalake(settings.lake, settings.data_dir, utc_now)
    return IngestBookUseCase(downloader, datalake, FileControlStateStore(settings.data_dir))


def build_index_use_case(settings: Settings, resources: ExitStack, stopwords: frozenset[str]) -> IndexBookUseCase:
    """Indexing of one book, with the configured datalake and index."""
    return IndexBookUseCase(
        build_datalake(settings.lake, settings.data_dir, utc_now),
        SqliteMetadataAdapter(open_metadata_database(metadata_database_path(settings.data_dir), resources)),
        build_index_writer(settings.index, settings.data_dir, _pipeline_postings(settings, resources)),
        FileControlStateStore(settings.data_dir),
        stopwords,
    )


def build_search_use_case(settings: Settings, resources: ExitStack) -> SearchUseCase:
    """Opens the configured index and the metadata, read-only, for searches (SPEC 9)."""
    catalog = SqliteBookCatalog(open_metadata_database_read_only(settings, resources))
    reader = build_postings_reader(settings.index, settings.data_dir, _pipeline_postings(settings, resources))
    return SearchUseCase(reader, catalog, load_stopwords(settings.shared_dir))


def build_datalake(layout: LakeLayout, data_dir: Path, clock: Callable[[], datetime]) -> DatalakeStorage:
    """The datalake structure under data_dir; only the time layout uses the clock (SPEC 4.1)."""
    match layout:
        case LakeLayout.TIME:
            return TimeBasedAdapter(data_dir, clock)
        case LakeLayout.BOOK:
            return BookBasedAdapter(data_dir)
        case LakeLayout.BATCH:
            return BatchBasedAdapter(data_dir)


def build_index_writer(layout: IndexLayout, data_dir: Path, open_postings: PostingsOpener) -> InvertedIndexStorage:
    """The index structure under data_dir; the MongoDB collection is opened only when it is needed (SPEC 7)."""
    match layout:
        case IndexLayout.JSON:
            return MonolithicJsonAdapter(data_dir)
        case IndexLayout.MONGO:
            return MongodbIndexAdapter(open_postings())
        case IndexLayout.FOLDERS:
            return HierarchicalFolderAdapter(data_dir)


def build_postings_reader(layout: IndexLayout, data_dir: Path, open_postings: PostingsOpener) -> PostingsReader:
    """The read side of the index structure; opening it is what a search pays once (SPEC 9, 11.5.3)."""
    match layout:
        case IndexLayout.JSON:
            return JsonPostingsReader(data_dir)
        case IndexLayout.MONGO:
            return MongoPostingsReader(open_postings())
        case IndexLayout.FOLDERS:
            return FolderPostingsReader(data_dir)


def open_metadata_database(path: Path, resources: ExitStack) -> sqlite3.Connection:
    """Read-write metadata connection, closed with the caller's ExitStack; creates the file if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return resources.enter_context(closing(sqlite3.connect(path)))


def open_metadata_database_read_only(settings: Settings, resources: ExitStack) -> sqlite3.Connection:
    """Read-only metadata connection: never creates or modifies the database; fails if nothing was indexed yet."""
    uri = metadata_database_path(settings.data_dir).resolve().as_uri() + _READ_ONLY_QUERY
    return resources.enter_context(closing(sqlite3.connect(uri, uri=True)))


def open_mongo_client(mongo_url: str, resources: ExitStack) -> MongoClient[PostingDocument]:
    """One client per process, closed with the caller's ExitStack."""
    client: MongoClient[PostingDocument] = resources.enter_context(MongoClient(mongo_url))
    return client


def _build_downloader(settings: Settings, resources: ExitStack) -> BookDownloader:
    match settings.downloader:
        case DownloaderKind.HTTP:
            session = resources.enter_context(requests.Session())
            return GutenbergHttpDownloader(
                session, GUTENBERG_BASE_URL, time.monotonic, time.sleep, MIN_SECONDS_BETWEEN_REQUESTS
            )
        case DownloaderKind.LOCAL:
            return LocalCorpusDownloader(settings.corpus_dir)


def _pipeline_postings(settings: Settings, resources: ExitStack) -> PostingsOpener:
    return lambda: open_mongo_client(settings.mongo_url, resources)[PIPELINE_DATABASE][POSTINGS_COLLECTION]
