from src.application.ingest_book_use_case import BookDownloaded, DownloadFailed, IngestBookUseCase
from src.domain.model import BookText, FailureReason
from tests.application.fakes import CallLog, FakeControlStateStore, FakeDatalake, FakeDownloader, paths_for

BOOK_ID = 2701
TEXT = BookText("Title: Moby Dick", "Call me Ishmael.")


def build(downloader: FakeDownloader, log: CallLog) -> IngestBookUseCase:
    return IngestBookUseCase(downloader, FakeDatalake(log), FakeControlStateStore(log))


def test_downloaded_book_is_stored_then_recorded() -> None:
    log = CallLog()

    result = build(FakeDownloader(TEXT), log).execute(BOOK_ID)

    assert log.calls == [("save_text", BOOK_ID, TEXT), ("record_download", BOOK_ID)]
    assert result == BookDownloaded(BOOK_ID, paths_for(BOOK_ID))


def test_failed_download_writes_nothing_and_records_reason() -> None:
    log = CallLog()

    result = build(FakeDownloader(failure=FailureReason.NO_MARKERS), log).execute(BOOK_ID)

    assert log.calls == [("record_failure", BOOK_ID, FailureReason.NO_MARKERS)]
    assert result == DownloadFailed(BOOK_ID, FailureReason.NO_MARKERS)
