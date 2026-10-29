"""Prototipo de maestros como tablas MySQL (Tarea 17): integridad referencial con los CSV de etl/salida/."""
from pathlib import Path

import pandas as pd
import pytest

from etl.catalogo.sql import cargar_catalogo
from prototipos.maestros import generar as g

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "etl" / "salida"
LIBRO = RAIZ / "Data Dils.xlsx"
pytestmark = pytest.mark.skipif(not LIBRO.exists(), reason="Falta Data Dils.xlsx")


@pytest.fixture(scope="module")
def dims():
    return g.construir_dimensiones(LIBRO, SALIDA)


def _csvs():
    return sorted(SALIDA.glob("mivau_*.csv"))  # el de SERPAVI no se versiona: si falta, simplemente no está


def test_hay_csv_de_salida():
    assert _csvs(), "no hay CSV en etl/salida/"


def test_territorios_de_las_tablas_existen(dims):
    cods = set(dims["dim_territorio"]["cod_territorio"])
    for csv in _csvs():
        usados = set(pd.read_csv(csv, sep=";", dtype=str, usecols=["cod_territorio"])["cod_territorio"])
        assert not usados - cods, f"{csv.name}: territorios fuera de dim_territorio: {sorted(usados - cods)[:5]}"


def test_periodos_de_las_tablas_existen(dims):
    periodos = set(dims["dim_periodo"]["periodo"])
    for csv in _csvs():
        usados = set(pd.read_csv(csv, sep=";", dtype=str, usecols=["periodo"])["periodo"])
        assert not usados - periodos, f"{csv.name}: periodos fuera de dim_periodo: {sorted(usados - periodos)[:5]}"


def test_categorias_de_las_tablas_existen(dims):
    cat = set(zip(dims["dim_categoria"]["dimension"], dims["dim_categoria"]["codigo"]))
    _, campos = cargar_catalogo()
    for fuente in g.fuentes_con_datos():
        csv = SALIDA / f"{fuente.TABLA}.csv"
        if not csv.exists():
            continue
        df = pd.read_csv(csv, sep=";", dtype=str)
        for d in fuente.DIMENSIONES:
            faltan = {(d, v) for v in df[d].unique()} - cat
            assert not faltan, f"{fuente.TABLA}: categorías fuera de dim_categoria: {sorted(faltan)[:5]}"


@pytest.mark.parametrize("tabla,pk", [("dim_territorio", ["cod_territorio"]), ("dim_periodo", ["periodo"]),
                                      ("dim_categoria", ["dimension", "codigo"]),
                                      ("dim_territorio_alias", ["id_alias"])])
def test_sin_pk_duplicadas(dims, tabla, pk):
    assert not dims[tabla].duplicated(pk).any()
    assert dims[tabla][pk].notna().all().all()


def test_alias_apuntan_a_territorios_existentes(dims):
    assert set(dims["dim_territorio_alias"]["cod_territorio"]) <= set(dims["dim_territorio"]["cod_territorio"])


def test_dim_periodo_jerarquia(dims):
    p = dims["dim_periodo"].set_index("periodo")
    assert p.loc["2026M06", "periodo_padre"] == "2026T2"
    assert p.loc["2026T2", "periodo_padre"] == "2026"
    assert pd.isna(p.loc["2026", "periodo_padre"])
    assert (p.loc["2026M06", "frecuencia"], str(p.loc["2026M06", "fecha"]), str(p.loc["2026M06", "fecha_fin"])) == \
           ("M", "2026-06-01", "2026-06-30")
    assert str(p.loc["2026T2", "fecha_fin"]) == "2026-06-30" and str(p.loc["2024", "fecha_fin"]) == "2024-12-31"
    assert set(p["periodo_padre"].dropna()) <= set(p.index)
    assert {"anio", "trimestre", "mes"}.isdisjoint(p.columns)  # ya son columnas generadas de las tablas de datos


def test_dim_periodo_orden_padres_primero(dims):
    vistos = set()
    for per, padre in zip(dims["dim_periodo"]["periodo"], dims["dim_periodo"]["periodo_padre"]):
        assert pd.isna(padre) or padre in vistos, f"{per} aparece antes que su padre {padre}"
        vistos.add(per)


def test_fk_cubren_todas_las_tablas_con_datos():
    sql = g.generar_fk_sql()
    tablas, _ = cargar_catalogo()
    con_datos = set(tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")]["tabla"])
    assert con_datos
    for t in con_datos:
        assert f"`MIVAU`.`{t}`" in sql
        assert sql.count(f"`MIVAU`.`{t}`\n") == 2 or sql.count(f"ALTER TABLE `MIVAU`.`{t}`") == 2
    assert "REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`)" in sql
    assert "REFERENCES `MAESTROS`.`dim_periodo` (`periodo`)" in sql
    ejecutable = "\n".join(l for l in sql.splitlines() if not l.startswith("--"))
    assert "dim_categoria" not in ejecutable  # solo documentada, no creada


def test_nombres_de_constraint_caben_en_mysql():
    import re
    for nombre in re.findall(r"ADD CONSTRAINT `([^`]+)`", g.generar_fk_sql()):
        assert len(nombre) <= 64, nombre
    assert len(set(re.findall(r"ADD CONSTRAINT `([^`]+)`", g.generar_fk_sql()))) == \
           len(re.findall(r"ADD CONSTRAINT `([^`]+)`", g.generar_fk_sql()))


def test_ddl_define_las_cuatro_dimensiones():
    ddl = g.generar_ddl()
    for t in ("dim_territorio", "dim_territorio_alias", "dim_periodo", "dim_categoria"):
        assert f"CREATE TABLE IF NOT EXISTS `MAESTROS`.`{t}`" in ddl
    assert "CREATE SCHEMA IF NOT EXISTS `MAESTROS`" in ddl


def test_archivos_generados_coinciden_con_el_generador():
    """Los .sql versionados son los que produce el generador (no se editan a mano)."""
    assert (RAIZ / "prototipos" / "maestros" / "maestros.sql").read_text(encoding="utf-8") == g.generar_maestros_sql()
    assert (RAIZ / "prototipos" / "maestros" / "maestros_fk.sql").read_text(encoding="utf-8") == g.generar_fk_sql()


def test_hoja_del_libro():
    from prototipos.maestros import hoja_libro
    (nombre, df), = hoja_libro.hojas()
    assert nombre == "Maestros (prototipo)" and len(nombre) <= 31
    assert "dim_territorio" in "\n".join(df.iloc[:, -1].astype(str))


def test_carga_de_datos_en_orden_de_dependencias():
    sql = g.generar_maestros_sql()
    a = sql.index("INFILE 'prototipos/maestros/datos/dim_territorio.csv'")
    b = sql.index("INFILE 'prototipos/maestros/datos/dim_territorio_alias.csv'")
    assert a < b
