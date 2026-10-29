"""MIVAU-34010110: ETI, número total de transacciones de vivienda por CCAA y provincia (trimestral)."""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, matriz_a_tabla, url_dataset
from etl.lib.territorios import cargar_maestro

DATASET_ID = "MIVAU-34010110"
TABLA = "mivau_eti_transacciones"
DIMENSIONES = []
MEDIDAS = ["num_transacciones"]
# Agregado Ceuta + Melilla de la fuente: sin código INE; las dos ciudades vienen también por separado.
OMITIR = frozenset({"Ceuta y Melilla"})


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín, resuelve territorios, expande uniprovinciales, construye y valida la tabla."""
    return matriz_a_tabla(path, DATASET_ID, TABLA, {}, "num_transacciones", cargar_maestro(LIBRO),
                          fecha_descarga, frecuencia="T", omitir=OMITIR)


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
