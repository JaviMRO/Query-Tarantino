#pragma once

#include "domain/model.h"

// TODO: Puerto que define como se persiste el contenido crudo de un libro en
// el datalake. Implementaciones concretas: organizacion por fecha/hora de
// descarga (time-based), por id de libro (book-based) o por lotes/rango/hash
// (batch-based).
class DatalakeStorage {
public:
    virtual ~DatalakeStorage() = default;
    // TODO: declarar metodos virtuales puros (save, load, exists, etc.)
};

// TODO: Puerto que define como se persiste y consulta la metadata (title,
// author, language) extraida del header de un libro. Implementacion
// concreta: SQLite.
class MetadataStorage {
public:
    virtual ~MetadataStorage() = default;
    // TODO: declarar metodos virtuales puros (save, findById, listIndexed, etc.)
};

// TODO: Puerto que define como se persiste el indice invertido.
// Implementaciones concretas: un unico JSON monolitico con todos los
// terminos, una coleccion MongoDB con un documento por termino, o una
// carpeta con un .txt por termino agrupado alfabeticamente.
class InvertedIndexStorage {
public:
    virtual ~InvertedIndexStorage() = default;
    // TODO: declarar metodos virtuales puros (addPosting, getPostingList, etc.)
};

// TODO: Puerto que define como se descarga el .txt de un libro desde Project
// Gutenberg y se separa header/body usando los marcadores START/END.
// Implementacion concreta: libcurl.
class BookDownloader {
public:
    virtual ~BookDownloader() = default;
    // TODO: declarar metodos virtuales puros (download, etc.)
};

// TODO: Puerto que define como se persiste el estado del pipeline de control
// (ultimo libro procesado, libros descargados/indexados, etc.) para poder
// reanudar. Implementacion concreta: fichero.
class ControlStateStore {
public:
    virtual ~ControlStateStore() = default;
    // TODO: declarar metodos virtuales puros (load, save, markDownloaded, etc.)
};
