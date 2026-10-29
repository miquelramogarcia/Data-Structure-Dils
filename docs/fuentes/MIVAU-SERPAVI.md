# MIVAU-SERPAVI: Sistema Estatal de Referencia del Precio del Alquiler de Vivienda (base de datos 2011-2024)

Tabla `mivau_serpavi_alquiler`. Rentas de alquiler de vivienda habitual (explotación estadística de fuentes tributarias, IRPF modelo 100, cruzadas con el Catastro), anual 2011-2024, por CCAA, provincia, municipio, distrito censal y sección censal. Módulo `etl/fuentes/mivau_serpavi.py`.

## URL
https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/2026-03_09_bd_SERPAVI_2011-2024%20-%20DEFINITIVO%20WEB_v2.xlsx (columna `fuente` de `tablas.csv`).

## Archivo y fecha de descarga
`etl/descargas/MIVAU-SERPAVI_AAAAMMDD.xlsx` (no versionado; 71.155.784 bytes, ~68 MB). Última descarga real: 2026-10-29 (16 s).

Salida: `etl/salida/mivau_serpavi_alquiler.csv`, **no versionado** (246 MB, 1.281.664 filas; entrada explícita en `.gitignore`). Se regenera con:

```
python -m etl.ejecutar_todo MIVAU-SERPAVI
```

Los tests usan una muestra versionada, `tests/fixtures/serpavi_muestra.xlsx` (214 KB), extraída con `python -m etl.herramientas.serpavi_muestra etl/descargas/MIVAU-SERPAVI_20261029.xlsx`. La muestra conserva las seis hojas, la fila de cabecera real y las 280 columnas de medidas (los 14 años); solo copia estas filas (fila del original → fila de la muestra):

| Hoja | Filas del original | Filas de la muestra | Qué son |
|---|---|---|---|
| Metadatos | 1-41 | 1-41 | entera |
| CCAA | 2-21 | 2-21 | las 19 comunidades y la fila 21 sin código |
| Provincias | 52, 53 | 2, 3 | Ceuta (51), Melilla (52) |
| Municipios | 2152, 4620, 4739, 8072, 8099, 8100 | 2-7 | Cesuras 15026 (extinguido, vacío), Abáigar 31001, Jaurrieta 31134, Valmadrid 50275, Ceuta 51001, Melilla 52001 |
| Distritos | 6146, 6290, 10460, 10499-10512 | 2, 3, 4, 5-18 | 3100101 (CUMUN incoherente), 3113401, 5027501, los 6 distritos de Ceuta y los 8 de Melilla |
| Secciones censales | 8576, 10403, 23450, 23643, 35673, 36195-36294 | 2-6, 7-106 | 1101208012 y 1402106037 (CPRO/CUMUN incoherentes), 3100101001, 3113401001, 5027501001, las 56 secciones de Ceuta y las 44 de Melilla |

Así la muestra tiene jerarquías completas (Ceuta, Melilla, Abáigar, Jaurrieta, Valmadrid) para probar el cuadre de recuentos y un caso de cada anomalía.

## Estructura del original
Seis hojas (modo `read_only` de openpyxl; abrir el libro tarda 0,4 s):

| Hoja | Columnas de identificación | Filas con código | Filas sin ningún dato |
|---|---|---|---|
| Metadatos | — (diseño de registro, 41 filas) | — | — |
| CCAA | CCAA, LITCCAA | 19 (+ fila 21 sin código) | 0 |
| Provincias | CPRO, LITPRO | 52 | 0 |
| Municipios | CPRO, NPRO, CUMUN, NMUN | 8.099 | 7 |
| Distritos | CPRO, LITPRO, CUMUN, LITMUN, CUDIS | 10.511 | 3 |
| Secciones censales | CPRO, LITPRO, CUMUN, LITMUN, CUSEC | 36.293 | 11 |

Formato ancho: tras las columnas de identificación, 280 columnas = 14 años (sufijo `_11` a `_24`) x 20 medidas, en el mismo orden en todas las hojas:
- `BI_ALVHEPCO_TVC_AA` / `_TVU_AA`: recuento del subconjunto de alquiler (bienes inmuebles con ingresos por arrendamiento de vivienda habitual, excluidos los alquileres a parientes) de vivienda colectiva (VC) o unifamiliar/rural (VU), "tipología de más superficie" (grupo GGT01).
- `ALQM2_LV_{M,25,75}_V{C,U}_AA`: alquiler mensual por m2, mediana y percentiles 25 y 75 (los Metadatos lo llaman `ALQM2mes_LV_…`).
- `ALQTBID12_{M,25,75}_V{C,U}_AA`: alquiler mensual de todo el inmueble.
- `SLVM2_{M,25,75}_V{C,U}_AA`: superficie en m2.

No hay columna de total de tipologías, ni fila nacional con etiqueta, ni marcas de provisional. Códigos: texto con ceros a la izquierda ('01001'), salvo algunas celdas guardadas como número (CCAA 15 y 16, CPRO 14, 19, 40, 50…; se normalizan a texto). Valores: número, vacío o cadena vacía `''` (126.642 en Distritos, 103.554 en Municipios); unas pocas cifras guardadas como texto ('600', '900', '728', '364'). El seccionado es el del Censo de Población 2021 (nota de la hoja Metadatos, corregida el 08/07/2026).

## Transformaciones
1. `leer_serpavi`: cada hoja fila a fila (`iter_rows(values_only=True)`). Las cabeceras se interpretan por nombre (`columnas_medidas`); un nombre desconocido, unas columnas de identificación distintas de las esperadas o un bloque (año, tipología) sin sus 10 medidas hacen fallar el proceso.
2. Una fila por (territorio, año, tipología) con alguna medida; los bloques vacíos no entran. `''`, vacío → NULL; '0' → 0; texto numérico → número. Rentas y superficies se redondean a 2 decimales (DECIMAL(10,2)/(12,2)); el recuento debe ser entero.
3. Territorio por **código**: `cod_territorio` = `CA`/`PR`/`MU`/`DI`/`SC` + código INE, buscado con `territorio_por_codigo` en el maestro (los distritos y secciones vienen de `etl/lib/secciones_serpavi.csv`). Las columnas `cod_distrito` (7) y `cod_seccion` (10) salen del código; nombres y códigos de CCAA, provincia y municipio, del maestro (INE).
4. `comprobar_coherencia`: CPRO (y CUMUN en distritos y secciones) deben coincidir con el código; lista cerrada `CODIGOS_INCOHERENTES` (6 filas, aviso).
5. `comprobar_recuentos` (en cada ejecución): CCAA = suma de provincias, provincia = suma de municipios, municipio = suma de distritos, distrito = suma de secciones, por año y tipología, donde el padre y algún hijo tienen recuento. Lista cerrada `EXCEPCIONES_RECUENTOS` (35).
6. `construir_tabla` con `territorio_extra=["cod_distrito", "cod_seccion"]` y validación contra Campos.

Resultado (descarga 2026-10-29): **1.281.664 filas**: CCAA 486, Provincia 1.362, Municipio 160.934, Distrito 221.814, Seccion 897.068 (COLECTIVA 641.617, UNIFAMILIAR 640.047).

Tiempo y memoria (Windows, Python 3.13, descargas ya en disco). Primera medida (primera ejecución de la Tarea 14, `python -m etl.ejecutar_todo MIVAU-34010110 MIVAU-ETI MIVAU-SERPAVI`, libro con muestra de 100.000 filas): SERPAVI completo ~2 min, pico 1,3 GB antes del libro; `construir_libro` 140-180 s y pico 3,4 GB; total 4,5-6,5 min. Ejecución final (2026-10-29, `python -m etl.ejecutar_todo MIVAU-ETI MIVAU-SERPAVI MIVAU-34010110`, libro con muestra de 1.000 filas por hoja): fuentes 526 s (equipo más cargado que en la primera medida), pico 1,28 GB; `construir_libro` 83,8 s (163,2 s con la regla anterior, medido el mismo día en el mismo equipo) sin subir el pico; total 610 s (10,2 min).

En el libro `Data Dils_v2.xlsx` la hoja `mivau_serpavi_alquiler` (oculta) tiene la nota "Muestra: 1000 de 1281664 filas. La tabla completa está en etl/salida/mivau_serpavi_alquiler.csv" en A1, la cabecera en la fila 2 y 1.000 filas de datos (regla `muestra_libro` / `FILAS_MUESTRA_LIBRO`, ver README): 2024 de los cinco niveles (200 municipios, 200 distritos, 200 secciones, 104 provincias) y las CCAA y provincias de los años anteriores hasta completar; la hoja Tablas muestra 1281664 en "Filas".

## Decisiones
- Una sola tabla con todos los niveles (`nivel` gana `'Distrito'` y `'Seccion'` en el ENUM de ESTA tabla; `cod_territorio` VARCHAR(12)); columnas propias `cod_distrito` CHAR(7) y `cod_seccion` CHAR(10) tras `nombre_municipio`.
- `tipologia` COLECTIVA / UNIFAMILIAR. Sin TOTAL: el archivo no lo trae y las medianas no se pueden combinar.
- Medidas con la unidad en el nombre: `renta_{mediana,p25,p75}_eur_m2_mes` DECIMAL(10,2), `renta_{…}_eur_mes` DECIMAL(12,2), `superficie_{…}_m2` DECIMAL(10,2), `num_inmuebles_alquiler` INT UNSIGNED (el archivo cuenta bienes inmuebles, no "testigos" ni contratos). `CUADRE = False` (medianas).
- El código INE de la fila manda sobre las columnas CPRO/CUMUN/LITMUN. Seis filas contradicen su código (`CODIGOS_INCOHERENTES`): Distritos fila 6146 (CUDIS 3100101 de Abáigar con CUMUN/LITMUN 31002 Abárzuza: sus recuentos son los del municipio 31001 y de la sección 3100101001) y Secciones filas 4706 y 4829 (Barcelona con CPRO '09' y CUMUN 08020), 8576 (Cádiz con CPRO '12' y CUMUN 11013), 10403 (Córdoba con CUMUN 14022) y 29741 (Sevilla con CPRO '42'). En las cinco secciones el nombre del municipio coincide con el que da el código.
- Maestro: `etl/lib/secciones_serpavi.csv` (10.503 distritos y 36.293 secciones; generador `etl/lib/secciones_serpavi_generar.py`) con las 12 columnas del maestro; cada código cuelga de un municipio de `municipios_ine.csv` (falla si no). Excepción documentada: los distritos de los cuatro municipios extinguidos que el archivo conserva sin datos (Cesuras 15026 y Oza dos Ríos 15063, fusionados en Oza-Cesuras en 2013; Cerdedo 36011 y Cotobade 36012, fusionados en Cerdedo-Cotobade en 2016) no entran; sus filas no tienen ningún dato y por eso no se cargan. `nombre_territorio` es descriptivo ("Ceuta - distrito 01 - sección 001"): las secciones no tienen nombre propio y nunca se resuelven por nombre.
- Fila 21 de la hoja CCAA (sin código ni nombre; solo recuentos 2012-2024, W21 = 1.060.264 en 2012 colectiva): sus recuentos son exactamente la suma de las 19 comunidades en todos los años (test), así que es el total nacional, pero no tiene etiqueta ni medianas: **no se carga** (no se inventan etiquetas). Pendiente de revisión por el usuario.
- Recuento no entero: Valmadrid (50275) 2022 colectiva, Municipios HQ8072 = 103,383236… (su distrito y su sección dicen 0 y la provincia cuadra con 0) → NULL (`RECUENTOS_NO_ENTEROS`); como era el único dato del bloque, la fila no entra. Cualquier otro recuento no entero hace fallar el proceso.
- Nada se omite en silencio: avisos (`UserWarning`) en cada ejecución para la fila sin código, las 6 incoherencias y el recuento no entero.

## Limitaciones
- 35 diferencias de recuento entre niveles, todas en Navarra (`EXCEPCIONES_RECUENTOS`): provincia 31 frente a sus municipios en 2023 unifamiliar (+2), 2024 colectiva (+2) y 2024 unifamiliar (+56); y en 2022, 15 municipios frente a sus distritos y 17 distritos frente a sus secciones (los distritos de 2022 de Navarra parecen desplazados entre municipios vecinos: municipio = suma de secciones, pero no = suma de distritos; p. ej. Jaurrieta 31134 colectiva 2022: municipio 1, distrito 3, sección 1). Se cargan tal cual. Pendiente de revisión por el usuario.
- Navarra y País Vasco (régimen foral): sin recuentos en la hoja CCAA (celdas vacías) y en muchos años sin datos; hay 4 celdas CCAA con recuento vacío cuyas provincias sí lo tienen (no es descuadre: el padre es NULL).
- Secreto estadístico: muchas medianas vacías en secciones y distritos pequeños (NULL).
- El CSV completo no se versiona (246 MB); el libro solo trae una muestra de 1.000 filas.
- El seccionado es el de 2021: secciones y distritos no se recodifican a seccionados de otros años.

## Valores comprobados
Leídos a mano de las celdas del archivo completo (hoja y coordenada) y comprobados en los tests contra la muestra (`tests/test_fuente_serpavi.py`):
- CCAA C19 (Ceuta, colectiva, 2011): 978 inmuebles → `CA18_COLECTIVA_2011`; E19 = 7,6923… €/m2 → 7.69. JE19 (2024) = 9,4488… → 9.45; JD19 (unifamiliar 2024) = 382.
- Secciones censales fila 36195 (sección 5100101001 de Ceuta, colectiva): F36195 (2011) = 44 inmuebles, H36195 = 8,7024… → 8.70 €/m2; 2024: JH36195 = 11,8597… → 11.86, JI36195 = 8,8888… → 8.89, JJ36195 = 14,8648… → 14.86, JN36195 = 751,2781… → 751.28 €/mes, JT36195 = 73 m2, JF36195 = 107 inmuebles; unifamiliar 2024: JG36195 = 0 (se queda 0) y JK36195 vacía (NULL).
- Municipios JP8100 (Melilla, unifamiliar 2024) = 500 €/mes; JF8100 = 540 inmuebles.
- Distritos CV10512 (5200108, colectiva 2015) = 73 m2; CH10512 = 631 inmuebles.
- Municipios HQ8072 (Valmadrid 2022 colectiva) = 103,38323643410851 (recuento no entero → NULL).
