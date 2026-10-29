"""MIVAU-32100500: viviendas libres iniciadas (serie mensual, sin desglose)."""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, matriz_a_tabla, url_dataset
from etl.lib.territorios import cargar_maestro

DATASET_ID = "MIVAU-32100500"
TABLA = "mivau_vivienda_libre_iniciadas"
DIMENSIONES = []
MEDIDAS = ["num_viviendas"]


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín, resuelve territorios, expande uniprovinciales, construye y valida la tabla."""
    return matriz_a_tabla(path, DATASET_ID, TABLA, {}, "num_viviendas", cargar_maestro(LIBRO), fecha_descarga)


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
