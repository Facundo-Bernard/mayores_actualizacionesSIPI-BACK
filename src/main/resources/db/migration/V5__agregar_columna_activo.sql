-- Migracion V5: Agregar columna activo a la tabla usuario

ALTER TABLE usuario ADD COLUMN activo BOOLEAN NOT NULL DEFAULT TRUE;
