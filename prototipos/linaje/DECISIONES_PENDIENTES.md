# Mapeo y control de cargas: decisiones pendientes (PROTOTIPO, Tarea 18)

Estado: prototipo. No cambia `etl.ejecutar_todo`, `sql/create_tables.sql` ni el catálogo. Todo vive en
`prototipos/linaje/` y en la hoja `Mapeo (prototipo)` (la añade `python -m prototipos.libro`).
Se regenera con `python -m prototipos.linaje.generar` (y `--ejemplo` para `control_cargas_ejemplo.csv`).

## Preguntas

1. **¿El mapeo se mantiene a mano o se genera?** Hoy es mixto: las columnas (de `campos.csv`), los datasets
   (de `etl/fuentes/`), el archivo (URL de `tablas.csv`) y las reglas comunes (territorio, periodo, columnas generadas,
   `provisional`) se deducen solos; la hoja, las celdas y los rótulos del original están a mano en `ORIGENES`
   (de `docs/fuentes/`). Si el original cambia de formato, el test no lo detecta. Opciones: (a) seguir mixto,
   (b) que cada módulo de `etl/fuentes/` declare su mapeo (una sola fuente de verdad junto al código),
   (c) solo a mano en una hoja del libro.
2. **¿Dónde vive `META`?** En el mismo servidor MySQL (un esquema más, simple de consultar junto a los datos) o aparte
   (sobrevive a recrear los esquemas de datos y no se mezcla con los permisos de los usuarios que leen).
3. **¿Se guardan los archivos originales (por hash) para auditoría?** El prototipo guarda solo el SHA-256 del
   archivo. Guardar los originales (en una carpeta o almacén de objetos, nombrados por hash) permite reproducir una
   carga pasada, pero `etl/descargas/` no se versiona y el SERPAVI pesa 67,8 MB.
4. **¿Se guarda el historial de revisiones?** Hoy la carga hace UPSERT por `id_registro`: la última cifra pisa a la
   anterior y se pierde cómo se revisó un dato. `control_cargas` registra qué se cargó y cuándo, pero no los valores
   antiguos. Decidir si se quiere una tabla de histórico (enlaza con la decisión de UPSERT) o basta el log.

## Decisiones tomadas en el prototipo (revisables)

- **Una fila de mapeo por tabla y columna destino** (242 filas, las 12 tablas con datos). Cuando varios datasets
  alimentan la misma tabla (ETI, valor medio, valor tasado), `dataset_id` y `archivo_origen` los listan separados por
  `;` en la misma fila, no una fila por dataset. `mivau_indice_costes_construccion` (solo_diseno) no entra.
- **`anio`, `trimestre` y `mes`** se mapean como "columna generada por MySQL" (`campos.csv`, columna `generado`),
  porque el CSV las lleva pero la carga las omite.
- **`control_cargas`**: `filas_leidas` es opcional (cada fuente tendría que informarlo; el prototipo solo lo calcula
  con un contador que se le pasa) y `avisos_cuadre` es NULL cuando el cuadre no aplica (medias). El archivo y el hash se
  resuelven DESPUÉS de ejecutar la fuente, anotando lo que devuelve `mivau.descargar` (la primera ejecución del día ya
  no registra el archivo de ayer, y los boletines MIVAU-ETI, guardados como `MIVAU-340101x0_*`, sí quedan). En
  fuentes con varios archivos (ETI, valor medio, valor tasado) `archivo` lista todos separados por `; ` (recortado a
  255 caracteres: los 9 de la ETI no caben enteros) y `hash_sha256_archivo` es el SHA-256 de las líneas
  `nombre:sha256` ordenadas. Limitación: ese hash identifica el conjunto, no cada archivo; para consultar por
  archivo haría falta una fila por archivo o una tabla hija.
- **Envoltorio, no cambio de producción**: `ejecutar_con_control` replica la lógica de `ejecutar_todo` (una fuente que
  falla no detiene a las demás) sin modificarlo. Si se adopta, lo natural es que `ejecutar_todo` lo llame.
- **Ejemplo real sin red**: `control_cargas_ejemplo.csv` sale de ejecutar la envoltura sobre la fixture
  `tests/fixtures/32100500.xls` (`transformar`, sin escribir `etl/salida/`); `version_codigo` es el commit en ese momento.
  No hay `etl/descargas/` en este clon, por eso se usó la fixture.
- **API del INE**: ver `API_INE.md`; sirve para maestros, no para las tablas del MIVAU (XLS sin API).
