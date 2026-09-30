from pathlib import Path

import pytest

from src.infrastructure.entrypoints.cli import main
from tests.conftest import SHARED_DIR

SPEC_14_3_BODIES = {1: "the car is nice", 2: "that car is mine", 3: "the car is the best"}
SPEC_14_3_INDEX = b'{"best":{"3":1},"car":{"1":1,"2":1,"3":1},"mine":{"2":1},"nice":{"1":1}}\n'
NO_ENVIRONMENT: dict[str, str] = {}


def corpus_text(book_id: int, body: str) -> str:
    return (
        f"Title: Book {book_id}\n"
        "Author: Jane Doe\n"
        "Language: English\n"
        "\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
        f"{body}\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK X ***\n"
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for book_id, body in SPEC_14_3_BODIES.items():
        (corpus_dir / f"{book_id}.txt").write_text(corpus_text(book_id, body), encoding="utf-8", newline="")
    (tmp_path / "ids.txt").write_text("1\n2\n3\n", encoding="utf-8", newline="")
    return tmp_path


def settings(workspace: Path, index: str = "json", lake: str = "book") -> list[str]:
    return [
        "--data-dir",
        str(workspace / "data"),
        "--shared-dir",
        str(SHARED_DIR),
        "--downloader",
        "local",
        "--corpus-dir",
        str(workspace / "corpus"),
        "--lake",
        lake,
        "--index",
        index,
    ]


def run_pipeline(workspace: Path, index: str = "json", lake: str = "book") -> int:
    ids = str(workspace / "ids.txt")
    return main(["run", "--steps", "6", "--ids", ids, *settings(workspace, index, lake)], NO_ENVIRONMENT)


def create_lock(workspace: Path) -> Path:
    lock = workspace / "data" / "control" / ".lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("4242\n2026-09-28T10:00:00Z\n", encoding="utf-8")
    return lock


@pytest.mark.parametrize("lake", ["time", "book", "batch"])
def test_running_the_pipeline_builds_the_spec_14_3_json_index(workspace: Path, lake: str) -> None:
    assert run_pipeline(workspace, lake=lake) == 0

    assert (workspace / "data/datamarts/inverted_index.json").read_bytes() == SPEC_14_3_INDEX


@pytest.mark.parametrize("index", ["json", "folders"])
def test_search_json_prints_one_canonical_line(workspace: Path, index: str, capsys: pytest.CaptureFixture[str]) -> None:
    run_pipeline(workspace, index=index)
    capsys.readouterr()

    exit_code = main(["search", "car best", "--json", *settings(workspace, index)], NO_ENVIRONMENT)

    assert exit_code == 0
    assert capsys.readouterr().out == (
        '{"query":"car best","results":[{"author":"Jane Doe","book_id":3,"language":"en",'
        '"score":2.079442,"title":"Book 3"}],"total":1}\n'
    )


def test_search_json_orders_ties_by_book_id(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_pipeline(workspace)
    capsys.readouterr()

    main(["search", "car", "--json", *settings(workspace)], NO_ENVIRONMENT)

    output = capsys.readouterr().out
    assert output.index('"book_id":1') < output.index('"book_id":2') < output.index('"book_id":3')
    assert output.count('"score":0.693147') == 3


def test_settings_are_accepted_before_the_command(workspace: Path) -> None:
    assert main([*settings(workspace), "download", "1"], NO_ENVIRONMENT) == 0

    assert (workspace / "data/datalake_book/1/body.txt").read_text(encoding="utf-8") == "the car is nice"


def test_the_argument_takes_precedence_over_the_environment(workspace: Path) -> None:
    environ = {"TARANTINO_LAKE": "batch"}

    main(["download", "1", *settings(workspace, lake="book")], environ)

    assert (workspace / "data/datalake_book/1/body.txt").exists()
    assert not (workspace / "data/datalake_batch").exists()


def test_the_environment_is_used_when_there_is_no_argument(workspace: Path) -> None:
    arguments = [option for option in settings(workspace) if option not in ("--lake", "book")]

    main(["download", "1", *arguments], {"TARANTINO_LAKE": "batch"})

    assert (workspace / "data/datalake_batch/000000-000999/1.body.txt").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["step", "--lake", "weekly"],
        ["fly"],
        ["download"],
        ["download", "zero"],
        ["run", "--steps", "0"],
    ],
)
def test_usage_errors_exit_with_code_1(argv: list[str]) -> None:
    assert main(argv, NO_ENVIRONMENT) == 1


def test_an_invalid_environment_value_is_a_usage_error() -> None:
    assert main(["search", "car"], {"TARANTINO_INDEX": "sql"}) == 1


def test_help_exits_with_code_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"], NO_ENVIRONMENT) == 0


def test_a_failed_download_exits_with_code_2_and_is_recorded(workspace: Path) -> None:
    assert main(["download", "99", *settings(workspace)], NO_ENVIRONMENT) == 2

    assert (workspace / "data/control/failed_books.txt").read_bytes() == b"99;HTTP_ERROR;1\n"


def test_a_step_deletes_tmp_leftovers_before_doing_anything_else(workspace: Path) -> None:
    leftover = workspace / "data/datalake_book/7/body.txt.tmp"
    leftover.parent.mkdir(parents=True)
    leftover.write_text("partial", encoding="utf-8")

    main(["step", "--ids", str(workspace / "ids.txt"), *settings(workspace)], NO_ENVIRONMENT)

    assert not leftover.exists()


def test_a_step_with_an_existing_lock_exits_with_code_2_and_touches_nothing(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = create_lock(workspace)
    leftover = workspace / "data/datalake_book/7/body.txt.tmp"
    leftover.parent.mkdir(parents=True)
    leftover.write_text("partial", encoding="utf-8")

    exit_code = main(["step", "--ids", str(workspace / "ids.txt"), *settings(workspace)], NO_ENVIRONMENT)

    assert exit_code == 2
    assert "4242" in capsys.readouterr().err
    assert lock.read_text(encoding="utf-8") == "4242\n2026-09-28T10:00:00Z\n"
    assert leftover.exists()
    assert sorted(path.name for path in (workspace / "data/control").iterdir()) == [".lock"]


def test_search_runs_normally_while_the_lock_exists(workspace: Path) -> None:
    run_pipeline(workspace)
    create_lock(workspace)

    assert main(["search", "car", *settings(workspace)], NO_ENVIRONMENT) == 0


def test_the_lock_is_deleted_after_a_successful_step(workspace: Path) -> None:
    main(["step", "--ids", str(workspace / "ids.txt"), *settings(workspace)], NO_ENVIRONMENT)

    assert not (workspace / "data/control/.lock").exists()


def test_the_lock_is_deleted_after_a_failing_command(workspace: Path) -> None:
    assert main(["index", "1", *settings(workspace)], NO_ENVIRONMENT) == 2

    assert not (workspace / "data/control/.lock").exists()


def test_a_step_with_no_valid_candidate_does_nothing(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (workspace / "ids.txt").write_text("", encoding="utf-8")

    assert main(["step", "--ids", str(workspace / "ids.txt"), *settings(workspace)], NO_ENVIRONMENT) == 0

    assert capsys.readouterr().out.startswith("Nothing to do")


def test_searching_before_indexing_is_a_runtime_error(workspace: Path) -> None:
    assert main(["search", "car", *settings(workspace)], NO_ENVIRONMENT) == 2


def test_a_missing_ids_file_is_a_usage_error(workspace: Path) -> None:
    missing = str(workspace / "missing_ids.txt")

    assert main(["step", "--ids", missing, *settings(workspace)], NO_ENVIRONMENT) == 1


def test_an_ids_file_with_a_line_that_is_not_an_id_is_a_usage_error(workspace: Path) -> None:
    (workspace / "ids.txt").write_text("1\nabc\n3\n", encoding="utf-8", newline="")

    assert main(["run", "--steps", "2", "--ids", str(workspace / "ids.txt"), *settings(workspace)], NO_ENVIRONMENT) == 1
    assert not (workspace / "data" / "control" / "downloaded_books.txt").exists()
