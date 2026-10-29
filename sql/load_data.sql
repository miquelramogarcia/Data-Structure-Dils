-- Generado por etl/catalogo/sql.py el 2026-10-29. No editar a mano.
-- Ejecutar DESPUÉS de create_tables.sql, desde la raíz del proyecto y con local_infile activo
-- (servidor: SET GLOBAL local_infile = 1; cliente: mysql --local-infile=1).
-- anio, trimestre y mes son columnas generadas: se leen en @omitir_* y MySQL las calcula desde fecha.

LOAD DATA LOCAL INFILE 'etl/salida/mivau_vpo_calificaciones_definitivas.csv' INTO TABLE `MIVAU`.`mivau_vpo_calificaciones_definitivas`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `regimen`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_viviendas, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_viviendas` = NULLIF(@num_viviendas, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_vivienda_libre_iniciadas.csv' INTO TABLE `MIVAU`.`mivau_vivienda_libre_iniciadas`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_viviendas, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_viviendas` = NULLIF(@num_viviendas, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_vivienda_libre_terminadas.csv' INTO TABLE `MIVAU`.`mivau_vivienda_libre_terminadas`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_viviendas, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_viviendas` = NULLIF(@num_viviendas, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_eti_transacciones.csv' INTO TABLE `MIVAU`.`mivau_eti_transacciones`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `regimen`, `antiguedad`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_transacciones, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_transacciones` = NULLIF(@num_transacciones, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_eti_compradores_extranjeros.csv' INTO TABLE `MIVAU`.`mivau_eti_compradores_extranjeros`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `cod_ccaa_comprador`, `nombre_ccaa_comprador`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_transacciones, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_transacciones` = NULLIF(@num_transacciones, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_valor_medio_vivienda_libre.csv' INTO TABLE `MIVAU`.`mivau_valor_medio_vivienda_libre`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `tipo_comprador`, `antiguedad`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @valor_medio_eur, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `valor_medio_eur` = NULLIF(@valor_medio_eur, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_valor_tasado_vivienda_libre.csv' INTO TABLE `MIVAU`.`mivau_valor_tasado_vivienda_libre`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `antiguedad`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @valor_tasado_eur_m2, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `valor_tasado_eur_m2` = NULLIF(@valor_tasado_eur_m2, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_valor_tasado_municipios_25000.csv' INTO TABLE `MIVAU`.`mivau_valor_tasado_municipios_25000`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `antiguedad`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @valor_tasado_eur_m2, @num_tasaciones, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `valor_tasado_eur_m2` = NULLIF(@valor_tasado_eur_m2, ''),
    `num_tasaciones` = NULLIF(@num_tasaciones, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_precio_suelo_urbano.csv' INTO TABLE `MIVAU`.`mivau_precio_suelo_urbano`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @precio_eur_m2, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `precio_eur_m2` = NULLIF(@precio_eur_m2, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_certificados_fin_obra.csv' INTO TABLE `MIVAU`.`mivau_certificados_fin_obra`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `promotor`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_viviendas, @valor_liquidacion_miles_eur, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_viviendas` = NULLIF(@num_viviendas, ''),
    `valor_liquidacion_miles_eur` = NULLIF(@valor_liquidacion_miles_eur, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_visados_direccion_obra.csv' INTO TABLE `MIVAU`.`mivau_visados_direccion_obra`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `tipo_obra`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @num_viviendas, @superficie_media_m2, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `num_viviendas` = NULLIF(@num_viviendas, ''),
    `superficie_media_m2` = NULLIF(@superficie_media_m2, '');

LOAD DATA LOCAL INFILE 'etl/salida/mivau_serpavi_alquiler.csv' INTO TABLE `MIVAU`.`mivau_serpavi_alquiler`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_registro`, `nivel`, `cod_territorio`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, @cod_distrito, @cod_seccion, `tipologia`, `periodo`, `frecuencia`, @omitir_anio, @omitir_trimestre, @omitir_mes, `fecha`, @renta_mediana_eur_m2_mes, @renta_p25_eur_m2_mes, @renta_p75_eur_m2_mes, @renta_mediana_eur_mes, @renta_p25_eur_mes, @renta_p75_eur_mes, @superficie_mediana_m2, @superficie_p25_m2, @superficie_p75_m2, @num_inmuebles_alquiler, `provisional`, `fecha_descarga`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, ''),
    `cod_distrito` = NULLIF(@cod_distrito, ''),
    `cod_seccion` = NULLIF(@cod_seccion, ''),
    `renta_mediana_eur_m2_mes` = NULLIF(@renta_mediana_eur_m2_mes, ''),
    `renta_p25_eur_m2_mes` = NULLIF(@renta_p25_eur_m2_mes, ''),
    `renta_p75_eur_m2_mes` = NULLIF(@renta_p75_eur_m2_mes, ''),
    `renta_mediana_eur_mes` = NULLIF(@renta_mediana_eur_mes, ''),
    `renta_p25_eur_mes` = NULLIF(@renta_p25_eur_mes, ''),
    `renta_p75_eur_mes` = NULLIF(@renta_p75_eur_mes, ''),
    `superficie_mediana_m2` = NULLIF(@superficie_mediana_m2, ''),
    `superficie_p25_m2` = NULLIF(@superficie_p25_m2, ''),
    `superficie_p75_m2` = NULLIF(@superficie_p75_m2, ''),
    `num_inmuebles_alquiler` = NULLIF(@num_inmuebles_alquiler, '');
