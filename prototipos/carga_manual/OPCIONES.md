# Carga manual de tablas no descargables: opciones (PROTOTIPO)

Estado: prueba de concepto, no está en producción. No toca `etl/catalogo/`, `sql/` ni `etl/fuentes/`.

## Qué se ha probado

Tablas de Idealista de precios de vivienda en alquiler y en venta por comunidades (septiembre 2026), guardadas en
`pegados/alquiler/2026-09_CCAA.txt` (copiada a mano) y `pegados/venta/2026-09_CCAA.txt` (leída de la web con el
navegador una sola vez, para la prueba: eso es extracción automática, ver opción B). Se ejecuta con:

```
python -m prototipos.carga_manual.idealista            # alquiler y venta
python -m prototipos.carga_manual.libro                # Excel de muestra: idealista_prototipo.xlsx
```

Resultado: `salida/idealista_precio_alquiler.csv` (27 filas) y `salida/idealista_precio_venta.csv` (40 filas, con el histórico de 12 meses de España): España,
las comunidades pegadas y las provincias de las comunidades uniprovinciales, con el mismo formato que el resto de tablas: códigos INE, `periodo` 2026M09,
`fecha` 2026-09-01, `id_registro` y validación con las mismas reglas.

## Cómo se copia y se pega

1. En la página de Idealista, seleccionar la tabla desde la cabecera "Localización" hasta la última fila.
2. Copiar (Ctrl+C) y pegar en el Bloc de notas (Ctrl+V). Se conservan los tabuladores entre columnas.
3. Guardar en `pegados/alquiler/` o `pegados/venta/` como `<AAAA-MM>_<nivel>.txt`, con nivel `CCAA`, `Provincia` o `Municipio`
   (por ejemplo, `2026-09_Provincia.txt`). El mes se lee de la cabecera ("Precio m2 sep 2026"); el nivel, del nombre.
4. Opcional: la misma página trae una segunda tabla, "Mes | Precio m2 | Variación mensual | …", con los últimos
   12 meses de España. Se copia igual y se guarda como `<AAAA-MM>_historico.txt` (ejemplo:
   `pegados/venta/2026-09_historico.txt`). Añade esos 12 meses para España, sin máximo histórico; si un mes ya está
   en la tabla de comunidades, se queda la fila de comunidades, que trae el máximo.
5. Ejecutar el comando de arriba.

Qué lee y qué comprueba:
- Lee los números en formato español: "15,1 €/m2", "- 0,3 %", "+ 5,6 %" y el máximo "15,3 €/m2 jul 2026".
- Si la cabecera no es la esperada, o una fila no tiene 7 columnas, falla con un mensaje claro (por ejemplo, si se
  pegó otra tabla).
- Los nombres propios de Idealista ("Euskadi", "Madrid Comunidad", "Murcia Región"…) se traducen con una lista propia,
  `alias_idealista.csv`, que no afecta a las demás fuentes.
- Si el mismo mes y territorio se pega dos veces, gana el archivo guardado más tarde.

## Opciones para pasarlo a producción (por decidir)

| Opción | Cómo | Ventajas | Inconvenientes |
|---|---|---|---|
| A. Copiar y pegar (lo probado) | Una persona pega la tabla cada mes | Sencillo; no depende de la web; respeta las condiciones de uso | Manual; hay que acordarse cada mes; el histórico solo empieza cuando se empieza a pegar |
| B. Lectura automática de la tabla HTML | `pandas.read_html` sobre la página | Sin trabajo manual | Idealista probablemente prohíbe la extracción automática (revisar sus condiciones); se rompe si cambia la web |
| C. Datos oficiales de pago | idealista/data (servicio de datos de Idealista) | Histórico completo, más niveles (distrito, municipio), sin riesgo legal | Coste |
| D. Plantilla Excel en lugar de .txt | Se pega en una hoja con columnas fijas | Más cómodo para quien no use el Bloc de notas | Excel puede cambiar formatos al pegar ("15,1 €/m2" → número, fechas); hay que fijar la hoja como texto |

El mismo esquema (pegar + lector + validación) vale para el Notariado (notas de prensa) o cualquier tabla de una web o
un PDF. En un PDF, `pdfplumber` puede extraer las tablas sin copiar a mano.

## Preguntas para decidir

1. ¿Opción A, B, C o D (o A ahora y C más adelante)?
2. ¿Qué niveles interesan: comunidades, provincias, municipios o distritos?
3. ¿Quién pega los datos y con qué frecuencia? (Idealista publica a primeros de cada mes.)
4. ¿Se guardan también las variaciones y el máximo histórico, o solo el precio? (Las variaciones se pueden calcular
   a partir de la serie de precios.)
5. Venta (IDEALISTA-VENTA) ya está probada con el mismo lector: solo cambia el nombre de la tabla y de la medida.
