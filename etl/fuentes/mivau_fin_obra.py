"""MIVAU-BOL09-FINOBRA: certificados de fin de obra (viviendas terminadas), serie mensual nacional por promotor.

Boletín 09011600 (hoja APAREJA_15, apartado 15 del boletín de obras en edificación). Los rótulos de las columnas
son una imagen incrustada en el .xls (no hay texto): la correspondencia columna -> promotor se leyó de esa
imagen y se comprobó con las sumas (TOTAL = privado + administraciones; privado = suma de sus cuatro tipos).
"""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import (DESCARGAS, LIBRO, escribir_csv, serie_vertical_a_tabla, url_dataset)
from etl.lib.territorios import cargar_maestro

DATASET_ID = "MIVAU-BOL09-FINOBRA"
TABLA = "mivau_certificados_fin_obra"
DIMENSIONES = ["promotor"]
MEDIDAS = ["num_viviendas", "valor_liquidacion_miles_eur"]
# Columna de valores (0 = primera, E en la hoja) -> (promotor, medida). Las columnas 6 y 7 (K y L) están vacías
# (celdas combinadas bajo "Administraciones públicas"); el dato de las administraciones está en la columna 8 (M).
COLUMNAS = {0: ("TOTAL", "num_viviendas"),
            1: ("PRIVADO_TOTAL", "num_viviendas"),
            2: ("PRIVADO_PERSONAS_FISICAS", "num_viviendas"),
            3: ("PRIVADO_SOCIEDADES", "num_viviendas"),
            4: ("PRIVADO_COOPERATIVAS", "num_viviendas"),
            5: ("PRIVADO_OTROS", "num_viviendas"),
            8: ("ADMINISTRACIONES_PUBLICAS", "num_viviendas"),
            9: ("TOTAL", "valor_liquidacion_miles_eur")}
# Identidades que se comprueban en cada ejecución (total = suma de partes) para detectar columnas permutadas.
IDENTIDADES = [("TOTAL", ["PRIVADO_TOTAL", "ADMINISTRACIONES_PUBLICAS"]),
               ("PRIVADO_TOTAL", ["PRIVADO_PERSONAS_FISICAS", "PRIVADO_SOCIEDADES", "PRIVADO_COOPERATIVAS",
                                  "PRIVADO_OTROS"])]


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín (sin red), resuelve el territorio, construye y valida la tabla."""
    return serie_vertical_a_tabla(path, DATASET_ID, TABLA, "promotor", COLUMNAS, cargar_maestro(LIBRO),
                                  fecha_descarga, decimales={"valor_liquidacion_miles_eur": 1}, identidades=IDENTIDADES)


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
