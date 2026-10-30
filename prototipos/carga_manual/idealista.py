"""PROTOTIPO de carga manual de los informes de precios de Idealista (no está en producción ni en el catálogo).

Dos informes con la misma forma de tabla, uno por tipo:
- alquiler (IDEALISTA-ALQUILER): renta de oferta en €/m²/mes,
  https://www.idealista.com/sala-de-prensa/informes-precio-vivienda/alquiler/
- venta (IDEALISTA-VENTA): precio de oferta en €/m²,
  https://www.idealista.com/sala-de-prensa/informes-precio-vivienda/

Idealista no ofrece descarga: la tabla de la web se copia y se pega en un archivo de texto en
prototipos/carga_manual/pegados/<tipo>/<AAAA-MM>_<nivel>.txt (nivel: CCAA, Provincia o Municipio); ver OPCIONES.md.
El periodo se lee de la cabecera ("Precio m2 sep 2026"); el nombre del archivo solo aporta el nivel.

Uso: python -m prototipos.carga_manual.idealista alquiler|venta   (sin argumento: los dos)
"""
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from etl.lib.fuente_comun import LIBRO, escribir_csv
from etl.lib.modelo import construir_tabla
from etl.lib.periodos import periodo_mensual
from etl.lib.territorios import cargar_maestro, expandir_uniprovinciales, normalizar, resolver, territorio_por_codigo
from etl.lib.validar import escala_decimal, validar_tabla

AQUI = Path(__file__).parent
SALIDA = AQUI / "salida"
ALIAS = AQUI / "alias_idealista.csv"     # nombres propios de Idealista; no afectan a las demás fuentes
NIVELES = ("CCAA", "Provincia", "Municipio")
CABECERA = ["Localización", "Precio m2", "Variación mensual", "Variación trimestral", "Variación anual",
            "Máximo histórico", "Variación máximo"]
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "mayo": 5, "jun": 6, "jul": 7, "ago": 8,
         "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12}

# Lo único que cambia entre alquiler y venta: tabla, carpeta, diseño y nombre de las dos medidas en €.
TIPOS = {
    "alquiler": {"dataset_id": "IDEALISTA-ALQUILER", "tabla": "idealista_precio_alquiler",
                 "precio": "renta_eur_m2_mes", "maximo": "max_historico_eur_m2_mes"},
    "venta": {"dataset_id": "IDEALISTA-VENTA", "tabla": "idealista_precio_venta",
              "precio": "precio_eur_m2", "maximo": "max_historico_eur_m2"},
}


def medidas(tipo: str) -> list[str]:
    t = TIPOS[tipo]
    return [t["precio"], "var_mensual_pct", "var_trimestral_pct", "var_anual_pct", t["maximo"],
            "max_historico_periodo", "var_maximo_pct"]


def _mes_anio(texto: str) -> tuple[int, int]:
    """'sep 2026' / 'mayo 2026' → (2026, 9). Error si el mes no es una abreviatura conocida."""
    m = re.fullmatch(r"([a-záéíóú]+)\.?\s+(\d{4})", texto.strip().lower())
    if not m or m.group(1) not in MESES:
        raise ValueError(f"Idealista: mes no reconocido en {texto!r}")
    return int(m.group(2)), MESES[m.group(1)]


def _numero(texto: str) -> float | None:
    """'15,1 €/m2' → 15.1; '2.930 €/m2' → 2930.0; '- 0,3 %' → -0.3; '+ 5,6 %' → 5.6; vacío o 'n.d.' → None."""
    t = str(texto).replace("€/m2", "").replace("%", "").replace(" ", "").replace(".", "").replace(",", ".")
    if t in ("", "nd", "n/d", "-"):
        return None
    try:
        return float(t)
    except ValueError:
        raise ValueError(f"Idealista: valor no numérico {texto!r}") from None


def leer_pegado(path: Path, tipo: str) -> tuple[pd.DataFrame, str]:
    """Lee el texto pegado (columnas separadas por tabulador) y devuelve (filas, nivel)."""
    t = TIPOS[tipo]
    nivel = path.stem.split("_")[-1]
    if nivel not in NIVELES:
        raise ValueError(f"{t['dataset_id']}: el archivo {path.name} debe acabar en _CCAA, _Provincia o _Municipio")
    lineas = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    cab = lineas[0].split("\t")
    if len(cab) != len(CABECERA) or not all(c.strip().startswith(e) for c, e in zip(cab, CABECERA)):
        raise ValueError(f"{t['dataset_id']}: {path.name}: cabecera inesperada {cab!r}; "
                         f"se esperaba {CABECERA!r} (¿se pegó otra tabla?)")
    anio, mes = _mes_anio(cab[1].strip()[len("Precio m2"):])
    filas = []
    for i, linea in enumerate(lineas[1:], 2):
        c = [x.strip() for x in linea.split("\t")]
        if len(c) != len(CABECERA):
            raise ValueError(f"{t['dataset_id']}: {path.name}, línea {i}: {len(c)} columnas en vez de {len(CABECERA)}")
        maximo = re.fullmatch(r"(.+€/m2)\s+(.+)", c[5])
        max_periodo = None
        if maximo:
            a, m = _mes_anio(maximo.group(2))
            max_periodo = periodo_mensual(a, m)["periodo"]
        filas.append({"territorio_txt": c[0], t["precio"]: _numero(c[1]), "var_mensual_pct": _numero(c[2]),
                      "var_trimestral_pct": _numero(c[3]), "var_anual_pct": _numero(c[4]),
                      t["maximo"]: _numero(maximo.group(1)) if maximo else _numero(c[5]),
                      "max_historico_periodo": max_periodo, "var_maximo_pct": _numero(c[6]),
                      **periodo_mensual(anio, mes)})
    return pd.DataFrame(filas), nivel


def _territorio(maestro: pd.DataFrame, alias: pd.DataFrame, texto: str, nivel: str) -> dict:
    """Alias propios de Idealista y, si no, el maestro común. 'España' es siempre Nacional."""
    fila = alias[(alias["texto"].map(normalizar) == normalizar(texto)) & (alias["nivel"] == nivel)]
    if not fila.empty:
        return territorio_por_codigo(maestro, fila.iloc[0]["cod_territorio"])
    return resolver(maestro, texto, nivel=None if normalizar(texto) == "espana" else nivel)


def transformar(path: Path, tipo: str, fecha_descarga: date, maestro: pd.DataFrame) -> pd.DataFrame:
    """Un archivo pegado → filas con territorio + periodo + medidas (sin validar)."""
    alias = pd.read_csv(ALIAS, dtype=str, keep_default_na=False)
    df, nivel = leer_pegado(path, tipo)
    terr = pd.DataFrame([_territorio(maestro, alias, t, nivel) for t in df["territorio_txt"]])
    df = pd.concat([terr, df.drop(columns="territorio_txt")], axis=1)
    df = expandir_uniprovinciales(df, maestro, claves=["periodo"])
    return construir_tabla(df, [], medidas(tipo), fecha_descarga)


def construir(tipo: str, maestro: pd.DataFrame | None = None) -> pd.DataFrame:
    """Todos los archivos pegados del tipo → tabla validada. fecha_descarga = día en que se guardó cada archivo."""
    t = TIPOS[tipo]
    maestro = cargar_maestro(LIBRO) if maestro is None else maestro
    archivos = sorted((AQUI / "pegados" / tipo).glob("*.txt"))
    if not archivos:
        raise FileNotFoundError(f"{t['dataset_id']}: no hay archivos pegados en pegados/{tipo}/")
    partes = [transformar(p, tipo, date.fromtimestamp(p.stat().st_mtime), maestro) for p in archivos]
    tabla = pd.concat(partes, ignore_index=True)
    # Si un mismo periodo y territorio se pegó dos veces, gana el archivo guardado más tarde.
    tabla = tabla.sort_values("fecha_descarga", kind="stable").drop_duplicates("id_registro", keep="last")
    tabla = tabla.sort_values(["fecha", "cod_territorio"]).reset_index(drop=True)
    campos = pd.read_csv(AQUI / f"campos_idealista_{tipo}.csv", dtype=str, keep_default_na=False)
    for _, c in campos.iterrows():
        escala = escala_decimal(c["tipo_mysql"])
        if escala is not None:
            tabla[c["campo"]] = pd.to_numeric(tabla[c["campo"]], errors="coerce").round(escala)
    errores = validar_tabla(tabla, campos, maestro)
    if errores:
        raise ValueError(f"{t['tabla']}: validación fallida:\n" + "\n".join(errores))
    return tabla


if __name__ == "__main__":
    maestro = cargar_maestro(LIBRO)
    for tipo in sys.argv[1:] or list(TIPOS):
        tabla = construir(tipo, maestro)
        print(f"{TIPOS[tipo]['tabla']}: {len(tabla)} filas -> {escribir_csv(tabla, TIPOS[tipo]['tabla'], SALIDA)}")
