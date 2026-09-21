"""
TODO: Modelos de dominio: Book (libro descargado de Project Gutenberg, con
id, title, author, language, etc.) y PostingList (lista de ocurrencias de un
termino del indice invertido). Implementados como dataclasses. No deben
depender de ninguna libreria externa.
"""

from dataclasses import dataclass


@dataclass
class Book:
    pass  # TODO: definir campos (id, title, author, language, etc.)


@dataclass
class PostingList:
    pass  # TODO: definir campos (term, postings, etc.)


@dataclass
class RawBook:
    pass  # TODO: definir campos (id, header, body, etc.)


@dataclass
class BookLocation:
    pass  # TODO: definir campos (book_id, path, etc.)
