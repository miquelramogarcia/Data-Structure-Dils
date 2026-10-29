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


def _tablas_compartidas():
    tablas = pd.DataFrame([
        {"dataset_id": "X-1", "esquema": "MIVAU", "tabla": "t_comun", "estadistica": "Valor tasado: vivienda libre total"},
        {"dataset_id": "X-2", "esquema": "MIVAU", "tabla": "t_comun", "estadistica": "Valor tasado: vivienda libre de hasta 5 años"},
        {"dataset_id": "X-3", "esquema": "MIVAU", "tabla": "t_otra", "estadistica": "Otra estadística"},
    ])
    campos = pd.DataFrame([{"tabla": t, "campo": "id_registro", "tipo_mysql": "VARCHAR(64)", "nulo": "NO",
                            "clave": "PRIMARY KEY", "descripcion": "clave", "ejemplo": ""}
                           for t in ("t_comun", "t_otra")])
    return tablas, campos


def test_descripcion_tabla_compartida_es_la_parte_comun():
    from etl.catalogo.sql import descripcion_tabla
    tablas, _ = _tablas_compartidas()
    assert descripcion_tabla(tablas, "MIVAU", "t_comun") == "Valor tasado: vivienda libre"
    assert descripcion_tabla(tablas, "MIVAU", "t_otra") == "Otra estadística"


def test_descripcion_tabla_explicita_gana():
    from etl.catalogo.sql import descripcion_tabla
    tablas, _ = _tablas_compartidas()
    tablas["descripcion_tabla"] = ["", "", ""]
    tablas.loc[0, "descripcion_tabla"] = "Descripción escrita a mano"
    assert descripcion_tabla(tablas, "MIVAU", "t_comun") == "Descripción escrita a mano"


def test_escribir_sql_un_solo_create_por_tabla(tmp_path, monkeypatch):
    from etl.catalogo import sql
    tablas, campos = _tablas_compartidas()
    monkeypatch.setattr(sql, "cargar_catalogo", lambda: (tablas, campos))
    destino = tmp_path / "x.sql"
    sql.escribir_sql(destino)
    txt = destino.read_text(encoding="utf-8")
    assert txt.count("CREATE TABLE IF NOT EXISTS `MIVAU`.`t_comun`") == 1
    assert txt.count("CREATE TABLE IF NOT EXISTS `MIVAU`.`t_otra`") == 1
    assert "COMMENT='Valor tasado: vivienda libre';" in txt


def test_real_ninguna_tabla_se_crea_dos_veces(tmp_path):
    from etl.catalogo import sql
    destino = tmp_path / "x.sql"
    sql.escribir_sql(destino)
    creadas = [l for l in destino.read_text(encoding="utf-8").splitlines() if l.startswith("CREATE TABLE")]
    assert len(creadas) == len(set(creadas))
