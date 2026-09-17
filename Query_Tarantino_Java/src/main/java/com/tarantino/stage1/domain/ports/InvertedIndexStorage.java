package com.tarantino.stage1.domain.ports;

import com.tarantino.stage1.domain.model.PostingList;

/**
 * TODO: Puerto que define como se persiste el indice invertido. Implementaciones
 * concretas: un unico JSON monolitico con todos los terminos, una coleccion
 * MongoDB con un documento por termino, o una carpeta con un .txt por termino
 * agrupado alfabeticamente.
 */
public interface InvertedIndexStorage {
    // TODO: definir metodos (addPosting, getPostingList, etc.)
}
