# Maestros como tablas MySQL: decisiones pendientes (PROTOTIPO, Tarea 17)

Estado: prototipo. Nada de esto toca `sql/create_tables.sql`, `sql/load_data.sql` ni `etl/catalogo/*.csv`.
Se regenera con `python -m prototipos.maestros.generar`. Para pasarlo a producción hay que responder:

## Preguntas

1. **¿FK reales o solo documentadas?** `maestros_fk.sql` crea 2 FK por tabla con datos (24 en total) hacia
   `dim_territorio(cod_territorio)` y `dim_periodo(periodo)`. En cargas masivas las FK ralentizan y obligan a cargar
   primero los maestros. Opción intermedia: crearlas después de la carga, o dejarlas solo como comprobación en los
   tests (ya existe: todo `cod_territorio` y `periodo` de `etl/salida/*.csv` está en las dimensiones).
2. **¿Esquema `MAESTROS` aparte o cada maestro dentro de cada esquema?** Aparte evita duplicar y sirve a MIVAU,
   NOTARIADO e IDEALISTA, pero las FK cruzan esquemas (necesitan permisos y que ambos usen la misma colación,
   `utf8mb4_spanish_ci`, como ahora).
3. **¿Se incluyen secciones censales y distritos?** El prototipo SÍ los incluye (55.000 filas en `dim_territorio`,
   unas 46.800 de ellas Distrito/Sección de SERPAVI; el CSV pesa 5,5 MB). Son necesarios para SERPAVI e Idealista,
   pero engordan la dimensión y el repositorio. Alternativa: dimensión aparte `dim_seccion`.
4. **¿`dim_categoria` genérica o una tabla por categoría?** Se prototipó la genérica `(dimension, codigo)`: simple,
   pero la FK compuesta no encaja con el diseño actual (cada tabla guarda solo `codigo`), por eso esas relaciones
   solo se documentan en `maestros_fk.sql`. Una tabla por dimensión (`dim_regimen`, `dim_antiguedad`...) permite FK
   reales y tipos precisos, a costa de más tablas. Además, la `descripcion` hoy es el propio código salvo en
   `cod_ccaa_comprador`: ¿quién escribe las descripciones legibles?
5. **¿Códigos INE de municipio versionados por año?** `dim_territorio` usa la relación a 1-1-2026: un municipio
   que cambió de código o desapareció no se puede resolver para años antiguos. Opciones: columnas
   `vigente_desde/vigente_hasta` y clave `(cod_territorio, vigente_desde)`, o mantener solo el último código.

## Decisiones tomadas en el prototipo (revisables)

- **Solapamiento con las columnas generadas.** `anio`, `trimestre` y `mes` ya son columnas STORED generadas en las
  tablas de datos (`campos.csv`, columna `generado`). Por eso `dim_periodo` solo modela
  `periodo / frecuencia / fecha / fecha_fin / periodo_padre` y NO repite anio/trimestre/mes. Si se quiere unir por
  trimestre o año, se hace con `periodo_padre` o `YEAR(fecha)`. Pregunta: ¿se quieren añadir de todos modos para
  consultas que no pasen por las tablas de datos?
- **Rango de `dim_periodo`: 1990-2030** (el brief decía 2004-2030, pero hay datos desde 1991M11 en fin de obra y
  1995 en valor tasado). 612 filas: años, trimestres y meses, con padres antes que hijos para poder cargar con la
  FK propia (`periodo_padre`).
- **`dim_territorio`: una fila por `cod_territorio`** (55.000). Los alias (46.838) van a `dim_territorio_alias`
  con clave sustituta `id_alias`; se omiten los alias que, normalizados, coinciden con el nombre oficial (el
  resolver los encuentra por `nombre_territorio`). Los aliases de Distrito/Sección de SERPAVI son la mayoría.
- **Tipos de FK**: `cod_territorio` es `VARCHAR(8)` o `VARCHAR(12)` según la tabla y `VARCHAR(12)` en la
  dimensión; MySQL lo admite en FK de cadenas con la misma colación.
- **`dim_categoria`** se alimenta de los CSV de `etl/salida/`; `tipologia` (SERPAVI) va fijada en el código
  porque su CSV no se versiona. `mivau_indice_costes_construccion` (solo_diseno) no entra.
- **Hoja del libro**: `Maestros (prototipo)` la añade `python -m prototipos.libro` mediante el parámetro opcional
  `hojas_extra` de `construir_libro`; `python -m etl.ejecutar_todo` no la incluye.

## Archivos

`generar.py`, `maestros.sql` (DDL + LOAD DATA), `maestros_fk.sql`, `datos/*.csv`, `hoja_libro.py`.
Orden de carga: `create_tables.sql` → `maestros.sql` → `load_data.sql` → `maestros_fk.sql`.
