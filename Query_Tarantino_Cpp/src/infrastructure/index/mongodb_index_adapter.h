#pragma once

#include "domain/ports.h"

// TODO: Implementacion de InvertedIndexStorage que guarda el indice invertido
// en una coleccion MongoDB con un documento por termino.
class MongoDbIndexAdapter : public InvertedIndexStorage {
public:
    // TODO: implementar metodos de InvertedIndexStorage usando mongo-cxx-driver
};
