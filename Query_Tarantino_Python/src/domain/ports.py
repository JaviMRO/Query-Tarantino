"""
TODO: Ports (interfaces) del dominio, definidos con typing.Protocol. No deben
depender de ninguna libreria externa (SQLite, MongoDB, JSON, HTTP son detalle
de infrastructure).
"""

from typing import Protocol

from src.domain.model import Book, PostingList


class DatalakeStorage(Protocol):
    """
    TODO: Puerto que define como se persiste el contenido crudo de un libro
    en el datalake. Implementaciones concretas: organizacion por fecha/hora
    de descarga (time-based), por id de libro (book-based) o por
    lotes/rango/hash (batch-based).
    """
    ...  # TODO: definir metodos (save, load, exists, etc.)


class MetadataStorage(Protocol):
    """
    TODO: Puerto que define como se persiste y consulta la metadata (title,
    author, language) extraida del header de un libro. Implementacion
    concreta: SQLite.
    """
    ...  # TODO: definir metodos (save, find_by_id, list_indexed, etc.)


class InvertedIndexStorage(Protocol):
    """
    TODO: Puerto que define como se persiste el indice invertido.
    Implementaciones concretas: un unico JSON monolitico con todos los
    terminos, una coleccion MongoDB con un documento por termino, o una
    carpeta con un .txt por termino agrupado alfabeticamente.
    """
    ...  # TODO: definir metodos (add_posting, get_posting_list, etc.)


class BookDownloader(Protocol):
    """
    TODO: Puerto que define como se descarga el .txt de un libro desde
    Project Gutenberg y se separa header/body usando los marcadores
    START/END. Implementacion concreta: HTTP.
    """
    ...  # TODO: definir metodos (download, etc.)


class ControlStateStore(Protocol):
    """
    TODO: Puerto que define como se persiste el estado del pipeline de
    control (ultimo libro procesado, libros descargados/indexados, etc.)
    para poder reanudar. Implementacion concreta: fichero.
    """
    ...  # TODO: definir metodos (load, save, mark_downloaded, etc.)
