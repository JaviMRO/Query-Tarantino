"""
Order of the configurations of one round (SPEC 11.6): every configuration of SPEC 11.1 for the three languages,
shuffled with random.Random(R). download only runs in rounds 0 to 3.

Usage: python benchmarks/plan.py --round R
Prints one configuration per line: language experiment structure n_books.
"""

import argparse
import random

LANGUAGES = ("cpp", "java", "python")
LAST_DOWNLOAD_ROUND = 3
CORPUS_SIZES = (100, 250, 500, 1000)
GRID = (
    ("datalake", ("time", "book", "batch"), CORPUS_SIZES),
    ("recovery", ("time", "book", "batch"), CORPUS_SIZES),
    ("index", ("json", "mongo", "folders"), CORPUS_SIZES),
    ("metadata", ("sqlite",), (1000, 10000, 50000)),
    ("download", ("none",), (50,)),
    ("baseline", ("none",), (0,)),
)


def configurations(round_number: int) -> list[tuple[str, str, str, int]]:
    """All the configurations of the round, in the order they must run."""
    planned = [
        (language, experiment, structure, n_books)
        for language in LANGUAGES
        for experiment, structures, sizes in GRID
        if experiment != "download" or round_number <= LAST_DOWNLOAD_ROUND
        for structure in structures
        for n_books in sizes
    ]
    random.Random(round_number).shuffle(planned)
    return planned


def main() -> None:
    """Prints the configurations of the round given with --round, one per line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, required=True, dest="round_number")
    for language, experiment, structure, n_books in configurations(parser.parse_args().round_number):
        print(language, experiment, structure, n_books)


if __name__ == "__main__":
    main()
