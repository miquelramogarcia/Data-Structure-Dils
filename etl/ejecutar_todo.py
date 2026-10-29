"""Ejecuta las fuentes: `python -m etl.ejecutar_todo [DATASET_ID ...]` (sin argumentos, todas).

Una fuente que falla no detiene a las demás: se imprime `ERROR <id>: <mensaje>`, se sigue, se construye el
libro con lo que haya salido bien y el proceso termina con código 1 si alguna falló.
"""
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
    correctas: dict[str, tuple[str, int]] = {}
    fallidas: list[str] = []
    for i in ids:
        fuente = REGISTRO[i]
        try:
            tabla = fuente.ejecutar(hoy)
            cuadre = cuadre_jerarquico(tabla, fuente.MEDIDAS[0], fuente.DIMENSIONES)
        except Exception as e:  # una fuente rota no debe parar al resto
            print(f"ERROR {i}: {e}", file=sys.stderr)
            fallidas.append(i)
            continue
        correctas[i] = (fuente.TABLA, len(tabla))
        print(f"{i}: {fuente.TABLA}: {len(tabla)} filas, {len(cuadre)} avisos de cuadre")
    raiz = Path(__file__).resolve().parent.parent
    construir_libro(raiz / "Data Dils.xlsx", raiz / "Data Dils_v2.xlsx")
    print(f"Resumen: {len(correctas)} correctas, {len(fallidas)} fallidas")
    for i, (tabla, n) in correctas.items():
        print(f"  OK {i}: {tabla} ({n} filas)")
    for i in fallidas:
        print(f"  FALLO {i}")
    if fallidas:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
