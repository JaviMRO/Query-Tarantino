from typing import Dict, Any, Optional
from ..domain.ports import ControlStateStore


class ControlPipeline:
    def __init__(self, control_store: ControlStateStore):
        self.control_store = control_store

    def next_book_to_process(self, candidates: list[int]) -> Dict[str, Any]:
        """
        Determines the next book to process based on the control state.
        Returns structured data indicating whether to 'INDEX' or 'DOWNLOAD'.
        """
        downloaded = self.control_store.get_downloaded_books()
        indexed = self.control_store.get_indexed_books()

        # 1. Prioritize books that are downloaded but not yet indexed
        pending_to_index = downloaded - indexed
        if pending_to_index:
            book_to_index = min(pending_to_index)
            return {
                "action": "INDEX",
                "book_id": book_to_index
            }

        # 2. If nothing to index, find a valid candidate to download
        failures = self.control_store.get_failure_counts()

        for candidate_id in candidates:
            if candidate_id not in downloaded and failures.get(candidate_id, 0) < 3:
                return {
                    "action": "DOWNLOAD",
                    "book_id": candidate_id
                }

        # 3. No action available
        return {
            "action": "NONE",
            "book_id": None
        }