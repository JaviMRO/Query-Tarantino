#pragma once

#include "domain/ports.h"

// TODO: Caso de uso que coordina el ciclo descarga -> indexado, usando el
// estado de libros descargados/indexados (via MetadataStorage o ficheros de
// control) para decidir que libro procesar a continuacion. Recibe sus
// dependencias (ports) por inyeccion en el constructor. No debe usar
// std::cout ni devolver strings formateadas; debe devolver datos
// estructurados.
class ControlPipeline {
public:
    // TODO: constructor con inyeccion de dependencias (ports)
    // TODO: metodo que determina el siguiente libro a procesar
};
