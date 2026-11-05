# Primitiva Mutar Estado y Condiciones de Aparición (Motor V2)

**Fecha de implementación:** 5 de Noviembre de 2026  
**Rama:** `feature/refactor-backend`  
**Módulos Afectados:**
- Backend:
  - `app/features/narrative/enums.py`
  - `app/features/narrative/schemas/rules_schemas.py`
  - `app/features/narrative/schemas/catalog_schemas.py`
  - `app/features/narrative/engine/rule_engine.py`
  - `app/features/narrative/admin/actions_crud_service.py`
  - `app/features/narrative/game/endings_service.py`
  - `app/features/narrative/game/setup_service.py`
  - `app/features/narrative/game/transition_service.py`
  - `tests/contract/snapshots/openapi.json` & `narrative_v3.openapi.json`
  - `tests/unit/test_narrative_actions_decoupled.py`
- Frontend:
  - `frontend/admin_src/narrative/EfectosEditor.jsx`
  - `frontend/admin_src/narrative/CondicionesAparicionEditor.jsx`
  - `frontend/admin_src/narrative/CartasTab.jsx`
  - `frontend/admin_src/narrative/PersonajesTab.jsx`
  - Compilación SPA en `backend/mayores_actualizacionesSIPI-BACK/app/static/admin/`

---

## 1. Resumen de la Implementación

Esta actualización introduce dos pilares fundamentales en la arquitectura de reglas del juego narrativo:

1. **Primitiva Genérica `mutar_estado` con Operaciones Matemáticas Avanzadas**: Permite que las acciones muten no solo recursos estándar, sino también límites dinámicos (`limites.<clave>.min`, `limites.<clave>.max`), afinidades y variables de universo, soportando cuentas aditivas, multiplicativas, divisorias, porcentuales y absolutas seleccionables por carta/personaje.
2. **Condiciones de Aparición (`condiciones_aparicion`)**: Cartas y personajes ahora pueden definir requisitos de estado de la partida (recursos mínimos, posesión de personajes, afinidad, tags o cartas) para estar disponibles en la oferta inicial y en los drafts mensuales.

---

## 2. Primitiva `mutar_estado`

### Operaciones Matemáticas Soportadas (`OperacionMatematicaEnum`)
| Operación | Clave Enum | Comportamiento | Salvaguardas |
|---|---|---|---|
| Suma / Unitaria | `sumar` | `nuevo = actual + valor` | Clamping según límites |
| Resta / Unitaria | `restar` | `nuevo = actual - valor` | Amortiguadores de daño si hay pérdida |
| Multiplicación | `multiplicar` | `nuevo = actual * valor` | Clamping según límites |
| División | `dividir` | `nuevo = actual / valor` | División por cero protegida (mantiene valor actual) |
| Porcentual | `porcentual` | `nuevo = actual + (actual * (valor / 100))` | Respeta modificadores pasivos ante caídas |
| Fijar / Asignación | `fijar` | `nuevo = valor` | Clamping según límites |

### Ruteo de Rutas en Estado Vivo (`run_data`)
- **`recursos.<clave>` o clave directa:** Muta el recurso numérico, verifica amortiguación pasiva si hay caída neta, y clampa entre `[limite_min, limite_max]`.
- **`limites.<clave>.min` / `limites.<clave>.max`:** Altera el piso o techo dinámico de un recurso en `run["limites"][clave]`, disparando un re-clamping inmediato sobre el recurso actual para evitar estados ilegales.
- **`afinidad.<target>`:** Muta la lealtad con el portador (`portador`) o con un personaje específico, clampando entre `[0, 100]`.
- **`variables.<clave>`:** Almacena o actualiza variables arbitrarias en `run["variables"]` (ej: multiplicadores económicos, inflación, nivel de amenaza).

### Colapso por Recurso Agotado (`endings_service.py`)
La función `verificar_colapso_recursos` ahora evalúa la derrota considerando el piso dinámico `run_doc.get("limites", {}).get(k, {}).get("min", 0)`. Si un recurso baja a dicho umbral (o 0 por defecto), se dispara la finalización por derrota de forma consistente.

---

## 3. Condiciones de Aparición (`condiciones_aparicion`)

### Modelo y Esquemas
Se agregó el campo opcional:
```python
condiciones_aparicion: List[CondicionSchema] = []
```
en `CartaCreateRequest`, `CartaResponse`, `PersonajeCreateRequest` y `PersonajeResponse`.

### Evaluación en Ciclo de Vida
1. **Oferta Inicial de Personajes y Cartas (`setup_service.py` - `obtener_setup_desafio`):**
   - Evalúa `condiciones_aparicion` contra el estado inicial de recursos y tags.
   - Si al menos 3 candidatos cumplen las condiciones, se restringe la oferta a ellos; en caso contrario, se aplica fallback para garantizar siempre opciones al jugador.
2. **Draft Mensual Inicial y Subsecuente (`setup_service.py` e `transition_service.py`):**
   - Al sortear 3 cartas de `pool_cartas_mensuales_ids`, se evalúa `evaluar_condiciones(c.condiciones_aparicion, run)`.
   - Se priorizan las cartas elegibles. Si hay menos de 3 elegibles, se complementa con cartas del pool para nunca bloquear el avance.

---

## 4. Panel de Administración (Frontend SPA)

1. **`EfectosEditor.jsx`:**
   - Detecta la primitiva `mutar_estado`.
   - Selector de tipo de ruta (Recurso, Límite, Afinidad, Variable, Manual) e input de ruta técnica.
   - Selector de operación matemática (`Sumar (+)`, `Restar (-)`, `Multiplicar (×)`, `Dividir (/)`, `Porcentual (%)`, `Fijar (=)`).
   - Input numérico para el valor exacto.
2. **`CondicionesAparicionEditor.jsx`:**
   - Componente modular reutilizable montado en `CartasTab.jsx` y `PersonajesTab.jsx`.
   - Permite configurar condiciones de tipo:
     - `comparar_recurso` (recurso, operador, valor)
     - `afinidad_personaje` (personaje_id, operador, valor)
     - `tiene_personaje` (personaje_id en corte)
     - `tiene_tag` (tag pasivo activo)
     - `tiene_carta` (carta en mano)
3. **Bundle compilado:**
   - Compilación exitosa con `vite build admin_src`.
   - Servido desde `/admin/` a través de FastAPI con archivos estáticos sincronizados.

---

## 5. Resultados de Pruebas

- **Pytest (Unit & Contract):**
  - **276 / 276 pruebas pasadas (100% GREEN)** en 15.71s.
  - Nuevas pruebas añadidas en `tests/unit/test_narrative_actions_decoupled.py`:
    - `test_mutar_estado_operaciones_matematicas`
    - `test_mutar_estado_limites_dinamicos`
    - `test_mutar_estado_afinidad_y_variables`
    - `test_condiciones_aparicion_evaluacion`
- **E2E Live (`testing_lab/test_admin_live_e2e.py`):**
  - **13 / 13 verificaciones pasadas** contra el backend en vivo (`http://127.0.0.1:8090`) y MongoDB local.
  - Creación y verificación de acciones con `mutar_estado`.
  - Creación de cartas y personajes con `condiciones_aparicion`.
  - Integridad referencial y bloqueo de borrado con 409 verificado.
  - Integridad de assets estáticos del panel admin verificada.
