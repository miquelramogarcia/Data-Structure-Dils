# Base de datos de vivienda Dils

## Qué es el proyecto

Proyecto Python (ETL) que descarga estadísticas de vivienda de fuentes públicas de España (MIVAU, Notariado, Idealista), las transforma a un formato común y genera:

- un catálogo en Excel (`Data Dils_v2.xlsx`) con las hojas Tablas, Campos y una hoja de datos por tabla, con hipervínculos;
- un fichero `sql/create_tables.sql` con un `CREATE TABLE` por tabla, listo para MySQL;
- un CSV limpio por tabla en `etl/salida/`.

Esquemas de base de datos: `MIVAU`, `NOTARIADO`, `IDEALISTA`.

El diseño completo está en `docs/2026-10-29-base-datos-vivienda-design.md` y el plan de implementación en `docs/plans/2026-10-29-base-datos-vivienda-fase1.md`.

## Estructura de carpetas

```
Data Dils/
  Data Dils.xlsx                  original del usuario (solo lectura; nunca se modifica)
  Data Dils_v2.xlsx               libro resultante (catálogo + hojas de datos)  [pendiente]
  sql/create_tables.sql           todos los CREATE TABLE  [pendiente]
  etl/
    descargas/                    ficheros originales descargados (no se versionan)
    fuentes/                      un script por dataset
    lib/                          utilidades comunes (territorios, periodos)
    salida/                       CSV limpio por tabla  [pendiente]
    ejecutar_todo.py              punto de entrada para regenerarlo todo  [pendiente]
  tests/                          tests con pytest
  docs/
    README.md                     este documento
    decisiones.md                 registro de decisiones con fecha y motivo
    fuentes/<DATASET_ID>.md       ficha por fuente  [pendiente]
```

## Catálogo y SQL

El catálogo vive en `etl/catalogo/tablas.csv` y `etl/catalogo/campos.csv` (fuente de verdad, sembrado una sola vez desde el Excel del usuario con `python -m etl.catalogo.sembrar`). Para regenerar `sql/create_tables.sql` tras cambiar el catálogo:

```
python -m etl.catalogo.sql
```

No se edita el SQL a mano. Las tablas sin campos diseñados aún se omiten.

## Requisitos e instalación

Python 3.13.

```
python -m pip install -r requirements.txt
```

## Cómo regenerarlo todo

```
python -m etl.ejecutar_todo
```

[pendiente] El punto de entrada se crea en fases posteriores.

## Tests

```
pytest
```

[pendiente] Los tests se añaden con cada tarea del plan. Mientras no existan, `pytest` termina con "no tests ran" (código de salida 5).

## Convenciones

- `periodo`: `AAAAMmm` (mensual), `AAAATn` (trimestral) o `AAAA` (anual). `frecuencia` vale `M`, `T` o `A`.
- `fecha`: fecha real `AAAA-MM-DD`, siempre el primer día del periodo.
- `cod_territorio`: `ES`, `CAxx`, `PRxx` o `MUxxxxx`. Códigos y nombres tomados de Maestro Territorios.
- `id_registro`: `cod_territorio` + dimensiones propias en orden + `periodo`, unidos con `_` (p. ej. `PR04_TOTAL_2026M06`).
- Valores vacíos: `-`, `..`, `.`, vacío o nota pasan a `NULL`. Un `0` literal se conserva como `0`.
- Nombres de tabla en minúsculas y de 64 caracteres como máximo; nombres de hoja de Excel de 31 caracteres como máximo y únicos.

Las decisiones de diseño con fecha y motivo están en `docs/decisiones.md`.
