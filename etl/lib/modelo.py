"""Modelo común de las tablas: columnas, orden y clave id_registro."""
from datetime import date

import pandas as pd

from etl.lib.territorios import COLUMNAS_TERRITORIO

COLUMNAS_TIEMPO = ["periodo", "frecuencia", "anio", "trimestre", "mes", "fecha"]
COLUMNAS_CONTROL = ["provisional", "fecha_descarga"]


def construir_tabla(df: pd.DataFrame, dimensiones: list[str], medidas: list[str],
                    fecha_descarga: date) -> pd.DataFrame:
    """Calcula id_registro, completa provisional y fecha_descarga, y ordena las columnas."""
    df = df.copy()
    partes = [df["cod_territorio"].astype(str)]
    partes += [df[d].astype(str) for d in dimensiones]
    partes.append(df["periodo"].astype(str))
    id_registro = partes[0]
    for p in partes[1:]:
        id_registro = id_registro + "_" + p
    df["id_registro"] = id_registro
    if "provisional" not in df.columns:
        df["provisional"] = 0
    else:
        df["provisional"] = df["provisional"].fillna(0)
    df["fecha_descarga"] = fecha_descarga
    orden = (["id_registro"] + COLUMNAS_TERRITORIO + list(dimensiones) + COLUMNAS_TIEMPO
             + list(medidas) + COLUMNAS_CONTROL)
    return df[orden].reset_index(drop=True)
