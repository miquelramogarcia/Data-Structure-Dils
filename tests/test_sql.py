from pathlib import Path

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


# --- columnas generadas y carga ---
import pandas as pd

from etl.catalogo.sql import load_data_sql


def _campos_gen():
    filas = [("id_registro", "VARCHAR(64)", "NO", "PRIMARY KEY", ""), ("frecuencia", "CHAR(1)", "NO", "", ""),
             ("anio", "SMALLINT UNSIGNED", "NO", "", "YEAR(fecha)"),
             ("trimestre", "TINYINT UNSIGNED", "SÍ", "", "CASE WHEN frecuencia = 'T' THEN QUARTER(fecha) END"),
             ("fecha", "DATE", "NO", "INDEX", ""), ("valor", "INT", "SÍ", "", "")]
    return pd.DataFrame([dict(tabla="t", campo=c, tipo_mysql=t, nulo=n, clave=k, descripcion="d", ejemplo="", generado=g)
                         for c, t, n, k, g in filas])


def test_create_columna_generada():
    sql = create_table_sql("MIVAU", "t", _campos_gen())
    assert "`anio` SMALLINT UNSIGNED GENERATED ALWAYS AS (YEAR(fecha)) STORED NOT NULL COMMENT 'd'" in sql
    assert "`trimestre` TINYINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN frecuencia = 'T' THEN QUARTER(fecha) END) STORED NULL" in sql
    assert "`valor` INT NULL" in sql and "GENERATED" not in sql.split("`valor`")[1]


def test_create_sin_columna_generado_sigue_funcionando():
    campos = _campos_gen().drop(columns="generado")
    assert "GENERATED" not in create_table_sql("MIVAU", "t", campos)


def test_load_data_omite_generadas_y_usa_nullif():
    sql = load_data_sql("MIVAU", "t", _campos_gen())
    assert "(`id_registro`, `frecuencia`, @omitir_anio, @omitir_trimestre, `fecha`, @valor)" in sql
    assert "SET `valor` = NULLIF(@valor, '');" in sql
    assert "LOAD DATA LOCAL INFILE 'etl/salida/t.csv' REPLACE INTO TABLE `MIVAU`.`t`" in sql
    assert r"LINES TERMINATED BY '\n'" in sql and "IGNORE 1 LINES" in sql
    assert "ESCAPED BY ''" in sql


RAIZ = Path(__file__).parent.parent


def test_load_data_columnas_igual_que_cabecera_csv(tmp_path):
    import re
    from etl.catalogo.sql import escribir_carga
    destino = tmp_path / "load_data.sql"
    escribir_carga(destino)
    texto = destino.read_text(encoding="utf-8")
    tablas, _ = cargar_catalogo()
    con_csv = {t for t in tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")]["tabla"]
               if (RAIZ / "etl" / "salida" / f"{t}.csv").exists()}
    sentencias = re.findall(r"INTO TABLE `\w+`\.`(\w+)`.*?IGNORE 1 LINES\n\((.*?)\)", texto, re.S)
    assert {t for t, _ in sentencias} == con_csv
    assert len(sentencias) == len(con_csv)
    for tabla, cols in sentencias:
        with (RAIZ / "etl" / "salida" / f"{tabla}.csv").open(encoding="utf-8", newline="") as f:
            cabecera = f.readline().rstrip("\r\n").split(";")
        lista = [c.strip() for c in cols.split(",")]
        assert len(lista) == len(cabecera), tabla
        for var, col in zip(lista, cabecera):
            assert var.strip("`@").replace("omitir_", "", 1) == col, (tabla, var, col)
            assert var.startswith("@omitir_") == (col in ("anio", "trimestre", "mes")), (tabla, col)


def test_csv_terminan_en_el_terminador_de_load_data():
    from etl.catalogo.sql import FIN_LINEA_CSV
    rutas = sorted((RAIZ / "etl" / "salida").glob("*.csv"))
    assert rutas
    for ruta in rutas:
        with ruta.open("rb") as f:
            cabecera = f.readline(1_000_000)
            resto = f.read(5_000_000)
        assert cabecera.endswith(FIN_LINEA_CSV.encode()) and not cabecera.endswith(b"\r\n"), ruta.name
        assert b"\r\n" not in resto, ruta.name


def test_escribir_csv_usa_lf(tmp_path):
    from etl.lib.fuente_comun import escribir_csv
    ruta = escribir_csv(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}), "t", tmp_path)
    assert b"\r" not in ruta.read_bytes()


def test_escribir_carga_replace_y_show_warnings(tmp_path):
    from etl.catalogo.sql import escribir_carga
    destino = tmp_path / "load_data.sql"
    escribir_carga(destino)
    txt = destino.read_text(encoding="utf-8")
    cargas = txt.count("LOAD DATA LOCAL INFILE")
    assert cargas >= 1
    assert txt.count(" REPLACE INTO TABLE ") == cargas
    assert txt.count("SHOW WARNINGS LIMIT 20;") == cargas
    assert "--local-infile=1" in txt and "rutas absolutas" in txt
