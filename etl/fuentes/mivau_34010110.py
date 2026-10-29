"""MIVAU-34010110 y MIVAU-ETI: ETI, número de transacciones de vivienda por CCAA y provincia (trimestral).

Nueve boletines de la página de la ETI (https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=34000000), con
la misma matriz (hojas por quinquenio, territorio x trimestre), van a UNA tabla `mivau_eti_transacciones` con
dos dimensiones, `regimen` (TOTAL / LIBRE / PROTEGIDA) y `antiguedad` (TOTAL / NUEVA / SEGUNDA_MANO): la
rejilla 3 x 3 completa, un boletín por celda (`BOLETINES`). 34010110 es la celda TOTAL x TOTAL (cargada desde la
Tarea 9); los otros ocho son el desglose que el catálogo llama MIVAU-ETI.

Los dos ids se registran con la misma `ejecutar` (cacheada: descarga y escribe la tabla una sola vez por
proceso). En cada ejecución se comprueban las seis sumas de la rejilla (`IDENTIDADES`) en cada territorio y
trimestre: la fuente tiene 18 diferencias conocidas (`EXCEPCIONES_IDENTIDADES`, lista cerrada); cualquier
otra hace fallar el proceso (columnas permutadas, boletín cambiado).
"""
import warnings
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from etl.lib import mivau
from etl.lib.fuente_comun import DESCARGAS, LIBRO, escribir_csv, matriz_a_filas, tabla_final, url_dataset
from etl.lib.territorios import cargar_maestro

DATASET_ID = "MIVAU-34010110"
DATASET_IDS = ["MIVAU-34010110", "MIVAU-ETI"]
TABLA = "mivau_eti_transacciones"
DIMENSIONES = ["regimen", "antiguedad"]
MEDIDA = "num_transacciones"
MEDIDAS = [MEDIDA]
# Agregado Ceuta + Melilla de la fuente: sin código INE; las dos ciudades vienen también por separado.
OMITIR = frozenset({"Ceuta y Melilla"})

# Código sedal del boletín -> (regimen, antiguedad)
BOLETINES = {
    "34010110": ("TOTAL", "TOTAL"),             # 1.    total de transacciones de viviendas
    "34010120": ("LIBRE", "TOTAL"),             # 1.1.  vivienda libre
    "34010130": ("LIBRE", "NUEVA"),             # 1.1.1 vivienda libre nueva
    "34010140": ("LIBRE", "SEGUNDA_MANO"),      # 1.1.2 vivienda libre de segunda mano
    "34010150": ("PROTEGIDA", "TOTAL"),         # 1.2.  vivienda protegida
    "34010160": ("PROTEGIDA", "NUEVA"),         # 1.2.1 vivienda protegida nueva
    "34010170": ("PROTEGIDA", "SEGUNDA_MANO"),  # 1.2.2 vivienda protegida de segunda mano
    "34010180": ("TOTAL", "NUEVA"),             # 1.3.  vivienda nueva
    "34010190": ("TOTAL", "SEGUNDA_MANO"),      # 1.4.  vivienda de segunda mano
}

# (nombre, total, partes) con celdas "REGIMEN_ANTIGUEDAD"; diferencia = total - suma de partes.
IDENTIDADES = [
    ("TOTAL_TOTAL=LIBRE+PROTEGIDA", "TOTAL_TOTAL", ["LIBRE_TOTAL", "PROTEGIDA_TOTAL"]),
    ("TOTAL_TOTAL=NUEVA+SEGUNDA_MANO", "TOTAL_TOTAL", ["TOTAL_NUEVA", "TOTAL_SEGUNDA_MANO"]),
    ("LIBRE_TOTAL", "LIBRE_TOTAL", ["LIBRE_NUEVA", "LIBRE_SEGUNDA_MANO"]),
    ("PROTEGIDA_TOTAL", "PROTEGIDA_TOTAL", ["PROTEGIDA_NUEVA", "PROTEGIDA_SEGUNDA_MANO"]),
    ("TOTAL_NUEVA", "TOTAL_NUEVA", ["LIBRE_NUEVA", "PROTEGIDA_NUEVA"]),
    ("TOTAL_SEGUNDA_MANO", "TOTAL_SEGUNDA_MANO", ["LIBRE_SEGUNDA_MANO", "PROTEGIDA_SEGUNDA_MANO"]),
]
# Diferencias publicadas por la fuente (descarga 2026-10-29): (identidad, cod_territorio, periodo) -> diferencia.
# Lista cerrada: una diferencia nueva o de otro importe hace fallar el proceso. Pendiente de revisión por el usuario.
EXCEPCIONES_IDENTIDADES = {
    ("TOTAL_TOTAL=NUEVA+SEGUNDA_MANO", "CA09", "2015T3"): 2,
    ("LIBRE_TOTAL", "ES", "2006T1"): -1,
    ("LIBRE_TOTAL", "CA09", "2006T1"): -1,
    ("LIBRE_TOTAL", "PR08", "2006T1"): -1,
    ("LIBRE_TOTAL", "PR20", "2011T2"): 167,
    ("LIBRE_TOTAL", "PR20", "2011T3"): 3,
    ("PROTEGIDA_TOTAL", "PR44", "2018T1"): -7,
    ("PROTEGIDA_TOTAL", "PR50", "2018T1"): 7,
    ("PROTEGIDA_TOTAL", "PR50", "2024T3"): 1,
    ("TOTAL_NUEVA", "ES", "2006T1"): -1,
    ("TOTAL_NUEVA", "CA09", "2006T1"): -1,
    ("TOTAL_NUEVA", "PR08", "2006T1"): -1,
    ("TOTAL_NUEVA", "PR20", "2011T2"): 167,
    ("TOTAL_NUEVA", "PR20", "2011T3"): 3,
    ("TOTAL_NUEVA", "PR44", "2018T1"): -7,
    ("TOTAL_NUEVA", "PR50", "2018T1"): 7,
    ("TOTAL_NUEVA", "PR50", "2024T3"): 1,
    ("TOTAL_SEGUNDA_MANO", "CA09", "2015T3"): -2,
}


def comprobar_identidades_eti(df: pd.DataFrame) -> None:
    """Sumas de la rejilla regimen x antiguedad en cada territorio y trimestre.

    Una celda en blanco (NULL) cuenta como 0 en la suma de partes. ValueError con la identidad, el territorio y
    el periodo si aparece una diferencia que no está en `EXCEPCIONES_IDENTIDADES` (o con otro importe); aviso si
    una de la lista ya no aparece (la fuente la habría corregido).
    """
    d = df.assign(celda=df["regimen"] + "_" + df["antiguedad"],
                  v=pd.to_numeric(df[MEDIDA], errors="coerce").astype("float64"))
    ancho = d.pivot_table(index=["cod_territorio", "periodo"], columns="celda", values="v", aggfunc="first",
                          dropna=False)
    vistas = {}
    for nombre, total, partes in IDENTIDADES:
        dif = ancho[total] - ancho[partes].sum(axis=1, min_count=1)
        for (terr, per), v in dif[dif.notna() & (dif != 0)].items():
            vistas[(nombre, terr, per)] = v
    nuevas = {k: v for k, v in vistas.items() if EXCEPCIONES_IDENTIDADES.get(k) != v}
    if nuevas:
        (nombre, terr, per), v = sorted(nuevas.items())[0]
        raise ValueError(f"{TABLA}: identidad {nombre} rota en {terr} {per} (diferencia {v:g}; "
                         f"{len(nuevas)} diferencias fuera de la lista cerrada); el boletín ha cambiado")
    desaparecidas = sorted(set(EXCEPCIONES_IDENTIDADES) - set(vistas))
    if desaparecidas:
        warnings.warn(f"{TABLA}: {len(desaparecidas)} diferencias conocidas ya no aparecen (p. ej. "
                      f"{desaparecidas[0]}); revisar EXCEPCIONES_IDENTIDADES", stacklevel=2)


def transformar(paths: dict[str, Path], fecha_descarga: date) -> pd.DataFrame:
    """Lee los nueve boletines (`paths`: código sedal -> archivo), comprueba las sumas y valida la tabla."""
    faltan = sorted(set(BOLETINES) - set(paths))
    if faltan:
        raise ValueError(f"{TABLA}: faltan boletines {faltan}")
    maestro = cargar_maestro(LIBRO)
    partes = [matriz_a_filas(paths[c], f"MIVAU-{c}", {"regimen": reg, "antiguedad": ant}, MEDIDA, maestro,
                             frecuencia="T", omitir=OMITIR) for c, (reg, ant) in BOLETINES.items()]
    filas = pd.concat(partes, ignore_index=True)
    comprobar_identidades_eti(filas)
    return tabla_final(filas, "MIVAU-34010110/ETI", TABLA, DIMENSIONES, MEDIDA, maestro, fecha_descarga)


def _url(codigo: str) -> str:
    """URL del boletín: la de 34010110 en tablas.csv con su código cambiado (la de MIVAU-ETI es la página índice)."""
    return url_dataset("MIVAU-34010110").replace("34010110", codigo)


@lru_cache(maxsize=1)
def _ejecutar_cacheado(fecha_descarga: date) -> pd.DataFrame:
    paths = {c: mivau.descargar(_url(c), f"MIVAU-{c}", DESCARGAS) for c in BOLETINES}
    tabla = transformar(paths, fecha_descarga)
    escribir_csv(tabla, TABLA)
    return tabla


def ejecutar(fecha_descarga: date) -> pd.DataFrame:
    """Descarga los nueve boletines y escribe etl/salida/<TABLA>.csv (una vez por proceso y fecha)."""
    return _ejecutar_cacheado(fecha_descarga)


# Un objeto por dataset_id para el REGISTRO; los dos comparten tabla y `ejecutar`.
FUENTES = [SimpleNamespace(DATASET_ID=i, TABLA=TABLA, DIMENSIONES=DIMENSIONES, MEDIDAS=MEDIDAS, ejecutar=ejecutar)
           for i in DATASET_IDS]
