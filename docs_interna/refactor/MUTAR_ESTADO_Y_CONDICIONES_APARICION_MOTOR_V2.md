# Primitiva Mutar Estado, Condiciones de Aparición y Conexión de Grafos (Motor V2)

**Fecha de implementación:** 5 de Noviembre de 2026  
**Rama Backend:** `feature/refactor-backend`  
**Rama Frontend:** `feature/juego-narrativo`  

---

## 1. Conexión del Motor de Grafos (V2) con el Motor de Reglas y Recursos

### ¿Cómo están conectados los grafos con el cálculo de recursos?

El motor narrativo V2 opera en un pipeline desacoplado pero estrechamente coordinado:

```
[Fase 1: Draft Mensual]
  │
  ├── Jugador elige carta de apoyo ofrecida en el mes.
  └── turn_service.py despacha efectos AL_OBTENER de la carta usando rule_engine.py.
  │
[Fase 2: Grafo de Evento Mensual]
  │
  ├── graph_engine.sortear_evento_v2() filtra eventos según sinergias, tags y recursos.
  ├── Jugador navega opciones en /v2/partida/avanzar-nodo.
  ├── Cada opción evalúa sus requisitos dinámicos contra el estado vivo (rule_engine.evaluar_condicion).
  └── Al alcanzar el NODO TERMINAL (es_final = True):
        │
        ├── 1. Impactos de Recursos con Modificadores Pasivos:
        │      Si el impacto es pérdida (delta < 0), se evalúan los modificadores pasivos
        │      activos de la partida (ej: "amortiguar_danio" al 50% de oro otorgado por cartas/perks)
        │      reduciendo la pérdida neta.
        │
        ├── 2. Clamping contra Límites Dinámicos:
        │      El recurso resultante se clampa estrictamente contra run["limites"][recurso]
        │      (piso dinámico y techo dinámico configurados mediante mutar_estado),
        │      con fallback al mapa de recursos del universo.
        │
        ├── 3. Disparo de Efectos Reactivos:
        │      Si la decisión generó delta neto positivo o negativo, se despacha
        │      automáticamente el evento reactivo (EN_EVENTO_POSITIVO o EN_EVENTO_NEGATIVO)
        │      sobre las cartas en mano y los personajes de la corte.
        │
        ├── 4. Impactos de Afinidad y Umbrales:
        │      Aplica deltas a afinidad (0-100) y detecta cruces de lealtad (>=95) o traición (<15),
        │      encadenando eventos especiales si corresponde.
        │
        ├── 5. Tags Permanentes:
        │      Agrega los tags otorgados por el nodo a run["tags_activos"].
        │
        └── 6. Verificación de Derrota por Colapso:
               verificar_colapso_recursos(run) comprueba si algún recurso cayó a su límite
               mínimo (0 por defecto o límite dinámico). En caso afirmativo, epílogo y game_over.
```

---

## 2. Selectores Dinámicos en el Panel de Administrador (Sin Hardcodeo)

En `frontend/admin_src/narrative/`:

1. **Consulta Dinámica a la API:**
   - Recursos: cargados dinámicamente desde `/api/narrative/admin/universos/{universo_id}`.
   - Personajes: cargados dinámicamente desde `/api/narrative/admin/personajes?universo_id={universo_id}`.
   - Acciones: cargadas desde `/api/narrative/admin/acciones?universo_id={universo_id}`.
   - Frecuencias: cargadas desde `/api/narrative/admin/frecuencias?universo_id={universo_id}`.

2. **Editor de Mutador Genérico (`EfectosEditor.jsx`):**
   - **Tipo de Objetivo:**
     - `Recurso Numérico` (`recursos.<clave>`)
     - `Límite Máximo / Techo` (`limites.<clave>.max`)
     - `Límite Mínimo / Piso` (`limites.<clave>.min`)
     - `Afinidad Personaje` (`afinidad.<target>`)
     - `Variable del Universo` (`variables.<clave>`)
     - `Ruta Manual`
   - **Selector Específico:**
     - Si es recurso o límite: despliega un `<select>` con los recursos propios del universo (Oro, Pueblo, Ejército, Fe, etc.).
     - Si es afinidad: despliega un `<select>` con los personajes del universo (Elena de Valoria, Marcus Thorne, etc.) + opción de "Portador (Él mismo)".
     - Si es variable: input limpio para el nombre de la variable.
   - **Operación Matemática:**
     - `Sumar (+)`
     - `Restar (-)`
     - `Multiplicar (×)`
     - `Dividir (/)`
     - `Porcentual (%)`
     - `Fijar (=)`
   - **Valor:**
     - Campo numérico para el delta o factor.

3. **Editor de Condiciones de Aparición (`CondicionesAparicionEditor.jsx`):**
   - Al configurar condiciones de tipo `Tiene Personaje` o `Afinidad Personaje`, despliega el listado de personajes del universo cargado por API, eliminando la necesidad de recordar o escribir identificadores manuales.
   - Al configurar `Comparar Recurso`, despliega los recursos del universo.

---

## 3. Pruebas y Validación

- **Pytest (Backend):**
  - **276 / 276 tests pasados (100% green)** en 14.54s.
- **E2E Live Test (`test_admin_live_e2e.py`):**
  - **13 / 13 checks exitosos** contra backend en vivo y MongoDB local (`http://127.0.0.1:8090`).
  - Creación de acciones con `mutar_estado`.
  - Creación de cartas y personajes con `condiciones_aparicion`.
  - Integridad referencial y bloqueo de borrado con 409 verificado.
  - Verificación del bundle estático SPA montado en `/admin/`.
