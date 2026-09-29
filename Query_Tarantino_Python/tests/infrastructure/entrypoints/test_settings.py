from pathlib import Path

import pytest

from src.infrastructure.entrypoints.settings import (
    DownloaderKind,
    IndexLayout,
    LakeLayout,
    Settings,
    option_flag,
    resolve_settings,
)


def test_defaults_follow_spec_2() -> None:
    assert resolve_settings({}, {}) == Settings(
        data_dir=Path("./data"),
        lake=LakeLayout.TIME,
        index=IndexLayout.JSON,
        downloader=DownloaderKind.HTTP,
        corpus_dir=Path("./corpus_raw"),
        mongo_url="mongodb://localhost:27017",
        shared_dir=Path("./shared"),
    )


def test_environment_variables_override_the_defaults() -> None:
    settings = resolve_settings({}, {"TARANTINO_DATA_DIR": "/srv/data", "TARANTINO_INDEX": "folders"})

    assert settings.data_dir == Path("/srv/data")
    assert settings.index == IndexLayout.FOLDERS


def test_arguments_override_the_environment() -> None:
    settings = resolve_settings({"index": "mongo"}, {"TARANTINO_INDEX": "folders"})

    assert settings.index == IndexLayout.MONGO


def test_an_absent_argument_falls_back_to_the_environment() -> None:
    settings = resolve_settings({"index": None}, {"TARANTINO_INDEX": "folders"})

    assert settings.index == IndexLayout.FOLDERS


def test_a_value_outside_the_allowed_ones_raises_value_error() -> None:
    with pytest.raises(ValueError, match="--downloader"):
        resolve_settings({"downloader": "ftp"}, {})


def test_option_flags_are_the_variable_names_in_lowercase_with_hyphens() -> None:
    assert option_flag("data_dir") == "--data-dir"
