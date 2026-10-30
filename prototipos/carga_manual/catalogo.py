"""Filas de catálogo (en memoria) de las tablas de Idealista del prototipo, para prototipos/libro.py.

Devuelve las filas de tablas.csv y campos.csv que tendrían si se adoptaran, y la ruta de cada CSV. No escribe nada
en etl/catalogo/. Antes hay que generar los CSV: python -m prototipos.carga_manual.idealista
"""
import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from prototipos.carga_manual.idealista import AQUI, SALIDA, TIPOS


def catalogo() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    tablas, _ = cargar_catalogo()
    filas = tablas[tablas["dataset_id"].isin([t["dataset_id"] for t in TIPOS.values()])].copy()
    rutas = {}
    for t in TIPOS.values():
        i = filas.index[filas["dataset_id"] == t["dataset_id"]]
        filas.loc[i, ["esquema", "tabla", "hoja", "formato_origen", "estado"]] = [
            "IDEALISTA", t["tabla"], t["tabla"],
            "PROTOTIPO: copia manual de la tabla HTML (prototipos/carga_manual/pegados/)", "con_datos"]
        filas.loc[i, "estadistica"] = "[PROTOTIPO] " + filas.loc[i, "estadistica"]
        csv = SALIDA / f"{t['tabla']}.csv"
        if csv.exists():
            rutas[t["tabla"]] = csv
    campos = pd.concat([pd.read_csv(AQUI / f"campos_idealista_{tipo}.csv", dtype=str, keep_default_na=False)
                        for tipo in TIPOS], ignore_index=True)
    return filas, campos, rutas
