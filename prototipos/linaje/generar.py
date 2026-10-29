"""PROTOTIPO (Tarea 18): mapeo origen -> destino y control de cargas (linaje).

  - `mapeo.csv`: una fila por tabla destino y columna destino de las tablas con datos. Se deduce de
    `campos.csv` (columnas), `etl/fuentes/` (datasets, dimensiones, medidas) y `tablas.csv` (URL y archivo); lo que
    no se puede deducir (hoja, celdas, rótulos del original) está a mano en `ORIGENES`, tomado de `docs/fuentes/`.
  - `control_cargas.sql`: DDL de `META.control_cargas`.
  - `ejecutar_con_control`: envoltorio que ejecuta fuentes igual que `etl.ejecutar_todo` (sin modificarlo) y anota
    una fila por fuente en un CSV con las columnas del DDL.

Uso: python -m prototipos.linaje.generar            (regenera mapeo.csv y control_cargas.sql)
     python -m prototipos.linaje.generar --ejemplo  (regenera control_cargas_ejemplo.csv con la fixture de 32100500)
"""
import hashlib
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.fuentes import REGISTRO
from etl.lib.fuente_comun import DESCARGAS, url_dataset
from etl.lib.validar import cuadre_jerarquico

RAIZ = Path(__file__).resolve().parents[2]
DIR = Path(__file__).resolve().parent
COLUMNAS_MAPEO = ["tabla", "columna_destino", "dataset_id", "archivo_origen", "hoja_origen", "ubicacion_origen",
                  "transformacion", "regla"]
COLUMNAS_TERRITORIO = ["nivel", "cod_territorio", "cod_ccaa", "nombre_ccaa", "cod_provincia", "nombre_provincia",
                       "cod_municipio", "nombre_municipio"]
EJEMPLO_CSV = DIR / "control_cargas_ejemplo.csv"

# --- Parte manual: dónde está cada cosa en el original (fuente: docs/fuentes/<DATASET_ID>.md) ---------------------
# territorio: ubicación del texto de territorio; periodo: ubicación de año/subperiodo y función de periodo;
# provisional: regla; dims / medidas: columna destino -> (ubicación, transformación, regla).
_MATRIZ_M = "periodo_mensual(año, mes)"
_MATRIZ_T = "periodo_trimestral(año, trimestre)"
_PROV_CABECERA = ("cabecera de periodo con marca '(**)'", "marca_provisional(cabecera) → 0/1",
                  "1 solo si la cabecera lleva la marca de dato provisional; si no, 0")
_PROV_CERO = ("(no existe en el original)", "constante 0", "La fuente no marca datos provisionales")
_TERR_CCAA_PROV = "columna B (TOTAL NACIONAL, comunidades y provincias; 'Ceuta y Melilla' se omite)"
_TERR_TASADO = "columna B, desde la fila 15 (TOTAL NACIONAL, comunidades y provincias; 'Ceuta y Melilla' se omite)"

ORIGENES: dict[str, dict] = {
    "mivau_vpo_calificaciones_definitivas": {
        "hoja": "Tabla 1.6",
        "territorio": "columna B, filas 13 a 75 (63 territorios)",
        "periodo": ("fila 11 ('AAAA por meses', cada 12 columnas) y fila 12 (mes), columnas C a HP", _MATRIZ_M),
        "provisional": _PROV_CABECERA,
        "dims": {"regimen": ("(no existe en el original)", "constante 'TOTAL'",
                             "Solo existe el total de planes estatales y autonómicos")},
        "medidas": {"num_viviendas": ("celdas C13:HP75", "a_numero(celda) → entero",
                                      "'-', '..', vacío o nota → NULL; 0 se conserva")}},
    "mivau_vivienda_libre_iniciadas": {
        "hoja": "Tabla 3.1",
        "territorio": "columna B, filas 13 a 75 (63 territorios)",
        "periodo": ("fila 11 ('AAAA por meses', cada 12 columnas) y fila 12 (mes), columnas C a HP", _MATRIZ_M),
        "provisional": _PROV_CABECERA, "dims": {},
        "medidas": {"num_viviendas": ("celdas C13:HP75", "a_numero(celda) → entero",
                                      "'-', '..', vacío o nota → NULL; 0 se conserva")}},
    "mivau_vivienda_libre_terminadas": {
        "hoja": "Tabla 3.2",
        "territorio": "columna B, filas 13 a 75 (63 territorios)",
        "periodo": ("fila 11 ('AAAA por meses', cada 12 columnas) y fila 12 (mes), columnas C a HP", _MATRIZ_M),
        "provisional": _PROV_CABECERA, "dims": {},
        "medidas": {"num_viviendas": ("celdas C13:HP75", "a_numero(celda) → entero",
                                      "'-', '..', vacío o nota → NULL; 0 se conserva")}},
    "mivau_eti_transacciones": {
        "hoja": "una hoja por quinquenio ('2004, 2005, 2006, 2007, 2008' ...)",
        "territorio": "columna B, desde la fila 15 (TOTAL NACIONAL, comunidades y provincias; 'Ceuta y Melilla' se omite)",
        "periodo": ("fila 12 ('Año AAAA', cada 4 columnas) y fila 14 ('1º'..'4º')", _MATRIZ_T),
        "provisional": _PROV_CABECERA,
        "dims": {"regimen": ("(no existe en el original)", "BOLETINES[código sedal] → regimen",
                             "Cada boletín 34010110..34010190 es una celda de la rejilla régimen x antigüedad"),
                 "antiguedad": ("(no existe en el original)", "BOLETINES[código sedal] → antiguedad",
                                "TOTAL / NUEVA / SEGUNDA_MANO según el boletín")},
        "medidas": {"num_transacciones": ("celdas desde C15 (20 trimestres por hoja)", "a_numero(celda) → entero",
                                          "'-', '..', vacío o nota → NULL; 0 se conserva")}},
    "mivau_eti_compradores_extranjeros": {
        "hoja": "una hoja por trimestre ('1t 2007' ... '2t 2026')",
        "territorio": "columna B, filas 16 a 34 (España, 17 comunidades y 'Ceuta y Melilla'): lugar de la vivienda comprada",
        "periodo": ("título de la hoja, celda B12 ('Primer trimestre de 2007') y nombre de la hoja", _MATRIZ_T),
        "provisional": _PROV_CABECERA,
        "dims": {"cod_ccaa_comprador": ("cabecera de columnas, filas 14 y 15, desde C ('en España' y 18 comunidades)",
                                        "resolver(maestro, rótulo de columna) → cod_ccaa",
                                        "Comunidad de residencia del comprador; 'en España' = 00"),
                 "nombre_ccaa_comprador": ("cabecera de columnas, filas 14 y 15, desde C",
                                           "resolver(maestro, rótulo de columna) → nombre_ccaa",
                                           "Descriptiva: no entra en id_registro")},
        "medidas": {"num_transacciones": ("matriz C16:U34 (19 x 19 celdas por hoja)", "a_numero(celda) → entero",
                                          "'-', '..', vacío o nota → NULL; 0 se conserva")}},
    "mivau_valor_medio_vivienda_libre": {
        "hoja": "34020150/160/170: una hoja por grupo de años; 34020180: una hoja por trimestre ('1t 2019' ...)",
        "territorio": "columna B, desde la fila 16 (TOTAL NACIONAL, comunidades y provincias; 'Ceuta y Melilla' se omite)",
        "periodo": ("34020150/160/170: fila 13 ('Año AAAA') y fila 15 ('1º'..'4º'); 34020180: celda B12 del título",
                    _MATRIZ_T),
        "provisional": _PROV_CABECERA,
        "dims": {"tipo_comprador": ("(no existe en el original)", "constante por dataset",
                                    "TOTAL (34020150/160/170) o EXTRANJERO_RESIDENTE (34020180)"),
                 "antiguedad": ("34020180: fila 15, columnas D, E y F; resto: no existe",
                                "POR_ANIOS[dataset] / ANTIGUEDAD_COLUMNA[rótulo] → antiguedad",
                                "TOTAL / NUEVA / SEGUNDA_MANO")},
        "medidas": {"valor_medio_eur": ("celdas desde C16", "a_numero(celda) → decimal",
                                        "'-', '..', vacío o nota → NULL; 0 se conserva. Medias: no se suman")}},
    "mivau_valor_tasado_vivienda_libre": {
        "hoja": "una hoja por grupo de cuatro años ('1995, 1996, 1997, 1998' ...)",
        "territorio": _TERR_TASADO,
        "periodo": ("fila 12 ('Año AAAA', cada 4 columnas) y fila 14 ('1º'..'4º')", _MATRIZ_T),
        "provisional": _PROV_CABECERA,
        "dims": {"antiguedad": ("(no existe en el original)", "ANTIGUEDAD[dataset] → antiguedad",
                                "35101000 = TOTAL, 35101500 = HASTA_5_ANOS, 35102000 = MAS_5_ANOS")},
        "medidas": {"valor_tasado_eur_m2": ("celdas desde C15", "a_numero(celda) → decimal",
                                            "'n.r', '-', vacío o nota → NULL; 0 se conserva")}},
    "mivau_valor_tasado_municipios_25000": {
        "hoja": "una hoja por trimestre ('T1A2005' ... 'T2A2026')",
        "territorio": "columna C (municipio); la provincia, en B solo en la primera fila de cada grupo",
        "periodo": ("título de la hoja ('Primer trimestre de 2005') y nombre de la hoja", _MATRIZ_T),
        "provisional": _PROV_CERO,
        "dims": {"antiguedad": ("2005T1-2009T4: solo 'Total' (D); 2010T1 en adelante: D hasta 5 años, E más de 5, F total",
                                "rótulo de columna → antiguedad", "TOTAL / HASTA_5_ANOS / MAS_5_ANOS")},
        "medidas": {
            "valor_tasado_eur_m2": ("columnas 'Valor medio' (D/E/F según el formato)", "a_numero(celda) → decimal",
                                    "'n.r' → NULL"),
            "num_tasaciones": ("columnas 'Tasaciones' (F, o H/I/J desde 2010T1)", "a_numero(celda) → entero",
                               "'n.r' → NULL")}},
    "mivau_precio_suelo_urbano": {
        "hoja": "Tabla 4",
        "territorio": "columna B, desde la fila 14 (TOTAL NACIONAL, comunidades y provincias; 'Ceuta y Melilla' se omite)",
        "periodo": ("fila 11 ('Año AAAA', cada 4 columnas) y fila 13 ('1º'..'4º'), columnas C a CN", _MATRIZ_T),
        "provisional": _PROV_CABECERA, "dims": {},
        "medidas": {"precio_eur_m2": ("celdas C14:CN (90 trimestres)", "a_numero(celda) → decimal",
                                      "Las columnas 'Variación Trimestral/Interanual' no son periodos y se ignoran")}},
    "mivau_certificados_fin_obra": {
        "hoja": "APAREJA_15",
        "territorio": "celda B6 ('TOTAL NACIONAL', único territorio)",
        "periodo": ("columna B (año, solo en la primera fila de cada bloque) y columna D (mes), filas 14 a 429",
                    _MATRIZ_M + "; las filas 8 a 12 (totales anuales) se ignoran"),
        "provisional": _PROV_CERO,
        "dims": {"promotor": ("columnas E a M (rótulos en una imagen PNG incrustada)",
                              "columna → promotor (E=TOTAL, F=PRIVADO_TOTAL ... M=ADMINISTRACIONES_PUBLICAS)",
                              "Las columnas K y L (vacías) no se cargan")},
        "medidas": {"num_viviendas": ("columnas E a M", "a_numero(celda) → entero", "Una fila por columna de promotor"),
                    "valor_liquidacion_miles_eur": ("columna N", "a_numero(celda) → decimal",
                                                    "Solo en la fila promotor = TOTAL")}},
    "mivau_visados_direccion_obra": {
        "hoja": "APAREJA_6",
        "territorio": "celda A6 ('TOTAL NACIONAL', único territorio)",
        "periodo": ("columna A (año, solo en la primera fila de cada bloque) y columna C (mes), filas 14 a 429",
                    _MATRIZ_M + "; las filas 8 a 12 (totales anuales) se ignoran"),
        "provisional": _PROV_CERO,
        "dims": {"tipo_obra": ("columnas D a J (rótulos en una imagen GIF incrustada)",
                               "columna → tipo_obra (D=TOTAL, E=OBRA_NUEVA ... J=REFORMA_RESTAURACION)", "")},
        "medidas": {"num_viviendas": ("columnas D a J", "a_numero(celda) → entero", "Una fila por tipo de obra"),
                    "superficie_media_m2": ("columnas K a N (unifamiliar, bloque, otros edificios, ampliación)",
                                            "a_numero(celda) → decimal",
                                            "Solo en 4 tipos de obra; el resto NULL")}},
    "mivau_serpavi_alquiler": {
        "hoja": "CCAA; Provincias; Municipios; Distritos; Secciones censales",
        "territorio": "columnas de identificación: CPRO, CUMUN, CUDIS, CUSEC según la hoja",
        "periodo": ("sufijo _AA del nombre de columna (_11 a _24 = 2011 a 2024)", "periodo_anual(2000 + AA)"),
        "provisional": _PROV_CERO,
        "dims": {"tipologia": ("sufijo VC / VU (o TVC / TVU) del nombre de columna", "sufijo → COLECTIVA / UNIFAMILIAR",
                               "El archivo no trae total de tipologías")},
        "extra": {
            "cod_distrito": ("columnas CUDIS (hojas Distritos y Secciones: CUSEC[:7])", "territorio_por_codigo(maestro, 'DI'+cod)",
                             "NULL fuera de Distrito y Seccion"),
            "cod_seccion": ("columna CUSEC (hoja Secciones censales)", "territorio_por_codigo(maestro, 'SC'+cod)",
                            "NULL fuera de Seccion")},
        "medidas": {
            "renta_mediana_eur_m2_mes": ("ALQM2_LV_M_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "renta_p25_eur_m2_mes": ("ALQM2_LV_25_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "renta_p75_eur_m2_mes": ("ALQM2_LV_75_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "renta_mediana_eur_mes": ("ALQTBID12_M_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "renta_p25_eur_mes": ("ALQTBID12_25_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "renta_p75_eur_mes": ("ALQTBID12_75_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "superficie_mediana_m2": ("SLVM2_M_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "superficie_p25_m2": ("SLVM2_25_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "superficie_p75_m2": ("SLVM2_75_V{C,U}_AA", "a_numero → decimal(2)", "'' o vacío → NULL"),
            "num_inmuebles_alquiler": ("BI_ALVHEPCO_TV{C,U}_AA", "a_numero → entero", "'' o vacío → NULL")}},
}
# Archivos de origen cuando la URL del catálogo no apunta a un archivo (MIVAU-ETI: página de la ETI).
ARCHIVO_ESPECIAL = {"MIVAU-ETI": "34010120.XLS ... 34010190.XLS (8 boletines)"}


def _datasets_de(tabla: str) -> list[str]:
    return [i for i, f in REGISTRO.items() if f.TABLA == tabla]


def _archivo(dataset_id: str, tablas: pd.DataFrame) -> str:
    if dataset_id in ARCHIVO_ESPECIAL:
        return ARCHIVO_ESPECIAL[dataset_id]
    url = tablas.loc[tablas["dataset_id"] == dataset_id, "fuente"].iloc[0].strip().splitlines()[0]
    return unquote(url.rsplit("/", 1)[-1])


def generar_mapeo() -> pd.DataFrame:
    tablas, campos = cargar_catalogo()
    con_datos = tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")]
    filas = []
    for tabla in con_datos.drop_duplicates("tabla").sort_values("tabla")["tabla"]:
        if tabla not in ORIGENES:
            raise KeyError(f"Falta el origen de {tabla} en ORIGENES (tabla con datos sin mapear)")
        o = ORIGENES[tabla]
        datasets = _datasets_de(tabla)
        ids = ";".join(datasets)
        archivos = "; ".join(_archivo(i, tablas) for i in datasets)
        generadas = dict(zip(campos["campo"][campos["tabla"] == tabla], campos["generado"][campos["tabla"] == tabla]))
        per_ubic, per_fn = o["periodo"]
        propias = {**o["dims"], **o.get("extra", {}), **o["medidas"]}
        for campo in campos.loc[campos["tabla"] == tabla, "campo"]:
            if campo == "id_registro":
                ub, tr, rg = ("(calculada)", "construir_tabla: cod_territorio + dimensiones + periodo unidos con '_'",
                              "Clave natural PK; igual en cada descarga (UPSERT)")
            elif campo in COLUMNAS_TERRITORIO:
                resolver_fn = ("territorio_por_codigo(maestro, código INE)" if tabla.endswith("serpavi_alquiler")
                               else "resolver(maestro, texto)")
                ub = o["territorio"]
                tr = f"{resolver_fn} → {campo}"
                rg = ("Del Maestro Territorios, nunca del texto del archivo; si no existe, el proceso falla"
                      if campo == "cod_territorio" else "Código/nombre oficial del maestro")
                if campo == "cod_provincia":
                    rg += "; en comunidades uniprovinciales se copia la fila de la comunidad (expandir_uniprovinciales)"
            elif campo in ("periodo", "frecuencia", "fecha"):
                ub, tr, rg = per_ubic, f"{per_fn} → {campo}", {
                    "periodo": "AAAAMmm / AAAATn / AAAA", "frecuencia": "M, T o A",
                    "fecha": "Primer día del periodo (fecha real AAAA-MM-DD)"}[campo]
            elif generadas.get(campo):
                ub, tr, rg = ("(no se carga)", f"Columna generada por MySQL: {generadas[campo]}",
                              "El CSV la lleva pero LOAD DATA la omite (@omitir_*)")
            elif campo == "provisional":
                ub, tr, rg = o["provisional"]
            elif campo == "fecha_descarga":
                ub, tr, rg = "(no existe en el original)", "date.today() al ejecutar", "Día de la descarga"
            elif campo in propias:
                ub, tr, rg = propias[campo]
            else:
                raise KeyError(f"{tabla}.{campo}: columna sin regla de mapeo")
            filas.append([tabla, campo, ids, archivos, o["hoja"], ub, tr, rg])
    return pd.DataFrame(filas, columns=COLUMNAS_MAPEO)


# --- Control de cargas -------------------------------------------------------------------------------------------
_DDL = """CREATE SCHEMA IF NOT EXISTS `META` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

CREATE TABLE IF NOT EXISTS `META`.`control_cargas` (
  `id_carga` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Una fila por fuente y ejecución',
  `dataset_id` VARCHAR(40) NOT NULL COMMENT 'Código del catálogo (tablas.csv)',
  `tabla` VARCHAR(64) NOT NULL COMMENT 'Tabla destino',
  `url` VARCHAR(500) NULL COMMENT 'URL de descarga',
  `archivo` VARCHAR(255) NULL COMMENT 'Nombre del archivo descargado',
  `hash_sha256_archivo` CHAR(64) NULL COMMENT 'SHA-256 del archivo: identifica la versión exacta del original',
  `fecha_descarga` DATE NOT NULL COMMENT 'Día de la descarga',
  `inicio` DATETIME NOT NULL,
  `fin` DATETIME NOT NULL,
  `filas_leidas` INT UNSIGNED NULL COMMENT 'Celdas o filas leídas del original (NULL si la fuente no lo informa)',
  `filas_escritas` INT UNSIGNED NULL COMMENT 'Filas de la tabla resultante (NULL si falló)',
  `avisos_cuadre` INT UNSIGNED NULL COMMENT 'Avisos de cuadre jerárquico (NULL si no aplica o falló)',
  `estado` ENUM('OK','ERROR') NOT NULL,
  `mensaje_error` TEXT NULL,
  `version_codigo` VARCHAR(40) NULL COMMENT 'Commit de git del código que hizo la carga',
  `script` VARCHAR(200) NULL COMMENT 'Comando o módulo ejecutado',
  PRIMARY KEY (`id_carga`),
  INDEX `ix_control_dataset` (`dataset_id`, `inicio`),
  INDEX `ix_control_hash` (`hash_sha256_archivo`)
) ENGINE=InnoDB COMMENT='PROTOTIPO: auditoría de cargas (linaje)';
"""


def generar_ddl() -> str:
    return _DDL


def columnas_ddl() -> list[str]:
    """Columnas de META.control_cargas, en el orden del DDL."""
    cuerpo = _DDL.split("control_cargas` (", 1)[1]
    return re.findall(r"^  `(\w+)` ", cuerpo, flags=re.M)


def url_de(dataset_id: str) -> str:
    return url_dataset(dataset_id).splitlines()[0]


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _version_codigo() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _ultima_descarga(dataset_id: str) -> Path | None:
    candidatos = sorted(DESCARGAS.glob(f"{dataset_id}_*"))
    return candidatos[-1] if candidatos else None


def ejecutar_con_control(ids: list[str], destino: Path = EJEMPLO_CSV, *, archivos: dict[str, Path] | None = None,
                         ejecutar_fuente=None, contar_leidas=None, version: str | None = None,
                         script: str = "python -m etl.ejecutar_todo", hoy: date | None = None) -> list[dict]:
    """Ejecuta las fuentes como `etl.ejecutar_todo` (una fuente que falla no detiene a las demás) y anexa una fila
    por fuente a `destino` con las columnas de META.control_cargas. No modifica `etl.ejecutar_todo`.

    `archivos`: dataset_id -> archivo descargado (por defecto, el más reciente de etl/descargas/<id>_*; si no hay,
    archivo y hash quedan vacíos: las fuentes con varios archivos solo registran uno). `ejecutar_fuente(fuente, hoy)`
    sustituye a `fuente.ejecutar(hoy)` (para pruebas o fixtures); `contar_leidas(ruta)` informa `filas_leidas`.
    """
    hoy = hoy or date.today()
    version = version or _version_codigo()
    ejecutar_fuente = ejecutar_fuente or (lambda f, h: f.ejecutar(h))
    destino = Path(destino)
    previas = pd.read_csv(destino, sep=";", dtype=str) if destino.exists() else pd.DataFrame(columns=columnas_ddl())
    siguiente = int(previas["id_carga"].astype(int).max()) + 1 if len(previas) else 1
    filas = []
    for i in ids:
        fuente = REGISTRO[i]
        ruta = (archivos or {}).get(i) or _ultima_descarga(i)
        inicio = datetime.now().replace(microsecond=0)
        fila = {"id_carga": siguiente, "dataset_id": i, "tabla": fuente.TABLA, "url": url_de(i),
                "archivo": ruta.name if ruta else None,
                "hash_sha256_archivo": _sha256(ruta) if ruta and ruta.exists() else None,
                "fecha_descarga": hoy.isoformat(), "inicio": inicio, "filas_leidas": None, "filas_escritas": None,
                "avisos_cuadre": None, "version_codigo": version, "script": script, "mensaje_error": None}
        try:
            tabla = ejecutar_fuente(fuente, hoy)
            if getattr(fuente, "CUADRE", True):
                fila["avisos_cuadre"] = len(cuadre_jerarquico(tabla, fuente.MEDIDAS[0], fuente.DIMENSIONES))
            fila["filas_escritas"] = len(tabla)
            if contar_leidas and ruta:
                fila["filas_leidas"] = contar_leidas(ruta)
            fila["estado"] = "OK"
        except Exception as e:  # igual que ejecutar_todo: se registra y se sigue
            fila["estado"], fila["mensaje_error"] = "ERROR", str(e)
        fila["fin"] = datetime.now().replace(microsecond=0)
        filas.append(fila)
        siguiente += 1
    nuevas = pd.DataFrame(filas)[columnas_ddl()]
    pd.concat([previas, nuevas], ignore_index=True).to_csv(destino, sep=";", index=False, encoding="utf-8",
                                                           lineterminator="\n")
    return filas


def generar_ejemplo() -> list[dict]:
    """Fila de ejemplo REAL de la envoltura, sin red ni escribir etl/salida/: transforma la fixture de 32100500."""
    from etl.lib import mivau
    fixture = RAIZ / "tests" / "fixtures" / "32100500.xls"
    fuente_id = "MIVAU-32100500"
    EJEMPLO_CSV.unlink(missing_ok=True)
    return ejecutar_con_control(
        [fuente_id], EJEMPLO_CSV, archivos={fuente_id: fixture},
        ejecutar_fuente=lambda f, h: f.transformar(fixture, h), contar_leidas=lambda p: len(mivau.leer_matriz(p)),
        script="prototipos.linaje.generar --ejemplo (transformar sobre tests/fixtures/32100500.xls)")


def main(argv: list[str]) -> None:
    generar_mapeo().to_csv(DIR / "mapeo.csv", sep=";", index=False, encoding="utf-8", lineterminator="\n")
    (DIR / "control_cargas.sql").write_text(generar_ddl(), encoding="utf-8", newline="\n")
    print(f"mapeo.csv: {len(generar_mapeo())} filas")
    if "--ejemplo" in argv:
        filas = generar_ejemplo()
        print(f"control_cargas_ejemplo.csv: {len(filas)} fila(s), estado {filas[0]['estado']}")


if __name__ == "__main__":
    main(sys.argv[1:])
