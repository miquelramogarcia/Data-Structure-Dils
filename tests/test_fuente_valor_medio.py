from datetime import date
from pathlib import Path

import pytest

from etl.fuentes import REGISTRO, mivau_valor_medio as vm
from etl.lib import mivau
from etl.lib.fuente_comun import LIBRO, validar_o_fallar
from etl.lib.territorios import cargar_maestro

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)
IDS = ["MIVAU-34020150", "MIVAU-34020160", "MIVAU-34020170", "MIVAU-34020180"]


@pytest.fixture(scope="module")
def tabla():
    return vm.transformar({i: FIXTURES / f"{i.split('-')[1]}.xls" for i in IDS}, FECHA)


def _v(tabla, id_registro):
    s = tabla.set_index("id_registro")["valor_medio_eur"]
    return s.loc[id_registro]


def test_registradas_las_cuatro_en_una_tabla():
    for i in IDS:
        f = REGISTRO[i]
        assert f.DATASET_ID == i and f.TABLA == "mivau_valor_medio_vivienda_libre"
        assert f.DIMENSIONES == ["tipo_comprador", "antiguedad"] and f.MEDIDAS == ["valor_medio_eur"]
        assert f.CUADRE is False  # las medias no suman: no se ejecuta cuadre_jerarquico
        assert f.ejecutar is vm.ejecutar  # una sola ejecucion produce la tabla de los cuatro


def test_valores_conocidos_total(tabla):
    assert _v(tabla, "ES_TOTAL_TOTAL_2004T1") == 124201.8  # 34020150, hoja "2004, ..., 2007", C16
    assert _v(tabla, "ES_TOTAL_TOTAL_2026T2") == 228036.1  # 34020150, hoja "2024, 2025, 2026", L16


def test_valores_conocidos_nueva_y_segunda_mano(tabla):
    assert _v(tabla, "ES_TOTAL_NUEVA_2004T1") == 144967.7  # 34020160, C16
    assert _v(tabla, "ES_TOTAL_NUEVA_2026T2") == 291742.2  # 34020160, L16 de la ultima hoja
    assert _v(tabla, "ES_TOTAL_SEGUNDA_MANO_2004T1") == 114141.9  # 34020170, C16
    assert _v(tabla, "ES_TOTAL_SEGUNDA_MANO_2026T2") == 220815.0  # 34020170, L16 de la ultima hoja
    assert _v(tabla, "PR04_TOTAL_TOTAL_2026T2") == 147992.2  # Almeria, 34020150, L18


def test_valores_conocidos_extranjeros(tabla):
    p = "ES_EXTRANJERO_RESIDENTE_"
    assert _v(tabla, p + "TOTAL_2019T1") == 140175.7  # hoja "1t 2019", D16
    assert _v(tabla, p + "NUEVA_2019T1") == 237355.5  # E16
    assert _v(tabla, p + "SEGUNDA_MANO_2019T1") == 135227.2  # F16
    assert _v(tabla, p + "TOTAL_2026T2") == 222271.5  # hoja "2t 2026", D16
    assert _v(tabla, p + "NUEVA_2026T2") == 329299.3
    assert _v(tabla, p + "SEGUNDA_MANO_2026T2") == 215965.2
    assert _v(tabla, "PR04_EXTRANJERO_RESIDENTE_TOTAL_2026T2") == 117191.4  # Almeria, D18


def test_guion_es_nulo_no_cero(tabla):
    t = tabla.set_index("id_registro")["valor_medio_eur"]
    assert t.isna()["PR14_EXTRANJERO_RESIDENTE_NUEVA_2019T1"]  # Cordoba, "-" en E20 de "1t 2019"
    assert t.isna()["PR51_EXTRANJERO_RESIDENTE_TOTAL_2026T2"]  # Ceuta, "-" en D78 de "2t 2026"
    # un 0 literal de la fuente se queda como 0 (no pasa a NULL): Zamora 3t y 4t 2022 (E45) y Albacete 2t y
    # 3t 2024 (E47) en vivienda nueva de extranjeros; son los unicos ceros de la tabla
    ceros = sorted(t[t == 0].index)
    assert ceros == ["PR02_EXTRANJERO_RESIDENTE_NUEVA_2024T2", "PR02_EXTRANJERO_RESIDENTE_NUEVA_2024T3",
                     "PR49_EXTRANJERO_RESIDENTE_NUEVA_2022T3", "PR49_EXTRANJERO_RESIDENTE_NUEVA_2022T4"]
    assert (t.dropna() >= 0).all()


def test_uniprovincial_copiada(tabla):
    a, b = (_v(tabla, f"{c}_EXTRANJERO_RESIDENTE_TOTAL_2026T2") for c in ("PR28", "CA13"))
    assert a == b == 438235.7  # Madrid, D69 de "2t 2026"


def test_forma_claves_y_niveles(tabla):
    assert tabla["id_registro"].is_unique
    assert set(tabla["tipo_comprador"]) == {"TOTAL", "EXTRANJERO_RESIDENTE"}
    assert set(tabla["antiguedad"]) == {"TOTAL", "NUEVA", "SEGUNDA_MANO"}
    # 72 territorios; 90 trimestres (2004T1-2026T2) x 3 series + 30 trimestres (2019T1-2026T2) x 3 series
    assert len(tabla) == 72 * (90 * 3 + 30 * 3)
    assert set(tabla["nivel"]) == {"Nacional", "CCAA", "Provincia"}
    assert "Ceuta y Melilla" not in set(tabla["nombre_ccaa"])  # agregado sin codigo INE: no se carga
    assert tabla["id_registro"].str.len().max() <= 64


def test_provisionales(tabla):
    def prov(tc, an):
        return sorted(tabla[(tabla["tipo_comprador"] == tc) & (tabla["antiguedad"] == an)
                            & (tabla["provisional"] == 1)]["periodo"].unique())
    assert prov("TOTAL", "TOTAL") == prov("TOTAL", "NUEVA") == prov("TOTAL", "SEGUNDA_MANO") == ["2026T2"]
    # pie "** Datos provisionales." en las hojas 2t 2024, 4t 2024, 1t 2026 y 2t 2026
    for an in ("TOTAL", "NUEVA", "SEGUNDA_MANO"):
        assert prov("EXTRANJERO_RESIDENTE", an) == ["2024T2", "2024T4", "2026T1", "2026T2"]


def test_validacion_limpia(tabla):
    validar_o_fallar(tabla, vm.TABLA, cargar_maestro(LIBRO))


def test_lector_hojas_trimestre():
    df = mivau.leer_hojas_trimestre(FIXTURES / "34020180.xls")
    assert list(df.columns) == ["hoja", "anio", "trimestre", "territorio_txt", "columna_txt", "valor_txt",
                                "provisional"]
    assert df["hoja"].nunique() == 30 and df["territorio_txt"].nunique() == 64
    assert sorted(df["columna_txt"].unique()) == ["TOTAL", "Vivienda de segunda mano", "Vivienda nueva"]
    f = df[(df["anio"] == 2026) & (df["trimestre"] == 2) & (df["territorio_txt"] == "TOTAL NACIONAL")]
    assert len(f) == 3 and f["provisional"].all()
    assert len(df) == 30 * 64 * 3


def test_ejecutar_una_vez_para_los_cuatro(monkeypatch, tmp_path):
    llamadas = []
    monkeypatch.setattr(vm, "_ejecutar", lambda fecha: llamadas.append(fecha) or "tabla")
    vm._ejecutar_cacheado.cache_clear()
    try:
        assert [vm.ejecutar(FECHA) for _ in IDS] == ["tabla"] * 4 and llamadas == [FECHA]
    finally:
        vm._ejecutar_cacheado.cache_clear()
