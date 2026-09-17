package com.tarantino.stage1.application;

import com.tarantino.stage1.domain.ports.MetadataStorage;

/**
 * TODO: Caso de uso que coordina el ciclo descarga -> indexado, usando el
 * estado de libros descargados/indexados (via MetadataStorage o ficheros de
 * control) para decidir que libro procesar a continuacion. Recibe sus
 * dependencias (ports) por inyeccion en el constructor. No debe imprimir por
 * consola ni devolver strings formateadas; debe devolver datos estructurados.
 */
public class ControlPipeline {
    // TODO: constructor con inyeccion de dependencias (ports)
    // TODO: metodo que determina el siguiente libro a procesar
}
