"""
Configuration of SPEC 2: each setting comes from its --argument, else from its
TARANTINO_ environment variable, else from its default.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar

ENVIRONMENT_PREFIX = "TARANTINO_"

DEFAULTS = {
    "data_dir": "./data",
    "lake": "time",
    "index": "json",
    "downloader": "http",
    "corpus_dir": "./corpus_raw",
    "mongo_url": "mongodb://localhost:27017",
    "shared_dir": "./shared",
}
SETTING_NAMES = tuple(DEFAULTS)


class LakeLayout(Enum):
    """Datalake structures (SPEC 4.1)."""

    TIME = "time"
    BOOK = "book"
    BATCH = "batch"


class IndexLayout(Enum):
    """Inverted index structures (SPEC 7)."""

    JSON = "json"
    MONGO = "mongo"
    FOLDERS = "folders"


class DownloaderKind(Enum):
    """Where the books come from (SPEC 3)."""

    HTTP = "http"
    LOCAL = "local"


_Choice = TypeVar("_Choice", LakeLayout, IndexLayout, DownloaderKind)


@dataclass(frozen=True, slots=True)
class Settings:
    """The resolved configuration of one process."""

    data_dir: Path
    lake: LakeLayout
    index: IndexLayout
    downloader: DownloaderKind
    corpus_dir: Path
    mongo_url: str
    shared_dir: Path


def option_flag(name: str) -> str:
    """Command-line argument of a setting: the variable name without prefix, lowercase, with hyphens."""
    return "--" + name.replace("_", "-")


def resolve_settings(arguments: Mapping[str, str | None], environ: Mapping[str, str]) -> Settings:
    """Raises ValueError if a value is not one of the allowed ones (a usage error)."""
    return Settings(
        data_dir=Path(_resolve("data_dir", arguments, environ)),
        lake=_choice(LakeLayout, "lake", arguments, environ),
        index=_choice(IndexLayout, "index", arguments, environ),
        downloader=_choice(DownloaderKind, "downloader", arguments, environ),
        corpus_dir=Path(_resolve("corpus_dir", arguments, environ)),
        mongo_url=_resolve("mongo_url", arguments, environ),
        shared_dir=Path(_resolve("shared_dir", arguments, environ)),
    )


def _resolve(name: str, arguments: Mapping[str, str | None], environ: Mapping[str, str]) -> str:
    """The argument takes precedence over the environment variable (SPEC 2)."""
    given = arguments.get(name)
    if given is not None:
        return given
    return environ.get(ENVIRONMENT_PREFIX + name.upper(), DEFAULTS[name])


def _choice(
    choices: type[_Choice], name: str, arguments: Mapping[str, str | None], environ: Mapping[str, str]
) -> _Choice:
    value = _resolve(name, arguments, environ)
    allowed = [choice.value for choice in choices]
    if value not in allowed:
        raise ValueError(f"Invalid {option_flag(name)} {value!r}; allowed values: {', '.join(allowed)}")
    return choices(value)
