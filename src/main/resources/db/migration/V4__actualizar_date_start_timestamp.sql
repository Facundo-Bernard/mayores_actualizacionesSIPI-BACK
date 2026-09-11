-- Migracion V4: Convertir date_start a DATETIME con valor por defecto y actualizar registros existentes con NULL

ALTER TABLE usuario MODIFY COLUMN date_start DATETIME DEFAULT CURRENT_TIMESTAMP;

UPDATE usuario SET date_start = NOW() WHERE date_start IS NULL;
