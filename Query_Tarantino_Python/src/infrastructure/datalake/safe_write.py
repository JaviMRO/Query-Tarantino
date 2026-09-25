"""
Safe write shared by every DatalakeStorage adapter (SPEC 4.3): the content is
written to a file named like the final one plus ".tmp", closed, then renamed
to its final name. This way a reader never observes a partially written file,
and an interrupted write leaves only a stray ".tmp" behind instead of a
corrupt final file.
"""

from pathlib import Path

_TMP_SUFFIX = ".tmp"


def write_text_safely(path: Path, content: str) -> None:
    """
    Writes UTF-8 content with no line-ending conversion (SPEC 13.3), via the
    safe write of SPEC 4.3. Creates parent folders if missing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + _TMP_SUFFIX)
    tmp_path.write_text(content, encoding="utf-8", newline="")
    tmp_path.replace(path)
