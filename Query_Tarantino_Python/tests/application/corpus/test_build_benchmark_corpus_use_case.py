from src.application.corpus.build_benchmark_corpus_use_case import BuildBenchmarkCorpusUseCase
from tests.application.fakes import CallLog, FakeCorpusStore, FakeRawTextSource


def gutenberg_text(language: str, body: str = "Call me Ishmael.") -> str:
    return (
        f"Title: Some book\nLanguage: {language}\n\n"
        f"*** START OF THE PROJECT GUTENBERG EBOOK X ***\n{body}\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\n"
    )


def build(
    texts: dict[int, str], target: int, store: FakeCorpusStore | None = None
) -> tuple[BuildBenchmarkCorpusUseCase, FakeRawTextSource, FakeCorpusStore, list[tuple[int, bool]]]:
    source = FakeRawTextSource(texts)
    corpus_store = store or FakeCorpusStore(CallLog())
    progress: list[tuple[int, bool]] = []
    use_case = BuildBenchmarkCorpusUseCase(source, corpus_store, target, lambda *step: progress.append(step))
    return use_case, source, corpus_store, progress


def test_keeps_valid_english_books_in_ascending_id_order_until_the_target() -> None:
    texts = {1: gutenberg_text("English"), 2: gutenberg_text("French"), 4: gutenberg_text("English"), 5: ""}
    texts[6] = gutenberg_text("English")
    use_case, source, store, _ = build(texts, target=2)

    selected = use_case.execute()

    assert selected == [1, 4]
    assert source.fetched == [1, 2, 3, 4]
    assert store.selected == [1, 4]


def test_invalid_downloads_are_skipped() -> None:
    texts = {1: "no markers", 2: gutenberg_text("English", body=" "), 3: gutenberg_text("English")}
    use_case, _, _, _ = build(texts, target=1)

    assert use_case.execute() == [3]


def test_the_whole_normalized_text_is_stored_before_the_id_is_recorded() -> None:
    log = CallLog()
    use_case, _, store, _ = build({1: gutenberg_text("English")}, target=1, store=FakeCorpusStore(log))

    use_case.execute()

    assert store.texts == {1: gutenberg_text("English")}
    assert log.calls == [("save_text", 1), ("record_selected", 1)]


def test_resumes_after_the_last_selected_book() -> None:
    store = FakeCorpusStore(CallLog(), selected=[1, 4])
    use_case, source, _, _ = build({7: gutenberg_text("English")}, target=3, store=store)

    assert use_case.execute() == [1, 4, 7]
    assert source.fetched == [5, 6, 7]


def test_does_nothing_when_the_target_is_already_reached() -> None:
    use_case, source, _, _ = build({}, target=2, store=FakeCorpusStore(CallLog(), selected=[1, 2]))

    assert use_case.execute() == [1, 2]
    assert source.fetched == []


def test_reports_every_checked_book() -> None:
    use_case, _, _, progress = build({2: gutenberg_text("English")}, target=1)

    use_case.execute()

    assert progress == [(1, False), (2, True)]
