"""Safe writes and line appends shared by the file-based adapters (SPEC 4.3, 7.1, 7.3, 8)."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

TMP_SUFFIX = ".tmp"


@contextmanager
def atomic_text_writer(target: Path) -> Iterator[TextIO]:
    """Stream text into a temporary sibling and rename it over the target (SPEC 4.3)."""
    temporary = target.with_name(target.name + TMP_SUFFIX)
    target.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as file:
        yield file
    temporary.replace(target)


def append_line(path: Path, line: str) -> None:
    """Append one complete line to a file that only grows; the parent folder must exist (SPEC 7.3, 8)."""
    with path.open("a", encoding="utf-8", newline="") as file:
        file.write(line + "\n")
