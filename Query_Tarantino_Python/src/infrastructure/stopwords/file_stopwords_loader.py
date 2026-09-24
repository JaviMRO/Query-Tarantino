"""
Loads the stopwords of a language from <shared_dir>/stopwords_<language>.txt
(SPEC 1). shared_dir comes from TARANTINO_SHARED_DIR / --shared-dir.
"""

from pathlib import Path


def load_stopwords(shared_dir: Path, language: str = "en") -> frozenset[str]:
    text = (shared_dir / f"stopwords_{language}.txt").read_text(encoding="utf-8")
    return frozenset(text.split())
