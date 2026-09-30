from src.infrastructure.downloader.local_corpus_downloader import LocalCorpusDownloader
from src.infrastructure.entrypoints.bench.experiments.download_experiment import run_download
from src.infrastructure.entrypoints.bench.measurement.timing import Measurement, Unit
from tests.infrastructure.entrypoints.bench.conftest import Workspace, bench_context


def test_throughput_is_the_books_divided_by_the_elapsed_seconds(workspace: Workspace) -> None:
    context = bench_context(workspace, tuple(range(1, 51)))

    measurements = run_download(context, LocalCorpusDownloader(workspace.corpus_dir))

    assert measurements == [Measurement("http_throughput", 50_000.0, Unit.BOOKS_PER_S)]
    assert (context.bench_dir / "datalake_book" / "50" / "body.txt").is_file()
