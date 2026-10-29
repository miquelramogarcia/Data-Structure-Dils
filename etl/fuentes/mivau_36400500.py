"""MIVAU-36400500: precio medio del metro cuadrado de suelo urbano por CCAA y provincia (euros/m2, trimestral).

El archivo NO desglosa por tamaño de municipio ni trae número de transacciones (la hoja General lo
describía así por error): una hoja "Tabla 4" con territorios en filas y trimestres en columnas.
Son precios medios: no se suman, por eso `CUADRE = False`.
"""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, matriz_a_tabla, url_dataset
from etl.lib.territorios import cargar_maestro

DATASET_ID = "MIVAU-36400500"
TABLA = "mivau_precio_suelo_urbano"
DIMENSIONES = []
MEDIDAS = ["precio_eur_m2"]
CUADRE = False
# Agregado Ceuta + Melilla de la fuente: sin código INE; la fuente no las da por separado.
OMITIR = frozenset({"Ceuta y Melilla"})


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín, resuelve territorios, expande uniprovinciales, construye y valida la tabla."""
    return matriz_a_tabla(path, DATASET_ID, TABLA, {}, "precio_eur_m2", cargar_maestro(LIBRO),
                          fecha_descarga, entero=False, frecuencia="T", omitir=OMITIR)


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
