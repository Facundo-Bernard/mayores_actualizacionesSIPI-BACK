# Dossier de Introspección y Plan de Refactorización: Motor Narrativo (`/features/narrative/`)

> **Destinatario:** Agente de IA o Desarrollador encargado de la refactorización arquitectónica.  
> **Objetivo:** Desacoplar, estructurar y clarificar el motor del juego narrativo (KingsCourt) eliminando su estado de "caja negra" sin alterar ningún flujo, contrato de API ni comportamiento en tiempo de ejecución.  
> **Fecha de Elaboración:** Octubre 2026.

---

## 1. Diagnóstico Forense: ¿Por qué el código actual es una "Caja Negra"?

El módulo actual ubicado en `app/features/narrative/` contiene **3.336 líneas de código Python**, de las cuales la mitad están concentradas en un único archivo monstruoso (`service.py` con 1.593 líneas).

### Los 5 Grandes Problemas Detectados (Code Smells & Riesgos):
1. **Monolito de Servicio Todo-en-Uno (`service.py`):**
   - Agrupa en un solo archivo: CRUDs administrativos de 7 colecciones de MongoDB, generadores de seeds, el Game Loop completo de 12 meses, lógica de cálculo de fin de partida, y serializadores de respuestas HTTP.
2. **Inversión y Falsa Optimización en V2 (Wrappers Ineficientes):**
   - Los endpoints V2 ligeros (`iniciar_partida_v2`, `elegir_carta_mes_v2`, etc.) fueron implementados como un envoltorio que **ejecuta el método V1 completo**, el cual llama a `_construir_estado_respuesta()`.
   - `_construir_estado_respuesta()` realiza múltiples consultas complejas a MongoDB (corte, inventario, historial, eventos, resultados), y luego la función V2 **descarta el 90% de los datos** para retornar un delta pequeño. El backend sigue haciendo el trabajo pesado de V1 innecesariamente.
3. **Bloat en `schemas.py` (433 líneas, 45 clases Pydantic):**
   - En un solo archivo coexisten: DTOs de creación de catálogo, reglas ECA (Evento-Condición-Acción), estructuras internas de sesión en MongoDB, respuestas V1 gigantes y esquemas delta V2.
4. **Acoplamiento Directo con MongoDB en la Lógica de Negocio:**
   - No existe capa de repositorios. Cada función de negocio hace `db["narrative_runs"].find_one(...)`, `replace_one(...)`, `to_list(None)`, mezclando mutación de estado del juego con I/O de base de datos.
5. **Inconsistencias Legacy Silenciosas:**
   - Se detectó que en `_construir_estado_respuesta()`, el campo `epilogo_final` se dejó hardcodeado en `None` en favor de `finalizacion`, lo que hace fallar las suites de integración históricas (`tests/test_narrative_game.py`).

---

## 2. Inventario de Archivos Actuales y Responsabilidades

| Archivo | Líneas | Responsabilidad Actual | Problemas / Deuda Técnica |
| :--- | :---: | :--- | :--- |
| `service.py` | 1.593 | **El Monolito:** CRUDs de catálogo, sembrado de datos, Game Loop, cálculo de finalizaciones y adaptadores V2. | Extremadamente difícil de navegar, mezcla capas de datos, negocio y presentación. |
| `schemas.py` | 433 | **Catálogo de Tipos:** Contiene 45 modelos Pydantic (Reglas, Catálogo, Estado Run, V1, V2). | Falta de modularización por contexto/dominio. |
| `admin_router.py` | 552 | **Endpoints de Administración:** CRUDs para universos, personajes, cartas, eventos, resultados, conversaciones y finalizaciones. | Funcional pero altamente acoplado a funciones sueltas de `service.py`. |
| `router.py` | 288 | **Router V1 Legacy & Consultas On-Demand:** Contiene los endpoints históricos y los endpoints de modales (`/corte`, `/inventario`, `/historial`, `/setup`). | Mezcla rutas deprecadas de juego con endpoints útiles de consulta bajo demanda. |
| `router_v2.py` | 110 | **Router V2 Ligero:** Los 5 endpoints del Game Loop delta (`/iniciar`, `/elegir-carta-mes`, `/decidir-evento`, `/responder-conversacion`, `/avanzar-mes`) y `/estado`. | Es el router activo que consume el frontend actual. |
| `rule_engine.py` | 157 | **Motor de Reglas ECA:** Evalúa condiciones (`COMPARAR_RECURSO`, `TIENE_TAG`, etc.) y despacha acciones sobre el estado de la partida con clamping de límites. | Código puro y limpio, pero acoplado a dicts mutables. |
| `event_director.py` | 177 | **Director de Eventos:** Selección aleatoria ponderada de eventos del mes según tags de corte, inventario y recursos en crisis; cálculo de opciones y desenlaces. | Buena lógica algorítmica; requiere desacople de imports circulares con `rule_engine`. |
| `enums.py` | 59 | **Enumeraciones:** `RunPhaseEnum`, `DisparadorEnum`, `OperadorEnum`, `TipoCondicionEnum`, `TipoAccionEnum`, etc. | Muy claro y autocontenido. |
| `__init__.py` | 1 | Archivo de inicialización de paquete. | Vacío. |

---

## 3. Invariantes Críticas y Reglas Intocables (Lo que DEBE mantenerse idéntico)

> [!CAUTION]
> Cualquier modificación sobre los siguientes puntos alterará el flujo del juego, romperá la comunicación con el Frontend o corromperá partidas en MongoDB.

### 3.1. Validaciones y Restricciones de Entrada
1. **Selección Inicial de Corte y Cartas:**
   - La partida **exige exactamente 3 personajes** (`len(req.corte_elegida_ids) == 3`) y **exactamente 3 cartas** (`len(req.cartas_iniciales_ids) == 3`). Si no se cumple, debe responder HTTP 400.
   - Cada personaje y carta elegidos deben pertenecer a los arrays `daily_challenges.config.setup_corte_ofrecidos_ids` y `daily_challenges.config.setup_cartas_ofrecidas_ids` del día.
2. **Draft Mensual:**
   - Al iniciar la partida (Mes 1) y al avanzar cada mes (Mes 2 al 12), el backend toma 3 cartas aleatorias de `daily_challenges.config.pool_cartas_mensuales_ids` y las deposita en `run.turno_actual.cartas_ofrecidas_ids`.

### 3.2. Máquina de Estados del Turno (`RunPhaseEnum`)
El ciclo del mes sigue una secuencia estricta de fases:
```text
[Inicio Mes] -> DRAFT_MENSUAL
     │
     ▼ (POST /elegir-carta-mes)
TOMA_DECISION_EVENTO
     │
     ▼ (POST /decidir-evento)
     ├── Si recurso <= 0: FINALIZADA (status: "game_over", derrota)
     ├── Si se activó conversación incidental: RESOLVER_CONVERSACION
     │         │
     │         ▼ (POST /responder-conversacion)
     │    BALANCE_MES
     └── Si NO hubo conversación: BALANCE_MES
               │
               ▼ (POST /avanzar-mes)
          ├── Si mes_actual > 12: FINALIZADA (status: "completed", victoria)
          └── Si mes_actual <= 12: DRAFT_MENSUAL (Mes siguiente)
```

### 3.3. Algoritmo del Director de Eventos (`event_director.py`)
La función `seleccionar_evento_mes` debe preservar su fórmula exacta de selección ponderada:
* `peso_base` inicial del evento (por defecto `100.0`).
* **Sinergia Corte:** Multiplica por `2.0` si comparte tags con los personajes activos de la corte.
* **Sinergia Cartas:** Multiplica por `2.5` si comparte tags con las cartas en mano del jugador.
* **Urgencia por Crisis:** Multiplica por `3.0` si algún recurso del jugador es `< 25.0` y el evento tiene ese recurso como tag temático.
* Los eventos ya jugados (`eventos_jugados`) se excluyen, a menos que se hayan agotado todos los del pool (en cuyo caso se reciclan).

### 3.4. Reglas ECA y Clamping de Recursos (`rule_engine.py`)
1. **Disparadores:**
   - `al_obtener`: Se despacha al inicio para la corte y cartas iniciales, y cada vez que se agrega una carta en `/elegir-carta-mes`.
   - `cada_mes`: Se despacha en `/avanzar-mes` para todas las cartas activas en `run.cartas_en_mano`.
2. **Límites de Recursos:**
   - Al ejecutar `MODIFICAR_RECURSO`, el nuevo valor numérico debe ajustarse obligatoriamente con el rango `[min, max]` definido en `narrative_universes.recursos_config`:
     $$\text{nuevo\_valor} = \max(\text{min}, \min(\text{max}, \text{redondear}(\text{valor\_actual} + \text{delta})))$$
3. **Límites de Afinidad:**
   - La afinidad con personajes de la corte se ajusta siempre en el rango `[0, 100]`.

### 3.5. Nombres Exactos de Colecciones en MongoDB
El nuevo código no debe renombrar ni cambiar la semántica de las colecciones:
* `narrative_settings` $\rightarrow$ Universos y recursos base.
* `narrative_characters` $\rightarrow$ Personajes de la corte.
* `narrative_cards` $\rightarrow$ Cartas y objetos.
* `narrative_results` $\rightarrow$ Resultados y consecuencias.
* `narrative_events` $\rightarrow$ Eventos mensuales y opciones.
* `narrative_conversations` $\rightarrow$ Conversaciones incidentales entre consejeros.
* `narrative_endings` $\rightarrow$ Finalizaciones (Endings) de victoria y derrotas.
* `narrative_runs` $\rightarrow$ Documento vivo de partida del jugador.
* `daily_challenges` $\rightarrow$ Configuración del día (`game_id="narrativo"`).
* `user_attempts` $\rightarrow$ Registro de completitud diaria sincronizado al terminar.

### 3.6. Contratos de API V2 (Deltas requeridos por Frontend)
El Frontend espera las siguientes respuestas exactas:
* `POST /api/narrative/v2/partida/iniciar` $\rightarrow$ `IniciarPartidaV2Response` (`mes_actual`, `fase_actual`, `recursos`, `afinidad`, `cartas_draft_actual`).
* `POST /api/narrative/v2/partida/elegir-carta-mes` $\rightarrow$ `ElegirCartaMesV2Response` (`fase_actual`, `recursos`, `evento_actual`).
* `POST /api/narrative/v2/partida/decidir-evento` $\rightarrow$ `DecidirEventoV2Response` (`fase_actual`, `recursos`, `resultado_actual`, `conversacion_actual`, `finalizacion`).
* `POST /api/narrative/v2/partida/responder-conversacion` $\rightarrow$ `ResponderConversacionV2Response` (`fase_actual`, `afinidad`, `resultado_texto`, `impacto_afinidad`).
* `POST /api/narrative/v2/partida/avanzar-mes` $\rightarrow$ `AvanzarMesV2Response` (`mes_actual`, `fase_actual`, `status`, `recursos`, `cartas_draft_actual`, `finalizacion`).
* `GET /api/narrative/v2/partida/estado` $\rightarrow$ `EstadoTurnoResponse` (para restauración tras recarga F5).

### 3.7. Punto de Entrada en `main.py`
En `app/main.py` existen integraciones fijas que no deben romperse:
```python
from app.features.narrative.router import router as narrative_router
from app.features.narrative.router_v2 import router_v2 as narrative_v2_router
from app.features.narrative.admin_router import admin_router as narrative_admin_router
from app.features.narrative.service import sembrar_finalizaciones_default
```

---

## 4. Propuesta de Nueva Estructura Modular

Proponemos una arquitectura en capas limpia, modular y desacoplada:

```text
app/features/narrative/
│
├── domain/                         # MODELO DE DOMINIO Y DTOs
│   ├── __init__.py
│   ├── enums.py                    # Enums (RunPhaseEnum, DisparadorEnum, etc.)
│   └── schemas/
│       ├── __init__.py             # Exporta todos los schemas para compatibilidad
│       ├── rules.py                # CondicionSchema, AccionSchema, EfectoSchema
│       ├── catalog.py              # DTOs de Universos, Personajes, Cartas, Eventos, Endings
│       ├── run.py                  # NarrativeRunSchema, TurnoSnapshot, HistorialMes
│       ├── requests.py             # IniciarPartidaRequest, ElegirCartaMesRequest, etc.
│       ├── responses_v1.py         # EstadoPartidaActivaResponse, SetupDesafioResponse
│       └── responses_v2.py         # IniciarPartidaV2Response, etc. (Deltas ligeros)
│
├── engine/                         # MOTORES PUROS DE JUEGO (Sin dependencias de I/O)
│   ├── __init__.py
│   ├── rule_engine.py              # Evaluación de condiciones y ejecución de acciones ECA
│   └── event_director.py           # Algoritmo de selección ponderada y cálculo de probabilidades
│
├── repositories/                   # PERSISTENCIA (Acceso a MongoDB)
│   ├── __init__.py
│   ├── catalog_repository.py       # Lecturas/escrituras de colecciones estáticas
│   ├── challenge_repository.py     # Acceso a daily_challenges y user_attempts
│   └── run_repository.py           # CRUD y operaciones atómicas sobre narrative_runs
│
├── services/                       # CASOS DE USO / LÓGICA DE APLICACIÓN
│   ├── __init__.py
│   ├── game_service.py             # Orquestación del Game Loop V2 (Rápido, sin sobrecarga V1)
│   ├── query_service.py            # Consultas on-demand (setup, corte, inventario, historial)
│   ├── admin_catalog_service.py    # CRUDs y lógica de administración para admin_router
│   └── seeder_service.py           # sembrar_finalizaciones_default() y generadores de seeds
│
├── routers/                        # CONTROLADORES FASTAPI (Capa de Transporte)
│   ├── __init__.py
│   ├── router_v2.py                # Router principal activo (/api/narrative/v2/partida)
│   ├── router_queries.py           # Endpoints de soporte bajo demanda (/api/narrative/partida/*)
│   └── admin_router.py             # Endpoints administrativos (/api/narrative/admin/*)
│
├── service.py                      # FACHADA DE RETROCOMPATIBILIDAD (Re-exporta funciones)
├── schemas.py                      # FACHADA DE RETROCOMPATIBILIDAD (Re-exporta schemas)
└── __init__.py                     # Re-exporta routers y servicios raíz
```

---

## 5. Plan de Ejecución Paso a Paso para la IA Refactorizadora

Para garantizar **cero regresiones** y mantener la aplicación funcionando en cada commit:

### Paso 1: Modularización de Dominio (`domain/`)
- Mover `enums.py` a `domain/enums.py`.
- Dividir `schemas.py` en la carpeta `domain/schemas/`.
- Dejar en la raíz `app/features/narrative/schemas.py` importando todo desde `domain/schemas/` para que ningún archivo externo sufra rupturas.

### Paso 2: Modularización de Motores de Juego (`engine/`)
- Reubicar `rule_engine.py` y `event_director.py` dentro de `engine/`.
- Verificar que no tengan imports circulares y que reciban dicts o modelos de dominio puros.

### Paso 3: Creación de la Capa de Repositorios (`repositories/`)
- Extraer las consultas de base de datos a `catalog_repository.py`, `challenge_repository.py` y `run_repository.py`.
- Centralizar nombres de colecciones (`COLL_*`) en un solo archivo de configuración o constantes de repositorio.

### Paso 4: Desacoplamiento de Servicios (`services/`)
- Separar `service.py` en:
  1. `admin_catalog_service.py` (CRUDs).
  2. `game_service.py` (Lógica del Game Loop V2 nativa, optimizada para persistir en `narrative_runs` y retornar deltas inmediatamente sin llamar a `_construir_estado_respuesta`).
  3. `query_service.py` (Endpoints de modales: corte, inventario, historial, setup).
  4. `seeder_service.py` (`sembrar_finalizaciones_default`).
- Mantener `app/features/narrative/service.py` como un módulo fachada que re-exporta todas las firmas anteriores.

### Paso 5: Reubicación de Routers y Verificación Final
- Mover routers a `routers/`.
- Corregir en `query_service.py` el campo `finalizacion` vs `epilogo_final` para que el test suite de integración pase al 100%.
- Ejecutar:
  ```bash
  python -m pytest tests/test_narrative_game.py
  ```
- Probar el flujo completo en `http://localhost:5173/test_narrativo.html`.
