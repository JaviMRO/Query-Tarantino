package com.tarantino.stage1.domain.ports;

/**
 * TODO: Puerto que define como se persiste el estado del pipeline de control
 * (ultimo libro procesado, libros descargados/indexados, etc.) para poder
 * reanudar. Implementacion concreta: fichero.
 */
public interface ControlStateStore {
    // TODO: definir metodos (load, save, markDownloaded, markIndexed, etc.)
}
