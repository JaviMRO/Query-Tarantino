"""
TODO: Caso de uso que, dado un book_id, orquesta: descarga (BookDownloader)
-> guardado en datalake (DatalakeStorage) -> extraccion de metadata
(MetadataStorage) -> construccion de indice (InvertedIndexStorage). Recibe
sus dependencias (ports) por inyeccion en el constructor. No debe imprimir
por consola (print) ni devolver strings formateadas; debe devolver datos
estructurados.
"""

from src.domain.ports import BookDownloader, DatalakeStorage, InvertedIndexStorage, MetadataStorage


class IngestBookUseCase:
    def __init__(self):
        pass  # TODO: inyeccion de dependencias (ports)

    def execute(self, book_id: str):
        pass  # TODO: orquestar descarga -> datalake -> metadata -> indice
