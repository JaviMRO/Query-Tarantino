package com.tarantino.stage1.domain.ports;

import com.tarantino.stage1.domain.model.Book;

/**
 * TODO: Puerto que define como se persiste el contenido crudo de un libro en
 * el datalake. Implementaciones concretas: organizacion por fecha/hora de
 * descarga (time-based), por id de libro (book-based) o por lotes/rango/hash
 * (batch-based).
 */
public interface DatalakeStorage {
    // TODO: definir metodos (save, load, exists, etc.)
}
