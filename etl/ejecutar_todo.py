"""Ejecuta las fuentes: `python -m etl.ejecutar_todo [DATASET_ID ...]` (sin argumentos, todas)."""
import sys
from datetime import date
from pathlib import Path

from etl.construir_libro import construir_libro
from etl.fuentes import REGISTRO
from etl.lib.validar import cuadre_jerarquico


def main(ids: list[str]) -> None:
    ids = ids or list(REGISTRO)
    desconocidos = [i for i in ids if i not in REGISTRO]
    if desconocidos:
        raise SystemExit(f"Fuentes desconocidas: {desconocidos}; disponibles: {list(REGISTRO)}")
    hoy = date.today()
    for i in ids:
        fuente = REGISTRO[i]
        tabla = fuente.ejecutar(hoy)
        cuadre = cuadre_jerarquico(tabla, fuente.MEDIDAS[0], fuente.DIMENSIONES)
        print(f"{i}: {fuente.TABLA}: {len(tabla)} filas, {len(cuadre)} avisos de cuadre")
    raiz = Path(__file__).resolve().parent.parent
    construir_libro(raiz / "Data Dils.xlsx", raiz / "Data Dils_v2.xlsx")


if __name__ == "__main__":
    main(sys.argv[1:])
