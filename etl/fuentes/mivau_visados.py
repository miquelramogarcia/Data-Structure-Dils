"""MIVAU-BOL09-VISADOS: visados de dirección de obra (obra nueva, ampliación, reforma), serie mensual nacional.

Boletín 09010600 (hoja APAREJA_6, apartado 6 del boletín de obras en edificación): nº de viviendas y superficie
media por vivienda según tipo de obra. Los rótulos de las columnas son una imagen incrustada en el .xls (no hay
texto): la correspondencia columna -> tipo de obra se leyó de esa imagen y se comprobó con las sumas
(TOTAL = obra nueva + ampliación + reforma; obra nueva = unifamiliar + bloque + otros edificios) y con
superficie x viviendas = m2 enteros.
"""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, serie_vertical_a_tabla, url_dataset
from etl.lib.territorios import cargar_maestro

DATASET_ID = "MIVAU-BOL09-VISADOS"
TABLA = "mivau_visados_direccion_obra"
DIMENSIONES = ["tipo_obra"]
MEDIDAS = ["num_viviendas", "superficie_media_m2"]
# Columna de valores (0 = primera, D en la hoja) -> (tipo de obra, medida). Columnas 0-6: nº de viviendas;
# columnas 7-10 (K a N): superficie media por vivienda (m2), solo para obra nueva por tipo de edificio y ampliación.
COLUMNAS = {0: ("TOTAL", "num_viviendas"),
            1: ("OBRA_NUEVA", "num_viviendas"),
            2: ("OBRA_NUEVA_UNIFAMILIAR", "num_viviendas"),
            3: ("OBRA_NUEVA_EN_BLOQUE", "num_viviendas"),
            4: ("OBRA_NUEVA_OTROS_EDIFICIOS", "num_viviendas"),
            5: ("AMPLIACION", "num_viviendas"),
            6: ("REFORMA_RESTAURACION", "num_viviendas"),
            7: ("OBRA_NUEVA_UNIFAMILIAR", "superficie_media_m2"),
            8: ("OBRA_NUEVA_EN_BLOQUE", "superficie_media_m2"),
            9: ("OBRA_NUEVA_OTROS_EDIFICIOS", "superficie_media_m2"),
            10: ("AMPLIACION", "superficie_media_m2")}


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín (sin red), resuelve el territorio, construye y valida la tabla."""
    return serie_vertical_a_tabla(path, DATASET_ID, TABLA, "tipo_obra", COLUMNAS, cargar_maestro(LIBRO),
                                  fecha_descarga, decimales={"superficie_media_m2": 4})


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
