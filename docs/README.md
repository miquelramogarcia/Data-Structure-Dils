# Base de datos de vivienda Dils

## Qué es el proyecto

Proyecto Python (ETL) que descarga estadísticas de vivienda de fuentes públicas de España (MIVAU, Notariado, Idealista), las transforma a un formato común y genera:

- un catálogo en Excel (`Data Dils_v2.xlsx`) con las hojas Tablas, Campos y una hoja de datos por tabla, con hipervínculos;
- un fichero `sql/create_tables.sql` con un `CREATE TABLE` por tabla y `sql/load_data.sql` con su carga, listos para MySQL;
- un CSV limpio por tabla en `etl/salida/`;
- un glosario (`etl/catalogo/glosario.csv`, también hoja Glosario del libro) y una ficha por fuente en `docs/fuentes/`.

Esquemas de base de datos: `MIVAU`, `NOTARIADO`, `IDEALISTA`.

El diseño completo está en `docs/2026-10-29-base-datos-vivienda-design.md` y el plan de implementación en `docs/plans/2026-10-29-base-datos-vivienda-fase1.md`.

## Estructura de carpetas

```
Data Dils/
  Data Dils.xlsx                  original del usuario (solo lectura; nunca se modifica)
  Data Dils_v2.xlsx               libro resultante (catálogo + hojas de datos); no se versiona
  Libro1.xlsx                     copia antigua sin versionar (ver "Pendiente de decisión del usuario")
  .gitattributes                  fija eol=lf para etl/salida/*.csv
  pytest.ini, requirements.txt
  sql/
    create_tables.sql             esquemas y CREATE TABLE (generado desde el catálogo)
    load_data.sql                 un LOAD DATA LOCAL INFILE por tabla con datos (generado)
  etl/
    catalogo/                     tablas.csv, campos.csv, glosario.csv (fuente de verdad), sql.py (genera el SQL), sembrar.py (solo se usó una vez)
    descargas/                    ficheros originales descargados (no se versionan)
    fuentes/                      un módulo por fuente (mivau_*.py)
    herramientas/                 utilidades puntuales (extraer_imagenes_xls.py, serpavi_muestra.py)
    lib/                          utilidades comunes (territorios, periodos, validación, lectores MIVAU) y maestros en CSV (municipios_ine.csv, secciones_serpavi.csv, territorios_extra.csv)
    salida/                       CSV limpio por tabla (el de SERPAVI no se versiona)
    construir_libro.py            genera Data Dils_v2.xlsx
    ejecutar_todo.py              punto de entrada para regenerarlo todo
  tests/                          tests con pytest (fixtures/ con copias de los originales)
  docs/
    README.md                     este documento
    decisiones.md                 registro de decisiones con fecha y motivo
    2026-10-29-base-datos-vivienda-design.md   diseño; plans/ trae el plan de implementación
    fuentes/<DATASET_ID>.md       ficha por fuente (19)
    fuentes/img/                  imágenes extraídas de los .xls (rótulos de columna)
```

## Catálogo y SQL

El catálogo vive en `etl/catalogo/tablas.csv` y `etl/catalogo/campos.csv` (fuente de verdad, sembrado una sola vez desde el Excel del usuario con `python -m etl.catalogo.sembrar`; no volver a ejecutarlo: sobrescribiría los cambios posteriores). Para regenerar `sql/create_tables.sql` tras cambiar el catálogo:

```
python -m etl.catalogo.sql
```

No se edita el SQL a mano. Las tablas sin campos diseñados aún se omiten. Cuando varios datasets comparten tabla se emite UN solo `CREATE TABLE` (y el mismo en la hoja Tablas del libro); su `COMMENT` es la columna opcional `descripcion_tabla` de `tablas.csv` si existe y, si no, la parte común (prefijo de palabras) de las `estadistica` de sus datasets.

## Maestro de territorios y municipios

`cargar_maestro` lee la hoja "Maestro Territorios" del usuario (Nacional, CCAA y provincias), añade `etl/lib/territorios_extra.csv` (alias de etiquetas de las fuentes) y añade `etl/lib/municipios_ine.csv`: los 8.132 municipios de la relación oficial del INE "Relación de municipios y sus códigos por comunidades autónomas y provincias", situación a 1 de enero de 2026 (`diccionario26.xlsx`, https://www.ine.es/daco/daco42/codmun/codmun.htm). El original se guarda en `etl/descargas/` (no versionado) y el CSV se regenera con `python -m etl.lib.municipios_ine_generar`. Códigos: `cod_territorio` = `MU` + CPRO + CMUN (5 dígitos); los nombres de CCAA y provincia salen del maestro del usuario. Sin `nivel`, `resolver` prefiere CCAA > Provincia > Municipio (los nombres como "Madrid" o "Soria" siguen siendo la provincia); con `nivel="Municipio"` acepta el artículo al principio o al final y cada parte de un nombre bilingüe; un nombre repetido en varias provincias da `TerritorioAmbiguo` y se resuelve con `resolver_municipio(maestro, municipio, provincia)`. La hoja "Maestro Territorios" del libro de salida es el maestro completo que devuelve `cargar_maestro` (desde la Tarea 14, 55.043 filas con municipios, distritos y secciones).

Distritos y secciones censales: `cargar_maestro` añade también `etl/lib/secciones_serpavi.csv` (10.503 distritos, `DI` + 7 dígitos, y 36.293 secciones, `SC` + 10 dígitos, del seccionado del Censo 2021 tal como lo trae SERPAVI; mismas 12 columnas, `nivel` Distrito / Seccion). Cada código cuelga de un municipio del INE. Se regenera con `python -m etl.lib.secciones_serpavi_generar etl/descargas/MIVAU-SERPAVI_AAAAMMDD.xlsx`. Estos niveles se buscan por código con `territorio_por_codigo(maestro, cod_territorio)`, nunca por nombre.

## Importar a MySQL

Orden: primero `sql/create_tables.sql` (esquemas y tablas) y después `sql/load_data.sql` (un `LOAD DATA LOCAL INFILE` por tabla con datos, leyendo `etl/salida/<tabla>.csv`). Ambos se regeneran con `python -m etl.catalogo.sql`.

```
mysql --local-infile=1 -u USUARIO -p < sql/create_tables.sql
mysql --local-infile=1 -u USUARIO -p < sql/load_data.sql     # desde la raíz del proyecto (rutas relativas)
```

- `local_infile` debe estar activo en el servidor (`SET GLOBAL local_infile = 1;`) y en el cliente (`--local-infile=1`).
- `anio`, `trimestre` y `mes` son columnas generadas (`GENERATED ALWAYS AS ... STORED`) calculadas por MySQL desde `fecha` y `frecuencia`, de modo que nunca contradicen la fecha. MySQL no admite valores explícitos en ellas, por eso `load_data.sql` las lee en variables `@omitir_*` y las descarta; el catálogo las marca en la columna `generado` de `campos.csv` (hoja Campos: "Generada como"). Los CSV conservan las tres columnas.
- En los CSV, NULL es el campo vacío: las columnas que admiten NULL se cargan con `NULLIF(@var, '')`.
- Los CSV terminan siempre en LF en cualquier sistema (`escribir_csv` fuerza `lineterminator="\n"` y `.gitattributes` fija `eol=lf` para `etl/salida/*.csv`); `load_data.sql` declara `LINES TERMINATED BY '\n'` y `ESCAPED BY ''` (pandas no escapa con barra invertida). Un test lo comprueba.
- El servidor debe usar modo SQL estricto (`STRICT_TRANS_TABLES`, el predeterminado de MySQL 8): un vacío en una columna NOT NULL debe fallar, no convertirse en 0 ni en `0000-00-00`.

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

Tras clonar: `python -m pip install -r requirements.txt`; como `etl/descargas/` no se versiona, el comando vuelve a descargar los originales. La ejecución completa (todas las fuentes más el libro) tarda unos 10 minutos y usa ~1,3 GB de memoria (pico ~3,4 GB al escribir el libro). SERPAVI es el único CSV no versionado (ver más abajo).

Al terminar las fuentes se reconstruye `Data Dils_v2.xlsx` (hojas: Tablas, Campos, Maestro Territorios, Glosario, General y una por tabla con datos). Para regenerar solo el libro, sin volver a ejecutar las fuentes, a partir de los CSV de `etl/salida/`:

```
python -c "from etl.construir_libro import construir_libro; construir_libro()"
```

El libro y los CSV: los CSV de `etl/salida/` son las tablas COMPLETAS y la fuente de la importación a MySQL; las hojas de datos del libro (ocultas: clic derecho > Mostrar) son solo una MUESTRA de cada tabla, de como mucho `FILAS_MUESTRA_LIBRO` = 1.000 filas, con la nota "Muestra: N de TOTAL filas. La tabla completa está en etl/salida/<tabla>.csv" en A1 y la cabecera en la fila 2. La columna `Filas` de la hoja Tablas da el TOTAL de filas del CSV. Regla de la muestra (`muestra_libro`, estable entre ejecuciones): orden por `fecha` descendente, `nivel` (Nacional, CCAA, Provincia, Municipio, Distrito, Seccion), `cod_territorio` e `id_registro`; cada nivel presente recibe 1.000 // nº de niveles filas (las más recientes) y el resto se rellena con las siguientes en ese orden, así aparecen todos los niveles y los periodos más recientes.

Tablas grandes: `mivau_serpavi_alquiler` (1,3 millones de filas, CSV de ~246 MB) no se versiona (está en `.gitignore`); tras clonar el repositorio hay que generarla con `python -m etl.ejecutar_todo MIVAU-SERPAVI` (descarga ~68 MB y tarda unos 2 minutos, más la construcción del libro) antes de construir el libro (si falta, el libro se construye igual y esa hoja solo lleva una nota con el comando). 

El libro se crea siempre desde cero (nunca se escribe `Data Dils.xlsx`); `Data Dils.xlsx` solo se lee, desde una copia temporal, para el Maestro Territorios y la hoja General.

## Tests

```
python -m pytest
```

La suite completa tarda unos 7 minutos. `tests/test_global.py` comprueba: 23 filas en `tablas.csv` (las que tienen esquema y tabla tienen `CREATE TABLE`; los cuatro datasets de Notariado e Idealista no tienen tabla), cabeceras de cada CSV de `etl/salida/` iguales a `campos.csv`, una ficha por cada dataset con tabla, el glosario, y que `Data Dils_v2.xlsx` (hojas ocultas incluidas) no tiene celdas con error de Excel (se salta si el libro no existe: constrúyalo antes).

## Resumen de tablas (ejecución completa de 2026-10-29)

Filas de cada CSV de `etl/salida/` tras `python -m etl.ejecutar_todo`. Todas las tablas con datos están en el esquema `MIVAU`.

| Tabla | Datasets | Filas | Ficha |
|---|---|---:|---|
| `mivau_vpo_calificaciones_definitivas` | 31205000 | 15.984 | [ficha](fuentes/MIVAU-31205000.md) |
| `mivau_vivienda_libre_iniciadas` | 32100500 | 15.984 | [ficha](fuentes/MIVAU-32100500.md) |
| `mivau_vivienda_libre_terminadas` | 32101000 | 15.984 | [ficha](fuentes/MIVAU-32101000.md) |
| `mivau_eti_transacciones` | 34010110 + ETI (34010120-34010190) | 58.320 | [34010110](fuentes/MIVAU-34010110.md), [ETI](fuentes/MIVAU-ETI.md) |
| `mivau_eti_compradores_extranjeros` | 340101g0 | 37.050 | [ficha](fuentes/MIVAU-340101g0.md) |
| `mivau_valor_medio_vivienda_libre` | 34020150, 34020160, 34020170, 34020180 | 25.920 | [34020150](fuentes/MIVAU-34020150.md), [34020160](fuentes/MIVAU-34020160.md), [34020170](fuentes/MIVAU-34020170.md), [34020180](fuentes/MIVAU-34020180.md) |
| `mivau_valor_tasado_vivienda_libre` | 35101000, 35101500, 35102000 | 18.448 | [35101000](fuentes/MIVAU-35101000.md), [35101500](fuentes/MIVAU-35101500.md), [35102000](fuentes/MIVAU-35102000.md) |
| `mivau_valor_tasado_municipios_25000` | 35103500 | 63.610 | [ficha](fuentes/MIVAU-35103500.md) |
| `mivau_precio_suelo_urbano` | 36400500 | 6.120 | [ficha](fuentes/MIVAU-36400500.md) |
| `mivau_certificados_fin_obra` | BOL09-FINOBRA | 2.912 | [ficha](fuentes/MIVAU-BOL09-FINOBRA.md) |
| `mivau_visados_direccion_obra` | BOL09-VISADOS | 2.912 | [ficha](fuentes/MIVAU-BOL09-VISADOS.md) |
| `mivau_serpavi_alquiler` | SERPAVI | 1.281.664 (CSV local, no versionado) | [ficha](fuentes/MIVAU-SERPAVI.md) |

Total: 1.544.908 filas en 12 tablas. Sin datos (`solo_diseno`): `MIVAU-57010000` (tabla prevista `mivau_indice_costes_construccion`; columnas sin rótulo en el archivo; [ficha](fuentes/MIVAU-57010000.md)) y los cuatro datasets de Notariado e Idealista (`NOT-NP-MENSUAL`, `NOT-PEN`, `IDEALISTA-ALQUILER`, `IDEALISTA-VENTA`), sin esquema, tabla ni ficha.

Avisos de la ejecución (esperados, documentados en las fichas): 7 municipios de 35103500 con la provincia heredada equivocada (`PROVINCIA_REAL`); en SERPAVI, la fila 21 de la hoja CCAA sin código, 6 filas con CPRO/CUMUN incoherentes y un recuento no entero de Valmadrid; avisos de cuadre jerárquico (2 en iniciadas, 5 en ETI, 193 en compradores extranjeros).

## Pendiente de decisión del usuario

Cada punto está marcado en `docs/decisiones.md` como pendiente de revisión del usuario.

- **Ceuta y Melilla como agregado en `340101g0`** (compradores extranjeros): la fila de vivienda "Ceuta y Melilla" no se carga y se pierden sus cifras; ES no es la suma de las comunidades cargadas. [Ficha](fuentes/MIVAU-340101g0.md).
- **Ceuta y Melilla en `34020180`** (valor medio, extranjeros residentes): se omite el agregado, no sus partes. [Ficha](fuentes/MIVAU-34020180.md).
- **Ceros de `34020180`**: 4 ceros literales (vivienda nueva de Zamora 2022T3/T4 y Albacete 2024T2/T3) cargados como 0; probablemente significan "sin operaciones". [Ficha](fuentes/MIVAU-34020180.md).
- **Ceuta y Melilla en `35101000/1500/2000`** (valor tasado): se omite el agregado; sus valores por separado sí se cargan. [Ficha](fuentes/MIVAU-35101000.md).
- **`MIVAU-57010000`** (índice de costes): `solo_diseno`; hay que confirmar los nombres de las 13 columnas, sin rótulo en el archivo. [Ficha](fuentes/MIVAU-57010000.md).
- **`BOL09-FINOBRA`**: rótulos de columna tomados de una imagen incrustada, no de texto del archivo. [Ficha](fuentes/MIVAU-BOL09-FINOBRA.md).
- **`BOL09-VISADOS`**: rótulos de columna tomados de una imagen incrustada. [Ficha](fuentes/MIVAU-BOL09-VISADOS.md).
- **Boletines ETI no cargados** (tipología del edificio, residencia del comprador, valor y superficie, etc.): decidir si interesan. [Ficha](fuentes/MIVAU-ETI.md).
- **ETI, 18 diferencias en las sumas de la rejilla** régimen x antigüedad (lista cerrada `EXCEPCIONES_IDENTIDADES`), cargadas tal cual. [Ficha](fuentes/MIVAU-ETI.md).
- **SERPAVI, fila 21 de la hoja CCAA** (total nacional sin etiqueta, solo recuentos): decidir si se carga como ES. [Ficha](fuentes/MIVAU-SERPAVI.md).
- **SERPAVI, 35 diferencias de recuento entre niveles**, todas en Navarra, cargadas tal cual. [Ficha](fuentes/MIVAU-SERPAVI.md).

Además:

- **Tarea 15 aplazada** (Notariado e Idealista): `NOT-NP-MENSUAL`, `NOT-PEN`, `IDEALISTA-ALQUILER` e `IDEALISTA-VENTA` siguen en `solo_diseno`, sin esquema, tabla ni ficha; el usuario indicó que no interesan por ahora. Si se retoman, Idealista probablemente prohíbe la extracción automática y la vía sería su acceso oficial (decisión del 2026-10-29).
- **Validación de la sintaxis MySQL pendiente**: no hay servidor MySQL ni MariaDB en la máquina, así que `sql/create_tables.sql` y `sql/load_data.sql` no se han ejecutado contra uno real.
- **`Libro1.xlsx`**: copia antigua sin versionar en la raíz; preguntar al usuario antes de borrarla.

## Convenciones

- `periodo`: `AAAAMmm` (mensual), `AAAATn` (trimestral) o `AAAA` (anual). `frecuencia` vale `M`, `T` o `A`.
- `fecha`: fecha real `AAAA-MM-DD`, siempre el primer día del periodo.
- `cod_territorio`: `ES`, `CAxx`, `PRxx` o `MUxxxxx`. Códigos y nombres tomados de Maestro Territorios.
- `id_registro`: `cod_territorio` + dimensiones propias en orden + `periodo`, unidos con `_` (p. ej. `PR04_TOTAL_2026M06`).
- Valores vacíos: `-`, `..`, `.`, vacío o nota pasan a `NULL`. Un `0` literal se conserva como `0`.
- Nombres de tabla en minúsculas y de 64 caracteres como máximo; nombres de hoja de Excel de 31 caracteres como máximo y únicos.

Las decisiones de diseño con fecha y motivo están en `docs/decisiones.md`.
