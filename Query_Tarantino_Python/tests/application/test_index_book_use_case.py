from datetime import datetime, timezone

from src.application.index_book_use_case import STATUS_INDEXED, STATUS_SKIPPED, IndexBookUseCase

ENGLISH_HEADER = "Title: Moby Dick\nLanguage: English"
SPANISH_HEADER = "Title: Don Quijote\nLanguage: Spanish"
FIXED_NOW = datetime(2026, 9, 24, 8, 5, 3, tzinfo=timezone.utc)


class FakeDatalake:
    def __init__(self, header: str, body: str):
        self.header, self.body = header, body

    def load(self, book_id):
        return self.header, self.body

    def get_paths(self, book_id):
        return f"lake/{book_id}.header.txt", f"lake/{book_id}.body.txt"


class Recorder:
    """Records every call, in order, across all the stores it plays."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args))


def build(header: str, body: str = "whale whale ship"):
    recorder = Recorder()
    use_case = IndexBookUseCase(
        datalake=FakeDatalake(header, body),
        metadata_store=recorder,
        index_store=recorder,
        control=recorder,
        stopwords=frozenset({"the"}),
        clock=lambda: FIXED_NOW,
    )
    return use_case, recorder


def test_english_book_is_indexed_in_spec_order():
    use_case, recorder = build(ENGLISH_HEADER)

    result = use_case.execute(2701)

    assert [call[0] for call in recorder.calls] == [
        "save", "write_book_terms", "update_indexed_at", "record_indexing",
    ]
    assert result == {"status": STATUS_INDEXED, "book_id": 2701, "language": "en", "terms_count": 2}


def test_metadata_is_saved_with_datalake_paths():
    use_case, recorder = build(ENGLISH_HEADER)

    use_case.execute(2701)

    _, book, header_path, body_path = recorder.calls[0]
    assert book.title == "Moby Dick"
    assert (header_path, body_path) == ("lake/2701.header.txt", "lake/2701.body.txt")


def test_indexed_at_uses_spec_format():
    use_case, recorder = build(ENGLISH_HEADER)

    use_case.execute(2701)

    assert ("update_indexed_at", 2701, "2026-09-24T08:05:03Z") in recorder.calls


def test_non_english_book_only_saves_metadata():
    use_case, recorder = build(SPANISH_HEADER)

    result = use_case.execute(2000)

    assert [call[0] for call in recorder.calls] == ["save", "record_indexing"]
    assert result == {"status": STATUS_SKIPPED, "book_id": 2000, "language": "es", "terms_count": 0}
