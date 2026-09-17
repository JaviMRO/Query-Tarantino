#pragma once

#include "domain/ports.h"

// TODO: Caso de uso que, dado un book_id, orquesta: descarga (BookDownloader)
// -> guardado en datalake (DatalakeStorage) -> extraccion de metadata
// (MetadataStorage) -> construccion de indice (InvertedIndexStorage). Recibe
// sus dependencias (ports) por inyeccion en el constructor. No debe usar
// std::cout ni devolver strings formateadas; debe devolver datos
// estructurados.
class IngestBookUseCase {
public:
    // TODO: constructor con inyeccion de dependencias (ports)
    // TODO: metodo execute(bookId)
};
