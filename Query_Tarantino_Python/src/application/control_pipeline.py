"""
TODO: Caso de uso que coordina el ciclo descarga -> indexado, usando el
estado de libros descargados/indexados (via MetadataStorage o ficheros de
control) para decidir que libro procesar a continuacion. Recibe sus
dependencias (ports) por inyeccion en el constructor. No debe imprimir por
consola (print) ni devolver strings formateadas; debe devolver datos
estructurados.
"""

from src.domain.ports import MetadataStorage


class ControlPipeline:
    def __init__(self):
        pass  # TODO: inyeccion de dependencias (ports)

    def next_book_to_process(self):
        pass  # TODO: determinar el siguiente libro a procesar
