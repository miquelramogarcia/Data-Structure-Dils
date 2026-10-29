from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from etl import construir_libro as cl
from etl.catalogo.sql import cargar_catalogo
from etl.construir_libro import construir_libro, nombre_hoja

ORIGEN = Path(__file__).parent.parent / "Data Dils.xlsx"
VPO = "mivau_vpo_calificaciones_definitivas"
pytestmark = pytest.mark.skipif(not ORIGEN.exists(), reason="Falta Data Dils.xlsx")


@pytest.fixture(scope="module")
def libro_real(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("libro") / "v2.xlsx"
    construir_libro(ORIGEN, ruta)
    return load_workbook(ruta)


def _catalogo_sintetico(nombres):
    tablas = pd.DataFrame([{"dataset_id": f"D{i}", "esquema": "MIVAU", "tabla": n, "hoja": "",
                            "estadistica": "x", "origen": "o", "fuente": "f", "frecuencia": "Mensual",
                            "formato_origen": "XLS", "prioridad": "1", "estado": "con_datos"}
                           for i, n in enumerate(nombres)])
    campos = pd.DataFrame([{"tabla": n, "campo": c, "tipo_mysql": t, "nulo": "NO", "clave": "",
                            "descripcion": "d", "ejemplo": ""}
                           for n in nombres for c, t in (("cod_territorio", "VARCHAR(8)"), ("valor", "INT"))])
    return tablas, campos


def _csv(dir_, tabla, filas):
    pd.DataFrame({"cod_territorio": ["ES"] * filas, "valor": range(filas)}).to_csv(
        Path(dir_) / f"{tabla}.csv", sep=";", index=False, encoding="utf-8")


def test_nombre_hoja_recorta_y_desempata():
    usados = set()
    a = nombre_hoja("x" * 40, usados)
    usados.add(a)
    b = nombre_hoja("x" * 45, usados)
    assert len(a) == 31 and len(b) == 31 and a != b and b.endswith("~2")


def test_hipervinculo_apunta_a_hoja(libro_real):
    ws = libro_real["Tablas"]
    fila = next(r for r in ws.iter_rows(min_row=2) if r[1].value == VPO)
    hoja = libro_real.sheetnames[5]
    assert fila[1].hyperlink.location == f"'{hoja}'!A1"


def test_hojas_en_orden(libro_real):
    assert libro_real.sheetnames[:5] == ["Tablas", "Campos", "Maestro Territorios", "Glosario", "General"]
    tablas, _ = cargar_catalogo()
    con_datos = tablas[tablas["estado"] == "con_datos"]
    assert len(libro_real.sheetnames) == 5 + con_datos["tabla"].nunique()  # datasets que comparten tabla: una hoja


def test_nombres_hoja_unicos(tmp_path):
    n1, n2 = "a" * 35 + "_uno", "a" * 35 + "_dos"
    _csv(tmp_path, n1, 3)
    _csv(tmp_path, n2, 3)
    salida = tmp_path / "v2.xlsx"
    construir_libro(ORIGEN, salida, dir_salida=tmp_path, catalogo=_catalogo_sintetico([n1, n2]))
    wb = load_workbook(salida)
    hojas = wb.sheetnames[5:]
    assert len(hojas) == 2 and len(set(hojas)) == 2 and all(len(h) <= 31 for h in hojas)
    enlaces = {r[1].value: r[1].hyperlink.location for r in wb["Tablas"].iter_rows(min_row=2) if r[1].value}
    assert enlaces[n1] == f"'{hojas[0]}'!A1" and enlaces[n2] == f"'{hojas[1]}'!A1"


def test_sin_vinculos_externos(libro_real):
    assert libro_real._external_links == []
    assert len(libro_real.defined_names) == 0


def test_fecha_es_fecha(libro_real):
    ws = libro_real[libro_real.sheetnames[5]]
    cab = [c.value for c in ws[2]]          # fila 1: nota de muestra; fila 2: cabecera
    celda = ws.cell(3, cab.index("fecha") + 1)
    assert isinstance(celda.value, datetime) and celda.number_format == "yyyy-mm-dd"
    assert ws.cell(3, cab.index("cod_ccaa") + 1).number_format == "@"
    assert ws.cell(3, cab.index("cod_ccaa") + 1).value == "00"
    assert isinstance(ws.cell(3, cab.index("num_viviendas") + 1).value, (int, float))


def test_hojas_de_datos_son_muestra(libro_real):
    # Toda hoja de datos lleva como mucho FILAS_MUESTRA_LIBRO filas y la nota con el total; Filas = total del CSV
    tablas = libro_real["Tablas"]
    cab = [c.value for c in tablas[1]]
    vistas = set()
    for r in tablas.iter_rows(min_row=2):
        if r[1].hyperlink is None:
            continue
        hoja = r[1].hyperlink.location.rsplit("!", 1)[0].strip("'").replace("''", "'")
        ws, total = libro_real[hoja], r[cab.index("Filas")].value
        vistas.add(hoja)
        if total is None:      # CSV no versionado aún sin generar (clon recién hecho): solo la nota
            assert "python -m etl.ejecutar_todo" in ws["A1"].value
            continue
        n = min(total, cl.FILAS_MUESTRA_LIBRO)
        assert ws["A1"].value == (f"Muestra: {n} de {total} filas. "
                                  f"La tabla completa está en etl/salida/{r[1].value}.csv")
        assert ws.max_row == n + 2 and ws.sheet_state == "hidden"
    assert vistas == set(libro_real.sheetnames[5:])


def test_general_sin_kpis_ni_errores(libro_real):
    ws = libro_real["General"]
    cab = [c.value for c in ws[1]]
    k = cab.index("KPIs") + 1
    assert ws.cell(1, k).comment is not None and "vaciada" in ws.cell(1, k).comment.text
    assert all(ws.cell(i, k).value is None for i in range(2, ws.max_row + 1))
    errores = {"#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}
    assert not any(c.value in errores for fila in ws.iter_rows() for c in fila)


def _serie(niveles=(("Nacional", "ES"), ("CCAA", "CA01"), ("Seccion", "SC0400101001")), anios=range(2005, 2025)):
    """Tabla con columnas de territorio y tiempo, desordenada a propósito (secciones primero, años al revés)."""
    filas = [{"cod_territorio": cod, "nivel": niv, "fecha": f"{a}-01-01", "valor": a}
             for niv, cod in reversed(niveles) for a in anios]
    return pd.DataFrame(filas)


def test_muestra_libro_recientes_primero_y_todos_los_niveles():
    # 60 filas, 3 niveles: cuota 10 // 3 = 3 filas por nivel (las más recientes) + 1 de relleno (la siguiente
    # en el orden fecha desc, nivel, cod_territorio); se presentan en ese mismo orden.
    m = cl.muestra_libro(_serie(), 10)
    assert list(zip(m["fecha"], m["cod_territorio"])) == [
        ("2024-01-01", "ES"), ("2024-01-01", "CA01"), ("2024-01-01", "SC0400101001"),
        ("2023-01-01", "ES"), ("2023-01-01", "CA01"), ("2023-01-01", "SC0400101001"),
        ("2022-01-01", "ES"), ("2022-01-01", "CA01"), ("2022-01-01", "SC0400101001"),
        ("2021-01-01", "ES")]
    # estable: el mismo resultado sea cual sea el orden de entrada
    assert m.equals(cl.muestra_libro(_serie().sample(frac=1, random_state=1), 10))


def test_muestra_libro_tabla_pequena_entera_y_sin_columnas_de_orden():
    df = _serie(anios=range(2020, 2022))
    assert len(cl.muestra_libro(df, 10)) == 6
    sin = pd.DataFrame({"cod_territorio": ["ES"] * 5, "valor": range(5)})   # sin fecha ni nivel: primeras filas
    assert cl.muestra_libro(sin, 3)["valor"].tolist() == [0, 1, 2]


def test_tabla_grande_hoja_muestra(tmp_path, monkeypatch):
    # Riesgo 5 (SERPAVI > 1.048.576 filas): la hoja es una muestra con nota, Filas = total del CSV
    monkeypatch.setattr(cl, "FILAS_MUESTRA_LIBRO", 10)
    _serie().to_csv(tmp_path / "grande.csv", sep=";", index=False, encoding="utf-8")
    tablas, campos = _catalogo_sintetico(["grande"])
    salida = tmp_path / "v2.xlsx"
    construir_libro(ORIGEN, salida, dir_salida=tmp_path, catalogo=(tablas, campos))
    wb = load_workbook(salida)
    ws = wb["grande"]
    assert ws["A1"].value == "Muestra: 10 de 60 filas. La tabla completa está en etl/salida/grande.csv"
    assert ws.max_row == 12            # nota + cabecera + 10 filas
    assert ws.sheet_state == "hidden"
    t = wb["Tablas"]
    cab = [c.value for c in t[1]]
    assert t.cell(2, cab.index("Filas") + 1).value == 60


def test_general_cuenta_errores_fuera_de_kpis(tmp_path, capsys):
    from openpyxl import Workbook
    src = Workbook()
    src.active.title = "General"
    src["General"].append(["Dataset ID", "Nota", "KPIs"])
    src["General"].append(["A", "#REF!", "#VALUE!"])
    src["General"].append(["B", "ok", "#VALUE!"])
    src.create_sheet("Maestro Territorios").append(["alias", "nivel", "cod_territorio", "cod_ccaa", "nombre_ccaa",
                                                    "cod_provincia", "nombre_provincia", "cod_municipio",
                                                    "nombre_municipio", "nombre_territorio", "fuente_alias",
                                                    "cod_fuente_alias"])
    _csv(tmp_path, "t", 2)
    ruta = tmp_path / "origen.xlsx"
    src.save(ruta)
    salida = tmp_path / "v2.xlsx"
    construir_libro(ruta, salida, dir_salida=tmp_path, catalogo=_catalogo_sintetico(["t"]))
    ws = load_workbook(salida)["General"]
    assert ws["B2"].value is None and ws["B3"].value == "ok"
    assert ws["C2"].value is None and ws["C3"].value is None
    out = capsys.readouterr().out
    assert "2 celdas con error en la columna KPIs" in out and "1 celdas con error de Excel vaciadas" in out


def test_datasets_con_la_misma_tabla_comparten_hoja(tmp_path):
    tablas, campos = _catalogo_sintetico(["compartida", "otra"])
    tablas.loc[1, "tabla"] = "compartida"          # D0 y D1 -> misma tabla; D1 sustituye a "otra"
    tablas.loc[0, "hoja"] = tablas.loc[1, "hoja"] = "compartida"
    tablas.loc[2:, "dataset_id"] = "x"
    tablas = pd.concat([tablas, _catalogo_sintetico(["otra"])[0].assign(dataset_id="D9")], ignore_index=True)
    campos = pd.concat([campos, _catalogo_sintetico(["otra"])[1]], ignore_index=True).drop_duplicates()
    _csv(tmp_path, "compartida", 4)
    _csv(tmp_path, "otra", 2)
    salida = tmp_path / "v2.xlsx"
    construir_libro(ORIGEN, salida, dir_salida=tmp_path, catalogo=(tablas, campos))
    wb = load_workbook(salida)
    assert wb.sheetnames[5:] == ["compartida", "otra"]
    assert wb["compartida"].max_row == 6            # nota + cabecera + 4 filas, escritas una sola vez
    assert wb["compartida"]["A1"].value == "Muestra: 4 de 4 filas. La tabla completa está en etl/salida/compartida.csv"
    filas = {r[1].value: r[9].value for r in wb["Tablas"].iter_rows(min_row=2) if r[1].value}
    assert filas == {"compartida": 4, "otra": 2}
    enlaces = [r[1].hyperlink.location for r in wb["Tablas"].iter_rows(min_row=2) if r[1].value == "compartida"]
    assert enlaces == ["'compartida'!A1"] * 2


def test_csv_no_versionado_ausente_deja_nota(tmp_path, capsys):
    # mivau_serpavi_alquiler.csv (246 MB) no se versiona: en un clon recién hecho falta y el libro se construye
    # igual, con una nota que dice cómo generarlo; cualquier otro CSV ausente sigue haciendo fallar el proceso.
    salida = tmp_path / "v2.xlsx"
    construir_libro(ORIGEN, salida, dir_salida=tmp_path, catalogo=_catalogo_sintetico(["mivau_serpavi_alquiler"]))
    ws = load_workbook(salida)["mivau_serpavi_alquiler"]
    assert "python -m etl.ejecutar_todo MIVAU-SERPAVI" in ws["A1"].value
    assert [c.value for c in ws[2]] == ["cod_territorio", "valor"] and ws.max_row == 2
    assert "AVISO" in capsys.readouterr().out
    with pytest.raises(FileNotFoundError, match="otra_tabla"):
        construir_libro(ORIGEN, salida, dir_salida=tmp_path, catalogo=_catalogo_sintetico(["otra_tabla"]))


def test_campos_muestra_columna_generada_como(libro_real):
    ws = libro_real["Campos"]
    cabecera = [c.value for c in next(ws.iter_rows(max_row=1))]
    assert "Generada como" in cabecera
    col = cabecera.index("Generada como")
    campo = cabecera.index("Campo")
    valores = {r[campo].value: r[col].value for r in ws.iter_rows(min_row=2) if r[campo].value in ("anio", "id_registro")}
    assert valores["anio"] == "YEAR(fecha)"
    assert not valores["id_registro"]
