# Desacople de Acciones y Frecuencias - Motor Narrativo V2

Este documento resume las modificaciones implementadas para desacoplar las **Acciones** y las **Frecuencias** de las **Cartas** y los **Personajes**, dotando al motor narrativo V2 de catálogos configurables por universo en MongoDB, control de concurrencia optimista (OCC), integridad referencial estricta y sincronización visual con la Torre de Control (Panel de Administración).

---

## 1. Motivación y Objetivos

1. **Desacoplamiento Estructural**: Anteriormente, cada carta o personaje contenía una definición de acción inline embebida (`AccionSchema`) atada a enums estáticos en código Python (`TipoAccionEnum`).
2. **Catálogos Dinámicos**:
   - `narrative_actions`: Catálogo de acciones por universo con nombre amigable, descripción, primitiva ejecutable, control de disponibilidad y ámbito (`permitido_en: ["carta", "personaje"]`).
   - `narrative_frequencies`: Catálogo de frecuencias almacenado como un array dentro de un único documento por universo (`_id: "frecuencias_<universo_id>"`).
3. **Parámetros en la Entidad**: La acción de catálogo define *el verbo* (la operación soportada por el motor) y sus reglas, mientras que la carta o el personaje configuran *sobre qué y cuánto* (`clave`, `valor`, `tipo_calculo`, `destino`). Esto previene la explosión combinatoria de entradas en el catálogo.
4. **Periodicidad Relativa a la Adquisición**: Las frecuencias de intervalo (`cada: N` meses) se computan respecto del mes en que la carta o el personaje fue reclutado/adquirido (`(mes_actual - mes_adquisicion) % cada == 0`).
5. **Integridad Referencial y OCC**: Bloqueo de eliminación (HTTP 409) si una acción o frecuencia tiene referencias vivas en cartas o personajes. Control de versiones con `expected_version` ante ediciones concurrentes.

---

## 2. Arquitectura de Datos y Motor

### 2.1 Primitivas del Motor (`PrimitivaOperacionEnum`)
El motor de reglas (`rule_engine.py`) abstrae las mutaciones del estado de la partida en 5 primitivas genéricas:
- `modificar_recurso`: Suma, resta o calcula porcentualmente la alteración de un recurso numérico del universo, respetando límites `[min, max]` y evaluando modificadores pasivos de reducción de daño.
- `modificar_afinidad`: Ajusta el nivel de lealtad (0-100). Soporta `destino="portador"` (el personaje dueño del efecto) o un `personaje_id` explícito.
- `otorgar_tag`: Registra un tag permanente en `run["tags_activos"]` (idempotente).
- `remover_tag`: Elimina un tag activo de la partida.
- `amortiguar_danio`: Registra un modificador pasivo en `run["modificadores_pasivos"]` que absorbe porcentualmente las pérdidas del recurso indicado ante eventos negativos y balances mensuales.

### 2.2 Estructura de Efectos Desacoplados (`EfectoSchema`)
```json
{
  "frecuencia_id": "cada_2_meses",
  "disparador": "cada_mes",
  "condiciones": [
    { "tipo": "comparar_recurso", "clave": "pueblo", "operador": ">=", "valor": 40 }
  ],
  "acciones": [
    {
      "accion_id": "modificar_recurso",
      "parametros": { "clave": "pueblo", "valor": 10, "tipo_calculo": "fijo" }
    },
    {
      "accion_id": "otorgar_tag",
      "parametros": { "tag": "apoyo_popular" }
    }
  ]
}
```
*Compatibilidad dual:* El normalizador interno en Pydantic (`EfectoSchema.normalizar_compatibilidad`) convierte en memoria el formato legacy `{disparador, accion}` al nuevo formato desacoplado con array de acciones, garantizando compatibilidad retroactiva completa.

### 2.3 Registro de Adquisiciones Relativas
En `setup_service.py` y `turn_service.py`, al reclutar la corte inicial o seleccionar una carta del draft mensual, se actualiza el mapa:
```python
run["adquisiciones"][item_id] = {"mes": mes_actual, "tipo": "carta" | "personaje"}
```
En el ciclo mensual (`transition_service.py`), `despachar_efectos` evalúa si pasaron los meses necesarios desde la adquisición para disparar el efecto periódico.

---

## 3. Endpoints de Administración (`/api/narrative/admin/*`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/narrative/admin/operaciones` | Lista las 5 primitivas del motor y sus requerimientos de parámetros |
| `GET` | `/api/narrative/admin/eventos-motor` | Lista los eventos del ciclo de vida (`al_obtener`, `inicio_mes`) |
| `GET` | `/api/narrative/admin/acciones` | Lista acciones del catálogo (filtrable por `universo_id`) |
| `POST` | `/api/narrative/admin/acciones` | Registra una nueva acción de catálogo |
| `GET` | `/api/narrative/admin/acciones/{id}` | Detalle de una acción |
| `PUT` | `/api/narrative/admin/acciones/{id}` | Actualización con control optimista de concurrencia (`expected_version`) |
| `DELETE` | `/api/narrative/admin/acciones/{id}` | Eliminación segura (409 Conflict si está referenciada) |
| `GET` | `/api/narrative/admin/acciones/{id}/usos` | Referencias cruzadas en cartas y personajes |
| `GET` | `/api/narrative/admin/frecuencias` | Retorna el documento de frecuencias para el universo solicitado |
| `PUT` | `/api/narrative/admin/frecuencias/{universo_id}` | Actualiza el array de frecuencias con OCC (`expected_version`) |
| `GET` | `/api/narrative/admin/frecuencias/{id}/usos` | Referencias cruzadas de una frecuencia en cartas y personajes |

---

## 4. Frontend - Panel de Administración (Torre de Control)

1. **Pestaña Acciones (`AccionesTab.jsx`)**:
   - Visualización de tarjetas de acciones con selector de universo.
   - Creación y edición con modal interactivo que asocia la primitiva a la acción y define permisos de vinculación.
   - Botón "Ver referencias" que consulta en tiempo real los usos en cartas y personajes.
2. **Pestaña Frecuencias (`FrecuenciasTab.jsx`)**:
   - Gestión del array de frecuencias del universo.
   - Configuración de periodicidad (`cada`, `desfase`, `conteo_desde: adquisicion / inicio_partida`).
   - Botón "Ver referencias" y validación previa antes de eliminar.
3. **Editor Reutilizable (`EfectosEditor.jsx`)**:
   - Componente cohesivo integrado en `CartasTab.jsx` y `PersonajesTab.jsx`.
   - Permite agregar N efectos a cada entidad.
   - Cada efecto permite seleccionar la frecuencia del catálogo y ordenar múltiples acciones con sus respectivos parámetros dinámicos según la primitiva.
4. **Build de Producción**:
   - Compilado con `npm run build:admin` generando el bundle estático en `app/static/admin/`.

---

## 5. Resumen de Pruebas y Verificación

- **Suite Pytest**: 272 pruebas automatizadas pasando al 100% (unitarias, contratos y snapshots OpenAPI).
- **Prueba E2E en Vivo (`testing_lab/test_admin_live_e2e.py`)**:
  - Autenticación de administrador contra el backend en ejecución (puerto 8090).
  - Consulta de primitivas y eventos de motor.
  - CRUD de acciones con verificación de OCC (rechazo 409 y éxito 200).
  - CRUD de frecuencias en documento array con OCC.
  - Creación de carta con efectos desacoplados múltiples y verificación de actualización de referencias.
  - Bloqueo de eliminación con 409 Conflict mientras la acción se encuentra en uso.
  - Limpieza de entidades de prueba.
  - Verificación de entrega de assets en `/admin/`.
