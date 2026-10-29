"""Extrae las imágenes incrustadas de un .xls (BIFF8): los boletines MIVAU 09010600 y 09011600 llevan los
rótulos de las columnas como imagen, no como texto.

Uso: python -m etl.herramientas.extraer_imagenes_xls <archivo.xls> <carpeta_destino>

Escribe `<carpeta>/<nombre>_<n>.<ext>` (png, jpg o gif; el tipo se detecta por la firma de los bytes, porque el
contenedor Office dice "PNG" aunque la imagen sea un GIF) y lista el tamaño de cada una. En estos boletines
la imagen grande (~1 MB) es un logotipo; las pequeñas (~10 KB) son la cabecera de la tabla.
"""
import os
import struct
import sys
from pathlib import Path

from xlrd import compdoc

_BLIP = {0xF01A: "emf", 0xF01B: "wmf", 0xF01C: "pict", 0xF01D: "jpg", 0xF01E: "png", 0xF01F: "dib"}
_FIRMAS = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg", b"GIF8": "gif"}


def _dibujos(datos: bytes) -> bytes:
    """Concatena los registros MsoDrawingGroup (0xEB) y sus CONTINUE (0x3C) del flujo Workbook."""
    pos, trozos, actual = 0, [], None
    while pos + 4 <= len(datos):
        rid, largo = struct.unpack_from("<HH", datos, pos)
        carga = datos[pos + 4:pos + 4 + largo]
        if rid == 0xEB:
            actual = bytearray(carga)
            trozos.append(actual)
        elif rid == 0x3C and actual is not None:
            actual += carga
        else:
            actual = None
        pos += 4 + largo
    return b"".join(bytes(t) for t in trozos)


def extraer(ruta: Path, destino: Path) -> list[Path]:
    """Guarda las imágenes del .xls en `destino` y devuelve las rutas escritas."""
    ruta, destino = Path(ruta), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    bruto = ruta.read_bytes()
    with open(os.devnull, "w") as log:
        doc = compdoc.CompDoc(bruto, logfile=log)
    mem, base, tam = doc.locate_named_stream("Workbook")
    blob = _dibujos(bytes(mem[base:base + tam]))
    salidas = []
    pos = 0
    while pos + 8 <= len(blob):
        ver_inst, tipo, largo = struct.unpack_from("<HHI", blob, pos)
        if tipo in _BLIP and ver_inst & 0xF == 0 and 0 < largo <= len(blob) - pos - 8:
            carga = blob[pos + 8:pos + 8 + largo]
            for firma, ext in _FIRMAS.items():
                i = carga.find(firma, 0, 64)
                if i >= 0:
                    out = destino / f"{ruta.stem}_{len(salidas)}.{ext}"
                    out.write_bytes(carga[i:])
                    salidas.append(out)
                    break
            pos += 8 + largo
        else:
            pos += 1
    return salidas


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    for p in extraer(Path(sys.argv[1]), Path(sys.argv[2])):
        print(f"{p}  {p.stat().st_size} bytes")
