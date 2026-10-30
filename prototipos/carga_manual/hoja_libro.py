"""Hojas "(prototipo)" de la carga manual de Idealista para Data Dils_v2.xlsx (las recoge prototipos/libro.py).

Una hoja por tipo (alquiler, venta) con la tabla completa de prototipos/carga_manual/salida/ y una hoja con el
CREATE TABLE de las dos. Antes hay que generar los CSV: python -m prototipos.carga_manual.idealista
"""
import pandas as pd

from etl.catalogo.sql import create_table_sql
from prototipos.carga_manual.idealista import AQUI, SALIDA, TIPOS


def hojas() -> list[tuple[str, pd.DataFrame]]:
    resultado = []
    ddl = []
    for tipo, t in TIPOS.items():
        csv = SALIDA / f"{t['tabla']}.csv"
        if csv.exists():
            resultado.append((f"Idealista {tipo} (prototipo)", pd.read_csv(csv, sep=";", dtype=str,
                                                                          keep_default_na=False)))
        campos = pd.read_csv(AQUI / f"campos_idealista_{tipo}.csv", dtype=str, keep_default_na=False)
        ddl.append({"Tabla My SQL": t["tabla"], "Origen": "Idealista (carga manual)",
                    "CREATE TABLE": create_table_sql("IDEALISTA", t["tabla"], campos)})
    resultado.append(("Idealista SQL (prototipo)", pd.DataFrame(ddl)))
    return resultado
