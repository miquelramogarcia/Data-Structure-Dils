"""MIVAU-35101000/1500/2000: valor tasado medio de la vivienda libre (euros por m2, trimestral).

Tres boletines, UNA tabla `mivau_valor_tasado_vivienda_libre`, con la dimensión `antiguedad`:
- 35101000: total de vivienda libre              (TOTAL, desde 1995T1)
- 35101500: vivienda libre de hasta 5 años       (HASTA_5_ANOS, desde 2010T1)
- 35102000: vivienda libre de más de 5 años      (MAS_5_ANOS, desde 2010T1)

Cada boletín es una matriz territorio x trimestre en varias hojas de años. Las columnas "Variación
trimestral / anual" de las últimas hojas no son periodos y se ignoran (`leer_matriz`); "n.r" (dato no
representativo) pasa a NULL. Los tres ids se registran con la misma `ejecutar` (una escritura por proceso).
Los valores medios no se suman: `CUADRE = False`.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import (DESCARGAS, LIBRO, escribir_csv, matriz_a_filas, tabla_final,
                                  url_dataset)
from etl.lib.territorios import cargar_maestro

TABLA = "mivau_valor_tasado_vivienda_libre"
DIMENSIONES = ["antiguedad"]
MEDIDA = "valor_tasado_eur_m2"
MEDIDAS = [MEDIDA]
CUADRE = False
# Agregado Ceuta + Melilla de los boletines: sin código INE; Ceuta y Melilla vienen también por separado.
OMITIR = frozenset({"Ceuta y Melilla"})
# dataset_id -> antigüedad
ANTIGUEDAD = {"MIVAU-35101000": "TOTAL", "MIVAU-35101500": "HASTA_5_ANOS", "MIVAU-35102000": "MAS_5_ANOS"}
DATASET_IDS = list(ANTIGUEDAD)


def transformar(paths: dict[str, Path], fecha_descarga: date) -> pd.DataFrame:
    """Lee los tres boletines (`paths`: dataset_id -> archivo), los junta, expande uniprovinciales y valida."""
    maestro = cargar_maestro(LIBRO)
    partes = [matriz_a_filas(paths[i], i, {"antiguedad": ant}, MEDIDA, maestro, frecuencia="T", omitir=OMITIR)
              for i, ant in ANTIGUEDAD.items()]
    return tabla_final(pd.concat(partes, ignore_index=True), "MIVAU-35101000/1500/2000", TABLA, DIMENSIONES,
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
    """Descarga los tres boletines y escribe etl/salida/<TABLA>.csv (una vez por proceso y fecha)."""
    return _ejecutar_cacheado(fecha_descarga)


FUENTES = [SimpleNamespace(DATASET_ID=i, TABLA=TABLA, DIMENSIONES=DIMENSIONES, MEDIDAS=MEDIDAS,
                           CUADRE=CUADRE, ejecutar=ejecutar) for i in DATASET_IDS]
