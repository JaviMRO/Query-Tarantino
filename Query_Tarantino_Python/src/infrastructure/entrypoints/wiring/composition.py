"""
Composition root: the only place that knows the concrete adapters. Every
connection and client is created once and registered in the caller's
ExitStack, which closes it when the command ends.
"""

import sqlite3
import time
from contextlib import ExitStack, closing

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


def build_ingest_use_case(settings: Settings, resources: ExitStack) -> IngestBookUseCase:
    """Download and storage of one book, with the configured downloader and datalake."""
    downloader = _build_downloader(settings, resources)
    return IngestBookUseCase(downloader, _build_datalake(settings), FileControlStateStore(settings.data_dir))


def build_index_use_case(settings: Settings, resources: ExitStack, stopwords: frozenset[str]) -> IndexBookUseCase:
    """Indexing of one book, with the configured datalake and index."""
    return IndexBookUseCase(
        _build_datalake(settings),
        SqliteMetadataAdapter(_open_metadata_database(settings, resources)),
        _build_index_writer(settings, resources),
        FileControlStateStore(settings.data_dir),
        stopwords,
    )


def build_search_use_case(settings: Settings, resources: ExitStack) -> SearchUseCase:
    """Opens the configured index and the metadata, read-only, for searches (SPEC 9)."""
    catalog = SqliteBookCatalog(open_metadata_database_read_only(settings, resources))
    return SearchUseCase(_build_postings_reader(settings, resources), catalog, load_stopwords(settings.shared_dir))


def _build_datalake(settings: Settings) -> DatalakeStorage:
    match settings.lake:
        case LakeLayout.TIME:
            return TimeBasedAdapter(settings.data_dir, utc_now)
        case LakeLayout.BOOK:
            return BookBasedAdapter(settings.data_dir)
        case LakeLayout.BATCH:
            return BatchBasedAdapter(settings.data_dir)


def _build_downloader(settings: Settings, resources: ExitStack) -> BookDownloader:
    match settings.downloader:
        case DownloaderKind.HTTP:
            session = resources.enter_context(requests.Session())
            return GutenbergHttpDownloader(
                session, GUTENBERG_BASE_URL, time.monotonic, time.sleep, MIN_SECONDS_BETWEEN_REQUESTS
            )
        case DownloaderKind.LOCAL:
            return LocalCorpusDownloader(settings.corpus_dir)


def _build_index_writer(settings: Settings, resources: ExitStack) -> InvertedIndexStorage:
    match settings.index:
        case IndexLayout.JSON:
            return MonolithicJsonAdapter(settings.data_dir)
        case IndexLayout.MONGO:
            return MongodbIndexAdapter(_open_postings_collection(settings, resources))
        case IndexLayout.FOLDERS:
            return HierarchicalFolderAdapter(settings.data_dir)


def _build_postings_reader(settings: Settings, resources: ExitStack) -> PostingsReader:
    match settings.index:
        case IndexLayout.JSON:
            return JsonPostingsReader(settings.data_dir)
        case IndexLayout.MONGO:
            return MongoPostingsReader(_open_postings_collection(settings, resources))
        case IndexLayout.FOLDERS:
            return FolderPostingsReader(settings.data_dir)


def _open_metadata_database(settings: Settings, resources: ExitStack) -> sqlite3.Connection:
    path = metadata_database_path(settings.data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    return resources.enter_context(closing(sqlite3.connect(path)))


def open_metadata_database_read_only(settings: Settings, resources: ExitStack) -> sqlite3.Connection:
    """Read-only metadata connection: never creates or modifies the database; fails if nothing was indexed yet."""
    uri = metadata_database_path(settings.data_dir).resolve().as_uri() + _READ_ONLY_QUERY
    return resources.enter_context(closing(sqlite3.connect(uri, uri=True)))


def _open_postings_collection(settings: Settings, resources: ExitStack) -> Collection[PostingDocument]:
    client: MongoClient[PostingDocument] = resources.enter_context(MongoClient(settings.mongo_url))
    return client[PIPELINE_DATABASE][POSTINGS_COLLECTION]
