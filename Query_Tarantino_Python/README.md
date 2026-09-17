# Query_Tarantino_Python

Módulo Python de la capa de datos (datalake, datamart y control) del motor de
búsqueda Query Tarantino. Implementa Arquitectura Hexagonal (Ports & Adapters):
`domain/` no depende de ninguna librería externa, `application/` orquesta los
casos de uso vía inyección de dependencias, e `infrastructure/` contiene los
adaptadores concretos (SQLite, MongoDB, JSON, HTTP).

## Requisitos

- Python 3.10+

## Instalación de dependencias

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
python -m src.infrastructure.entrypoints.<futuro_entrypoint>
```

## Estructura

```
src/
├── domain/            # modelos (dataclasses) y ports (Protocol/ABC)
├── application/         # casos de uso (orquestación)
└── infrastructure/      # adaptadores concretos + entrypoints (futuro CLI/API/UI)
```
