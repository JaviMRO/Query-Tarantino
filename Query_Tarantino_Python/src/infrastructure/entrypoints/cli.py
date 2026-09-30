"""
Command line of SPEC 10 (python -m tarantino). The only place that reads
arguments and environment, holds the lock and decides the exit code.
"""

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from src.application.use_cases.index_book_use_case import utc_now
from src.infrastructure.entrypoints.bench import command as bench_command
from src.infrastructure.entrypoints.bench.configuration import Experiment, parse_configuration
from src.infrastructure.entrypoints.settings import SETTING_NAMES, Settings, option_flag, resolve_settings
from src.infrastructure.entrypoints.wiring import commands
from src.infrastructure.entrypoints.wiring.commands import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR
from src.infrastructure.startup.lock import acquire_lock, lock_path, read_lock_owner, release_lock
from src.infrastructure.startup.tmp_cleanup import delete_tmp_leftovers

PROGRAM_NAME = "tarantino"


def main(argv: Sequence[str], environ: Mapping[str, str]) -> int:
    """Runs one command and returns its exit code: 0 success, 1 usage error, 2 runtime error."""
    try:
        arguments = _build_parser().parse_args(argv)
    except SystemExit as parser_exit:
        return EXIT_OK if parser_exit.code == EXIT_OK else EXIT_USAGE_ERROR
    try:
        settings = resolve_settings(vars(arguments), environ)
    except ValueError as error:
        _print_error(str(error))
        return EXIT_USAGE_ERROR
    try:
        return _dispatch(arguments, settings)
    except Exception as error:
        _print_error(f"{type(error).__name__}: {error}")
        return EXIT_RUNTIME_ERROR


def _dispatch(arguments: argparse.Namespace, settings: Settings) -> int:
    match arguments.command:
        case "download":
            return _run_locked(settings, lambda: commands.download(settings, arguments.book_id))
        case "index":
            return _run_locked(settings, lambda: commands.index(settings, arguments.book_id))
        case "step":
            return _run_locked(settings, lambda: commands.run_steps(settings, 1, arguments.ids))
        case "run":
            return _run_locked(settings, lambda: commands.run_steps(settings, arguments.steps, arguments.ids))
        case "bench":
            return _bench(arguments, settings)
        case _:
            return commands.search(settings, arguments.text, arguments.as_json)


def _bench(arguments: argparse.Namespace, settings: Settings) -> int:
    """A combination outside SPEC 11.1 is a usage error, detected before taking the lock."""
    try:
        configuration = parse_configuration(arguments.experiment, arguments.structure, arguments.n, arguments.run)
    except ValueError as error:
        _print_error(str(error))
        return EXIT_USAGE_ERROR
    return _run_locked(settings, lambda: bench_command.bench(settings, configuration, arguments.out))


def _run_locked(settings: Settings, command: Callable[[], int]) -> int:
    """Lock, .tmp cleanup, command, and the own lock deleted on exit, even on errors (SPEC 13.1)."""
    lock = lock_path(settings.data_dir)
    try:
        acquire_lock(lock, os.getpid(), utc_now())
    except FileExistsError:
        _print_error(
            f"{lock} is held by process {read_lock_owner(lock)}. "
            f"If that process no longer exists, delete {lock} and try again."
        )
        return EXIT_RUNTIME_ERROR
    try:
        delete_tmp_leftovers(settings.data_dir)
        return command()
    finally:
        release_lock(lock)


def _build_parser() -> argparse.ArgumentParser:
    settings_options = _settings_options()
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME, parents=[settings_options])
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("download", "index"):
        subcommands.add_parser(name, parents=[settings_options]).add_argument("book_id", type=_positive_int)
    subcommands.add_parser("step", parents=[settings_options]).add_argument("--ids", type=_ids_file)
    run = subcommands.add_parser("run", parents=[settings_options])
    run.add_argument("--steps", type=_positive_int, required=True)
    run.add_argument("--ids", type=_ids_file)
    search = subcommands.add_parser("search", parents=[settings_options])
    search.add_argument("text")
    search.add_argument("--json", dest="as_json", action="store_true")
    _add_bench_arguments(subcommands.add_parser("bench", parents=[settings_options]))
    return parser


def _add_bench_arguments(bench: argparse.ArgumentParser) -> None:
    """tarantino bench --experiment E --structure S --n N --run R --out FILE.csv (SPEC 10, 11.2)."""
    bench.add_argument("--experiment", required=True, choices=[experiment.value for experiment in Experiment])
    bench.add_argument("--structure", required=True)
    bench.add_argument("--n", required=True, type=int)
    bench.add_argument("--run", required=True, type=int)
    bench.add_argument("--out", required=True, type=Path)


def _settings_options() -> argparse.ArgumentParser:
    """The SPEC 2 settings, accepted before or after the command; absent ones fall back to the environment."""
    options = argparse.ArgumentParser(add_help=False)
    for name in SETTING_NAMES:
        options.add_argument(option_flag(name), dest=name, default=argparse.SUPPRESS)
    return options


def _ids_file(text: str) -> Path:
    """An existing --ids file with one book id per line (SPEC 8.1); anything else is a usage error (SPEC 10)."""
    path = Path(text)
    try:
        invalid_line = _first_invalid_id_line(path)
    except OSError as error:
        raise argparse.ArgumentTypeError(f"cannot read {text}: {error.strerror}") from error
    if invalid_line is not None:
        raise argparse.ArgumentTypeError(f"line {invalid_line} of {text} is not a book id")
    return path


def _first_invalid_id_line(path: Path) -> int | None:
    """Checked once, line by line; the steps still read the file lazily."""
    with path.open(encoding="utf-8", newline="") as file:
        return next((number for number, line in enumerate(file, start=1) if not _is_id_line(line)), None)


def _is_id_line(line: str) -> bool:
    content = line.rstrip("\n")
    return not content or (content.isascii() and content.isdecimal())


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, not {text}")
    return value


def _print_error(message: str) -> None:
    print(f"{PROGRAM_NAME}: {message}", file=sys.stderr)
