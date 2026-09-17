package com.tarantino.stage1.application;

import com.tarantino.stage1.domain.ports.BookDownloader;
import com.tarantino.stage1.domain.ports.DatalakeStorage;
import com.tarantino.stage1.domain.ports.InvertedIndexStorage;
import com.tarantino.stage1.domain.ports.MetadataStorage;

/**
 * TODO: Caso de uso que, dado un book_id, orquesta: descarga (BookDownloader)
 * -> guardado en datalake (DatalakeStorage) -> extraccion de metadata
 * (MetadataStorage) -> construccion de indice (InvertedIndexStorage). Recibe
 * sus dependencias (ports) por inyeccion en el constructor. No debe imprimir
 * por consola ni devolver strings formateadas; debe devolver datos
 * estructurados.
 */
public class IngestBookUseCase {
    // TODO: constructor con inyeccion de dependencias (ports)
    // TODO: metodo execute(bookId)
}
