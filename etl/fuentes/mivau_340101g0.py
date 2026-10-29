"""MIVAU-340101g0: ETI, transacciones de vivienda de compradores extranjeros residentes (trimestral).

Una hoja por trimestre con una matriz vivienda (filas) × comunidad de residencia del comprador (columnas).
El territorio es la comunidad de la vivienda; la del comprador va en `cod_ccaa_comprador` (dimensión, entra
en id_registro) y `nombre_ccaa_comprador`.
"""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, tabla_final, url_dataset
from etl.lib.periodos import periodo_trimestral
from etl.lib.territorios import cargar_maestro, normalizar, resolver

DATASET_ID = "MIVAU-340101g0"
TABLA = "mivau_eti_compradores_extranjeros"
DIMENSIONES = ["cod_ccaa_comprador"]
DESCRIPTIVAS = ["nombre_ccaa_comprador"]
MEDIDAS = ["num_transacciones"]
# Agregado Ceuta + Melilla de la fuente: sin código INE; en las filas de vivienda se omite, en las columnas
# de comprador se conserva con un código propio.
AGREGADO = "Ceuta y Melilla"
COD_COMPRADOR_TOTAL = "00"  # columna "Residentes en España": total de compradores
COD_COMPRADOR_CEUTA_MELILLA = "99"


def _comprador(maestro: pd.DataFrame, etiqueta: str) -> tuple[str, str]:
    """(cod_ccaa_comprador, nombre_ccaa_comprador) de una cabecera de columna."""
    clave = normalizar(etiqueta)
    if clave == "en espana":
        return COD_COMPRADOR_TOTAL, "Total residentes en España"
    if clave == normalizar(AGREGADO):
        return COD_COMPRADOR_CEUTA_MELILLA, AGREGADO
    t = resolver(maestro, etiqueta, nivel="CCAA")
    return t["cod_ccaa"], t["nombre_ccaa"]


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín, resuelve vivienda y comprador contra el maestro, construye y valida la tabla."""
    maestro = cargar_maestro(LIBRO)
    largo = mivau.leer_matriz_cruzada(path)
    largo = largo[largo["fila_txt"].map(normalizar) != normalizar(AGREGADO)]
    viviendas = {t: resolver(maestro, t) for t in largo["fila_txt"].unique()}
    compradores = {c: _comprador(maestro, c) for c in largo["columna_txt"].unique()}
    filas = []
    for r in largo.itertuples(index=False):
        cod, nombre = compradores[r.columna_txt]
        filas.append({**viviendas[r.fila_txt], "cod_ccaa_comprador": cod, "nombre_ccaa_comprador": nombre,
                      **periodo_trimestral(int(r.anio), int(r.trimestre)),
                      "num_transacciones": mivau.a_numero(r.valor_txt), "provisional": int(r.provisional)})
    return tabla_final(pd.DataFrame(filas), DATASET_ID, TABLA, DIMENSIONES, "num_transacciones", maestro,
                       fecha_descarga, descriptivas=DESCRIPTIVAS)


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(url_dataset(DATASET_ID), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla
