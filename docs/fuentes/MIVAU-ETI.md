# MIVAU-ETI: Estadística de Transacciones Inmobiliarias (compraventa notarial), desglose por régimen y antigüedad

Se carga en la tabla existente `mivau_eti_transacciones` (la de MIVAU-34010110), que gana las dimensiones `regimen` y `antiguedad`. Módulo compartido: `etl/fuentes/mivau_34010110.py` (registrado como `MIVAU-34010110` y `MIVAU-ETI`).

## URL
Página índice (columna `fuente` de `tablas.csv`): https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=34000000. No es un archivo: enlaza 34 boletines `sedal/<código>.XLS`. Los boletines cargados se descargan de `https://apps.fomento.gob.es/BoletinOnline2/sedal/<código>.XLS` (la URL de 34010110 con el código cambiado).

### Inventario de la página (consultada el 2026-10-29)

| Código sedal | Título en la página | Estado en el proyecto |
|---|---|---|
| 34010110 | 1. Número total de transacciones inmobiliarias de viviendas | Cargado (Tarea 9) → `mivau_eti_transacciones` TOTAL/TOTAL |
| 34010120 | 1.1. … de vivienda libre | **Cargado aquí** → LIBRE/TOTAL |
| 34010130 | 1.1.1. … de vivienda libre nueva | **Cargado aquí** → LIBRE/NUEVA |
| 34010140 | 1.1.2. … de vivienda libre de segunda mano | **Cargado aquí** → LIBRE/SEGUNDA_MANO |
| 34010150 | 1.2. … de vivienda protegida | **Cargado aquí** → PROTEGIDA/TOTAL |
| 34010160 | 1.2.1. … de vivienda protegida nueva | **Cargado aquí** → PROTEGIDA/NUEVA |
| 34010170 | 1.2.2. … de vivienda protegida de segunda mano | **Cargado aquí** → PROTEGIDA/SEGUNDA_MANO |
| 34010180 | 1.3. … de vivienda nueva | **Cargado aquí** → TOTAL/NUEVA |
| 34010190 | 1.4. … de vivienda de segunda mano | **Cargado aquí** → TOTAL/SEGUNDA_MANO |
| 340101a0 | 1.5. … vivienda libre según tipología del edificio | No cargado |
| 340101b0 | 1.5.1. … vivienda libre nueva según tipología del edificio | No cargado |
| 340101c0 | 1.5.2. … vivienda libre de segunda mano según tipología del edificio | No cargado |
| 340101d0 | 1.6. … según residencia del comprador | No cargado |
| 340101e0 | 1.6.1. … residentes según CCAA del comprador y ubicación de la vivienda | No cargado |
| 340101f0 | 1.6.2. … residentes según provincia del comprador y ubicación de la vivienda | No cargado |
| 340101g0 | 1.6.3. … extranjeros residentes según CCAA del comprador y ubicación | Cargado (Tarea 9) → `mivau_eti_compradores_extranjeros` |
| 340101h0 | 1.6.4. … extranjeros residentes según provincia del comprador y ubicación | No cargado |
| 340101i0 / j0 / k0 | 1.6.5 (y .1, .2) … extranjeros residentes según calificación de la vivienda (todas / nueva / segunda mano) | No cargados |
| 340101l0 | 1.7. … vivienda libre según valor y superficie construida | No cargado |
| 34010210 | 2. Número total de transacciones … por municipios | No cargado |
| 34010220 / 230 / 240 / 250 | 2.1-2.4 Transacciones de vivienda libre / protegida / nueva / segunda mano por municipios | No cargados |
| 34020110 / 120 / 130 | 3.1 (y .1, .2) Valor de las transacciones de vivienda libre (total / nueva / segunda mano) | No cargados |
| 34020140 | 3.2 Valor de las transacciones de vivienda libre de extranjeros residentes | No cargado |
| 34020150 / 160 / 170 | 3.3 (y .1, .2) Valor medio de las transacciones de vivienda libre | Cargados (Tarea 10) → `mivau_valor_medio_vivienda_libre` |
| 34020180 | 3.4 Valor medio … de extranjeros residentes | Cargado (Tarea 10) → `mivau_valor_medio_vivienda_libre` |

Decisión: MIVAU-ETI **no** duplica lo cargado: los ocho boletines 34010120-34010190 son el desglose libre/protegida x nueva/segunda mano del total 34010110 y se cargan (`estado = con_datos`). El resto de boletines no cargados (tipología del edificio, residencia del comprador, valor y superficie, nivel municipal, valor total de las transacciones) quedan fuera del alcance de esta tarea: pendiente de revisión por el usuario si interesan (el nivel municipal 34010210-250 y el valor total 34020110-140 serían tablas nuevas).

## Archivo y fecha de descarga
`etl/descargas/MIVAU-<código>_AAAAMMDD.xls` (no versionados). Última descarga real: 2026-10-29. Los tests usan copias completas en `tests/fixtures/<código>.xls` (versionadas, 145-178 KB cada una). Destino: `etl/salida/mivau_eti_transacciones.csv` (7,7 MB, versionado).

## Estructura del original
Los ocho boletines tienen exactamente la estructura de 34010110 (ver `MIVAU-34010110.md`): 5 hojas por quinquenio ("2004, 2005, 2006, 2007, 2008" … "2024, 2025, 2026"), título en B5-B7 ("Tabla 1.1." / "Número de transacciones inmobiliarias de vivienda libre." / "Años: …"), cabeceras de año y trimestre en las filas 12-14, datos desde la fila 15 (TOTAL NACIONAL), 2004T1 a 2026T2 (90 trimestres). La última cabecera es "2º (**)" (provisional) en los nueve. Diferencias de etiquetas: "Asturias (Principado de )", "Asturias (Ppdo. de )" (34010130, alias nuevo), "Navarra (Com. Foral de)", "Comunidad Valenciana".

## Transformaciones
1. `matriz_a_filas` en cada boletín (trimestral, omite "Ceuta y Melilla"), con `regimen` y `antiguedad` fijos según `BOLETINES`.
2. `comprobar_identidades_eti`: en cada territorio y trimestre, antes de expandir uniprovinciales, se comprueban las seis sumas de la rejilla (TOTAL = LIBRE + PROTEGIDA; TOTAL = NUEVA + SEGUNDA_MANO; LIBRE = LIBRE_NUEVA + LIBRE_SEGUNDA_MANO; PROTEGIDA = PROTEGIDA_NUEVA + PROTEGIDA_SEGUNDA_MANO; NUEVA = LIBRE_NUEVA + PROTEGIDA_NUEVA; SEGUNDA_MANO = LIBRE_SEGUNDA_MANO + PROTEGIDA_SEGUNDA_MANO). Las 18 diferencias publicadas por la fuente están en `EXCEPCIONES_IDENTIDADES`; cualquier otra hace fallar el proceso.
3. `tabla_final`: expandir uniprovinciales, construir y validar. `id_registro` = `cod_territorio_regimen_antiguedad_periodo`.

Resultado: 58.320 filas = 9 combinaciones x 72 territorios x 90 trimestres.

## Decisiones
- Dos dimensiones (`regimen` TOTAL/LIBRE/PROTEGIDA y `antiguedad` TOTAL/NUEVA/SEGUNDA_MANO) en lugar de una sola `tipo_vivienda`: los nueve boletines llenan exactamente la rejilla 3 x 3 y así las sumas se leen por columnas. `antiguedad` usa los mismos valores que `mivau_valor_medio_vivienda_libre` para poder cruzarlas.
- Cambia el `id_registro` de las filas de 34010110 (`ES_2004T1` → `ES_TOTAL_TOTAL_2004T1`); sus valores no cambian (tests).
- Alias "Asturias (Ppdo. de )" en `territorios_extra.csv`.

## Limitaciones
- 18 diferencias en las sumas de la rejilla (lista en `EXCEPCIONES_IDENTIDADES`): por ejemplo Gipuzkoa 2011T2 libre: total 167 más que nueva + segunda mano; Cataluña 2015T3: total 2 más que nueva + segunda mano. Se cargan tal cual. Pendiente de revisión por el usuario.
- Cuadre jerárquico (ES = suma de CCAA, CCAA = suma de provincias) con 5 excepciones exactas (test `test_cuadre_transacciones_excepciones_exactas`): ES 2015T3 TOTAL/SEGUNDA_MANO (+2), CA16 2011T2 y 2011T3 LIBRE/NUEVA (+167, +3), CA02 2024T3 PROTEGIDA/NUEVA (+1), CA09 2015T3 TOTAL/SEGUNDA_MANO (-2). TOTAL/TOTAL (34010110) cuadra siempre.
- Ceuta, protegida nueva, 2009T4: celda en blanco en 34010160 → NULL.
- 2026T2 provisional en los nueve boletines.

## Valores comprobados
Primer y último trimestre de ES (celdas C15 de la hoja "2004, …, 2008" y L15 de la hoja "2024, 2025, 2026"), test `test_desgloses_valores_conocidos`:
- 34010120 (LIBRE/TOTAL): 178620 y 176171.
- 34010130 (LIBRE/NUEVA): 58292 y 17936.
- 34010160 (PROTEGIDA/NUEVA): 7012 y 1504.
- 34010190 (TOTAL/SEGUNDA_MANO): 125138 y 163197; Almería (L17) 2026T2: 3598.
