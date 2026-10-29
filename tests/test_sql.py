import pandas as pd

from etl.catalogo.sql import cargar_catalogo, create_table_sql

VPO = "mivau_vpo_calificaciones_definitivas"


def _sql():
    _, campos = cargar_catalogo()
    return create_table_sql("MIVAU", VPO, campos[campos["tabla"] == VPO])


def test_create_vpo_contiene_pk():
    assert "PRIMARY KEY (`id_registro`)" in _sql()


def test_create_nullable():
    sql = _sql()
    assert any(l.strip().startswith("`cod_provincia`") and " NULL" in l and "NOT NULL" not in l
               for l in sql.splitlines())
    assert any(l.strip().startswith("`nivel`") and "NOT NULL" in l for l in sql.splitlines())


def test_create_escapa_comillas():
    campos = pd.DataFrame([{"tabla": "t", "campo": "x", "tipo_mysql": "INT", "nulo": "SÍ", "clave": "",
                            "descripcion": "valor d'ejemplo", "ejemplo": ""}])
    assert "COMMENT 'valor d''ejemplo'" in create_table_sql("MIVAU", "t", campos)


def test_create_index():
    assert "INDEX `idx_fecha` (`fecha`)" in _sql()
