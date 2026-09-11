-- Migracion inicial V1: Estructura base de tablas existentes en produccion

CREATE TABLE IF NOT EXISTS usuario (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    password VARCHAR(255),
    tipo_usuario INT NOT NULL DEFAULT 1,
    is_black BOOLEAN DEFAULT FALSE,
    date_start DATE,
    date_end DATE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS progreso_usuario (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    progreso INT NOT NULL DEFAULT 0,
    completado BOOLEAN NOT NULL DEFAULT FALSE,
    examen_puntos INT NOT NULL DEFAULT 0,
    curso_id BIGINT,
    usuario_id BIGINT,
    CONSTRAINT fk_progreso_usuario FOREIGN KEY (usuario_id) REFERENCES usuario(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reunion (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255),
    descripcion TEXT,
    fecha DATETIME,
    abogado VARCHAR(255),
    estado VARCHAR(50) DEFAULT 'PENDIENTE'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
