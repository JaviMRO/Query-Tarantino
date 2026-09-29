"""
Loads the stopwords of a language from <shared_dir>/stopwords_<language>.txt
(SPEC 1). shared_dir comes from TARANTINO_SHARED_DIR / --shared-dir.
"""

from pathlib import Path


def load_stopwords(shared_dir: Path, language: str = "en") -> frozenset[str]:
    """One stopword per line; called once per process by the entrypoint."""
    with (shared_dir / f"stopwords_{language}.txt").open(encoding="utf-8", newline="") as file:
        return frozenset(word for line in file if (word := line.rstrip("\n")))
