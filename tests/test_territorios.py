from pathlib import Path

import pandas as pd
import pytest

from etl.lib.territorios import (TerritorioDesconocido, cargar_maestro,
                                 expandir_uniprovinciales, normalizar, resolver)

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def M():
    return cargar_maestro(RAIZ / "Data Dils.xlsx")


def test_normalizar():
    assert normalizar("  Andalucía   Oriental ") == "andalucia oriental"


def test_resolver_provincia(M):
    assert resolver(M, "Almería")["cod_territorio"] == "PR04"


def test_resolver_total_nacional(M):
    assert resolver(M, "TOTAL NACIONAL")["cod_territorio"] == "ES"


def test_resolver_ambiguo_por_nivel(M):
    assert resolver(M, "Cantabria")["cod_territorio"] == "CA06"
    assert resolver(M, "Cantabria", nivel="Provincia")["cod_territorio"] == "PR39"


def test_resolver_desconocido_falla(M):
    with pytest.raises(TerritorioDesconocido, match="Atlantis"):
        resolver(M, "Atlantis")


def test_resolver_devuelve_none_no_nan(M):
    r = resolver(M, "Andalucía")
    assert r["cod_provincia"] is None and r["cod_municipio"] is None


def test_expandir_uniprovinciales(M):
    # CA13 (Madrid) se expande a PR28; CA01 no se toca
    filas = []
    for texto, v in [("Madrid, Comunidad de", 5), ("Andalucía", 7)]:
        filas.append({**resolver(M, texto), "periodo": "2026M06", "valor": v})
    df = pd.DataFrame(filas)
    out = expandir_uniprovinciales(df, M)
    assert len(out) == 3
    pr = out[out["cod_territorio"] == "PR28"]
    assert len(pr) == 1 and pr.iloc[0]["valor"] == 5 and pr.iloc[0]["periodo"] == "2026M06"
    assert not (out["cod_territorio"].isin(["PR04"])).any()
    # idempotente: no duplica
    assert len(expandir_uniprovinciales(out, M)) == 3
