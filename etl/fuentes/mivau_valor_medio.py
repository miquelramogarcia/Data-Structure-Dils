"""MIVAU-34020150/160/170/180: ETI, valor medio de la vivienda libre (euros por vivienda, trimestral).

Cuatro boletines, UNA tabla `mivau_valor_medio_vivienda_libre`:
- 34020150: total de vivienda libre         (tipo_comprador TOTAL,                antiguedad TOTAL)
- 34020160: vivienda libre nueva            (tipo_comprador TOTAL,                antiguedad NUEVA)
- 34020170: vivienda libre de segunda mano  (tipo_comprador TOTAL,                antiguedad SEGUNDA_MANO)
- 34020180: compras de extranjeros residentes, una hoja por trimestre con tres columnas
            (tipo_comprador EXTRANJERO_RESIDENTE, antiguedad TOTAL / NUEVA / SEGUNDA_MANO)

Los cuatro ids se registran con la misma `ejecutar`, que descarga los cuatro archivos y escribe la tabla
completa una sola vez por proceso (si cada id escribiera su CSV, el último pisaría a los demás). Las medias
no se suman, por eso `CUADRE = False`: `ejecutar_todo` no aplica `cuadre_jerarquico` a esta tabla.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import (DESCARGAS, LIBRO, escribir_csv, matriz_a_filas, tabla_final,
                                  url_dataset)
from etl.lib.periodos import periodo_trimestral
from etl.lib.territorios import cargar_maestro, normalizar, resolver

TABLA = "mivau_valor_medio_vivienda_libre"
DIMENSIONES = ["tipo_comprador", "antiguedad"]
MEDIDAS = ["valor_medio_eur"]
MEDIDA = "valor_medio_eur"
CUADRE = False
# Agregado Ceuta + Melilla de las fuentes: sin código INE; Ceuta y Melilla vienen también por separado.
OMITIR = frozenset({"Ceuta y Melilla"})
TOTAL, NUEVA, SEGUNDA_MANO = "TOTAL", "NUEVA", "SEGUNDA_MANO"

# Boletines por hojas de años (matriz territorio x trimestre): dataset_id -> antigüedad.
POR_ANIOS = {"MIVAU-34020150": TOTAL, "MIVAU-34020160": NUEVA, "MIVAU-34020170": SEGUNDA_MANO}
# Boletín por hojas de trimestre (extranjeros residentes): rótulo de columna -> antigüedad.
EXTRANJEROS = "MIVAU-34020180"
ANTIGUEDAD_COLUMNA = {"total": TOTAL, "vivienda nueva": NUEVA, "vivienda de segunda mano": SEGUNDA_MANO}
DATASET_IDS = [*POR_ANIOS, EXTRANJEROS]


def _filas_extranjeros(path: Path, maestro: pd.DataFrame) -> pd.DataFrame:
    largo = mivau.leer_hojas_trimestre(path)
    largo = largo[~largo["territorio_txt"].map(normalizar).isin({normalizar(o) for o in OMITIR})]
    territorios = {t: resolver(maestro, t) for t in largo["territorio_txt"].unique()}
    filas = []
    for r in largo.itertuples(index=False):
        clave = normalizar(r.columna_txt)
        if clave not in ANTIGUEDAD_COLUMNA:
            raise ValueError(f"{EXTRANJEROS}: columna no reconocida {r.columna_txt!r} en la hoja {r.hoja!r}")
        filas.append({**territorios[r.territorio_txt], "tipo_comprador": "EXTRANJERO_RESIDENTE",
                      "antiguedad": ANTIGUEDAD_COLUMNA[clave],
                      **periodo_trimestral(int(r.anio), int(r.trimestre)),
                      MEDIDA: mivau.a_numero(r.valor_txt), "provisional": int(r.provisional)})
    return pd.DataFrame(filas)


def transformar(paths: dict[str, Path], fecha_descarga: date) -> pd.DataFrame:
    """Lee los cuatro boletines (`paths`: dataset_id -> archivo), los junta, expande y valida la tabla."""
    maestro = cargar_maestro(LIBRO)
    partes = [matriz_a_filas(paths[i], i, {"tipo_comprador": TOTAL, "antiguedad": ant}, MEDIDA, maestro,
                             frecuencia="T", omitir=OMITIR) for i, ant in POR_ANIOS.items()]
    partes.append(_filas_extranjeros(paths[EXTRANJEROS], maestro))
    return tabla_final(pd.concat(partes, ignore_index=True), "MIVAU-34020150/160/170/180", TABLA, DIMENSIONES,
                       MEDIDA, maestro, fecha_descarga, entero=False)


def _ejecutar(fecha_descarga: date) -> pd.DataFrame:
    paths = {i: mivau.descargar(url_dataset(i), i, DESCARGAS) for i in DATASET_IDS}
    tabla = transformar(paths, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla


@lru_cache(maxsize=1)
def _ejecutar_cacheado(fecha_descarga: date) -> pd.DataFrame:
    return _ejecutar(fecha_descarga)


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga los cuatro boletines y escribe etl/salida/<TABLA>.csv (una vez por proceso y fecha)."""
    return _ejecutar_cacheado(fecha_descarga)


# Un objeto por dataset_id para el REGISTRO; todos comparten tabla y `ejecutar`.
FUENTES = [SimpleNamespace(DATASET_ID=i, TABLA=TABLA, DIMENSIONES=DIMENSIONES, MEDIDAS=MEDIDAS,
                           CUADRE=CUADRE, ejecutar=ejecutar) for i in DATASET_IDS]
