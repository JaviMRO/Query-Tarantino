from pathlib import Path

from src.infrastructure.entrypoints.corpus_tools import main

NO_ENVIRONMENT: dict[str, str] = {}


def test_build_queries_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    queries = tmp_path / "shared" / "queries.txt"
    queries.parent.mkdir()
    queries.write_text("car\n", encoding="utf-8")

    exit_code = main(
        ["--shared-dir", str(tmp_path / "shared"), "--data-dir", str(tmp_path), "build-queries"], NO_ENVIRONMENT
    )

    assert exit_code == 2
    assert queries.read_text(encoding="utf-8") == "car\n"


def test_build_queries_without_an_index_is_a_runtime_error(tmp_path: Path) -> None:
    exit_code = main(
        ["--shared-dir", str(tmp_path), "--data-dir", str(tmp_path / "data"), "build-queries"], NO_ENVIRONMENT
    )

    assert exit_code == 2
    assert not (tmp_path / "queries.txt").exists()


def test_an_unknown_tool_is_a_usage_error() -> None:
    assert main(["build-everything"], NO_ENVIRONMENT) == 1
