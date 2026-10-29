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


def _df_madrid(M, v_ca, v_pr):
    return pd.DataFrame([
        {**resolver(M, "Madrid, Comunidad de"), "periodo": "2026M06", "valor": v_ca},
        {**resolver(M, "Madrid", nivel="Provincia"), "periodo": "2026M06", "valor": v_pr},
    ])


def test_expandir_no_duplica_si_provincia_existe_con_otro_valor(M):
    out = expandir_uniprovinciales(_df_madrid(M, 10, 11), M)
    assert len(out) == 2
    assert out[out["cod_territorio"] == "PR28"].iloc[0]["valor"] == 11


def test_expandir_con_claves_explicitas(M):
    df = _df_madrid(M, 10, 11)
    df["otra"] = [1, 2]  # columna numérica extra que no es clave
    assert len(expandir_uniprovinciales(df, M, claves=["periodo"])) == 2
    # con otro periodo en la provincia, la clave no coincide y se añade
    df.loc[1, "periodo"] = "2026M05"
    out = expandir_uniprovinciales(df, M, claves=["periodo"])
    assert len(out) == 3


# --- Municipios del INE (maestro ampliado con etl/lib/municipios_ine.csv) ---

def test_maestro_incluye_municipios_ine(M):
    mu = M[(M["nivel"] == "Municipio") & (M["fuente_alias"] == "INE")]  # sin los alias de territorios_extra.csv
    assert len(mu) == 8132
    assert mu["cod_territorio"].is_unique
    f = resolver(M, "Roquetas de Mar", nivel="Municipio")
    assert f["cod_territorio"] == "MU04079" and f["cod_municipio"] == "04079"
    assert f["cod_provincia"] == "04" and f["nombre_provincia"] == "Almería"
    assert f["cod_ccaa"] == "01" and f["nombre_ccaa"] == "Andalucía" and f["nivel"] == "Municipio"


def test_nombres_municipio_chocan_con_provincia_gana_provincia_y_ccaa(M):
    # sin nivel: CCAA > Provincia > Municipio, como antes de cargar los municipios
    assert resolver(M, "Madrid")["cod_territorio"] == "PR28"
    assert resolver(M, "Barcelona")["cod_territorio"] == "PR08"
    assert resolver(M, "Soria")["cod_territorio"] == "PR42"
    assert resolver(M, "Murcia")["cod_territorio"] == "PR30"
    assert resolver(M, "Cantabria")["cod_territorio"] == "CA06"
    assert resolver(M, "Ceuta")["cod_territorio"] == "CA18"
    # con nivel Municipio: el municipio
    assert resolver(M, "Madrid", nivel="Municipio")["cod_territorio"] == "MU28079"
    assert resolver(M, "Barcelona", nivel="Municipio")["cod_territorio"] == "MU08019"
    assert resolver(M, "Soria", nivel="Municipio")["cod_territorio"] == "MU42173"


def test_municipio_ambiguo_sin_provincia_falla(M):
    # mismo nombre en varias provincias: nunca se elige uno en silencio
    from etl.lib.territorios import TerritorioAmbiguo
    nombre = _municipio_repetido(M)
    with pytest.raises(TerritorioAmbiguo, match=nombre):
        resolver(M, nombre, nivel="Municipio")


def _municipio_repetido(M):
    mu = M[M["nivel"] == "Municipio"]
    rep = mu[mu["alias"].duplicated(keep=False)]
    assert len(rep), "el INE trae nombres repetidos entre provincias"
    return rep.iloc[0]["nombre_territorio"]


def test_resolver_municipio_con_provincia_desambigua(M):
    from etl.lib.territorios import resolver_municipio
    mu = M[M["nivel"] == "Municipio"]
    rep = mu[mu["alias"].duplicated(keep=False)]
    nombre = rep.iloc[0]["nombre_territorio"]
    for _, f in rep[rep["alias"] == rep.iloc[0]["alias"]].iterrows():
        r = resolver_municipio(M, nombre, f["nombre_provincia"])
        assert r["cod_territorio"] == f["cod_territorio"]


def test_resolver_municipio_fuera_de_la_provincia_falla(M):
    from etl.lib.territorios import resolver_municipio
    with pytest.raises(TerritorioDesconocido, match="Madrid.*Soria"):
        resolver_municipio(M, "Madrid", "Soria")


def test_municipio_articulo_al_final_y_al_principio(M):
    # el boletín escribe "Ejido (El)", "Línea de la Concepción (La)", "Palmas de Gran Canaria (Las)"
    assert resolver(M, "Ejido (El)", nivel="Municipio")["cod_territorio"] == "MU04902"
    assert resolver(M, "El Ejido", nivel="Municipio")["cod_territorio"] == "MU04902"
    assert resolver(M, "Palmas de Gran Canaria (Las)", nivel="Municipio")["cod_territorio"] == "MU35016"
    assert resolver(M, "Línea de la Concepción (La)", nivel="Municipio")["cod_territorio"] == "MU11022"


def test_articulo_no_cambia_provincias_ni_ccaa(M):
    # "Rioja (La)" y "Coruña (A)" siguen resolviéndose por sus alias; "Palmas (Las)" como provincia
    assert resolver(M, "Rioja (La)")["cod_territorio"] == "CA17"
    assert resolver(M, "Palmas (Las)")["cod_territorio"] == "PR35"


def test_municipio_nombre_bilingue_por_cualquiera_de_sus_partes(M):
    assert resolver(M, "Alcoy", nivel="Municipio")["cod_territorio"] == "MU03009"
    assert resolver(M, "Alcoi", nivel="Municipio")["cod_territorio"] == "MU03009"
    assert resolver(M, "Alcoy/Alcoi", nivel="Municipio")["cod_territorio"] == "MU03009"
    # sin nivel Municipio la parte suelta no resuelve (no se toca a CCAA ni provincias)
    with pytest.raises(TerritorioDesconocido):
        resolver(M, "Alcoy")
