"""Genera docs/Documentacion_Dils.pdf: resumen corto y legible de toda la documentación.

Fuentes del contenido (el PDF no inventa nada, solo resume):
- docs/README.md: tabla "Resumen de tablas" y sección "Pendiente de decisión del usuario".
- etl/catalogo/tablas.csv: frecuencia y estado de cada tabla.
- etl/catalogo/glosario.csv: glosario.
- prototipos/*/DECISIONES_PENDIENTES.md: preguntas de los prototipos.

Uso: python -m etl.herramientas.generar_pdf
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "docs" / "Documentacion_Dils.pdf"
README = RAIZ / "docs" / "README.md"
FUENTES_WIN = Path("C:/Windows/Fonts")
AZUL = colors.HexColor("#1F3A5F")
GRIS = colors.HexColor("#EEF1F5")


def _registrar_fuentes() -> tuple[str, str]:
    """Arial si está disponible (acentos y símbolos); si no, Helvetica."""
    normal, negrita = FUENTES_WIN / "arial.ttf", FUENTES_WIN / "arialbd.ttf"
    if normal.exists() and negrita.exists():
        pdfmetrics.registerFont(TTFont("Arial", str(normal)))
        pdfmetrics.registerFont(TTFont("Arial-Bold", str(negrita)))
        pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold")
        return "Arial", "Arial-Bold"
    return "Helvetica", "Helvetica-Bold"


def _md(texto: str) -> str:
    """Markdown en línea → marcado de Paragraph (negrita, código, enlaces como texto)."""
    t = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
    return t


def _seccion(md: str, titulo: str) -> list[str]:
    lineas, dentro = [], False
    for linea in md.splitlines():
        if linea.startswith("## "):
            dentro = linea[3:].strip().startswith(titulo)
            continue
        if dentro:
            lineas.append(linea)
    return lineas


def resumen_tablas(md: str) -> pd.DataFrame:
    filas = [l for l in _seccion(md, "Resumen de tablas") if l.startswith("| `")]
    reg = []
    for l in filas:
        c = [x.strip() for x in l.strip("|").split("|")]
        reg.append({"tabla": c[0].strip("`"), "datasets": c[1], "filas": c[2]})
    return pd.DataFrame(reg)


def pendientes(md: str) -> list[str]:
    # El enlace "[Ficha](...)" no sirve en papel: se quita (el texto ya remite a la ficha de la fuente).
    return [re.sub(r"\s*\[Ficha\]\([^)]+\)\.?", "", l[2:]).strip()
            for l in _seccion(md, "Pendiente de decisión") if l.startswith("- ")]


def preguntas_prototipo(ruta: Path) -> list[str]:
    preguntas, dentro = [], False
    for l in ruta.read_text(encoding="utf-8").splitlines():
        if l.startswith("## "):
            dentro = l.startswith("## Preguntas")
            continue
        m = re.match(r"\d+\.\s+\*\*(.+?)\*\*", l)
        if dentro and m:
            preguntas.append(m.group(1))
    return preguntas


def generar(salida: Path = SALIDA) -> Path:
    fuente, fuente_b = _registrar_fuentes()
    base = getSampleStyleSheet()
    e = {
        "titulo": ParagraphStyle("t", parent=base["Title"], fontName=fuente_b, fontSize=24, textColor=AZUL,
                                 alignment=TA_CENTER, spaceAfter=10),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontName=fuente, fontSize=11, alignment=TA_CENTER,
                              textColor=colors.HexColor("#555555")),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=fuente_b, fontSize=15, textColor=AZUL,
                             spaceBefore=6, spaceAfter=8),
        "p": ParagraphStyle("p", parent=base["Normal"], fontName=fuente, fontSize=9.5, leading=13, spaceAfter=5),
        "celda": ParagraphStyle("c", parent=base["Normal"], fontName=fuente, fontSize=8, leading=10),
        "celda_b": ParagraphStyle("cb", parent=base["Normal"], fontName=fuente_b, fontSize=8, leading=10,
                                  textColor=colors.white),
    }

    def tabla(cab: list[str], filas: list[list[str]], anchos: list[float]) -> Table:
        datos = [[Paragraph(_md(c), e["celda_b"]) for c in cab]]
        datos += [[Paragraph(_md(str(v)), e["celda"]) for v in f] for f in filas]
        t = Table(datos, colWidths=[a * cm for a in anchos], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8CED6")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    def lista(items: list[str]) -> ListFlowable:
        return ListFlowable([ListItem(Paragraph(_md(i), e["p"]), leftIndent=12) for i in items],
                            bulletType="bullet", start="•", leftIndent=12)

    md = README.read_text(encoding="utf-8")
    catalogo = pd.read_csv(RAIZ / "etl" / "catalogo" / "tablas.csv", dtype=str, keep_default_na=False)
    frec = catalogo[catalogo["tabla"] != ""].groupby("tabla")["frecuencia"].first().to_dict()
    resumen = resumen_tablas(md)
    glosario = pd.read_csv(RAIZ / "etl" / "catalogo" / "glosario.csv", dtype=str, keep_default_na=False)

    h: list = []
    h += [Spacer(1, 5 * cm), Paragraph("Base de datos de vivienda Dils", e["titulo"]),
          Paragraph("Documentación resumida · fase 1", e["sub"]), Spacer(1, 0.4 * cm),
          Paragraph(f"Generado el {date.today():%d/%m/%Y} desde el repositorio del proyecto", e["sub"]),
          Spacer(1, 3 * cm),
          Paragraph("Contenido: 1. Qué es · 2. Tablas · 3. Cómo se usa · 4. Pendiente de decisión · "
                    "5. Prototipos · 6. Glosario", e["sub"]), PageBreak()]

    h += [Paragraph("1. Qué es", e["h1"]),
          Paragraph("Un proceso en Python (ETL) que descarga estadísticas públicas de vivienda de España, sobre todo "
                    "del Ministerio de Vivienda (MIVAU), las limpia y las deja todas con el <b>mismo formato</b>: "
                    "territorio con códigos INE, periodo, fecha real y una clave única por fila. Con eso genera:", e["p"]),
          lista(["**Los datos completos** de cada tabla en CSV (`etl/salida/`), listos para importar a MySQL.",
                 "**El SQL**: `sql/create_tables.sql` (crea las tablas) y `sql/load_data.sql` (las carga).",
                 "**El Excel** `Data Dils_v2.xlsx`: catálogo de tablas con su `CREATE TABLE`, diccionario de campos, "
                 "maestro de territorios, glosario y una muestra de 1.000 filas de cada tabla (hojas ocultas).",
                 "**La documentación**: `docs/README.md`, una ficha por fuente en `docs/fuentes/` y el registro de "
                 "decisiones `docs/decisiones.md`."]),
          Paragraph("Formato común de todas las tablas: <b>periodo</b> 2026M06 / 2026T2 / 2026 · <b>fecha</b> "
                    "AAAA-MM-DD (primer día del periodo) · <b>territorio</b> ES, CAxx, PRxx, MUxxxxx, DIxxxxxxx, "
                    "SCxxxxxxxxxx · <b>anio, trimestre, mes</b> calculados por MySQL a partir de la fecha.", e["p"])]

    filas_tabla = [[r.tabla, r.datasets, frec.get(r.tabla, ""), r.filas] for r in resumen.itertuples()]
    h += [Spacer(1, 0.3 * cm), Paragraph("2. Tablas con datos", e["h1"]),
          Paragraph(f"{len(resumen)} tablas en el esquema MIVAU. El detalle de cada campo está en la hoja Campos "
                    "del Excel y el origen y las transformaciones en la ficha de cada fuente.", e["p"]),
          tabla(["Tabla", "Fuentes (boletín)", "Frecuencia", "Filas"], filas_tabla, [6.3, 5.6, 2.2, 3.4]),
          Spacer(1, 0.2 * cm),
          Paragraph("Sin datos por ahora: el índice de costes de construcción (columnas sin rótulo en el archivo) y "
                    "las fuentes del Notariado e Idealista (aplazadas).", e["p"]), PageBreak()]

    h += [Paragraph("3. Cómo se usa", e["h1"]),
          tabla(["Para…", "Ejecutar (desde la carpeta del proyecto)"], [
              ["Instalar", "`python -m pip install -r requirements.txt`"],
              ["Descargar y regenerar todo (~10 min)", "`python -m etl.ejecutar_todo`"],
              ["Regenerar una sola fuente", "`python -m etl.ejecutar_todo MIVAU-31205000`"],
              ["Rehacer solo el Excel", '`python -c "from etl.construir_libro import construir_libro; '
                                        'construir_libro()"`'],
              ["Regenerar el SQL", "`python -m etl.catalogo.sql`"],
              ["Crear las tablas en MySQL", "`mysql --local-infile=1 -u USUARIO -p < sql/create_tables.sql`"],
              ["Cargar los datos", "`mysql --local-infile=1 -u USUARIO -p < sql/load_data.sql`"],
              ["Comprobar que todo está bien (~8 min)", "`python -m pytest`"],
          ], [5.0, 12.5]),
          Spacer(1, 0.3 * cm),
          lista(["Volver a cargar **actualiza** las filas existentes (REPLACE); las que la fuente deja de publicar "
                 "no se borran.",
                 "El CSV de SERPAVI (1,3 millones de filas) no está en GitHub por tamaño: se genera con "
                 "`python -m etl.ejecutar_todo MIVAU-SERPAVI`.",
                 "Tu Excel original `Data Dils.xlsx` solo se lee; nunca se modifica.",
                 "No ejecutar `python -m etl.catalogo.sembrar`: sobrescribiría el catálogo (está protegido)."])]

    h += [Spacer(1, 0.3 * cm), Paragraph("4. Pendiente de tu decisión", e["h1"]),
          Paragraph("Cada punto está explicado en la ficha de su fuente y en docs/decisiones.md.", e["p"]),
          lista(pendientes(md)), PageBreak()]

    h += [Paragraph("5. Prototipos (por decidir)", e["h1"]),
          Paragraph("Están en la carpeta prototipos/ y no afectan a lo que ya funciona. Para pasarlos a producción "
                    "hay que responder estas preguntas:", e["p"])]
    for titulo, carpeta in [("Maestros como tablas MySQL y relaciones", "maestros"),
                            ("Mapeo origen → destino y control de cargas", "linaje")]:
        ruta = RAIZ / "prototipos" / carpeta / "DECISIONES_PENDIENTES.md"
        if ruta.exists():
            h += [KeepTogether([Paragraph(f"<b>{titulo}</b>", e["p"]), lista(preguntas_prototipo(ruta))])]
    h += [PageBreak(), Paragraph("6. Glosario", e["h1"]),
          tabla(["Término", "Definición"], glosario[["termino", "definicion"]].values.tolist(), [3.8, 13.7])]

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont(fuente, 7.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(2 * cm, 1.2 * cm, "Base de datos de vivienda Dils · documentación resumida")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(salida), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=2 * cm, title="Base de datos de vivienda Dils", author="Proyecto Dils")
    doc.build(h, onFirstPage=lambda c, d: None, onLaterPages=pie)
    return salida


if __name__ == "__main__":
    print(f"PDF escrito en {generar()}")
