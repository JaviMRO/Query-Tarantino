"""
Selection of the benchmark corpus (SPEC 1.1): Gutenberg ids are traversed in
ascending order and a book is kept if its download is valid and its language
is en, until the target is reached. Resumable: it continues after the last
selected id.
"""

from collections.abc import Callable

from src.application.control_pipeline import MAX_GUTENBERG_ID
from src.domain.model import DownloadException
from src.domain.ports import CorpusStore, RawTextSource
from src.domain.text_processing.gutenberg_text import split_header_body
from src.domain.text_processing.header_parser import parse_header

FIRST_GUTENBERG_ID = 1


class BuildBenchmarkCorpusUseCase:
    """
    Stores the normalized text of each selected book before recording it (SPEC 3.6, 8), so an interruption
    never lists a book whose text is missing. report_progress receives each checked id and whether it was kept.
    """

    def __init__(
        self,
        source: RawTextSource,
        store: CorpusStore,
        target_count: int,
        report_progress: Callable[[int, bool], None],
    ) -> None:
        self._source = source
        self._store = store
        self._target_count = target_count
        self._report_progress = report_progress

    def execute(self) -> list[int]:
        """Selected ids in ascending order; raises ValueError if the Gutenberg ids run out first."""
        selected = self._store.get_selected_books()
        book_id = selected[-1] + 1 if selected else FIRST_GUTENBERG_ID
        while len(selected) < self._target_count:
            if book_id > MAX_GUTENBERG_ID:
                raise ValueError(f"Only {len(selected)} valid English books up to id {MAX_GUTENBERG_ID}")
            is_selected = self._select_if_valid(book_id)
            if is_selected:
                selected.append(book_id)
            self._report_progress(book_id, is_selected)
            book_id += 1
        return selected

    def _select_if_valid(self, book_id: int) -> bool:
        """Valid download (SPEC 3) and English according to the header (SPEC 5)."""
        try:
            text = self._source.fetch_text(book_id)
            header = split_header_body(text).header
        except DownloadException:
            return False
        if not parse_header(book_id, header).is_indexable():
            return False
        self._store.save_text(book_id, text)
        self._store.record_selected(book_id)
        return True
