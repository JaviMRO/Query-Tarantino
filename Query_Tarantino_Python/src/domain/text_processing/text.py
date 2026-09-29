"""
Text helpers shared by the domain.

SPEC regular expressions are ASCII-only, as they are by default in Java and
C++ std::regex. Python's re is Unicode-aware by default (its whitespace class
also matches a non-breaking space), so every domain regex uses
ASCII_CASE_INSENSITIVE.
"""

import re

ASCII_CASE_INSENSITIVE = re.IGNORECASE | re.ASCII

ASCII_WHITESPACE = " \t\n\r\f\v"


def strip_ascii_whitespace(text: str) -> str:
    """Trims only ASCII whitespace, as required by SPEC 3.4 and 5.1."""
    return text.strip(ASCII_WHITESPACE)
