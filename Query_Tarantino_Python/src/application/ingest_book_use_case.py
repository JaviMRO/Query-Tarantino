from dataclasses import dataclass

from src.domain.model import DownloadException, FailureReason, StoredPaths
from src.domain.ports import BookDownloader, ControlStateStore, DatalakeStorage


@dataclass(frozen=True, slots=True)
class BookDownloaded:
    book_id: int
    paths: StoredPaths


@dataclass(frozen=True, slots=True)
class DownloadFailed:
    book_id: int
    reason: FailureReason


IngestResult = BookDownloaded | DownloadFailed


class IngestBookUseCase:
    """
    Downloads a book and stores it in the datalake (SPEC 8.1 step 4).
    A failed download writes nothing to the datalake (SPEC 3.4), and a
    successful one is recorded only after it is stored (SPEC 8).
    """

    def __init__(self, downloader: BookDownloader, datalake: DatalakeStorage, control: ControlStateStore):
        self.downloader = downloader
        self.datalake = datalake
        self.control = control

    def execute(self, book_id: int) -> IngestResult:
        try:
            text = self.downloader.download(book_id)
        except DownloadException as error:
            self.control.record_failure(book_id, error.reason)
            return DownloadFailed(book_id, error.reason)

        paths = self.datalake.save(book_id, text)
        self.control.record_download(book_id)
        return BookDownloaded(book_id, paths)
