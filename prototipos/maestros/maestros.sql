-- PROTOTIPO (Tarea 17). Generado por prototipos/maestros/generar.py. No editar a mano.

CREATE SCHEMA IF NOT EXISTS `MAESTROS` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

CREATE TABLE IF NOT EXISTS `MAESTROS`.`dim_territorio` (
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

CREATE TABLE IF NOT EXISTS `MAESTROS`.`dim_territorio_alias` (
  `id_alias` INT UNSIGNED NOT NULL,
  `alias` VARCHAR(200) NOT NULL COMMENT 'Texto tal como aparece en una fuente',
  `nivel` ENUM('Nacional','CCAA','Provincia','Municipio','Distrito','Seccion') NOT NULL,
  `cod_territorio` VARCHAR(12) NOT NULL,
  `fuente_alias` VARCHAR(40) NULL COMMENT 'Dataset o fuente donde se vio el texto',
  `cod_fuente_alias` VARCHAR(40) NULL COMMENT 'Código del territorio en esa fuente',
  PRIMARY KEY (`id_alias`),
  INDEX `ix_alias_texto` (`alias`),
  CONSTRAINT `fk_alias_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`)
) ENGINE=InnoDB COMMENT='Alias de territorios; solo los que difieren del nombre oficial al normalizar';

CREATE TABLE IF NOT EXISTS `MAESTROS`.`dim_periodo` (
  `periodo` VARCHAR(7) NOT NULL COMMENT 'AAAA / AAAATn / AAAAMmm',
  `frecuencia` CHAR(1) NOT NULL COMMENT 'A / T / M',
  `fecha` DATE NOT NULL COMMENT 'Primer día del periodo',
  `fecha_fin` DATE NOT NULL COMMENT 'Último día del periodo',
  `periodo_padre` VARCHAR(7) NULL COMMENT 'El mes apunta a su trimestre y el trimestre a su año',
  PRIMARY KEY (`periodo`),
  INDEX `ix_dim_periodo_fecha` (`fecha`),
  CONSTRAINT `fk_periodo_padre` FOREIGN KEY (`periodo_padre`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`)
) ENGINE=InnoDB COMMENT='Calendario M/T/A; anio/trimestre/mes ya son columnas generadas de las tablas de datos';

CREATE TABLE IF NOT EXISTS `MAESTROS`.`dim_categoria` (
  `dimension` VARCHAR(40) NOT NULL COMMENT 'Nombre de la columna propia (regimen, antiguedad...)',
  `codigo` VARCHAR(20) NOT NULL,
  `descripcion` VARCHAR(200) NOT NULL,
  PRIMARY KEY (`dimension`, `codigo`)
) ENGINE=InnoDB COMMENT='Valores de las dimensiones propias (genérica; alternativa: una tabla por dimensión)';

-- Carga de los CSV de prototipos/maestros/datos/ (desde la raíz del proyecto, con local_infile activo).
-- Orden obligatorio: dim_territorio antes que dim_territorio_alias; dim_periodo ya trae los padres primero.

LOAD DATA LOCAL INFILE 'prototipos/maestros/datos/dim_territorio.csv' INTO TABLE `MAESTROS`.`dim_territorio`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`cod_territorio`, `nivel`, `cod_ccaa`, `nombre_ccaa`, @cod_provincia, @nombre_provincia, @cod_municipio, @nombre_municipio, `nombre_territorio`)
SET `cod_provincia` = NULLIF(@cod_provincia, ''),
    `nombre_provincia` = NULLIF(@nombre_provincia, ''),
    `cod_municipio` = NULLIF(@cod_municipio, ''),
    `nombre_municipio` = NULLIF(@nombre_municipio, '');

LOAD DATA LOCAL INFILE 'prototipos/maestros/datos/dim_territorio_alias.csv' INTO TABLE `MAESTROS`.`dim_territorio_alias`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`id_alias`, `alias`, `nivel`, `cod_territorio`, @fuente_alias, @cod_fuente_alias)
SET `fuente_alias` = NULLIF(@fuente_alias, ''),
    `cod_fuente_alias` = NULLIF(@cod_fuente_alias, '');

LOAD DATA LOCAL INFILE 'prototipos/maestros/datos/dim_periodo.csv' INTO TABLE `MAESTROS`.`dim_periodo`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`periodo`, `frecuencia`, `fecha`, `fecha_fin`, @periodo_padre)
SET `periodo_padre` = NULLIF(@periodo_padre, '');

LOAD DATA LOCAL INFILE 'prototipos/maestros/datos/dim_categoria.csv' INTO TABLE `MAESTROS`.`dim_categoria`
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ';' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`dimension`, `codigo`, `descripcion`);
