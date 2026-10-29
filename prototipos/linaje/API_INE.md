# API JSON del INE (Tempus) como vía para automatizar los maestros

Nota de prototipo (Tarea 18). Las llamadas de abajo se probaron el 2026-10-29 (HTTP 200, sin clave ni registro) y
las respuestas son reales, recortadas con `...`. El MIVAU **no** tiene API: sus fuentes son ficheros XLS/XLSX que se
descargan por URL, por eso esta vía sirve para los **maestros** (territorios) y para series del INE, no para las
tablas del MIVAU.

## URL base

```
https://servicios.ine.es/wstempus/js/ES/<FUNCION>/<parámetro>?<opciones>
```

`js` = respuesta JSON; `ES` = idioma (también `EN`). Documentación del INE: sección "API JSON" de
https://www.ine.es/dyngs/DAB/index.htm?cid=1099.

## Lista de municipios (para el maestro)

Los municipios son la variable 19 (`VARIABLES` devuelve `{"Id":19,"Nombre":"Municipios","Codigo":"MUN"}`; las
provincias son la 115):

```
GET https://servicios.ine.es/wstempus/js/ES/VALORES_VARIABLE/19
```

```json
[{"Id":456, "FK_Variable":19, "Nombre":"Orbaizeta", "Codigo":"31195", "FK_JerarquiaPadres":[32,392378]},
 {"Id":457, "FK_Variable":19, "Nombre":"Orbara", "Codigo":"31196", "FK_JerarquiaPadres":[32,392378]},
 ...]
```

Cada valor trae `Codigo` (código INE de 5 dígitos = provincia + municipio) y `Nombre`. La respuesta pesa unos
890 KB y tarda varios segundos: hay que descargarla entera antes de parsearla (con un tiempo límite corto el JSON
llega cortado). Hoy devuelve 8.192 valores con código de 5 dígitos, mientras que la relación oficial a 1-1-2026 que
usa `etl/lib/municipios_ine.csv` tiene 8.132 municipios: la API no filtra por vigencia, así que habría que contrastar
(pendiente de investigar) antes de sustituir el CSV.

Provincias:

```
GET https://servicios.ine.es/wstempus/js/ES/VALORES_VARIABLE/115
```

```json
[{"Id": 16473, "FK_Variable": 115, "Nombre": "Total Nacional", "Codigo": "00"},
 {"Id": 3, "FK_Variable": 115, "Nombre": "Albacete", "Codigo": "02", "FK_JerarquiaPadres": [9004]}, ...]
```

(61 valores: el total nacional más provincias y ciudades autónomas.)

## Una serie

`DATOS_SERIE/<código de serie>` con `nult=N` (últimos N datos). Ejemplo, índice de precios de vivienda (IPV), base
2007, nacional, general (serie ya discontinuada: su último dato es de 2016):

```
GET https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/IPV1?nult=2
```

```json
{"COD": "IPV1", "Nombre": "Base 2007. Nacional. General. Indice",
 "Data": [{"Fecha": 1467324000000, "FK_TipoDato": 1, "FK_Periodo": 21, "Anyo": 2016, "Valor": 70.476, "Secreto": false},
          {"Fecha": 1475272800000, "FK_TipoDato": 1, "FK_Periodo": 22, "Anyo": 2016, "Valor": 70.755, "Secreto": false}]}
```

`Fecha` es una marca de tiempo en milisegundos (UTC), `FK_Periodo` el trimestre/mes y `Valor` el dato; `Secreto` = true
si está protegido. Otro ejemplo comprobado: `DATOS_SERIE/IPC251852?nult=2` (IPC nacional, índice general).

## Otras funciones útiles

| Función | Para qué | Comprobada |
|---|---|---|
| `OPERACIONES_DISPONIBLES` | Lista de estadísticas (166). Ejemplos de vivienda: `IPV` (id 15, Índice de Precios de la Vivienda), `IPVA` (432, precios de vivienda en alquiler), `IRAV` (481, referencia de arrendamientos) | sí |
| `SERIES_OPERACION/<operación>?page=1` | Series de una operación (IPV: 1.308 series; devuelve `COD` y `Nombre`) | sí |
| `VARIABLES`, `VARIABLE/<id>`, `VALORES_VARIABLE/<id>` | Variables (territorio, tipo de dato...) y sus valores | sí |
| `SERIE/<código>` | Metadatos de una serie (`FK_Periodicidad`, `FK_Unidad`...) | sí |

## Cómo encajaría

- **Maestros**: descargar `VALORES_VARIABLE/19` y `/115` y regenerar `municipios_ine.csv` y las provincias, en lugar
  de mantener el CSV a mano (ver la pregunta sobre versionado de códigos en `prototipos/maestros/`).
- **Linaje**: guardar en `META.control_cargas` la URL exacta consultada y el hash de la respuesta.
- **Límites**: el INE no cubre las fuentes del MIVAU ni Notariado/Idealista; los distritos y secciones censales
  vienen del seccionado (SERPAVI), no de esta API.
