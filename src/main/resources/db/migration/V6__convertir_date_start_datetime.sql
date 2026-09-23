-- Migracion V6: Convertir date_start a DATETIME(6) para sincronizar con LocalDateTime y Hibernate 6
ALTER TABLE usuario MODIFY COLUMN date_start DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6);

UPDATE usuario SET date_start = NOW(6) WHERE date_start IS NULL;
