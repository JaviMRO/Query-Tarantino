#pragma once

#include "domain/ports.h"

// TODO: Implementacion de BookDownloader que descarga el .txt de un libro
// desde Project Gutenberg via libcurl y separa header/body usando los
// marcadores START/END.
class GutenbergHttpDownloader : public BookDownloader {
public:
    // TODO: implementar metodos de BookDownloader usando libcurl
};
