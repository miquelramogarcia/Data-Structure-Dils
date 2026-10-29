"""PROTOTIPO (Tarea 17): maestros como tablas MySQL en el esquema MAESTROS y sus claves foráneas.

Genera, sin tocar nada de producción (sql/create_tables.sql, etl/catalogo/*.csv):
  - prototipos/maestros/datos/*.csv     (dim_territorio, dim_territorio_alias, dim_periodo, dim_categoria)
  - prototipos/maestros/maestros.sql    (CREATE SCHEMA/TABLE + LOAD DATA de esos CSV)
  - prototipos/maestros/maestros_fk.sql (ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY, opcional)

Uso: python -m prototipos.maestros.generar
"""
from pathlib import Path

import pandas as pd

from etl.catalogo.sql import cargar_catalogo
from etl.lib.territorios import cargar_maestro, normalizar

RAIZ = Path(__file__).resolve().parents[2]
DIR = Path(__file__).resolve().parent
DIR_DATOS = DIR / "datos"
LIBRO = RAIZ / "Data Dils.xlsx"
SALIDA = RAIZ / "etl" / "salida"
ESQUEMA = "MAESTROS"
# Los datos empiezan en 1991 (fin de obra); el brief decía 2004-2030 y se amplía para que ningún periodo quede fuera.
ANIO_DESDE, ANIO_HASTA = 1990, 2030
COLUMNAS_TERRITORIO = ["cod_territorio", "nivel", "cod_ccaa", "nombre_ccaa", "cod_provincia", "nombre_provincia",
                       "cod_municipio", "nombre_municipio", "nombre_territorio"]
# El CSV de SERPAVI no se versiona: sus categorías se conocen por el diseño de la tabla (docs/fuentes/MIVAU-SERPAVI.md).
CATEGORIAS_FIJAS = {"tipologia": ["COLECTIVA", "UNIFAMILIAR"]}


def fuentes_con_datos() -> list:
    """Un módulo de fuente por tabla con datos (las que comparten tabla tienen las mismas dimensiones)."""
    from etl.fuentes import REGISTRO
    vistas: dict[str, object] = {}
    for f in REGISTRO.values():
        vistas.setdefault(f.TABLA, f)
    return list(vistas.values())


def construir_dim_territorio(maestro: pd.DataFrame) -> pd.DataFrame:
    """Una fila por cod_territorio (los alias, que repiten el territorio, van a dim_territorio_alias)."""
    d = maestro.drop_duplicates("cod_territorio")[COLUMNAS_TERRITORIO]
    return d.sort_values("cod_territorio", kind="stable").reset_index(drop=True)


def construir_dim_territorio_alias(maestro: pd.DataFrame) -> pd.DataFrame:
    """Textos alternativos de cada territorio. Se omiten los alias que, normalizados (sin tildes ni mayúsculas),
    coinciden con el nombre oficial: el resolver los encuentra igualmente por nombre_territorio."""
    m = maestro[maestro["alias"].notna()].copy()
    distinto = m["alias"].map(normalizar) != m["nombre_territorio"].fillna("").map(normalizar)
    m = m[distinto].drop_duplicates(["alias", "cod_territorio", "fuente_alias"])
    m = m[["alias", "nivel", "cod_territorio", "fuente_alias", "cod_fuente_alias"]].reset_index(drop=True)
    m.insert(0, "id_alias", range(1, len(m) + 1))
    return m


def construir_dim_periodo(desde: int = ANIO_DESDE, hasta: int = ANIO_HASTA) -> pd.DataFrame:
    """Años, trimestres y meses entre `desde` y `hasta`, padres antes que hijos (para cargar con FK propia)."""
    filas = []
    for a in range(desde, hasta + 1):
        filas.append((f"{a}", "A", f"{a}-01-01", f"{a}-12-31", None))
    for a in range(desde, hasta + 1):
        for t in range(1, 5):
            ini = pd.Timestamp(a, 3 * t - 2, 1)
            filas.append((f"{a}T{t}", "T", ini.date().isoformat(), (ini + pd.offsets.MonthEnd(3)).date().isoformat(),
                          f"{a}"))
    for a in range(desde, hasta + 1):
        for m in range(1, 13):
            ini = pd.Timestamp(a, m, 1)
            filas.append((f"{a}M{m:02d}", "M", ini.date().isoformat(),
                          (ini + pd.offsets.MonthEnd(0)).date().isoformat(), f"{a}T{(m - 1) // 3 + 1}"))
    return pd.DataFrame(filas, columns=["periodo", "frecuencia", "fecha", "fecha_fin", "periodo_padre"])


def construir_dim_categoria(salida: Path = SALIDA) -> pd.DataFrame:
    """Valores de las dimensiones propias de las tablas con datos: (dimension, codigo, descripcion).

    La descripción es la columna `nombre_<dimension>` cuando la tabla la trae (p. ej. nombre_ccaa_comprador);
    si no, se repite el código (pendiente de decidir: ver DECISIONES_PENDIENTES.md).
    """
    filas: dict[tuple[str, str], str] = {}
    for f in fuentes_con_datos():
        csv = Path(salida) / f"{f.TABLA}.csv"
        df = pd.read_csv(csv, sep=";", dtype=str, keep_default_na=False) if csv.exists() else None
        for d in f.DIMENSIONES:
            if df is not None:
                nombre = f"nombre_{d.removeprefix('cod_')}"
                nombre = nombre if nombre in df.columns else d
                for cod, desc in df[[d, nombre]].drop_duplicates().itertuples(index=False):
                    filas.setdefault((d, cod), desc)
            for cod in CATEGORIAS_FIJAS.get(d, []):
                filas.setdefault((d, cod), cod)
    res = pd.DataFrame([(d, c, desc) for (d, c), desc in filas.items()], columns=["dimension", "codigo", "descripcion"])
    return res.sort_values(["dimension", "codigo"], kind="stable").reset_index(drop=True)


def construir_dimensiones(libro: Path = LIBRO, salida: Path = SALIDA) -> dict[str, pd.DataFrame]:
    maestro = cargar_maestro(libro)
    return {"dim_territorio": construir_dim_territorio(maestro),
            "dim_territorio_alias": construir_dim_territorio_alias(maestro),
            "dim_periodo": construir_dim_periodo(),
            "dim_categoria": construir_dim_categoria(salida)}


_DDL = f"""CREATE SCHEMA IF NOT EXISTS `{ESQUEMA}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

CREATE TABLE IF NOT EXISTS `{ESQUEMA}`.`dim_territorio` (
  `cod_territorio` VARCHAR(12) NOT NULL COMMENT 'ES / CAxx / PRxx / MUxxxxx / DI+7 dígitos / SC+10 dígitos',
  `nivel` ENUM('Nacional','CCAA','Provincia','Municipio','Distrito','Seccion') NOT NULL,
  `cod_ccaa` CHAR(2) NOT NULL COMMENT '00 = Nacional',
  `nombre_ccaa` VARCHAR(100) NOT NULL,
  `cod_provincia` CHAR(2) NULL,
  `nombre_provincia` VARCHAR(100) NULL,
  `cod_municipio` CHAR(5) NULL,
  `nombre_municipio` VARCHAR(100) NULL,
  `nombre_territorio` VARCHAR(150) NOT NULL COMMENT 'Nombre oficial del territorio en su nivel',
  PRIMARY KEY (`cod_territorio`),
  INDEX `ix_dim_territorio_nivel` (`nivel`),
  INDEX `ix_dim_territorio_municipio` (`cod_municipio`)
) ENGINE=InnoDB COMMENT='Maestro de territorios: una fila por cod_territorio (Maestro Territorios + INE + SERPAVI)';

CREATE TABLE IF NOT EXISTS `{ESQUEMA}`.`dim_territorio_alias` (
  `id_alias` INT UNSIGNED NOT NULL,
  `alias` VARCHAR(200) NOT NULL COMMENT 'Texto tal como aparece en una fuente',
  `nivel` ENUM('Nacional','CCAA','Provincia','Municipio','Distrito','Seccion') NOT NULL,
  `cod_territorio` VARCHAR(12) NOT NULL,
  `fuente_alias` VARCHAR(40) NULL COMMENT 'Dataset o fuente donde se vio el texto',
  `cod_fuente_alias` VARCHAR(40) NULL COMMENT 'Código del territorio en esa fuente',
  PRIMARY KEY (`id_alias`),
  INDEX `ix_alias_texto` (`alias`),
  CONSTRAINT `fk_alias_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `{ESQUEMA}`.`dim_territorio` (`cod_territorio`)
) ENGINE=InnoDB COMMENT='Alias de territorios; solo los que difieren del nombre oficial al normalizar';

CREATE TABLE IF NOT EXISTS `{ESQUEMA}`.`dim_periodo` (
  `periodo` VARCHAR(7) NOT NULL COMMENT 'AAAA / AAAATn / AAAAMmm',
  `frecuencia` CHAR(1) NOT NULL COMMENT 'A / T / M',
  `fecha` DATE NOT NULL COMMENT 'Primer día del periodo',
  `fecha_fin` DATE NOT NULL COMMENT 'Último día del periodo',
  `periodo_padre` VARCHAR(7) NULL COMMENT 'El mes apunta a su trimestre y el trimestre a su año',
  PRIMARY KEY (`periodo`),
  INDEX `ix_dim_periodo_fecha` (`fecha`),
  CONSTRAINT `fk_periodo_padre` FOREIGN KEY (`periodo_padre`) REFERENCES `{ESQUEMA}`.`dim_periodo` (`periodo`)
) ENGINE=InnoDB COMMENT='Calendario M/T/A; anio/trimestre/mes ya son columnas generadas de las tablas de datos';

CREATE TABLE IF NOT EXISTS `{ESQUEMA}`.`dim_categoria` (
  `dimension` VARCHAR(40) NOT NULL COMMENT 'Nombre de la columna propia (regimen, antiguedad...)',
  `codigo` VARCHAR(20) NOT NULL,
  `descripcion` VARCHAR(200) NOT NULL,
  PRIMARY KEY (`dimension`, `codigo`)
) ENGINE=InnoDB COMMENT='Valores de las dimensiones propias (genérica; alternativa: una tabla por dimensión)';
"""

_CARGA = {
    "dim_territorio": ["cod_territorio", "nivel", "cod_ccaa", "nombre_ccaa", "@cod_provincia", "@nombre_provincia",
                       "@cod_municipio", "@nombre_municipio", "nombre_territorio"],
    "dim_territorio_alias": ["id_alias", "alias", "nivel", "cod_territorio", "@fuente_alias", "@cod_fuente_alias"],
    "dim_periodo": ["periodo", "frecuencia", "fecha", "fecha_fin", "@periodo_padre"],
    "dim_categoria": ["dimension", "codigo", "descripcion"],
}


def generar_ddl() -> str:
    return "-- PROTOTIPO (Tarea 17). Generado por prototipos/maestros/generar.py. No editar a mano.\n\n" + _DDL


def generar_carga() -> str:
    partes = ["-- Carga de los CSV de prototipos/maestros/datos/ (desde la raíz del proyecto, con local_infile activo).",
              "-- Orden obligatorio: dim_territorio antes que dim_territorio_alias; dim_periodo ya trae los padres primero."]
    for tabla, cols in _CARGA.items():
        nulos = [c[1:] for c in cols if c.startswith("@")]
        lista = ", ".join(c if c.startswith("@") else f"`{c}`" for c in cols)
        sql = (f"\nLOAD DATA LOCAL INFILE 'prototipos/maestros/datos/{tabla}.csv' INTO TABLE `{ESQUEMA}`.`{tabla}`\n"
               "CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '\"' ESCAPED BY '' "
               "LINES TERMINATED BY '\\n'\nIGNORE 1 LINES\n"
               f"({lista})")
        if nulos:
            sql += "\nSET " + ",\n    ".join(f"`{c}` = NULLIF(@{c}, '')" for c in nulos)
        partes.append(sql + ";")
    return "\n".join(partes) + "\n"


def generar_maestros_sql() -> str:
    return generar_ddl() + "\n" + generar_carga()


def tablas_con_datos() -> list[tuple[str, str, list[str]]]:
    """(esquema, tabla, dimensiones) de las tablas con datos, según el catálogo."""
    tablas, _ = cargar_catalogo()
    con = tablas[(tablas["estado"] == "con_datos") & (tablas["tabla"] != "")].drop_duplicates("tabla")
    dims = {f.TABLA: f.DIMENSIONES for f in fuentes_con_datos()}
    return [(r.esquema, r.tabla, dims.get(r.tabla, [])) for r in con.sort_values("tabla").itertuples()]


def generar_fk_sql() -> str:
    """FK de cada tabla con datos hacia dim_territorio y dim_periodo. dim_categoria solo se documenta."""
    partes = ["-- PROTOTIPO (Tarea 17). Generado por prototipos/maestros/generar.py. No editar a mano.",
              "-- Ejecutar DESPUÉS de create_tables.sql y maestros.sql; mejor tras la carga masiva (las FK la ralentizan).",
              "-- dim_categoria NO se enlaza: la FK compuesta (dimension, codigo) no encaja con el diseño actual",
              "-- (cada tabla guarda solo el codigo en su columna propia). Relaciones documentadas, no creadas:"]
    tablas = tablas_con_datos()
    for esquema, tabla, dims in tablas:
        for d in dims:
            partes.append(f"--   {esquema}.{tabla}.{d} -> MAESTROS.dim_categoria (dimension = '{d}', codigo)")
    for esquema, tabla, _ in tablas:
        for col, dim, ref in (("cod_territorio", "territorio", "dim_territorio"), ("periodo", "periodo", "dim_periodo")):
            partes.append(f"\nALTER TABLE `{esquema}`.`{tabla}`\n"
                          f"  ADD CONSTRAINT `fk_{tabla}_{dim}` FOREIGN KEY (`{col}`) "
                          f"REFERENCES `{ESQUEMA}`.`{ref}` (`{col}`);")
    return "\n".join(partes) + "\n"


def escribir_csv(df: pd.DataFrame, nombre: str) -> None:
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    df.to_csv(DIR_DATOS / f"{nombre}.csv", sep=";", index=False, encoding="utf-8", lineterminator="\n")


def main() -> None:
    for nombre, df in construir_dimensiones().items():
        escribir_csv(df, nombre)
        print(f"{nombre}: {len(df)} filas")
    (DIR / "maestros.sql").write_text(generar_maestros_sql(), encoding="utf-8", newline="\n")
    (DIR / "maestros_fk.sql").write_text(generar_fk_sql(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
