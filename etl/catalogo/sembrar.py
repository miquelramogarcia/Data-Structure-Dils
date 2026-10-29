"""Siembra el catálogo (tablas.csv y campos.csv) desde el Excel del usuario. Se ejecuta una sola vez."""
from pathlib import Path

import pandas as pd

from etl.lib.territorios import leer_hoja_usuario, normalizar

DIR = Path(__file__).parent
XLSX = DIR.parent.parent / "Data Dils.xlsx"
COLS_TABLAS = ["dataset_id", "esquema", "tabla", "hoja", "estadistica", "origen", "fuente",
               "frecuencia", "formato_origen", "prioridad", "estado"]
COLS_CAMPOS = ["tabla", "campo", "tipo_mysql", "nulo", "clave", "descripcion", "ejemplo"]
VPO = "mivau_vpo_calificaciones_definitivas"
HOJA_VPO = "mivau_vpo_calificaciones_defini"


def _vacio(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def _txt(v) -> str:
    return "" if _vacio(v) else str(v).strip()


def _emparejar(tablas: pd.DataFrame, general: pd.DataFrame) -> list[int]:
    """Índice de General para cada fila de Tablas: por prefijo normalizado, y por orden como respaldo."""
    gnorm = [normalizar(x) for x in general["Estadística"]]
    usados: set[int] = set()
    res: list[int] = []
    for i, est in enumerate(tablas["Estadística"]):
        n = normalizar(est)
        cand = [j for j, g in enumerate(gnorm) if j not in usados and n and g.startswith(n)]
        if len(cand) > 1 and i in cand:
            cand = [i]
        if len(cand) == 1:
            j = cand[0]
        elif not cand and i < len(general) and i not in usados:
            j = i
        else:
            raise ValueError(f"No se pudo emparejar la fila {i} de Tablas con General: {est!r}")
        usados.add(j)
        res.append(j)
    if len(usados) != len(general):
        raise ValueError("Hay datasets de General sin tabla asignada")
    return res


def sembrar(xlsx: Path = XLSX) -> None:
    tablas = leer_hoja_usuario(xlsx, "Tablas", dtype=str)
    campos = leer_hoja_usuario(xlsx, "Campos", dtype=str)
    general = leer_hoja_usuario(xlsx, "General", dtype=str)
    orden = _emparejar(tablas, general)
    filas = []
    for i, j in enumerate(orden):
        t, g = tablas.iloc[i], general.iloc[j]
        did = _txt(g["Dataset ID"])
        tabla = _txt(t["Tabla My SQL"])
        if tabla == VPO:
            estado = "con_datos"
        elif did.startswith(("NOT-", "IDEALISTA-")):
            estado = "solo_diseno"
        else:
            estado = "pendiente"
        filas.append({
            "dataset_id": did,
            "esquema": _txt(t["Esquema"]),
            "tabla": tabla,
            "hoja": HOJA_VPO if tabla == VPO else "",
            "estadistica": " ; ".join(_txt(g["Estadística"]).split("\n")),
            "origen": _txt(t["Origen"]) or _txt(g["Organismo"]),
            "fuente": _txt(t["Fuente"]) or _txt(g["URL datos / API"]) or _txt(g["URL ficha"]),
            "frecuencia": _txt(t["Frecuencia"]) or _txt(g["Frecuencia"]),
            "formato_origen": _txt(t["Formato Origen"]) or _txt(g["Formato"]),
            "prioridad": _txt(t["Prioridad"]) or _txt(g["PRIORIDAD"]),
            "estado": estado,
        })
    pd.DataFrame(filas, columns=COLS_TABLAS).to_csv(DIR / "tablas.csv", index=False, encoding="utf-8")

    c = campos.iloc[:, :7].copy()
    c.columns = COLS_CAMPOS
    c = c.fillna("")
    extra = {"tabla": VPO, "campo": "fecha_descarga", "tipo_mysql": "DATE", "nulo": "NO", "clave": "",
             "descripcion": "Día en que se descargó el dato de la fuente", "ejemplo": ""}
    pos = c.index[(c["tabla"] == VPO)].max()
    c = pd.concat([c.iloc[:pos + 1], pd.DataFrame([extra]), c.iloc[pos + 1:]], ignore_index=True)
    c.to_csv(DIR / "campos.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    sembrar()
