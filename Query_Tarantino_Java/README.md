# Query_Tarantino_Java

Módulo Java (Maven) de la capa de datos (datalake, datamart y control) del motor
de búsqueda Query Tarantino. Implementa Arquitectura Hexagonal (Ports & Adapters):
`domain/` no depende de ninguna librería externa, `application/` orquesta los
casos de uso vía inyección de dependencias, e `infrastructure/` contiene los
adaptadores concretos (SQLite, MongoDB, JSON, HTTP).

## Requisitos

- JDK 17+
- Maven 3.8+

## Instalación de dependencias

```bash
mvn dependency:resolve
```

## Build

```bash
mvn clean package
```

## Test

```bash
mvn test
```

## Estructura

```
src/main/java/com/tarantino/stage1/
├── domain/            # modelos y ports (interfaces puras)
├── application/        # casos de uso (orquestación)
└── infrastructure/     # adaptadores concretos + entrypoints (futuro CLI/API/UI)
```
