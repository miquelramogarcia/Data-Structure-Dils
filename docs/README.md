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
  Data Dils_v2.xlsx               libro resultante (catálogo + hojas de datos); no se versiona
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

No se edita el SQL a mano. Las tablas sin campos diseñados aún se omiten. Cuando varios datasets comparten tabla se emite UN solo `CREATE TABLE` (y el mismo en la hoja Tablas del libro); su `COMMENT` es la columna opcional `descripcion_tabla` de `tablas.csv` si existe y, si no, la parte común (prefijo de palabras) de las `estadistica` de sus datasets.

## Maestro de territorios y municipios

`cargar_maestro` lee la hoja "Maestro Territorios" del usuario (Nacional, CCAA y provincias), añade `etl/lib/territorios_extra.csv` (alias de etiquetas de las fuentes) y añade `etl/lib/municipios_ine.csv`: los 8.132 municipios de la relación oficial del INE "Relación de municipios y sus códigos por comunidades autónomas y provincias", situación a 1 de enero de 2026 (`diccionario26.xlsx`, https://www.ine.es/daco/daco42/codmun/codmun.htm). El original se guarda en `etl/descargas/` (no versionado) y el CSV se regenera con `python -m etl.lib.municipios_ine_generar`. Códigos: `cod_territorio` = `MU` + CPRO + CMUN (5 dígitos); los nombres de CCAA y provincia salen del maestro del usuario. Sin `nivel`, `resolver` prefiere CCAA > Provincia > Municipio (los nombres como "Madrid" o "Soria" siguen siendo la provincia); con `nivel="Municipio"` acepta el artículo al principio o al final y cada parte de un nombre bilingüe; un nombre repetido en varias provincias da `TerritorioAmbiguo` y se resuelve con `resolver_municipio(maestro, municipio, provincia)`. La hoja "Maestro Territorios" del libro de salida es el maestro completo que devuelve `cargar_maestro` (desde la Tarea 14, 55.043 filas con municipios, distritos y secciones).

Distritos y secciones censales: `cargar_maestro` añade también `etl/lib/secciones_serpavi.csv` (10.503 distritos, `DI` + 7 dígitos, y 36.293 secciones, `SC` + 10 dígitos, del seccionado del Censo 2021 tal como lo trae SERPAVI; mismas 12 columnas, `nivel` Distrito / Seccion). Cada código cuelga de un municipio del INE. Se regenera con `python -m etl.lib.secciones_serpavi_generar etl/descargas/MIVAU-SERPAVI_AAAAMMDD.xlsx`. Estos niveles se buscan por código con `territorio_por_codigo(maestro, cod_territorio)`, nunca por nombre.

## Requisitos e instalación

Python 3.13.

```
python -m pip install -r requirements.txt
```

## Cómo regenerarlo todo

```
python -m etl.ejecutar_todo                  # todas las fuentes
python -m etl.ejecutar_todo MIVAU-31205000   # solo una
```

Al terminar las fuentes se reconstruye `Data Dils_v2.xlsx` (hojas: Tablas, Campos, Maestro Territorios, Glosario, General y una por tabla con datos). Para regenerar solo el libro, sin volver a ejecutar las fuentes, a partir de los CSV de `etl/salida/`:

```
python -c "from etl.construir_libro import construir_libro; construir_libro()"
```

Tablas grandes: `mivau_serpavi_alquiler` (1,3 millones de filas, CSV de ~246 MB) no se versiona (está en `.gitignore`); tras clonar el repositorio hay que generarla con `python -m etl.ejecutar_todo MIVAU-SERPAVI` (descarga ~68 MB y tarda unos 2 minutos, más la construcción del libro) antes de construir el libro (si falta, el libro se construye igual y esa hoja solo lleva una nota con el comando). En el libro su hoja muestra las 100.000 primeras filas con una nota.

El libro se crea siempre desde cero (nunca se escribe `Data Dils.xlsx`); `Data Dils.xlsx` solo se lee, desde una copia temporal, para el Maestro Territorios y la hoja General.

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
