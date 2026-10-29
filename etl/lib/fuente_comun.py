"""Helpers comunes a todas las fuentes: rutas, URL del catálogo, validación, CSV y matriz mensual → tabla."""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.lib import mivau
from etl.lib.modelo import construir_tabla
from etl.lib.periodos import periodo_mensual
from etl.lib.territorios import expandir_uniprovinciales, resolver
from etl.lib.validar import validar_tabla

RAIZ = Path(__file__).resolve().parents[2]
LIBRO = RAIZ / "Data Dils.xlsx"
SALIDA = RAIZ / "etl" / "salida"
DESCARGAS = RAIZ / "etl" / "descargas"


def url_dataset(dataset_id: str) -> str:
    """URL de descarga del dataset según la columna `fuente` de tablas.csv."""
    tablas, _ = cargar_catalogo()
    return tablas.loc[tablas["dataset_id"] == dataset_id, "fuente"].iloc[0].strip()


def validar_o_fallar(df: pd.DataFrame, tabla: str, maestro: pd.DataFrame) -> None:
    """Valida `df` contra los campos de `tabla` en el catálogo; ValueError con los mensajes si falla."""
    _, campos = cargar_catalogo()
    errores = validar_tabla(df, campos[campos["tabla"] == tabla], maestro)
    if errores:
        raise ValueError(f"{tabla}: validación fallida:\n" + "\n".join(errores))


def escribir_csv(df: pd.DataFrame, tabla: str, destino: Path = SALIDA) -> Path:
    """Escribe `<destino>/<tabla>.csv` en UTF-8 con ';' (fechas ISO, enteros Int64 sin '.0')."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{tabla}.csv"
    df.to_csv(ruta, sep=";", index=False, encoding="utf-8")
    return ruta


def matriz_a_tabla(path: Path, dataset_id: str, tabla: str, dimensiones: dict[str, str], medida: str,
                   maestro: pd.DataFrame, fecha_descarga: date, entero: bool = True) -> pd.DataFrame:
    """Matriz mensual de territorios del MIVAU → tabla validada.

    leer_matriz → resolver → periodo_mensual → expandir_uniprovinciales → construir_tabla → validar.
    `dimensiones` asigna un valor fijo a cada dimensión propia ({} si la fuente no tiene desglose).
    Falla si alguna columna no es mensual.
    """
    largo = mivau.leer_matriz(path)
    territorios = {t: resolver(maestro, t) for t in largo["territorio_txt"].unique()}
    filas = []
    for r in largo.itertuples(index=False):
        tipo, n = mivau.subperiodo(r.subperiodo_txt)
        if tipo != "M":
            raise ValueError(f"Subperiodo no mensual en {dataset_id}: {r.subperiodo_txt!r}")
        filas.append({**territorios[r.territorio_txt], **dimensiones,
                      **periodo_mensual(int(r.anio), n), medida: mivau.a_numero(r.valor_txt)})
    df = pd.DataFrame(filas)
    if entero:
        df[medida] = df[medida].round().astype("Int64")
    claves = list(dimensiones) + ["periodo"]
    df = expandir_uniprovinciales(df, maestro, claves=claves)
    if entero:
        df[medida] = df[medida].astype("Int64")
    df["provisional"] = 0
    resultado = construir_tabla(df, list(dimensiones), [medida], fecha_descarga)
    try:
        validar_o_fallar(resultado, tabla, maestro)
    except ValueError as e:
        raise ValueError(f"{dataset_id}: {e}") from None
    return resultado
