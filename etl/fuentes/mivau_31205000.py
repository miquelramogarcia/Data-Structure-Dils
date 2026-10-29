"""MIVAU-31205000: viviendas protegidas con calificación definitiva (planes estatales y autonómicos).

Patrón de todas las fuentes: DATASET_ID, TABLA, DIMENSIONES, MEDIDAS, transformar() y ejecutar().
"""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.lib import mivau
from etl.lib.modelo import construir_tabla
from etl.lib.periodos import periodo_mensual
from etl.lib.territorios import cargar_maestro, expandir_uniprovinciales, resolver
from etl.lib.validar import validar_tabla

DATASET_ID = "MIVAU-31205000"
TABLA = "mivau_vpo_calificaciones_definitivas"
DIMENSIONES = ["regimen"]
MEDIDAS = ["num_viviendas"]

RAIZ = Path(__file__).resolve().parents[2]
LIBRO = RAIZ / "Data Dils.xlsx"
SALIDA = RAIZ / "etl" / "salida"
DESCARGAS = RAIZ / "etl" / "descargas"


def _url() -> str:
    tablas, _ = cargar_catalogo()
    return tablas.loc[tablas["dataset_id"] == DATASET_ID, "fuente"].iloc[0].strip()


def transformar(path: Path, fecha_descarga: date) -> pd.DataFrame:
    """Lee el boletín, resuelve territorios, expande uniprovinciales, construye y valida la tabla."""
    maestro = cargar_maestro(LIBRO)
    largo = mivau.leer_matriz(path)
    territorios = {t: resolver(maestro, t) for t in largo["territorio_txt"].unique()}
    filas = []
    for r in largo.itertuples(index=False):
        tipo, n = mivau.subperiodo(r.subperiodo_txt)
        if tipo != "M":
            raise ValueError(f"Subperiodo no mensual en {DATASET_ID}: {r.subperiodo_txt!r}")
        filas.append({**territorios[r.territorio_txt], "regimen": "TOTAL",
                      **periodo_mensual(int(r.anio), n), "num_viviendas": mivau.a_numero(r.valor_txt)})
    df = pd.DataFrame(filas)
    df["num_viviendas"] = df["num_viviendas"].round().astype("Int64")
    df = expandir_uniprovinciales(df, maestro, claves=DIMENSIONES + ["periodo"])
    df["num_viviendas"] = df["num_viviendas"].astype("Int64")
    df["provisional"] = 0
    tabla = construir_tabla(df, DIMENSIONES, MEDIDAS, fecha_descarga)
    _, campos = cargar_catalogo()
    errores = validar_tabla(tabla, campos[campos["tabla"] == TABLA], maestro)
    if errores:
        raise ValueError(f"{DATASET_ID}: validación fallida:\n" + "\n".join(errores))
    return tabla


def escribir_csv(tabla: pd.DataFrame, destino: Path = SALIDA) -> Path:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{TABLA}.csv"
    tabla.to_csv(ruta, sep=";", index=False, encoding="utf-8")
    return ruta


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga, transforma y escribe etl/salida/<TABLA>.csv."""
    path = mivau.descargar(_url(), DATASET_ID, DESCARGAS)
    tabla = transformar(path, fecha_descarga)
    escribir_csv(tabla)
    return tabla
