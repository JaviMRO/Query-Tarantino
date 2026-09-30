import pytest

from src.infrastructure.entrypoints.bench.configuration import Configuration, Experiment, parse_configuration


@pytest.mark.parametrize(
    ("experiment", "structure", "n_books"),
    [
        ("datalake", "time", 100),
        ("recovery", "batch", 1000),
        ("index", "folders", 250),
        ("metadata", "sqlite", 50000),
        ("download", "none", 50),
        ("baseline", "none", 0),
    ],
)
def test_every_combination_of_the_spec_table_is_accepted(experiment: str, structure: str, n_books: int) -> None:
    configuration = parse_configuration(experiment, structure, n_books, 3)

    assert configuration == Configuration(Experiment(experiment), structure, n_books, 3)


@pytest.mark.parametrize(
    ("experiment", "structure", "n_books", "run"),
    [
        ("index", "time", 100, 1),
        ("datalake", "json", 100, 1),
        ("datalake", "time", 50, 1),
        ("metadata", "sqlite", 100, 1),
        ("download", "none", 100, 1),
        ("baseline", "none", 0, -1),
    ],
)
def test_a_combination_outside_the_spec_table_is_a_usage_error(
    experiment: str, structure: str, n_books: int, run: int
) -> None:
    with pytest.raises(ValueError):
        parse_configuration(experiment, structure, n_books, run)
