"""
TODO: Implementacion de MetadataStorage que extrae metadata (title, author,
language) del header del libro via regex y la persiste en SQLite (stdlib
sqlite3).
"""

import sqlite3

from src.domain.ports import MetadataStorage


class SqliteMetadataAdapter:
    pass  # TODO: implementar metodos de MetadataStorage usando sqlite3
