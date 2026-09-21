#pragma once

#include <string>
#include <vector>

// TODO: Modelo de dominio que representa un libro descargado de Project
// Gutenberg: identificador, titulo, autor, idioma, etc. No debe depender de
// ninguna libreria externa.
struct Book {
    // TODO: definir campos (id, title, author, language, etc.)
};

// TODO: Modelo de dominio que representa la lista de ocurrencias (posting
// list) de un termino del indice invertido: termino y libros/posiciones en
// los que aparece. No debe depender de ninguna libreria externa.
struct PostingList {
    // TODO: definir campos (term, postings, etc.)
};

// TODO: Modelo de dominio que representa un libro tal como se descarga, sin
// procesar (header y body separados). No debe depender de ninguna libreria
// externa.
struct RawBook {
    // TODO: definir campos (id, header, body, etc.)
};

// TODO: Modelo de dominio que representa donde esta almacenado un libro en
// el datalake (ruta/clave segun la convencion de organizacion). No debe
// depender de ninguna libreria externa.
struct BookLocation {
    // TODO: definir campos (bookId, path, etc.)
};
