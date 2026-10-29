"""Helpers comunes a todas las fuentes: rutas, URL del catálogo, validación, CSV y matriz mensual → tabla."""
from datetime import date
from pathlib import Path

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.lib import mivau
from etl.lib.modelo import construir_tabla
from etl.lib.periodos import periodo_mensual, periodo_trimestral
from etl.lib.territorios import expandir_uniprovinciales, normalizar, resolver
from etl.lib.validar import validar_tabla

RAIZ = Path(__file__).resolve().parents[2]
LIBRO = RAIZ / "Data Dils.xlsx"
SALIDA = RAIZ / "etl" / "salida"
DESCARGAS = RAIZ / "etl" / "descargas"


def url_dataset(dataset_id: str) -> str:
    """URL de descarga del dataset según la columna `fuente` de tablas.csv."""
    tablas, _ = cargar_catalogo()
    return tablas.loc[tablas["dataset_id"] == dataset_id, "fuente"].iloc[0].strip()


def validar_o_fallar(df: pd.DataFrame, tabla: str, maestro: pd.DataFrame) -> None:
    """Valida `df` contra los campos de `tabla` en el catálogo; ValueError con los mensajes si falla."""
    _, campos = cargar_catalogo()
    errores = validar_tabla(df, campos[campos["tabla"] == tabla], maestro)
    if errores:
        raise ValueError(f"{tabla}: validación fallida:\n" + "\n".join(errores))


def escribir_csv(df: pd.DataFrame, tabla: str, destino: Path = SALIDA) -> Path:
    """Escribe `<destino>/<tabla>.csv` en UTF-8 con ';' (fechas ISO, enteros Int64 sin '.0')."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{tabla}.csv"
    df.to_csv(ruta, sep=";", index=False, encoding="utf-8")
    return ruta


def _clave_texto(txt: str) -> str:
    return normalizar(txt)


def tabla_final(df: pd.DataFrame, dataset_id: str, tabla: str, dimensiones: list[str], medida: str,
                maestro: pd.DataFrame, fecha_descarga: date, entero: bool = True,
                descriptivas: list[str] | None = None,
                medidas_enteras: list[str] | None = None,
                medidas_decimales: list[str] | None = None) -> pd.DataFrame:
    """Filas con territorio + dimensiones + periodo + medida + provisional → tabla validada.

    `medidas_enteras`: medidas adicionales (recuentos) que van tras `medida`, como Int64.
    `medidas_decimales`: medidas adicionales no enteras (superficies, importes) que van tras las enteras, como float.

    expandir_uniprovinciales → construir_tabla → validar. `df` lleva ya las columnas del territorio, las
    dimensiones, las del periodo, `medida` (float o Int64) y `provisional`.
    """
    df = df.copy()
    if entero:
        df[medida] = df[medida].round().astype("Int64")
    df = expandir_uniprovinciales(df, maestro, claves=list(dimensiones) + ["periodo"])
    if entero:
        df[medida] = df[medida].astype("Int64")
    extras = list(medidas_enteras or [])
    for m in extras:
        df[m] = df[m].round().astype("Int64")
    decimales = list(medidas_decimales or [])
    for m in decimales:
        df[m] = pd.to_numeric(df[m], errors="coerce").astype("float64")
    resultado = construir_tabla(df, list(dimensiones), [medida, *extras, *decimales], fecha_descarga, descriptivas)
    try:
        validar_o_fallar(resultado, tabla, maestro)
    except ValueError as e:
        raise ValueError(f"{dataset_id}: {e}") from None
    return resultado


def matriz_a_filas(path: Path, dataset_id: str, dimensiones: dict[str, str], medida: str,
                   maestro: pd.DataFrame, frecuencia: str = "M",
                   omitir: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Matriz de territorios del MIVAU (mensual o trimestral) → filas listas para `tabla_final`.

    leer_matriz → resolver → periodo. `dimensiones` asigna un valor fijo a cada dimensión propia ({} si la
    fuente no tiene desglose). `frecuencia` "M" o "T": falla si alguna columna no lo es. `omitir`:
    etiquetas de territorio que son agregados sin código INE (se comparan sin tildes ni mayúsculas);
    cualquier otra etiqueta que no resuelva hace fallar el proceso. Una cabecera con marca de provisional
    ("2º (**)") pone `provisional` = 1 en esas filas. Sirve también para juntar varios archivos en una
    sola tabla antes de expandir y validar.
    """
    construir_periodo = {"M": periodo_mensual, "T": periodo_trimestral}[frecuencia]
    ignorar = {_clave_texto(o) for o in omitir}
    largo = mivau.leer_matriz(path)
    largo = largo[~largo["territorio_txt"].map(_clave_texto).isin(ignorar)]
    territorios = {t: resolver(maestro, t) for t in largo["territorio_txt"].unique()}
    filas = []
    for r in largo.itertuples(index=False):
        tipo, n = mivau.subperiodo(r.subperiodo_txt)
        if tipo != frecuencia:
            raise ValueError(f"Subperiodo no {'mensual' if frecuencia == 'M' else 'trimestral'} "
                             f"en {dataset_id}: {r.subperiodo_txt!r}")
        filas.append({**territorios[r.territorio_txt], **dimensiones,
                      **construir_periodo(int(r.anio), n), medida: mivau.a_numero(r.valor_txt),
                      "provisional": int(mivau.marca_provisional(r.subperiodo_txt))})
    return pd.DataFrame(filas)


def matriz_a_tabla(path: Path, dataset_id: str, tabla: str, dimensiones: dict[str, str], medida: str,
                   maestro: pd.DataFrame, fecha_descarga: date, entero: bool = True,
                   frecuencia: str = "M", omitir: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Matriz de territorios del MIVAU (mensual o trimestral) → tabla validada (`matriz_a_filas` + `tabla_final`)."""
    filas = matriz_a_filas(path, dataset_id, dimensiones, medida, maestro, frecuencia, omitir)
    return tabla_final(filas, dataset_id, tabla, list(dimensiones), medida, maestro, fecha_descarga, entero)


def serie_vertical_a_tabla(path: Path, dataset_id: str, tabla: str, dimension: str,
                           columnas: dict[int, tuple[str, str]], maestro: pd.DataFrame, fecha_descarga: date,
                           decimales: dict[str, int] | None = None,
                           identidades: list[tuple[str, list[str]]] | None = None,
                           productos: list[str] | None = None, tolerancia_m2: float = 0.01) -> pd.DataFrame:
    """Serie mensual con periodos en filas y columnas sin rótulo (09010600, 09011600) → tabla validada.

    `columnas`: índice de columna de valores (0 = primera) -> (valor de `dimension`, nombre de la medida). El
    significado de las columnas lo da una imagen incrustada en el .xls, no texto: por eso el mapa es explícito
    y cualquier columna con datos que no esté en él hace fallar el proceso (la fuente habría cambiado de forma).
    La primera medida (por orden de aparición en `columnas`) es el recuento entero; las demás son decimales,
    redondeadas a `decimales[medida]` cifras (por defecto 4, como el DECIMAL del catálogo). Cada fila de la
    tabla es una (territorio, valor de la dimensión, mes) con todas las medidas que le correspondan.

    Control en tiempo de ejecución contra columnas permutadas (`comprobar_identidades`): `identidades` lista
    (total, [partes]) de valores de la dimensión cuyo recuento debe cumplir total = suma de partes en cada
    mes; `productos` lista valores de la dimensión cuya segunda medida (media por unidad) x recuento debe ser un
    número entero (dentro de `tolerancia_m2`). Si falla, ValueError con la identidad y el primer periodo.
    """
    decimales = decimales or {}
    largo = mivau.leer_serie_vertical(path)
    medidas = list(dict.fromkeys(m for _, m in columnas.values()))
    sobrantes = largo[~largo["columna"].isin(columnas) & largo["valor_txt"].astype(str).str.strip().ne("")]
    if len(sobrantes):
        cols = sorted(sobrantes["columna"].unique().tolist())
        raise ValueError(f"{dataset_id}: columna {cols[0]} con datos sin significado conocido (mapeadas: "
                         f"{sorted(columnas)}); la estructura del archivo ha cambiado")
    territorios = {t: resolver(maestro, t) for t in largo["territorio_txt"].unique()}
    filas: dict[tuple, dict] = {}
    for r in largo[largo["columna"].isin(columnas)].itertuples(index=False):
        valor_dim, medida = columnas[r.columna]
        clave = (r.territorio_txt, valor_dim, int(r.anio), int(r.mes))
        fila = filas.setdefault(clave, {**territorios[r.territorio_txt], dimension: valor_dim,
                                        **periodo_mensual(int(r.anio), int(r.mes)), "provisional": 0})
        valor = mivau.a_numero(r.valor_txt)
        fila[medida] = valor
    df = pd.DataFrame(list(filas.values()))
    for m in medidas:
        if m not in df.columns:
            df[m] = None
    comprobar_identidades(df, dataset_id, dimension, medidas, identidades or [], productos or [], tolerancia_m2)
    for m in medidas[1:]:
        df[m] = df[m].map(lambda v: None if pd.isna(v) else round(v, decimales.get(m, 4)))
    return tabla_final(df, dataset_id, tabla, [dimension], medidas[0], maestro, fecha_descarga,
                       medidas_decimales=medidas[1:])


def comprobar_identidades(df: pd.DataFrame, dataset_id: str, dimension: str, medidas: list[str],
                          identidades: list[tuple[str, list[str]]], productos: list[str],
                          tolerancia_m2: float = 0.01) -> None:
    """Detecta columnas permutadas por cambio de estructura del archivo: ValueError con la identidad rota y el
    primer periodo. Solo detecta permutaciones que rompen una suma; no ve intercambios entre partes de la misma
    suma (p. ej. personas físicas <-> sociedades)."""
    cuenta = medidas[0]
    ancho = df.pivot_table(index=["cod_territorio", "periodo"], columns=dimension, values=cuenta, aggfunc="first")
    for total, partes in identidades:
        dif = (ancho[total] - ancho[partes].sum(axis=1, min_count=1)).abs()
        malos = dif[dif > 0]
        if len(malos):
            terr, per = malos.index[0]
            raise ValueError(f"{dataset_id}: identidad rota {total} = {' + '.join(partes)} en {terr} {per} "
                             f"(diferencia {malos.iloc[0]:g}); las columnas del archivo han cambiado de orden")
    if productos:
        medida = medidas[1]
        for valor_dim in productos:
            sub = df[df[dimension] == valor_dim].dropna(subset=[cuenta, medida])
            m2 = sub[cuenta].astype(float) * sub[medida].astype(float)
            dif = (m2 - m2.round()).abs()
            malos = sub[dif > tolerancia_m2]
            if len(malos):
                raise ValueError(f"{dataset_id}: {medida} x {cuenta} no es un número entero de m2 para {valor_dim} en "
                                 f"{malos.iloc[0]['periodo']} (tolerancia {tolerancia_m2}); las columnas del "
                                 f"archivo han cambiado de orden")
