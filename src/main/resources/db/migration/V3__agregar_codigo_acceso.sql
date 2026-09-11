-- Migracion V3: Agregar codigo de acceso para ingreso rapido sin correo
ALTER TABLE usuario ADD COLUMN codigo_acceso VARCHAR(50) UNIQUE;
