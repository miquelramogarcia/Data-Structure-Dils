"""Genera etl/lib/municipios_ine.csv a partir de la relación oficial de municipios del INE.

Uso: python -m etl.lib.municipios_ine_generar [etl/descargas/diccionario26.xlsx]

Fuente: INE, "Relación de municipios y sus códigos por comunidades autónomas y provincias"
(https://www.ine.es/daco/daco42/codmun/codmun.htm, archivo diccionarioAA.xlsx, situación a 1 de enero
de 2026). Columnas del original: CODAUTO, CPRO, CMUN, DC (dígito de control), NOMBRE.
Los nombres de CCAA y de provincia salen del Maestro Territorios (hoja del usuario), no del INE, para que
todo el libro use una sola forma de cada nombre.
"""
import sys
from pathlib import Path

import pandas as pd

from etl.lib.territorios import COLUMNAS_MAESTRO, leer_hoja_usuario, normalizar

RAIZ = Path(__file__).resolve().parents[2]
CSV = Path(__file__).with_name("municipios_ine.csv")
ORIGINAL = RAIZ / "etl" / "descargas" / "diccionario26.xlsx"
LIBRO = RAIZ / "Data Dils.xlsx"


def generar(original: Path = ORIGINAL, libro: Path = LIBRO, destino: Path = CSV) -> pd.DataFrame:
    """Lee el original del INE y escribe el CSV con las 12 columnas del maestro; devuelve el DataFrame."""
    ine = pd.read_excel(original, header=1, dtype=str)
    ine.columns = [c.strip() for c in ine.columns]
    ine = ine.dropna(subset=["CPRO", "CMUN"])
    maestro = leer_hoja_usuario(libro, "Maestro Territorios", header=0, dtype=str)
    maestro.columns = COLUMNAS_MAESTRO + list(maestro.columns[len(COLUMNAS_MAESTRO):])
    prov = maestro[maestro["nivel"] == "Provincia"].drop_duplicates("cod_provincia").set_index("cod_provincia")
    ccaa = maestro[maestro["nivel"] == "CCAA"].drop_duplicates("cod_ccaa").set_index("cod_ccaa")
    filas = []
    for r in ine.itertuples(index=False):
        cpro, cmun, cca, nombre = r.CPRO.strip(), r.CMUN.strip(), r.CODAUTO.strip(), r.NOMBRE.strip()
        if cpro not in prov.index or cca not in ccaa.index:
            raise ValueError(f"Municipio {nombre!r}: provincia {cpro} o CCAA {cca} no está en el maestro")
        if prov.loc[cpro, "cod_ccaa"] != cca:
            raise ValueError(f"Municipio {nombre!r}: la provincia {cpro} no pertenece a la CCAA {cca} del maestro")
        filas.append({"alias": normalizar(nombre), "nivel": "Municipio", "cod_territorio": f"MU{cpro}{cmun}",
                      "cod_ccaa": cca, "nombre_ccaa": ccaa.loc[cca, "nombre_territorio"],
                      "cod_provincia": cpro, "nombre_provincia": prov.loc[cpro, "nombre_territorio"],
                      "cod_municipio": f"{cpro}{cmun}", "nombre_municipio": nombre, "nombre_territorio": nombre,
                      "fuente_alias": "INE", "cod_fuente_alias": f"{Path(original).name} (1-1-2026)"})
    df = pd.DataFrame(filas, columns=COLUMNAS_MAESTRO)
    if df["cod_territorio"].duplicated().any():
        raise ValueError("Códigos de municipio duplicados en el original del INE")
    df.to_csv(destino, index=False, encoding="utf-8")
    return df


if __name__ == "__main__":
    out = generar(Path(sys.argv[1]) if len(sys.argv) > 1 else ORIGINAL)
    print(f"{len(out)} municipios escritos en {CSV}")
