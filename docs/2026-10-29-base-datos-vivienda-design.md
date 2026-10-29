# Base de datos de vivienda Dils — Diseño (fase 1)

Fecha: 2026-10-29 · Estado: aprobado por el usuario (2026-10-29)

## 1. Intención

Se está construyendo, desde cero, una base de datos MySQL con estadísticas de vivienda de España procedentes de 23 fuentes públicas y privadas (MIVAU, Notariado, Idealista). El objetivo final del proyecto (largo plazo) es una **ETL completa y automatizada en Python**: descarga, limpieza y carga periódica sin intervención manual.

Esta fase 1 pone **la base**: la base de datos organizada y documentada, con todas las tablas diseñadas, su `CREATE TABLE` listo y una primera carga de datos histórica preparada para importar. Los scripts de automatización vienen después.

El fichero de trabajo es `Data Dils/Data Dils.xlsx` (el usuario lo mantiene abierto en Excel; `Libro1.xlsx` es una copia idéntica antigua).

## 2. Objetivos

1. **Catálogo completo** en el Excel:
   - Hoja **Tablas**: una fila por tabla MySQL (las 23 estadísticas de la hoja General) con esquema, nombre de tabla, estadística, origen, fuente, frecuencia, formato de origen, prioridad y una columna nueva **`CREATE TABLE`** con la sentencia MySQL completa, lista para copiar y pegar. El nombre de la tabla es un **hipervínculo** a su hoja de datos.
   - Hoja **Campos**: una fila por campo de cada tabla (tabla, campo, tipo MySQL, nulo, clave, descripción, ejemplo). Es la fuente de verdad del diseño; el `CREATE TABLE` se genera desde aquí.
   - Hoja **Maestro Territorios**: maestro de códigos territoriales (ya creada por el usuario), con fila de cabecera añadida.
2. **Una hoja de datos por tabla** con el histórico descargado, limpio y en formato común, lista para importar a MySQL.
3. **Todas las tablas comparten el mismo formato** de fechas, periodos y códigos territoriales, para que se puedan cruzar.
4. **Documentarlo todo** (petición explícita y prioritaria del usuario): cada decisión, cada fuente, cada transformación y cada limitación deben quedar escritas y fáciles de encontrar (ver §7).
5. Un fichero `.sql` con todos los `CREATE TABLE` juntos.

## 3. No objetivos (fase 1)

- No se crea ni se carga un servidor MySQL real: el entregable es el Excel + el `.sql`.
- No se programan ejecuciones automáticas, ni alertas, ni control de errores de la ETL.
- No se consiguen datos del Notariado ni de Idealista (ver §5.4).

## 4. Anti-objetivos (sería un fracaso aunque "funcione")

- Tablas con formatos de fecha, periodo o territorio distintos entre sí.
- Datos transformados a mano sin un script que permita repetirlo.
- Decisiones o limitaciones de una fuente que solo existen en la cabeza de alguien (sin documentar).
- Modificar `Data Dils.xlsx` mientras está abierto en Excel, o perder trabajo del usuario en él.

## 5. Decisiones

### 5.1 Tomadas por el usuario
- Esquema por organismo; una hoja de datos por tabla; hipervínculo desde Tablas.
- `CREATE TABLE` por tabla dentro del catálogo, listo para copiar y pegar.
- Mismo formato de fecha y de todo en todas las tablas.
- Claude descarga todos los datos él mismo desde `URL datos / API` (o `URL ficha` si no hay); el formato intermedio (CSV, XLS…) es indiferente.
- Python para descargar y transformar; los scripts serán la base de la ETL futura.
- Maestro Territorios como referencia de códigos.

### 5.2 Modelo común de todas las tablas (propuesta de Claude, basada en la tabla VPO existente)
Cada tabla tiene, en este orden:

| Grupo | Columnas |
|---|---|
| Clave | `id_registro` VARCHAR(64) PK — clave natural concatenando `cod_territorio`, las dimensiones propias y `periodo` con `_`; estable entre descargas (UPSERT) |
| Territorio | `nivel` ENUM('Nacional','CCAA','Provincia','Municipio',…), `cod_territorio` (ES / CAxx / PRxx / MUxxxxx), `cod_ccaa`, `nombre_ccaa`, `cod_provincia`, `nombre_provincia`, `cod_municipio`, `nombre_municipio` — códigos y nombres INE tomados de Maestro Territorios |
| Dimensiones propias | p. ej. `regimen`, `promotor`, `antiguedad`, `componente`… (VARCHAR, en mayúsculas, valores controlados y documentados en Campos) |
| Tiempo | `periodo` (`AAAAMmm` / `AAAATn` / `AAAA`), `frecuencia` (M/T/A), `anio`, `trimestre`, `mes`, `fecha` DATE = primer día del periodo, escrita como fecha real `AAAA-MM-DD` |
| Medidas | columnas numéricas con la unidad en el nombre o la descripción (`num_viviendas`, `precio_m2_eur`, `valor_tasado_eur_m2`, `indice`…) |
| Control | `provisional` TINYINT(1) (0 si la fuente no marca provisionalidad), `fecha_descarga` DATE (día en que se descargó el dato de la fuente) |

**Cortes de serie** (decisión del usuario, 2026-10-29): cuando una fuente publica una misma medida en varias bases o metodologías (p. ej. el índice de costes en base 2005/2010/2015), cada base se guarda como una serie separada mediante una dimensión `base` que entra en `id_registro`. No se enlazan series ni se descartan bases antiguas.

**Revisiones** (decisión del usuario, 2026-10-29): la carga reemplaza el valor anterior (UPSERT) y `fecha_descarga` deja constancia de cuándo se obtuvo. El historial completo de revisiones queda para la fase de ETL, si llega a hacer falta.

Formato largo: una fila por territorio × dimensiones × periodo.

### 5.3 Otras decisiones de Claude (modificables)
- Esquemas: `MIVAU`, `NOTARIADO`, `IDEALISTA`. Nombres de tabla `organismo_tema_detalle` en minúsculas, ≤ 64 caracteres.
- Hojas de datos con nombre corto (≤ 31 caracteres, límite de Excel); el nombre completo vive en Tablas y el hipervínculo las une.
- En CCAA uniprovinciales (Madrid, Asturias, Baleares, Cantabria, Murcia, Navarra, La Rioja, Ceuta, Melilla) se generan también las filas de nivel Provincia copiando el valor de la CCAA, para que las consultas por provincia estén completas. Se documenta en la descripción del campo `nivel`.
- Maestro Territorios: se añade cabecera; la búsqueda de alias se hace por (alias, nivel) porque hay alias repetidos entre CCAA y provincia. Se amplía con municipios (y secciones censales si SERPAVI lo requiere) a partir del INE cuando una tabla lo necesite.
- Correcciones del libro existente: `provisional` `#REF!` → 0; columna `KPIs` `#VALUE!` → vacía con nota; se eliminan el vínculo externo a `Dils_Catalogo_Fuentes_DWH_2.xlsx` y los 49 nombres definidos que dependen de él; `fecha` pasa de número de serie a fecha; se completan textos truncados de Tablas desde General.
- Ceros: se conservan como 0 si la fuente trae 0; si trae "-", ".." o vacío → NULL. Se documenta por tabla.
- Si un dataset de General resulta contener varias medidas o tablas en origen (p. ej. MIVAU-31205000 con desgloses, ETI), se decide en ese momento si es una tabla con dimensión extra o varias tablas, y se documenta.

- **Fuente de verdad del catálogo** (decisión de Claude): `Data Dils.xlsx` sigue siendo el libro del usuario y nunca se sobrescribe. Los scripts leen de él General, Campos y Maestro Territorios (solo lectura) y generan un libro nuevo de salida. Cuando el usuario lo valide, decide si ese libro sustituye al original. Los cambios de diseño que proponga Claude se apuntan en `docs/decisiones.md` y se aplican en el libro de salida.
- **Desgloses que no son territorios INE** (decisión de Claude), como el tamaño de municipio, los municipios de más de 25.000 habitantes, la comunidad del comprador o los extranjeros residentes. Van como **dimensiones propias** de la tabla, nunca como códigos inventados en Maestro Territorios. `cod_territorio` siempre es un territorio INE real. Cuando hay dos territorios por fila (comunidad del comprador y comunidad de la vivienda), el principal es el de la vivienda y el otro va en columnas extra `cod_ccaa_comprador` / `nombre_ccaa_comprador`. Si la dimensión forma parte de la clave, entra en `id_registro`.
- **Fuentes del MIVAU sin fichero descargable** (decisión de Claude): si el MIVAU solo publica tablas HTML en su web, se extraen de ahí, porque son datos públicos de la Administración. Se documenta en la ficha de la fuente. Esto no aplica a Idealista ni al Notariado (ver §5.4).

### 5.4 Fuentes sin descarga (Notariado ×2, Idealista ×2)
Se catalogan con diseño completo (Tablas, Campos, `CREATE TABLE`) pero **sin datos** en fase 1. Idealista probablemente prohíbe la extracción automática; la vía sería acceso oficial (idealista/data). Pendiente de decisión del usuario más adelante.

## 6. Entregables y estructura de carpeta

```
Data Dils/
  Data Dils.xlsx                  ← original del usuario (no se toca mientras esté abierto)
  Data Dils_v2.xlsx               ← libro resultante (catálogo + hojas de datos)  [nombre a confirmar]
  sql/create_tables.sql           ← todos los CREATE TABLE
  etl/
    descargas/                    ← ficheros originales descargados (con fecha de descarga)
    scripts/                      ← un script por dataset + utilidades comunes (territorios, periodos)
    salida/                       ← CSV limpio por tabla (lo mismo que va a la hoja)
  docs/
    README.md                     ← qué es el proyecto, cómo está organizado, cómo regenerar todo
    decisiones.md                 ← registro de decisiones con fecha y motivo
    fuentes/<dataset>.md          ← ficha por fuente: URL, qué se descargó, cuándo, transformaciones, problemas, limitaciones
```

El libro se regenera por script (catálogo + hojas + hipervínculos + `CREATE TABLE`) desde Campos y los CSV limpios, para que sea repetible.

> Nota (Tarea 16): en el código final la carpeta `etl/scripts/` de este esquema es `etl/fuentes/` (un módulo por fuente) más `etl/lib/` (utilidades comunes), `etl/catalogo/` y `etl/herramientas/`; la estructura real está en `docs/README.md`.

## 7. Documentación (requisito explícito)

- Se documenta **a medida que se avanza**, no al final: cada dataset procesado deja su ficha en `docs/fuentes/` y su línea en `decisiones.md` antes de pasar al siguiente.
- La hoja **Glosario** (hoy vacía) se rellena con los términos del dominio (VPO, calificación definitiva, ETI, valor tasado, asking price, sección censal…) y con las convenciones de códigos.
- Cada campo en Campos lleva descripción completa y ejemplo real.
- El README explica cómo volver a ejecutar las descargas y regenerar el Excel.

## 8. Validaciones por tabla

- Sin `id_registro` duplicados; sin celdas de error.
- Todos los `cod_territorio` existen en Maestro Territorios.
- Tipos y nulos coherentes con Campos; longitudes dentro de lo declarado.
- Cuadre jerárquico cuando la fuente lo permita (Nacional = Σ CCAA = Σ Provincias), documentando excepciones.
- Comparación puntual de 2-3 valores contra la fuente original.
- El `CREATE TABLE` generado se valida sintácticamente (p. ej. contra un MySQL/MariaDB local o un parser) si es viable.

## 9. Riesgos conocidos

- URLs del MIVAU marcadas como "Parcial" o "por confirmar" en General: pueden haber cambiado o no ser accesibles.
- Formatos XLS antiguos con cabeceras multinivel y notas: la limpieza será específica por fichero.
- SERPAVI pesa ~68 MB y llega a sección censal: puede exceder lo razonable para una hoja de Excel (límite 1.048.576 filas); en ese caso los datos irían solo a CSV y la hoja tendría una muestra + nota.

## 10. Lo que queda a criterio del implementador

Orden de procesamiento de datasets (sugerido: los de prioridad 1 de MIVAU con descarga directa primero), nombres concretos de tablas y columnas de medida, librerías Python, y la estructura interna de los scripts.
