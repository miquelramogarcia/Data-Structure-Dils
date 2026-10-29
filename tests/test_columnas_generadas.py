"""anio/trimestre/mes son columnas generadas de MySQL: deben reproducir exactamente lo que hay en los CSV."""
from pathlib import Path

import pandas as pd
import pytest

from etl.catalogo.sql import cargar_catalogo

SALIDA = Path(__file__).parent.parent / "etl" / "salida"
CSVS = sorted(SALIDA.glob("*.csv"))
EXPRESIONES = {
    "anio": "YEAR(fecha)",
    "trimestre": "CASE WHEN frecuencia = 'T' THEN QUARTER(fecha) END",
    "mes": "CASE WHEN frecuencia = 'M' THEN MONTH(fecha) END",
}


def _recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """Evalúa en pandas las tres expresiones de EXPRESIONES (misma semántica que MySQL)."""
    f = pd.to_datetime(df["fecha"], format="%Y-%m-%d")
    return pd.DataFrame({
        "anio": f.dt.year.astype("Int64"),
        "trimestre": f.dt.quarter.astype("Int64").where(df["frecuencia"] == "T"),
        "mes": f.dt.month.astype("Int64").where(df["frecuencia"] == "M"),
    })


def _comprobar(ruta: Path) -> None:
    cols = ["frecuencia", "anio", "trimestre", "mes", "fecha"]
    for trozo in pd.read_csv(ruta, sep=";", usecols=cols, dtype={"frecuencia": str, "fecha": str},
                             chunksize=200_000):
        esperado = _recalcular(trozo)
        for c in ("anio", "trimestre", "mes"):
            real = trozo[c].astype("Int64")
            malas = ~((real == esperado[c]) | (real.isna() & esperado[c].isna()))
            assert not malas.any(), f"{ruta.name}: {c} no coincide con lo generado en {int(malas.sum())} filas"


@pytest.mark.parametrize("ruta", CSVS, ids=lambda p: p.stem)
def test_columnas_generadas_reproducen_el_csv(ruta):
    _comprobar(ruta)


def test_hay_csvs():
    assert len(CSVS) >= 11


def test_catalogo_marca_generadas_en_todas_las_tablas():
    _, campos = cargar_catalogo()
    for tabla, g in campos.groupby("tabla"):
        por_campo = dict(zip(g["campo"], g["generado"]))
        for c, expr in EXPRESIONES.items():
            assert por_campo[c] == expr, f"{tabla}.{c}"
        assert all(not v for k, v in por_campo.items() if k not in EXPRESIONES), tabla
        orden = list(g["campo"])
        assert orden.index("frecuencia") < orden.index("anio")  # legibilidad; fecha puede ir después (base column)
