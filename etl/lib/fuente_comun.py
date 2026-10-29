"""Helpers comunes a todas las fuentes: rutas, URL del catálogo, validación, CSV y matriz mensual → tabla."""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.lib import mivau
from etl.lib.modelo import construir_tabla
from etl.lib.periodos import periodo_mensual, periodo_trimestral
from etl.lib.territorios import expandir_uniprovinciales, normalizar, resolver
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


def _clave_texto(txt: str) -> str:
    return normalizar(txt)


def tabla_final(df: pd.DataFrame, dataset_id: str, tabla: str, dimensiones: list[str], medida: str,
                maestro: pd.DataFrame, fecha_descarga: date, entero: bool = True,
                descriptivas: list[str] | None = None) -> pd.DataFrame:
    """Filas con territorio + dimensiones + periodo + medida + provisional → tabla validada.

    expandir_uniprovinciales → construir_tabla → validar. `df` lleva ya las columnas del territorio, las
    dimensiones, las del periodo, `medida` (float o Int64) y `provisional`.
    """
    df = df.copy()
    if entero:
        df[medida] = df[medida].round().astype("Int64")
    df = expandir_uniprovinciales(df, maestro, claves=list(dimensiones) + ["periodo"])
    if entero:
        df[medida] = df[medida].astype("Int64")
    resultado = construir_tabla(df, list(dimensiones), [medida], fecha_descarga, descriptivas)
    try:
        validar_o_fallar(resultado, tabla, maestro)
    except ValueError as e:
        raise ValueError(f"{dataset_id}: {e}") from None
    return resultado


def matriz_a_filas(path: Path, dataset_id: str, dimensiones: dict[str, str], medida: str,
                   maestro: pd.DataFrame, frecuencia: str = "M",
                   omitir: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Matriz de territorios del MIVAU (mensual o trimestral) → filas listas para `tabla_final`.

    leer_matriz → resolver → periodo. `dimensiones` asigna un valor fijo a cada dimensión propia ({} si la
    fuente no tiene desglose). `frecuencia` "M" o "T": falla si alguna columna no lo es. `omitir`:
    etiquetas de territorio que son agregados sin código INE (se comparan sin tildes ni mayúsculas);
    cualquier otra etiqueta que no resuelva hace fallar el proceso. Una cabecera con marca de provisional
    ("2º (**)") pone `provisional` = 1 en esas filas. Sirve también para juntar varios archivos en una
    sola tabla antes de expandir y validar.
    """
    construir_periodo = {"M": periodo_mensual, "T": periodo_trimestral}[frecuencia]
    ignorar = {_clave_texto(o) for o in omitir}
    largo = mivau.leer_matriz(path)
    largo = largo[~largo["territorio_txt"].map(_clave_texto).isin(ignorar)]
    territorios = {t: resolver(maestro, t) for t in largo["territorio_txt"].unique()}
    filas = []
    for r in largo.itertuples(index=False):
        tipo, n = mivau.subperiodo(r.subperiodo_txt)
        if tipo != frecuencia:
            raise ValueError(f"Subperiodo no {'mensual' if frecuencia == 'M' else 'trimestral'} "
                             f"en {dataset_id}: {r.subperiodo_txt!r}")
        filas.append({**territorios[r.territorio_txt], **dimensiones,
                      **construir_periodo(int(r.anio), n), medida: mivau.a_numero(r.valor_txt),
                      "provisional": int(mivau.marca_provisional(r.subperiodo_txt))})
    return pd.DataFrame(filas)


def matriz_a_tabla(path: Path, dataset_id: str, tabla: str, dimensiones: dict[str, str], medida: str,
                   maestro: pd.DataFrame, fecha_descarga: date, entero: bool = True,
                   frecuencia: str = "M", omitir: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Matriz de territorios del MIVAU (mensual o trimestral) → tabla validada (`matriz_a_filas` + `tabla_final`)."""
    filas = matriz_a_filas(path, dataset_id, dimensiones, medida, maestro, frecuencia, omitir)
    return tabla_final(filas, dataset_id, tabla, list(dimensiones), medida, maestro, fecha_descarga, entero)
