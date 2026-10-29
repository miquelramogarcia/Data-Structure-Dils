CREATE SCHEMA IF NOT EXISTS `META` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

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
