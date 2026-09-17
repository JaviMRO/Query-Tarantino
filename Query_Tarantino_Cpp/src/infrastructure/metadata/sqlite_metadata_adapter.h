#pragma once

#include "domain/ports.h"

// TODO: Implementacion de MetadataStorage que extrae metadata (title, author,
// language) del header del libro via regex y la persiste en SQLite.
class SqliteMetadataAdapter : public MetadataStorage {
public:
    // TODO: implementar metodos de MetadataStorage usando sqlite3
};
