from pathlib import Path

import pytest

from src.infrastructure.stopwords.file_stopwords_loader import load_stopwords

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"


@pytest.fixture(scope="session")
def official_stopwords() -> frozenset[str]:
    return load_stopwords(SHARED_DIR)
