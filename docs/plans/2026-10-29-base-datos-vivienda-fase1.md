# Base de datos de vivienda Dils — Fase 1 — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** catálogo MySQL completo (23 tablas con su `CREATE TABLE`) y datos históricos de las fuentes descargables del MIVAU, limpios y en un formato común, en un libro Excel generado por script y listo para importar.

**Arquitectura:** el proyecto se organiza así:
- **Librerías comunes** (`etl/lib/`): periodos, territorios, modelo común, validación, descarga y lectura de los boletines del MIVAU.
- **Un módulo por fuente** (`etl/fuentes/`): convierte el archivo descargado en un CSV limpio en `etl/salida/`.
- **Catálogo** (`etl/catalogo/tablas.csv`, `campos.csv`): es la fuente de verdad del diseño. Se siembra a partir del Excel del usuario y genera los `CREATE TABLE`.
- **Script final** (`etl/construir_libro.py`): monta el libro de salida a partir del catálogo y de los CSV. El libro del usuario solo se lee, y siempre desde una copia temporal.

**Tecnología:** Python 3.13, pandas, openpyxl, xlrd (archivos `.xls`), requests y pytest.

**Diseño de referencia:** `docs/2026-10-29-base-datos-vivienda-design.md`. Quien ejecute el plan debe leer los dos documentos.

## Restricciones globales

- Todo el trabajo vive en `C:\Users\miquel.ramo\ClaudeSP\Data Dils\`, que será su propio repositorio git. El repositorio padre `ClaudeSP` no se toca.
- Nunca se escribe en `Data Dils.xlsx`. Para leerlo, primero se copia a un archivo temporal (puede estar abierto en Excel).
- Libro de salida: `Data Dils_v2.xlsx`.
- Columnas comunes, en este orden:
  - **Clave:** `id_registro`.
  - **Territorio:** `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, `cod_provincia`, `nombre_provincia`, `cod_municipio`, `nombre_municipio`.
  - **Dimensiones propias** de cada tabla (incluida `base` cuando exista).
  - **Tiempo:** `periodo`, `frecuencia`, `anio`, `trimestre`, `mes`, `fecha`.
  - **Medidas.**
  - **Control:** `provisional`, `fecha_descarga`.
- `periodo` se escribe `AAAAMmm` (mensual), `AAAATn` (trimestral) o `AAAA` (anual). `frecuencia` vale `M`, `T` o `A`. `fecha` es una fecha real `AAAA-MM-DD`, siempre el primer día del periodo.
- `cod_territorio` toma la forma `ES`, `CAxx`, `PRxx` o `MUxxxxx`. Los códigos y nombres salen siempre de Maestro Territorios.
- `id_registro` = `cod_territorio` + las dimensiones en el orden de Campos + `periodo`, unidos con `_`. Ejemplo: `PR04_TOTAL_2026M06`.
- En las comunidades de una sola provincia (`03`, `04`, `06`, `13`, `14`, `15`, `17`, `18`, `19`), si la fuente no trae la fila de provincia, se genera copiando la de la comunidad.
- Valores vacíos:
  - `-`, `..`, `.`, un vacío o una nota → `NULL`;
  - un `0` literal se queda como `0`.
- `provisional` = 0 salvo que la fuente marque el dato como provisional.
- Esquemas `MIVAU`, `NOTARIADO` e `IDEALISTA`. Tablas en minúsculas y como máximo 64 caracteres. Hojas de Excel con 31 caracteres como máximo y nombre único.
- **Documentar a medida que se avanza** (requisito explícito del usuario). Cada tarea que trata una fuente deja:
  - su ficha en `docs/fuentes/<DATASET_ID>.md`, con este orden: URL, archivo y fecha de descarga, estructura del original, transformaciones, decisiones, limitaciones y valores comprobados;
  - una línea con fecha en `docs/decisiones.md` por cada decisión.

## Riesgos que vigilar en la revisión

1. **Nombre de territorio que no está en el maestro** (variantes como "Alicante", "Andalucía " con espacio, mayúsculas, "Total Nacional"). El proceso debe parar con un error que nombre el texto, nunca saltarse la fila. Se cubre con el test `test_resolver_desconocido_falla` de la Tarea 2.
2. **Celdas `-`, `..` o vacías.** Deben convertirse en NULL, no en 0. Se cubre con `test_valor_vacio_es_nulo` de la Tarea 5.
3. **Columnas de total anual o de media mezcladas con las de meses o trimestres** en las matrices del MIVAU. No pueden convertirse en un periodo. Se cubre con `test_columna_total_ignorada` de la Tarea 5.
4. **Nombres de hoja cortados a 31 caracteres que acaban repetidos.** Hay que desempatarlos y el enlace debe apuntar a la hoja correcta. Se cubre con `test_nombres_hoja_unicos` de la Tarea 7.
5. **Tabla de más de 1.048.576 filas** (SERPAVI). La hoja muestra una muestra con nota, el CSV guarda la tabla completa y el proceso no se rompe. Se cubre con `test_tabla_grande_hoja_muestra` de la Tarea 7.

---

### Tarea 1: Estructura del proyecto

**Archivos:**
- Crear: `.gitignore`, `requirements.txt`, `pytest.ini`, `etl/__init__.py`, `etl/lib/__init__.py`, `etl/fuentes/__init__.py`, `tests/__init__.py`, `docs/README.md`, `docs/decisiones.md`

- [ ] **Paso 1:** ejecutar `git init` en `Data Dils/`. `.gitignore` excluye `etl/descargas/`, `~$*`, `__pycache__/`, `.venv/` y `*_v2.xlsx`. Los `.xlsx` del usuario sí se versionan, para tener historial.
- [ ] **Paso 2:** `requirements.txt` con `pandas`, `openpyxl`, `xlrd`, `requests` y `pytest`. Instalar con `python -m pip install -r requirements.txt`.
- [ ] **Paso 3:** `docs/README.md` con qué es el proyecto, la estructura de carpetas (sección 6 del diseño) y cómo regenerarlo todo (`python -m etl.ejecutar_todo`). Los apartados aún vacíos se marcan "pendiente".
- [ ] **Paso 4:** `docs/decisiones.md` con una tabla `Fecha | Decisión | Motivo | Quién`. Copiar como filas las decisiones de las secciones 5.1 a 5.4 del diseño.
- [ ] **Paso 5:** ejecutar `pytest`. Resultado esperado: "no tests ran", sin errores.
- [ ] **Paso 6:** commit `chore: estructura inicial del proyecto Dils`.

### Tarea 2: Periodos y territorios

**Archivos:**
- Crear: `etl/lib/periodos.py`, `etl/lib/territorios.py`, `tests/test_periodos.py`, `tests/test_territorios.py`

**Interfaces que produce:**
- `periodo_mensual(anio: int, mes: int) -> dict`, `periodo_trimestral(anio: int, trimestre: int) -> dict` y `periodo_anual(anio: int) -> dict`. Devuelven las claves `periodo, frecuencia, anio, trimestre, mes, fecha`; `fecha` es un `datetime.date`, y `trimestre`/`mes` valen `None` cuando no aplican.
- `mes_desde_texto(txt: str) -> int`. Acepta "Ene.", "enero", "ENE" y "Sept.".
- `normalizar(txt: str) -> str`: minúsculas, sin tildes, espacios recortados y colapsados.
- `class TerritorioDesconocido(ValueError)`.
- `cargar_maestro(xlsx: Path) -> pd.DataFrame`. Copia el archivo a un temporal, lee la hoja "Maestro Territorios" y le pone estas cabeceras: `alias, nivel, cod_territorio, cod_ccaa, nombre_ccaa, cod_provincia, nombre_provincia, cod_municipio, nombre_municipio, nombre_territorio, fuente_alias, cod_fuente_alias`. Lo detecta solo si la fila 1 ya trae cabeceras.
- `resolver(maestro: pd.DataFrame, texto: str, nivel: str | None = None) -> dict`. Busca por `normalizar(texto)` en `alias` y en `normalizar(nombre_territorio)`. Si encuentra varias filas sin `nivel`, prefiere CCAA. Devuelve las 8 columnas de territorio, con `None` en lugar de NaN.
- `expandir_uniprovinciales(df: pd.DataFrame, maestro: pd.DataFrame) -> pd.DataFrame`.
- `etl/lib/territorios_extra.csv`: alias adicionales con las mismas columnas. `cargar_maestro` los añade al maestro. Aquí van las variantes que aparezcan en cada fuente (la Tarea 5 y siguientes añaden filas, cada una con su línea en decisiones).

- [ ] **Paso 1: tests**

```python
def test_periodo_mensual():
    assert periodo_mensual(2026, 6) == {"periodo": "2026M06", "frecuencia": "M", "anio": 2026,
        "trimestre": None, "mes": 6, "fecha": date(2026, 6, 1)}
def test_periodo_trimestral():
    p = periodo_trimestral(2025, 3); assert (p["periodo"], p["fecha"], p["mes"]) == ("2025T3", date(2025, 7, 1), None)
def test_periodo_anual():
    assert periodo_anual(2024)["fecha"] == date(2024, 1, 1) and periodo_anual(2024)["periodo"] == "2024"
def test_mes_desde_texto():
    assert [mes_desde_texto(t) for t in ["Ene.", "Sept.", "DICIEMBRE"]] == [1, 9, 12]
def test_resolver_provincia():
    assert resolver(M, "Almería")["cod_territorio"] == "PR04"
def test_resolver_total_nacional():
    assert resolver(M, "TOTAL NACIONAL")["cod_territorio"] == "ES"
def test_resolver_ambiguo_por_nivel():
    assert resolver(M, "Cantabria")["cod_territorio"] == "CA06"
    assert resolver(M, "Cantabria", nivel="Provincia")["cod_territorio"] == "PR39"
def test_resolver_desconocido_falla():
    with pytest.raises(TerritorioDesconocido, match="Atlantis"): resolver(M, "Atlantis")
def test_expandir_uniprovinciales():  # 1 fila CA13 → se añade PR28 con el mismo valor; CA01 no se toca
```
`M` es un fixture que hace `cargar_maestro(Path("Data Dils.xlsx"))`.

- [ ] **Paso 2:** ejecutar `pytest tests/test_periodos.py tests/test_territorios.py -v`. Esperado: FAIL (import).
- [ ] **Paso 3:** implementar las interfaces de arriba.
- [ ] **Paso 4:** volver a ejecutar los tests. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: periodos y territorios comunes`.

### Tarea 3: Modelo común y validación

**Archivos:**
- Crear: `etl/lib/modelo.py`, `etl/lib/validar.py`, `tests/test_modelo.py`

**Interfaces que consume:** las de la Tarea 2.

**Interfaces que produce:**
- `COLUMNAS_TERRITORIO: list[str]`, `COLUMNAS_TIEMPO: list[str]`, `COLUMNAS_CONTROL = ["provisional", "fecha_descarga"]`.
- `construir_tabla(df: pd.DataFrame, dimensiones: list[str], medidas: list[str], fecha_descarga: date) -> pd.DataFrame`.
  - Recibe filas que ya tienen las columnas de territorio, de tiempo, `dimensiones` y `medidas`.
  - Calcula `id_registro`, pone `provisional` = 0 si falta, añade `fecha_descarga` y ordena las columnas como indican las restricciones globales.
- `validar_tabla(df: pd.DataFrame, campos: pd.DataFrame, maestro: pd.DataFrame) -> list[str]`. Devuelve los errores en texto (una lista vacía significa que está bien). Comprueba:
  - que no haya `id_registro` duplicados;
  - que no haya celdas de error (`#REF!`, `#VALUE!`…);
  - que todos los `cod_territorio` estén en el maestro;
  - que no haya nulos donde Campos dice `NO`;
  - longitudes de VARCHAR/CHAR;
  - que los ENUM tengan valores permitidos;
  - que las columnas coincidan exactamente con Campos, en el mismo orden.
- `cuadre_jerarquico(df: pd.DataFrame, medida: str, dimensiones: list[str]) -> pd.DataFrame`. Devuelve los periodos y dimensiones en los que Nacional ≠ suma de CCAA o CCAA ≠ suma de sus provincias. Solo informa, no bloquea.

- [ ] **Paso 1: tests**
  - `test_id_registro`: con `dimensiones=["regimen"]`, la fila PR04/TOTAL/2026M06 da `"PR04_TOTAL_2026M06"`.
  - `test_orden_columnas`: el orden coincide con las restricciones globales.
  - `test_validar_detecta_duplicado` y `test_validar_detecta_territorio_inexistente`.
  - `test_validar_detecta_error_excel`: una celda con `"#REF!"` da un error que nombra la columna.
  - `test_cuadre_detecta_descuadre`.
- [ ] **Paso 2:** ejecutar `pytest tests/test_modelo.py -v`. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** volver a ejecutar los tests. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: modelo común y validación de tablas`.

### Tarea 4: Catálogo y generador de CREATE TABLE

**Archivos:**
- Crear: `etl/catalogo/sembrar.py`, `etl/catalogo/tablas.csv`, `etl/catalogo/campos.csv`, `etl/catalogo/sql.py`, `sql/create_tables.sql`, `tests/test_sql.py`

**Interfaces que produce:**
- `sembrar(xlsx: Path) -> None`. Se ejecuta una sola vez. Lee del Excel del usuario las hojas Tablas, Campos y General.
  - `tablas.csv` lleva las columnas: `dataset_id, esquema, tabla, hoja, estadistica, origen, fuente, frecuencia, formato_origen, prioridad, estado`, donde `estado` es `con_datos`, `solo_diseno` o `pendiente`.
  - Une Tablas y General por el texto de la estadística, normalizado, y completa los textos cortados con los de General.
  - `campos.csv` = Campos con las mismas cabeceras (`tabla, campo, tipo_mysql, nulo, clave, descripcion, ejemplo`).
  - En la tabla de VPO añade el campo `fecha_descarga` (`DATE`, `NO`, descripción "Día en que se descargó el dato de la fuente").
- `cargar_catalogo() -> tuple[pd.DataFrame, pd.DataFrame]`.
- `create_table_sql(esquema: str, tabla: str, campos: pd.DataFrame) -> str`.
  - Formato: `CREATE TABLE IF NOT EXISTS `esquema`.`tabla` (`, una columna por línea con `NOT NULL`/`NULL`, `COMMENT` con la descripción (escapando `'`), `PRIMARY KEY (...)` e `INDEX idx_<campo> (<campo>)` para cada clave INDEX, y al final `) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci COMMENT='<estadistica>';`.
  - Antes, `CREATE SCHEMA IF NOT EXISTS` solo en el archivo `.sql` completo.
- `escribir_sql(salida: Path) -> None`.

- [ ] **Paso 1: tests**
  - `test_create_vpo_contiene_pk`: `"PRIMARY KEY (`id_registro`)"` está en el SQL de `mivau_vpo_calificaciones_definitivas`.
  - `test_create_nullable`: `cod_provincia` está como `NULL` y `nivel` como `NOT NULL`.
  - `test_create_escapa_comillas`: una descripción con `'` sale como `''`.
  - `test_create_index`: aparece `INDEX `idx_fecha` (`fecha`)`.
- [ ] **Paso 2:** ejecutar los tests. Esperado: FAIL.
- [ ] **Paso 3:** implementar. Ejecutar `python -m etl.catalogo.sembrar` y revisar `tablas.csv` a mano: deben salir 23 filas y cada `dataset_id` de General debe quedar asignado a una tabla.
- [ ] **Paso 4:** ejecutar los tests (PASS). Si hay MySQL o MariaDB en la máquina (`where mysql`), cargar `sql/create_tables.sql` en un esquema temporal. Si no lo hay, apuntar en decisiones que esta validación queda pendiente.
- [ ] **Paso 5:** commit `feat: catálogo de tablas y generador CREATE TABLE`.

### Tarea 5: Descarga y lector de boletines del MIVAU

**Archivos:**
- Crear: `etl/lib/mivau.py`, `tests/test_mivau.py`, `tests/fixtures/31205000_muestra.xls`

**Interfaces que produce:**
- `descargar(url: str, dataset_id: str, destino: Path = Path("etl/descargas")) -> Path`. Guarda el archivo como `<dataset_id>_<AAAAMMDD>.<ext>` y, si ya existe el de hoy, no vuelve a descargarlo.
- `leer_matriz(path: Path, hojas: list[str] | None = None) -> pd.DataFrame`. Devuelve un formato largo con las columnas `hoja, territorio_txt, anio, subperiodo_txt, valor_txt`.
  - Detecta en cada hoja dos cabeceras: la fila del año (con "AAAA", "Año AAAA" o "AAAA por meses") y la del subperiodo (meses o trimestres).
  - Las filas de territorio son las que tienen texto en la columna B y números a la derecha.
  - Descarta las columnas de total o media ("Total", "Media", "Año") y las filas de notas o fuente.
- `a_numero(valor_txt) -> float | None`. `-`, `..`, `.`, vacío o texto devuelven `None`; `0` devuelve `0.0`.
- `subperiodo(txt: str) -> tuple[str, int]`. Devuelve `("M", mes)` o `("T", trimestre)`. Acepta "1T", "1º T", "Trimestre 1", "I"–"IV" y los nombres de mes.

- [ ] **Paso 1:** guardar como fixture un recorte del `31205000.XLS` real (cabecera + 3 territorios + 14 meses, incluida una columna de total si la hay).
- [ ] **Paso 2: tests**
  - `test_leer_matriz_vpo`: la fila TOTAL NACIONAL, 2008, Ene. da el valor `4918`.
  - `test_valor_vacio_es_nulo`: `a_numero("-") is None` y `a_numero("0") == 0.0`.
  - `test_columna_total_ignorada`: ningún `subperiodo_txt` del resultado se llama "Total" ni "Media".
  - `test_subperiodo_trimestre`: `subperiodo("3º T") == ("T", 3)` y `subperiodo("Ene.") == ("M", 1)`.
- [ ] **Paso 3:** ejecutar los tests (FAIL), implementar y volver a ejecutarlos (PASS).
- [ ] **Paso 4:** commit `feat: descarga y lector de matrices de boletines MIVAU`.

### Tarea 6: Tabla de referencia — VPO (MIVAU-31205000)

**Archivos:**
- Crear: `etl/fuentes/mivau_31205000.py`, `etl/fuentes/__init__.py` (registro), `etl/ejecutar_todo.py`, `tests/test_fuente_vpo.py`, `docs/fuentes/MIVAU-31205000.md`

**Interfaces que produce:** el patrón que siguen todas las fuentes:
- `DATASET_ID: str`, `TABLA: str`, `DIMENSIONES: list[str]`, `MEDIDAS: list[str]`.
- `ejecutar(fecha_descarga: date) -> pd.DataFrame`. Descarga, lee, resuelve territorios, construye la tabla, valida (lanza un error si `validar_tabla` devuelve algo) y escribe `etl/salida/<TABLA>.csv` en UTF-8, separado por `;`, con las fechas en ISO.
- `REGISTRO: dict[str, module]` en `etl/fuentes/__init__.py`.
- `etl/ejecutar_todo.py`: `python -m etl.ejecutar_todo [DATASET_ID ...]` ejecuta las fuentes indicadas (o todas), imprime filas y avisos de cuadre, y al final llama a `construir_libro` cuando exista (Tarea 7).

- [ ] **Paso 1: tests** (con el archivo descargado)
  - `test_vpo_valores_conocidos`: ES 2008M01 = 4918 y ES 2008M02 = 5075.
  - `test_vpo_uniprovinciales`: existe `PR28_TOTAL_<último periodo>` con el mismo valor que `CA13`.
  - `test_vpo_coincide_con_hoja_actual`: para los niveles Nacional y CCAA, todas las filas de la hoja actual `mivau_vpo_calificaciones_defini` tienen el mismo `num_viviendas` en el CSV nuevo. Las diferencias se aceptan solo si la fuente ha revisado el dato, y en ese caso se listan en la ficha.
  - `test_vpo_validacion_limpia`: `validar_tabla` devuelve `[]`.
- [ ] **Paso 2:** ejecutar los tests. Esperado: FAIL.
- [ ] **Paso 3:** implementar `mivau_31205000.py` (`DIMENSIONES=["regimen"]`, siempre `"TOTAL"`; `MEDIDAS=["num_viviendas"]`).
- [ ] **Paso 4:** ejecutar los tests (PASS) y `python -m etl.ejecutar_todo MIVAU-31205000`. Anotar en la ficha cuántos periodos no cuadran entre comunidades y provincias.
- [ ] **Paso 5:** escribir la ficha `docs/fuentes/MIVAU-31205000.md` y las líneas correspondientes en decisiones (provisional 0, uniprovinciales, fecha_descarga). Commit `feat: fuente VPO 31205000 como tabla de referencia`.

### Tarea 7: Constructor del libro de salida

**Archivos:**
- Crear: `etl/construir_libro.py`, `tests/test_construir_libro.py`

**Interfaces que consume:** `cargar_catalogo`, `create_table_sql`, `cargar_maestro` y los CSV de `etl/salida/`.

**Interfaces que produce:** `construir_libro(origen: Path = Path("Data Dils.xlsx"), salida: Path = Path("Data Dils_v2.xlsx")) -> None`. El libro de salida tiene estas hojas, en orden:
1. **Tablas:** las columnas del usuario más `Estado`, `Filas` y `CREATE TABLE`. La celda de la tabla es un hipervínculo interno (`#'<hoja>'!A1`) cuando hay datos.
2. **Campos.**
3. **Maestro Territorios:** con cabecera.
4. **Glosario:** desde `etl/catalogo/glosario.csv`.
5. **General:** la del usuario, con la columna KPIs vacía y una nota en la cabecera.
6. **Una hoja por tabla con datos.**

Detalles:
- Fuente Arial y cabecera en negrita con fila inmovilizada.
- `fecha` y `fecha_descarga` con formato `yyyy-mm-dd`.
- Los códigos (`cod_*`) como texto, para no perder los ceros a la izquierda.
- Sin vínculos externos ni nombres definidos.
- `nombre_hoja(tabla: str, usados: set[str]) -> str`: recorta a 31 caracteres y, si choca con otra, desempata con `~2`, `~3`…
- Si una tabla supera 1.048.575 filas, la hoja muestra las primeras 100.000 con una nota en A1 que remite al CSV, y la columna `Filas` de Tablas indica el total.

- [ ] **Paso 1: tests**
  - `test_hipervinculo_apunta_a_hoja`: la celda de la tabla de VPO tiene `hyperlink.location == "'<hoja>'!A1"`.
  - `test_nombres_hoja_unicos`: dos tablas con los mismos 31 primeros caracteres dan hojas distintas.
  - `test_sin_vinculos_externos`: `wb._external_links == []` y no hay nombres definidos.
  - `test_fecha_es_fecha`: la celda `fecha` de la primera fila de datos es un `datetime` con formato `yyyy-mm-dd`.
  - `test_tabla_grande_hoja_muestra`: un CSV sintético de 1.100.000 filas genera una hoja con nota y la columna `Filas` = 1100000. Se puede marcar como lento.
- [ ] **Paso 2:** ejecutar los tests (FAIL), implementar y volver a ejecutarlos (PASS).
- [ ] **Paso 3:** ejecutar `python -m etl.ejecutar_todo MIVAU-31205000`, abrir `Data Dils_v2.xlsx` con openpyxl y comprobar que tiene las 6 hojas y que el enlace funciona.
- [ ] **Paso 4:** actualizar el README (cómo regenerar el libro). Commit `feat: constructor del libro Excel de salida`.

### Tareas 8 a 14: una fuente del MIVAU por tarea

Todas siguen el patrón de la Tarea 6, con los mismos pasos:
1. Descargar y anotar la estructura en la ficha.
2. Añadir a `campos.csv` los campos propios de la tabla, con descripción y ejemplo real, y regenerar el SQL.
3. Escribir los tests:
   - dos valores conocidos leídos a mano del archivo original y copiados en el test (primer y último periodo de ES);
   - `validar_tabla == []`;
   - el cuadre jerárquico (o su excepción documentada).
4. Implementar el módulo y registrarlo.
5. Ejecutar.
6. Completar la ficha y decisiones.
7. Hacer commit.

Si el archivo no tiene la estructura prevista, se decide en la propia tarea (una tabla con dimensión extra o varias tablas) y se apunta en decisiones.

| Tarea | Dataset(s) | Tabla(s) propuesta(s) | Dimensiones / medidas previstas |
|---|---|---|---|
| 8 | MIVAU-32100500, MIVAU-32101000 | `mivau_vivienda_libre_iniciadas`, `mivau_vivienda_libre_terminadas` | — / `num_viviendas` (mensual) |
| 9 | MIVAU-34010110, MIVAU-340101g0 | `mivau_eti_transacciones`, `mivau_eti_compradores_extranjeros` | `tipo_vivienda` si existe / `num_transacciones`. En 340101g0 la comunidad de la vivienda va en el territorio y se añaden las columnas `cod_ccaa_comprador` y `nombre_ccaa_comprador`, que entran en `id_registro` |
| 10 | MIVAU-34020150/160/170/180 | `mivau_valor_medio_vivienda_libre` | `tipo_comprador` (TOTAL / EXTRANJERO_RESIDENTE), `antiguedad` (TOTAL / NUEVA / SEGUNDA_MANO) / `valor_medio_eur` (trimestral, varias hojas por grupo de años). Se decide si es una tabla o cuatro tras ver los archivos |
| 11 | MIVAU-35101000/1500/2000/3500 | `mivau_valor_tasado_vivienda_libre` (+ `mivau_valor_tasado_municipios_25000` para 3500) | `antiguedad` (TOTAL / HASTA_5 / MAS_5) / `valor_tasado_eur_m2`. Para 3500 hay que ampliar el maestro con los municipios del INE (descargar la relación de municipios del INE a `etl/lib/municipios_ine.csv`; `cargar_maestro` añade los MU) |
| 12 | MIVAU-36400500, MIVAU-57010000 | `mivau_precio_suelo_urbano`, `mivau_indice_costes_construccion` | Suelo: `tamano_municipio` / `precio_eur_m2`, `num_transacciones` si existe. Costes: `componente`, `base` / `indice` (nacional; las filas son años y los meses van en columnas, así que necesita lector propio en el módulo) |
| 13 | MIVAU-BOL09-FINOBRA, MIVAU-BOL09-VISADOS | `mivau_certificados_fin_obra`, `mivau_visados_obra_nueva` | Fin de obra: `promotor`. Visados: `tipo_obra` / `num_viviendas` |
| 14 | MIVAU-ETI, MIVAU-SERPAVI | `mivau_eti_compraventa_notarial`, `mivau_serpavi_alquiler` | ETI: comprobar primero si duplica la Tarea 9; si es así, `estado=solo_diseno` con nota. SERPAVI: anual, nivel sección censal (el ENUM `nivel` gana `'Seccion'`, `cod_territorio` `SCxxxxxxxxxx`), `tipologia` / renta mediana €/m² y número de contratos según el archivo. Su CSV puede superar el límite de filas de Excel (ver Tarea 7) |

### Tarea 15: Tablas solo de diseño (Notariado e Idealista)

**Archivos:**
- Modificar: `etl/catalogo/tablas.csv`, `etl/catalogo/campos.csv`
- Crear: `docs/fuentes/NOT-NP-MENSUAL.md`, `NOT-PEN.md`, `IDEALISTA-ALQUILER.md`, `IDEALISTA-VENTA.md`

- [ ] **Paso 1:** diseñar en `campos.csv` las cuatro tablas con el modelo común:
  - `notariado_hipotecas`: `finalidad` / `num_hipotecas`, `capital_medio_eur`, `ratio_capital_responsabilidad`.
  - `notariado_compraventas`: `tipo_vivienda` (LIBRE / VPO) / `num_compraventas`, `precio_medio_eur_m2`, `superficie_media_m2`.
  - `idealista_precio_alquiler`: `renta_eur_m2_mes`.
  - `idealista_precio_venta`: `precio_eur_m2`.
  - En las de Idealista, el ENUM `nivel` admite `'Distrito'`.
- [ ] **Paso 2:** `estado=solo_diseno`. Cada ficha explica por qué no hay datos y qué vías hay (idealista/data, solicitud al Notariado).
- [ ] **Paso 3:** comprobar que `pytest tests/test_sql.py` pasa y que `create_tables.sql` incluye las 4 tablas.
- [ ] **Paso 4:** commit `feat: tablas de diseño Notariado e Idealista`.

### Tarea 16: Glosario, documentación final y verificación global

**Archivos:**
- Crear: `etl/catalogo/glosario.csv`, `tests/test_global.py`
- Modificar: `docs/README.md`

- [ ] **Paso 1:** `glosario.csv` con las columnas `termino, definicion, fuente`. Como mínimo debe recoger:
  - VPO, calificación definitiva, vivienda libre, ETI, valor tasado, precio asking, SERPAVI y sección censal;
  - los códigos ES / CA / PR / MU / SC;
  - el formato de `periodo` y los valores de `nivel`.
- [ ] **Paso 2: `tests/test_global.py`**
  - `test_todas_las_tablas_en_catalogo`: hay 23 filas en `tablas.csv` y todas tienen `CREATE TABLE`.
  - `test_csv_coinciden_con_campos`: las columnas de cada CSV de `etl/salida/` son iguales a las de `campos.csv`.
  - `test_fichas_existen`: hay una ficha en `docs/fuentes/` por cada `dataset_id`.
  - `test_libro_sin_errores`: ninguna celda de `Data Dils_v2.xlsx` empieza por `#`, salvo en texto descriptivo.
- [ ] **Paso 3:** ejecutar `python -m etl.ejecutar_todo` completo y luego `pytest -v`. Esperado: todo PASS. Pegar en el README el resumen de filas por tabla.
- [ ] **Paso 4:** commit `docs: glosario, README final y verificación global`.
