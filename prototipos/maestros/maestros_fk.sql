-- PROTOTIPO (Tarea 17). Generado por prototipos/maestros/generar.py. No editar a mano.
-- Ejecutar DESPUÉS de create_tables.sql y maestros.sql; mejor tras la carga masiva (las FK la ralentizan).
-- dim_categoria NO se enlaza: la FK compuesta (dimension, codigo) no encaja con el diseño actual
-- (cada tabla guarda solo el codigo en su columna propia). Relaciones documentadas, no creadas:
--   MIVAU.mivau_certificados_fin_obra.promotor -> MAESTROS.dim_categoria (dimension = 'promotor', codigo)
--   MIVAU.mivau_eti_compradores_extranjeros.cod_ccaa_comprador -> MAESTROS.dim_categoria (dimension = 'cod_ccaa_comprador', codigo)
--   MIVAU.mivau_eti_transacciones.regimen -> MAESTROS.dim_categoria (dimension = 'regimen', codigo)
--   MIVAU.mivau_eti_transacciones.antiguedad -> MAESTROS.dim_categoria (dimension = 'antiguedad', codigo)
--   MIVAU.mivau_serpavi_alquiler.tipologia -> MAESTROS.dim_categoria (dimension = 'tipologia', codigo)
--   MIVAU.mivau_valor_medio_vivienda_libre.tipo_comprador -> MAESTROS.dim_categoria (dimension = 'tipo_comprador', codigo)
--   MIVAU.mivau_valor_medio_vivienda_libre.antiguedad -> MAESTROS.dim_categoria (dimension = 'antiguedad', codigo)
--   MIVAU.mivau_valor_tasado_municipios_25000.antiguedad -> MAESTROS.dim_categoria (dimension = 'antiguedad', codigo)
--   MIVAU.mivau_valor_tasado_vivienda_libre.antiguedad -> MAESTROS.dim_categoria (dimension = 'antiguedad', codigo)
--   MIVAU.mivau_visados_direccion_obra.tipo_obra -> MAESTROS.dim_categoria (dimension = 'tipo_obra', codigo)
--   MIVAU.mivau_vpo_calificaciones_definitivas.regimen -> MAESTROS.dim_categoria (dimension = 'regimen', codigo)

ALTER TABLE `MIVAU`.`mivau_certificados_fin_obra`
  ADD CONSTRAINT `fk_mivau_certificados_fin_obra_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_certificados_fin_obra`
  ADD CONSTRAINT `fk_mivau_certificados_fin_obra_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_eti_compradores_extranjeros`
  ADD CONSTRAINT `fk_mivau_eti_compradores_extranjeros_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_eti_compradores_extranjeros`
  ADD CONSTRAINT `fk_mivau_eti_compradores_extranjeros_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_eti_transacciones`
  ADD CONSTRAINT `fk_mivau_eti_transacciones_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_eti_transacciones`
  ADD CONSTRAINT `fk_mivau_eti_transacciones_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_precio_suelo_urbano`
  ADD CONSTRAINT `fk_mivau_precio_suelo_urbano_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_precio_suelo_urbano`
  ADD CONSTRAINT `fk_mivau_precio_suelo_urbano_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_serpavi_alquiler`
  ADD CONSTRAINT `fk_mivau_serpavi_alquiler_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_serpavi_alquiler`
  ADD CONSTRAINT `fk_mivau_serpavi_alquiler_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_valor_medio_vivienda_libre`
  ADD CONSTRAINT `fk_mivau_valor_medio_vivienda_libre_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_valor_medio_vivienda_libre`
  ADD CONSTRAINT `fk_mivau_valor_medio_vivienda_libre_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_valor_tasado_municipios_25000`
  ADD CONSTRAINT `fk_mivau_valor_tasado_municipios_25000_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_valor_tasado_municipios_25000`
  ADD CONSTRAINT `fk_mivau_valor_tasado_municipios_25000_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_valor_tasado_vivienda_libre`
  ADD CONSTRAINT `fk_mivau_valor_tasado_vivienda_libre_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_valor_tasado_vivienda_libre`
  ADD CONSTRAINT `fk_mivau_valor_tasado_vivienda_libre_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_visados_direccion_obra`
  ADD CONSTRAINT `fk_mivau_visados_direccion_obra_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_visados_direccion_obra`
  ADD CONSTRAINT `fk_mivau_visados_direccion_obra_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_vivienda_libre_iniciadas`
  ADD CONSTRAINT `fk_mivau_vivienda_libre_iniciadas_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_vivienda_libre_iniciadas`
  ADD CONSTRAINT `fk_mivau_vivienda_libre_iniciadas_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_vivienda_libre_terminadas`
  ADD CONSTRAINT `fk_mivau_vivienda_libre_terminadas_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_vivienda_libre_terminadas`
  ADD CONSTRAINT `fk_mivau_vivienda_libre_terminadas_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);

ALTER TABLE `MIVAU`.`mivau_vpo_calificaciones_definitivas`
  ADD CONSTRAINT `fk_mivau_vpo_calificaciones_definitivas_territorio` FOREIGN KEY (`cod_territorio`) REFERENCES `MAESTROS`.`dim_territorio` (`cod_territorio`);

ALTER TABLE `MIVAU`.`mivau_vpo_calificaciones_definitivas`
  ADD CONSTRAINT `fk_mivau_vpo_calificaciones_definitivas_periodo` FOREIGN KEY (`periodo`) REFERENCES `MAESTROS`.`dim_periodo` (`periodo`);
