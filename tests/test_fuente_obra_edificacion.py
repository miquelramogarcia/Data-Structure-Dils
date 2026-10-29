from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from etl.fuentes import REGISTRO, mivau_fin_obra as fin, mivau_visados as visados
from etl.lib import fuente_comun
from etl.lib.fuente_comun import LIBRO, validar_o_fallar
from etl.lib.territorios import cargar_maestro
from etl.lib.validar import cuadre_jerarquico

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = date(2026, 10, 29)
# 416 meses (1991M11 a 2026M06) x 1 territorio (nacional: el archivo no trae CCAA ni provincias)
MESES = 416


@pytest.fixture(scope="module")
def t_fin():
    return fin.transformar(FIXTURES / "09011600.xls", FECHA)


@pytest.fixture(scope="module")
def t_vis():
    return visados.transformar(FIXTURES / "09010600.xls", FECHA)


def _v(tabla, id_registro, medida):
    return tabla.set_index("id_registro").loc[id_registro, medida]


def test_registradas():
    assert REGISTRO["MIVAU-BOL09-FINOBRA"] is fin and REGISTRO["MIVAU-BOL09-VISADOS"] is visados
    assert fin.TABLA == "mivau_certificados_fin_obra" and fin.DIMENSIONES == ["promotor"]
    assert fin.MEDIDAS == ["num_viviendas", "valor_liquidacion_miles_eur"]
    assert visados.TABLA == "mivau_visados_direccion_obra" and visados.DIMENSIONES == ["tipo_obra"]
    assert visados.MEDIDAS == ["num_viviendas", "superficie_media_m2"]


def test_fin_obra_valores_conocidos(t_fin):
    # Archivo 09011600.xls, hoja APAREJA_15. Cabeceras de columna: imagen incrustada en el .xls.
    assert _v(t_fin, "ES_TOTAL_2026M06", "num_viviendas") == 39286                      # E14
    assert _v(t_fin, "ES_PRIVADO_TOTAL_2026M06", "num_viviendas") == 39175              # F14
    assert _v(t_fin, "ES_PRIVADO_PERSONAS_FISICAS_2026M06", "num_viviendas") == 9814    # G14
    assert _v(t_fin, "ES_PRIVADO_SOCIEDADES_2026M06", "num_viviendas") == 28270         # H14
    assert _v(t_fin, "ES_PRIVADO_COOPERATIVAS_2026M06", "num_viviendas") == 442         # I14
    assert _v(t_fin, "ES_PRIVADO_OTROS_2026M06", "num_viviendas") == 649                # J14
    assert _v(t_fin, "ES_ADMINISTRACIONES_PUBLICAS_2026M06", "num_viviendas") == 111    # M14
    assert _v(t_fin, "ES_TOTAL_2026M06", "valor_liquidacion_miles_eur") == 3087215.8    # N14
    assert _v(t_fin, "ES_TOTAL_1991M11", "num_viviendas") == 19393                      # E429 (primer periodo)
    assert pd.isna(_v(t_fin, "ES_PRIVADO_TOTAL_2026M06", "valor_liquidacion_miles_eur"))


def test_fin_obra_forma(t_fin):
    assert len(t_fin) == 7 * MESES and t_fin["id_registro"].is_unique
    assert set(t_fin["promotor"]) == {"TOTAL", "PRIVADO_TOTAL", "PRIVADO_PERSONAS_FISICAS", "PRIVADO_SOCIEDADES",
                                      "PRIVADO_COOPERATIVAS", "PRIVADO_OTROS", "ADMINISTRACIONES_PUBLICAS"}
    assert (t_fin["cod_territorio"] == "ES").all() and (t_fin["frecuencia"] == "M").all()
    assert t_fin["periodo"].min() == "1991M11" and t_fin["periodo"].max() == "2026M06"
    assert (t_fin["provisional"] == 0).all()
    assert str(t_fin["num_viviendas"].dtype) == "Int64"
    # el valor de liquidación solo existe para el total de promotores
    assert t_fin.loc[t_fin["promotor"] != "TOTAL", "valor_liquidacion_miles_eur"].isna().all()
    assert t_fin.loc[t_fin["promotor"] == "TOTAL", "valor_liquidacion_miles_eur"].notna().all()


def test_visados_valores_conocidos(t_vis):
    # Archivo 09010600.xls, hoja APAREJA_6. Cabeceras de columna: imagen incrustada en el .xls.
    nv = "num_viviendas"
    assert _v(t_vis, "ES_TOTAL_2026M06", nv) == 17149                    # D14
    assert _v(t_vis, "ES_OBRA_NUEVA_2026M06", nv) == 14603               # E14
    assert _v(t_vis, "ES_OBRA_NUEVA_UNIFAMILIAR_2026M06", nv) == 2455    # F14
    assert _v(t_vis, "ES_OBRA_NUEVA_EN_BLOQUE_2026M06", nv) == 12130     # G14
    assert _v(t_vis, "ES_OBRA_NUEVA_OTROS_EDIFICIOS_2026M06", nv) == 18  # H14
    assert _v(t_vis, "ES_AMPLIACION_2026M06", nv) == 275                 # I14
    assert _v(t_vis, "ES_REFORMA_RESTAURACION_2026M06", nv) == 2271      # J14
    sm = "superficie_media_m2"
    assert _v(t_vis, "ES_OBRA_NUEVA_UNIFAMILIAR_2026M06", sm) == pytest.approx(192.0029, abs=1e-4)   # K14
    assert _v(t_vis, "ES_OBRA_NUEVA_EN_BLOQUE_2026M06", sm) == pytest.approx(97.9338, abs=1e-4)      # L14
    assert _v(t_vis, "ES_AMPLIACION_2026M06", sm) == pytest.approx(161.9127, abs=1e-4)               # N14
    assert _v(t_vis, "ES_TOTAL_1991M11", nv) > 0


def test_visados_guion_es_nulo_y_cero_se_conserva(t_vis):
    # 2025M08: '-' en la superficie media de "otros edificios" (M24) porque hubo 0 viviendas (H24 = 0).
    assert pd.isna(_v(t_vis, "ES_OBRA_NUEVA_OTROS_EDIFICIOS_2025M08", "superficie_media_m2"))
    assert _v(t_vis, "ES_OBRA_NUEVA_OTROS_EDIFICIOS_2025M08", "num_viviendas") == 0


def test_visados_forma(t_vis):
    assert len(t_vis) == 7 * MESES and t_vis["id_registro"].is_unique
    assert set(t_vis["tipo_obra"]) == {"TOTAL", "OBRA_NUEVA", "OBRA_NUEVA_UNIFAMILIAR", "OBRA_NUEVA_EN_BLOQUE",
                                       "OBRA_NUEVA_OTROS_EDIFICIOS", "AMPLIACION", "REFORMA_RESTAURACION"}
    sm = t_vis.groupby("tipo_obra")["superficie_media_m2"].count()
    assert sm["TOTAL"] == 0 and sm["OBRA_NUEVA"] == 0 and sm["REFORMA_RESTAURACION"] == 0
    assert sm["OBRA_NUEVA_UNIFAMILIAR"] == MESES and sm["AMPLIACION"] == MESES
    assert sm["OBRA_NUEVA_OTROS_EDIFICIOS"] == 370  # 46 meses con '-' en la fuente


def test_validacion_limpia(t_fin, t_vis):
    maestro = cargar_maestro(LIBRO)
    validar_o_fallar(t_fin, fin.TABLA, maestro)
    validar_o_fallar(t_vis, visados.TABLA, maestro)


def test_cuadre_jerarquico_territorial_vacio(t_fin, t_vis):
    # Solo hay nivel Nacional: no hay hijos territoriales que comparar.
    assert cuadre_jerarquico(t_fin, "num_viviendas", ["promotor"]).empty
    assert cuadre_jerarquico(t_vis, "num_viviendas", ["tipo_obra"]).empty


def _por_periodo(tabla, dim):
    return tabla.pivot(index="periodo", columns=dim, values="num_viviendas").astype("int64")


def test_cuadre_entre_categorias_fin_obra(t_fin):
    # Sin excepciones: TOTAL = privado + administraciones; privado = personas físicas + sociedades + cooperativas + otros
    p = _por_periodo(t_fin, "promotor")
    assert (p["TOTAL"] - p["PRIVADO_TOTAL"] - p["ADMINISTRACIONES_PUBLICAS"] == 0).all()
    privados = p[["PRIVADO_PERSONAS_FISICAS", "PRIVADO_SOCIEDADES", "PRIVADO_COOPERATIVAS", "PRIVADO_OTROS"]]
    assert (p["PRIVADO_TOTAL"] - privados.sum(axis=1) == 0).all()


def test_cuadre_entre_categorias_visados(t_vis):
    # Sin excepciones: TOTAL = obra nueva + ampliación + reforma; obra nueva = unifamiliar + bloque + otros
    p = _por_periodo(t_vis, "tipo_obra")
    assert (p["TOTAL"] - p["OBRA_NUEVA"] - p["AMPLIACION"] - p["REFORMA_RESTAURACION"] == 0).all()
    nueva = p[["OBRA_NUEVA_UNIFAMILIAR", "OBRA_NUEVA_EN_BLOQUE", "OBRA_NUEVA_OTROS_EDIFICIOS"]]
    assert (p["OBRA_NUEVA"] - nueva.sum(axis=1) == 0).all()


def test_columna_no_mapeada_con_datos_falla(tmp_path, monkeypatch):
    largo = pd.DataFrame([{"hoja": "h", "territorio_txt": "TOTAL NACIONAL", "anio": 2026, "mes": 1,
                           "columna": 99, "valor_txt": "5"}])
    monkeypatch.setattr(fuente_comun.mivau, "leer_serie_vertical", lambda p: largo)
    with pytest.raises(ValueError, match="columna 99"):
        fuente_comun.serie_vertical_a_tabla(tmp_path / "x.xls", "X", "mivau_certificados_fin_obra", "promotor",
                                            {0: ("TOTAL", "num_viviendas")}, cargar_maestro(LIBRO), FECHA)


def test_tabla_final_medidas_decimales():
    maestro = cargar_maestro(LIBRO)
    filas = pd.DataFrame([{"nivel": "Nacional", "cod_territorio": "ES", "cod_ccaa": "00",
                           "nombre_ccaa": "Total Nacional", "cod_provincia": None, "nombre_provincia": None,
                           "cod_municipio": None, "nombre_municipio": None, "promotor": "TOTAL",
                           "periodo": "2026M01", "frecuencia": "M", "anio": 2026, "trimestre": None, "mes": 1,
                           "fecha": date(2026, 1, 1), "num_viviendas": 10.0, "valor_liquidacion_miles_eur": 2.5,
                           "provisional": 0}])
    t = fuente_comun.tabla_final(filas, "X", "mivau_certificados_fin_obra", ["promotor"], "num_viviendas", maestro,
                                 FECHA, medidas_decimales=["valor_liquidacion_miles_eur"])
    assert t.loc[0, "valor_liquidacion_miles_eur"] == 2.5 and str(t["num_viviendas"].dtype) == "Int64"
