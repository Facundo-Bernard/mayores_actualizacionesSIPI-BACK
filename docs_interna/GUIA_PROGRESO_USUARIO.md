# Documentación de API: Progreso del Alumno (`features/progreso`)

Este documento detalla la estructura, endpoints, payloads de petición (request) y formatos de respuesta (response) para el módulo de seguimiento de progreso de cursos de los alumnos en **Mayores Actualizaciones**.

---

## 1. ¿Cómo funciona y qué hay dentro de `features/progreso`?

El paquete `features/progreso/` contiene la lógica completa para persistir y consultar el avance de cada alumno en cada curso:

| Archivo | Responsabilidad |
|---|---|
| [`ProgresoUsuario.java`](file:///c:/Users/monti/Desktop/Coopya_sistemas/pagina_cursos/mayores_actualizacionesSIPI-BACK/src/main/java/com/example/uade/tpo/practica2back/features/progreso/ProgresoUsuario.java) | Entidad JPA (`@Entity`) mapeada a la tabla MySQL `progreso_usuario`, con sus esquemas DTOs embebidos (`CreateRequest`, `UpdateRequest`, `Response`). |
| [`ProgresoUsuarioRepository.java`](file:///c:/Users/monti/Desktop/Coopya_sistemas/pagina_cursos/mayores_actualizacionesSIPI-BACK/src/main/java/com/example/uade/tpo/practica2back/features/progreso/ProgresoUsuarioRepository.java) | Repositorio Spring Data JPA con métodos de consulta por `usuario_id` y por la combinación `usuario_id` + `curso_id`. |
| [`ProgresoUsuarioService.java`](file:///c:/Users/monti/Desktop/Coopya_sistemas/pagina_cursos/mayores_actualizacionesSIPI-BACK/src/main/java/com/example/uade/tpo/practica2back/features/progreso/ProgresoUsuarioService.java) | Interfaz del servicio de negocio. |
| [`ProgresoUsuarioServiceImpl.java`](file:///c:/Users/monti/Desktop/Coopya_sistemas/pagina_cursos/mayores_actualizacionesSIPI-BACK/src/main/java/com/example/uade/tpo/practica2back/features/progreso/ProgresoUsuarioServiceImpl.java) | Implementación transaccional (`@Transactional`) que guarda y actualiza los registros en base de datos. |
| [`ProgresoUsuarioController.java`](file:///c:/Users/monti/Desktop/Coopya_sistemas/pagina_cursos/mayores_actualizacionesSIPI-BACK/src/main/java/com/example/uade/tpo/practica2back/features/progreso/ProgresoUsuarioController.java) | Controlador REST (`/progreso`) con `@CrossOrigin(origins = "*")`. |

### ¿Se está guardando en la base de datos?
**SÍ, se guarda de forma persistente en MySQL.**
En la tabla `progreso_usuario` creada por Flyway (`V1__init_schema.sql`):
```sql
CREATE TABLE IF NOT EXISTS progreso_usuario (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    progreso INT NOT NULL DEFAULT 0,         -- Porcentaje de 0 a 100
    completado BOOLEAN NOT NULL DEFAULT FALSE, -- Si finalizó el curso
    examen_puntos INT NOT NULL DEFAULT 0,    -- Puntaje obtenido en la evaluación
    curso_id BIGINT,                         -- ID del curso
    usuario_id BIGINT,                       -- ID del alumno (FK hacia usuario.id)
    CONSTRAINT fk_progreso_usuario FOREIGN KEY (usuario_id) REFERENCES usuario(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 2. Endpoints y Contratos de Datos

Base URL: `http://localhost:8080` (o variable `VITE_API_URL`)

### 2.1. Crear Progreso Inicial de un Curso para un Alumno

Crea el registro de seguimiento para un curso específico.

- **Método:** `POST`
- **Ruta:** `/progreso/crear`
- **Cabeceras:** `Content-Type: application/json`

#### Payload de Entrada (Request Body):
```json
{
  "progreso": 0,
  "completado": false,
  "examenPuntos": 0,
  "cursoId": 1,
  "usuarioId": 4
}
```

#### Respuesta Exitosa (`201 Created`):
```json
{
  "id": 1,
  "progreso": 0,
  "completado": false,
  "examenPuntos": 0,
  "cursoId": 1,
  "usuarioId": 4
}
```

---

### 2.2. Actualizar Progreso de un Curso

Actualiza el porcentaje de avance, si fue completado y los puntos del examen de un curso en curso.

- **Método:** `PUT`
- **Ruta:** `/progreso/actualizar/{usuarioId}/{cursoId}`
- **Parámetros de Ruta:**
  - `usuarioId`: ID del alumno (ej: `4`).
  - `cursoId`: ID del curso (ej: `1`).
- **Cabeceras:** `Content-Type: application/json`

#### Payload de Entrada (Request Body):
```json
{
  "progreso": 75,
  "completado": false,
  "examenPuntos": 0
}
```

*(Cuando el alumno finaliza el curso y aprueba el examen)*:
```json
{
  "progreso": 100,
  "completado": true,
  "examenPuntos": 10
}
```

#### Respuesta Exitosa (`200 OK`):
```json
{
  "id": 1,
  "progreso": 75,
  "completado": false,
  "examenPuntos": 0,
  "cursoId": 1,
  "usuarioId": 4
}
```

#### Respuestas de Error:
* **`500 Internal Server Error`** (si aún no existía un registro para ese usuario y curso):
  ```json
  {
    "message": "No se encontró ningún progreso para el usuario 4 y curso 1"
  }
  ```
  *(Recomendación: Si el registro aún no existe, llamar primero a `POST /progreso/crear`, o podemos implementar un Upsert automático en el backend).*

---

### 2.3. Obtener Todo el Progreso de un Alumno

Recupera la lista de todos los cursos iniciados por un alumno junto con su porcentaje y estado de completitud.

- **Método:** `GET`
- **Ruta:** `/progreso/obtenerUsuario/{usuarioId}`
- **Parámetros de Ruta:**
  - `usuarioId`: ID del alumno (ej: `4`).

#### Respuesta Exitosa (`200 OK`):
```json
[
  {
    "id": 1,
    "progreso": 100,
    "completado": true,
    "examenPuntos": 10,
    "cursoId": 1,
    "usuarioId": 4
  },
  {
    "id": 2,
    "progreso": 40,
    "completado": false,
    "examenPuntos": 0,
    "cursoId": 2,
    "usuarioId": 4
  }
]
```

*(Si el alumno no inició ningún curso aún, devuelve un array vacío `[]`)*.

---

## 3. Ejemplos de Integración en el Frontend (React / JS)

### 3.1. Obtener progreso al cargar la pantalla de cursos
```javascript
const obtenerProgresoCursos = async (usuarioId) => {
  try {
    const res = await fetch(`http://localhost:8080/progreso/obtenerUsuario/${usuarioId}`);
    if (!res.ok) throw new Error('Error al obtener progreso');
    const data = await res.json();
    
    // data es un array de progresos: [{ cursoId: 1, progreso: 80, completado: false, ... }]
    return data;
  } catch (error) {
    console.error('Error cargando progreso:', error);
    return [];
  }
};
```

### 3.2. Guardar avance al completar una lección o video
```javascript
const guardarAvanceCurso = async (usuarioId, cursoId, nuevoPorcentaje, estaCompletado = false, puntosExamen = 0) => {
  try {
    const res = await fetch(`http://localhost:8080/progreso/actualizar/${usuarioId}/${cursoId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        progreso: nuevoPorcentaje,
        completado: estaCompletado,
        examenPuntos: puntosExamen
      })
    });

    if (res.status === 500 || res.status === 404) {
      // Si todavía no existía el registro para este curso, lo creamos
      const resCrear = await fetch('http://localhost:8080/progreso/crear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          progreso: nuevoPorcentaje,
          completado: estaCompletado,
          examenPuntos: puntosExamen,
          cursoId: cursoId,
          usuarioId: usuarioId
        })
      });
      return await resCrear.json();
    }

    return await res.json();
  } catch (error) {
    console.error('Error actualizando progreso:', error);
  }
};
```
