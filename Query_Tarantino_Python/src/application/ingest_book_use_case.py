from typing import Dict, Any
from src.domain.ports import BookDownloader, DatalakeStorage, ControlStateStore
from src.domain.model import DownloadException

class IngestBookUseCase:
    def __init__(
        self,
        downloader: BookDownloader,
        datalake: DatalakeStorage,
        control: ControlStateStore
    ):
        self.downloader = downloader
        self.datalake = datalake
        self.control = control

    def execute(self, book_id: int) -> Dict[str, Any]:
        """
        Orchestrates the download and datalake storage for a given book.
        Returns structured data about the operation's outcome.
        """
        try:
            header_text, body_text = self.downloader.download(book_id)
            header_path, body_path = self.datalake.save(book_id, header_text, body_text)

            self.control.record_download(book_id)

            return {
                "status": "SUCCESS",
                "book_id": book_id,
                "paths": {
                    "header": header_path,
                    "body": body_path
                }
            }

        except DownloadException as e:
            self.control.record_failure(book_id, e.reason.value)
            return {
                "status": "FAILED",
                "book_id": book_id,
                "reason": e.reason.value
            }
