"""Modelo común de las tablas: columnas, orden y clave id_registro."""
from datetime import date

import pandas as pd

from etl.lib.territorios import COLUMNAS_TERRITORIO

COLUMNAS_TIEMPO = ["periodo", "frecuencia", "anio", "trimestre", "mes", "fecha"]
COLUMNAS_CONTROL = ["provisional", "fecha_descarga"]


def construir_tabla(df: pd.DataFrame, dimensiones: list[str], medidas: list[str],
                    fecha_descarga: date, descriptivas: list[str] | None = None,
                    territorio_extra: list[str] | None = None) -> pd.DataFrame:
    """Calcula id_registro, completa provisional y fecha_descarga, y ordena las columnas.

    `descriptivas`: columnas propias que acompañan a las dimensiones (p. ej. el nombre de la comunidad del
    comprador) pero no entran en id_registro; van justo después de las dimensiones.
    `territorio_extra`: columnas de territorio propias de una tabla (cod_distrito y cod_seccion en SERPAVI); van
    tras nombre_municipio y antes de las dimensiones, y tampoco entran en id_registro.
    """
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
    orden = (["id_registro"] + COLUMNAS_TERRITORIO + list(territorio_extra or []) + list(dimensiones) + list(descriptivas or []) + COLUMNAS_TIEMPO
             + list(medidas) + COLUMNAS_CONTROL)
    return df[orden].reset_index(drop=True)
