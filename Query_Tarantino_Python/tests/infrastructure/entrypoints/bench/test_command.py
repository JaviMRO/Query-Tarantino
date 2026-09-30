from pathlib import Path

import pytest

from src.infrastructure.entrypoints.cli import main
from tests.infrastructure.entrypoints.bench.conftest import Workspace

NO_ENVIRONMENT: dict[str, str] = {}
HEADER = "language,experiment,structure,n_books,metric,value,unit,run"


def bench(workspace: Workspace, out: Path, experiment: str, structure: str, n_books: int) -> int:
    arguments = ["bench", "--experiment", experiment, "--structure", structure, "--n", str(n_books), "--run", "1"]
    settings = ["--data-dir", str(workspace.data_dir), "--corpus-dir", str(workspace.corpus_dir)]
    return main([*arguments, "--out", str(out), *settings, "--shared-dir", str(workspace.shared_dir)], NO_ENVIRONMENT)


def test_a_valid_run_appends_its_rows_after_the_header(workspace: Workspace, tmp_path: Path) -> None:
    out = tmp_path / "python_datalake.csv"

    exit_code = bench(workspace, out, "datalake", "book", 100)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert exit_code == 0
    assert lines[0] == HEADER
    assert len(lines) == 9
    assert all(line.startswith("python,datalake,book,100,") and line.endswith(",1") for line in lines[1:])


def test_a_combination_outside_spec_11_1_is_a_usage_error(workspace: Workspace, tmp_path: Path) -> None:
    out = tmp_path / "out.csv"

    assert bench(workspace, out, "index", "time", 100) == 1
    assert not out.exists()


def test_a_list_shorter_than_n_is_an_invalid_run_without_rows(workspace: Workspace, tmp_path: Path) -> None:
    out = tmp_path / "out.csv"

    assert bench(workspace, out, "datalake", "book", 250) == 2
    assert not out.exists()


def test_baseline_writes_no_rows(workspace: Workspace, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "python_baseline.csv"

    assert bench(workspace, out, "baseline", "none", 0) == 0
    assert not out.exists()
    assert "no rows written" in capsys.readouterr().out


def test_metadata_needs_the_whole_list_of_1000_books(workspace: Workspace, tmp_path: Path) -> None:
    out = tmp_path / "python_metadata.csv"

    assert bench(workspace, out, "metadata", "sqlite", 1000) == 2
    assert not out.exists()


def test_bench_only_touches_the_bench_area(workspace: Workspace, tmp_path: Path) -> None:
    pipeline_file = workspace.data_dir / "control" / "downloaded_books.txt"
    pipeline_file.parent.mkdir(parents=True)
    pipeline_file.write_text("1342\n", encoding="utf-8")

    bench(workspace, tmp_path / "out.csv", "datalake", "time", 100)

    assert pipeline_file.read_text(encoding="utf-8") == "1342\n"
    assert not (workspace.data_dir / "control" / ".lock").exists()


def test_a_held_lock_stops_the_run(workspace: Workspace, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lock = workspace.data_dir / "control" / ".lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("4242\n2026-09-29T10:00:00Z\n", encoding="utf-8")

    exit_code = bench(workspace, tmp_path / "out.csv", "datalake", "book", 100)

    assert exit_code == 2
    assert "4242" in capsys.readouterr().err
    assert lock.exists()
