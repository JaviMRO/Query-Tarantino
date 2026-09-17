# Query_Tarantino_Cpp

Módulo C++ (CMake) de la capa de datos (datalake, datamart y control) del
motor de búsqueda Query Tarantino. Implementa Arquitectura Hexagonal (Ports &
Adapters): `domain/` no depende de ninguna librería externa, `application/`
orquesta los casos de uso vía inyección de dependencias, e `infrastructure/`
contiene los adaptadores concretos (SQLite, MongoDB, JSON, libcurl).

## Requisitos

- CMake 3.20+
- Compilador C++20
- Librerías: sqlite3, nlohmann-json, mongo-cxx-driver, libcurl

### Instalación de dependencias (ejemplo vcpkg)

```bash
vcpkg install sqlite3 nlohmann-json mongo-cxx-driver curl
```

## Build

```bash
cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE=<path-to-vcpkg>/scripts/buildsystems/vcpkg.cmake
cmake --build build
```

## Ejecución

```bash
./build/stage1
```

## Estructura

```
src/
├── domain/            # modelos (structs) y ports (clases abstractas puras)
├── application/         # casos de uso (orquestación)
└── infrastructure/      # adaptadores concretos + entrypoints (futuro CLI/API/UI)
```
