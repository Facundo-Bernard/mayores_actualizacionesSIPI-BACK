# Narrativo V1 y V2 — contexto para la refactorización

> **Alcance:** motores narrativos V1 (eventos planos) y V2 (grafo), panel admin, seeds, estado de partida y su relación con la economía.
> **Base analizada:** commit `d2a117b` (30/10/2026).
> **Método:** lectura completa de `app/features/narrative/**`, `app/scripts/seed_narrative*.py`, documentación interna y revisión del commit `832563c`.
> **Estado:** análisis estático. No se ejecutó la app contra MongoDB ni se modificó código.

> **Errata (2/11/2026):** diferencias verificadas contra el código actual en [05-plan-solucion.md §2](05-plan-solucion.md). Este documento se conserva como foto original del relevamiento.
> **Audiencia:** desarrolladores que se incorporan al backend y van a refactorizar sin romper el frontend.

---

## 0. Cómo usar este documento

1. Las secciones 1 a 3 explican los dos motores y desarman la ambigüedad de nombres.
2. Las secciones 4 y 5 son el contrato HTTP y el modelo de datos.
3. Las secciones 6 y 7 describen el flujo de una partida en cada motor.
4. La sección 8 explica cómo conviven y cómo se elige el motor.
5. La sección 9 contrasta **comportamiento actual vs. esperado**.
6. La sección 10 lista defectos con archivo:línea.
7. Las secciones 11 a 13 fijan reglas, plan de refactor y tests.

Documentos hermanos:

- [Juegos clásicos](01-juegos-clasicos.md)
- [Economía, puntos y vidas](03-economia-puntos-vidas.md)
- [Testing](04-testing.md)

---

## 1. Resumen ejecutivo

- **No existen dos routers separados.** El router `/api/narrative/v2/partida` sirve tanto al motor V1 como al motor de grafos V2. La elección se hace por `run.motor` dentro de `elegir_carta_mes_v2` (`app/features/narrative/game/turn_service.py:112-138`).
- “V2” designa tres cosas distintas: el **contrato HTTP liviano** (`*V2Response`), el **router** `/api/narrative/v2/partida` y el **motor de grafos**. Esto explica gran parte de la confusión documental.
- El motor se elige **por universo**, no por desafío: se lee `narrative_settings.motor` al crear la run y se guarda en `run.motor` (`setup_service.py:149-150,189`). El default es `"v1"` (`schemas/catalog_schemas.py:32`).
- **V2 no está sembrado ni habilitado por defecto.** `main.py` siembra V1 y finalizaciones, pero nunca `seed_narrative_v2_graphs.py` (`app/main.py:49-67`). El seed V1 se ejecuta en cada arranque y reescribe el universo con `motor="v1"` (`seed_narrative.py:60-72`).
- **V2 no puede completar 12 meses con el contenido sembrado:** hay 7 eventos V2 y el sorteo no recicla eventos jugados (`graph_engine.py:105-147`). Al agotarse, `elegir-carta-mes` responde 500.
- Los endpoints manuales `iniciar-evento-grafo` e `iniciar-conversacion-grafo` **no validan fase, estado ni `grafo_activo`** (`v2_graph_service.py:84-129`). Permiten saltar meses, repetir eventos, farmear recursos y revivir partidas finalizadas.
- La autenticación del jugador es opcional: `_get_current_user_id` devuelve `0` ante ausencia o invalidez de token (`game/router.py:74-86`). Todos los invitados comparten `run_0_<fecha>`.
- **No hay validador estructural de grafos** ni el endpoint `/v2/simular` que documenta la spec. Un grafo con raíz inexistente, punteros rotos o pesos 0 produce 500 o soft-lock.
- **No hay control de concurrencia ni transacciones:** todas las mutaciones son `find_one` → mutar dict → `replace_one`.
- **El narrativo está fuera de la economía:** no otorga puntos, no consume vidas y no verifica suscripción ni desbloqueo. Escribe `user_attempts` con escala 1000/850/700/500/250, incompatible con 100/90/75/50/0.
- Los assets y la documentación están desalineados: 52 de 57 rutas de imagen del seed V1 no existen; la spec describe endpoints y contratos que no existen.

---

## 2. Glosario: desarmar “V1”, “V2” y “V2 ligero”

| Término | Qué es | Dónde vive |
|---|---|---|
| **V1** | Motor de eventos planos: evento → opciones → resultado externo; conversaciones planas con frases y decisiones. | `engine/event_director.py`, `engine/rule_engine.py`, `turn_service.py`, `transition_service.py` |
| **V2 (motor)** | Motor de grafos: evento/conversación autocontenido con `nodo_raiz` y `nodos{}`; aristas implícitas; impactos inline. | `engine/graph_engine.py`, `game/v2_graph_service.py` |
| **V2 ligero (contrato)** | DTOs de respuesta con deltas (`IniciarPartidaV2Response`, `ElegirCartaMesV2Response`, etc.). Lo usan **ambos** motores. | `schemas/game_schemas.py` |
| **Router V2** | Prefijo `/api/narrative/v2/partida` para el loop de juego. No implica motor V2. | `game/router.py:92-216` |
| **Run** | Documento de partida en `narrative_runs`; guarda recursos, afinidad, cartas, fase, turno, historial y motor. | `setup_service.py:183-209` |
| **Universo** | Configuración del mundo en `narrative_settings`: recursos, imágenes y `motor`. | `schemas/catalog_schemas.py:18-46` |
| **Corte** | Los 3 personajes elegidos al iniciar. Se infiere de las claves de `afinidad`. | `setup_service.py:153-181` |
| **Draft** | Oferta mensual de 3 cartas; el jugador elige 1. | `setup_service.py:236-240` |
| **Fase** | Estado de la máquina: `DRAFT_MENSUAL`, `TOMA_DECISION_EVENTO`, `RESOLVER_CONVERSACION`, `BALANCE_MES`, `FINALIZADA`. | `enums.py:35-42` |
| **Nodo** | Unidad de un grafo V2: texto, hablante, opciones y/o impactos terminales. | `schemas/v2_graph_schemas.py:46-56` |
| **Opción** | Elección dentro de un nodo; puede tener `siguiente_nodo`, `desenlaces` ponderados y condiciones. | `v2_graph_schemas.py:20-38` |
| **Desenlace** | Par `(nodo, peso)` que resuelve el siguiente nodo de forma aleatoria. | `v2_graph_schemas.py:16-18` |
| **Impacto** | Cambio terminal de recursos, afinidad o tags aplicado al llegar a un nodo final. | `v2_graph_schemas.py:36-44` |
| **Afinidad** | Mapa `personaje_id → 0..100`; los cruces de 95/15 disparan eventos especiales. | `graph_engine.py:245-264` |
| **Tags** | Etiquetas activas de la run; se usan en condiciones y sinergias. | `graph_engine.py:442-445` |
| **Recursos** | `oro`, `pueblo`, `ejercito`, `fe` en el universo seed; si uno llega a ≤0, derrota. | `seed_narrative.py:65-70`, `endings_service.py:24-37` |
| **Finalización** | Victoria (mes 12) o derrota por recurso; se sincroniza a `user_attempts`. | `endings_service.py` |

### Aclaración crucial

Un desafío con `motor="v1"` también responde `IniciarPartidaV2Response`, `ElegirCartaMesV2Response` y `AvanzarMesV2Response`. **“V2” en el nombre del DTO no significa motor de grafos.** El único discriminador real es `run.motor == "v2"`.

---

## 3. Mapa de módulos

### 3.1 Archivos y responsabilidades

| Archivo | Rol |
|---|---|
| `engine/rule_engine.py` | ECA puro: evalúa condiciones, ejecuta acciones y despacha efectos. |
| `engine/event_director.py` | Selección ponderada de eventos V1, cálculo de opciones/probabilidades y sorteo de resultados. |
| `engine/graph_engine.py` | Motor V2: sorteo de eventos/conversaciones, inicio, avance, impactos, especiales y conversación incidental. |
| `game/router.py` | Routers de jugador: loop V2 ligero, grafos, setup, reinicio y modales. |
| `game/setup_service.py` | Setup del día, caché de recursos, reset, creación de run y draft inicial. |
| `game/turn_service.py` | Fases 1-3: draft/evento V1, decisión V1 y conversación V1; bifurcación V2. |
| `game/transition_service.py` | Fase 4: historial, pasivos `cada_mes`, victoria/derrota y nuevo draft. |
| `game/modals_service.py` | Historial, inventario, corte, finalización, estado y modales actuales. |
| `game/endings_service.py` | Colapso por recurso, victoria y sincronización con `user_attempts`. |
| `game/v2_graph_service.py` | Orquestación delgada V2: estado del grafo, avance y arranques manuales. |
| `schemas/rules_schemas.py` | `CondicionSchema`, `AccionSchema`, `EfectoSchema`. |
| `schemas/catalog_schemas.py` | Universos, personajes, cartas, resultados, eventos V1, conversaciones V1, finalizaciones. |
| `schemas/game_schemas.py` | Config de desafío, run, requests, respuestas V1 y deltas V2. |
| `schemas/v2_graph_schemas.py` | Nodos, opciones, desenlaces, impactos, grafos V2 y DTOs. |
| `admin/router.py` | 44 endpoints admin: catálogo, imágenes, CRUD V1, CRUD V2, generador mensual y finales. |
| `admin/crud_service.py` | CRUD genérico con `replace_one`, sin validación referencial ni semántica. |
| `admin/challenge_service.py` | Generación procedural de `daily_challenges` y siembra de finalizaciones. |
| `admin/image_service.py` | Decodifica JPG/PNG, redimensiona y guarda WebP en `app/static/narrative/{categoria}`. |
| `app/scripts/seed_narrative.py` | Seed V1: 1 universo, 5 personajes, 10 cartas, 15 resultados, 12 eventos, 16 conversaciones y desafíos del mes. |
| `app/scripts/seed_narrative_v2_graphs.py` | Seed V2: 7 eventos, 6 conversaciones y 10 eventos especiales. No toca V1 ni configura el motor. |

### 3.2 Grafo de dependencias

```text
game/router.py
 ├─ setup_service ──> Mongo, catálogo, rule_engine, endings_service
 ├─ turn_service
 │   ├─ event_director (V1)
 │   ├─ graph_engine (V2)
 │   ├─ rule_engine
 │   └─ endings_service
 ├─ transition_service ──> rule_engine, endings_service
 ├─ modals_service ──> Mongo, v2_graph_service
 └─ v2_graph_service ──> graph_engine

admin/router.py
 ├─ crud_service
 ├─ challenge_service
 └─ image_service
```

### 3.3 Qué comparten V1 y V2

| Componente | V1 | V2 | Compartido |
|---|---|---|---|
| `narrative_runs` | Sí | Sí | Sí |
| Personajes y cartas | Sí | Sí | Sí |
| Draft mensual y pasivos | Sí | Sí | Sí |
| Condiciones ECA | `rule_engine` | `rule_engine` | Sí |
| Resultados | `narrative_results` | Inline en nodo terminal | No |
| Conversaciones | Planas | Grafo | No |
| Eventos | `narrative_events` | `narrative_v2_events` | No |
| Selección de evento | `event_director` | `graph_engine` | No, lógica duplicada |
| Probabilidades | Expuestas | Ocultas | No |
| Eventos especiales | No existen | `narrative_v2_eventos_especiales` | No |
| Finales | `narrative_endings` + victoria hardcodeada | Igual | Sí |
| Administración | CRUD V1 | CRUD V2 separado | No, duplicado |
| Economía / vidas | No integrado | No integrado | Ninguno |

---

## 4. Contratos HTTP congelados

> **Regla:** no cambiar paths, métodos, campos ni códigos de estado. La refactorización debe preservar estos contratos; los cambios de comportamiento (por ejemplo, agregar guardas de fase) deben devolver errores claros sin alterar el camino feliz.

### 4.1 Autenticación y roles

- **Jugador:** `_get_current_user_id` (`game/router.py:74-86`). Sin token, token inválido o sin `id`, devuelve `0` (invitado). No valida `servicios`, `activo`, existencia del usuario ni rol.
- **Invitado compartido:** la run es `run_{user_id}_{date}`; todos los invitados comparten `run_0_<fecha>` (`setup_service.py:183-184`).
- **Admin:** router con `dependencies=[Depends(get_current_admin)]` (`admin/router.py:84-88`); exige `tipo_usuario == 2`, JWT válido, permiso de servicio, cuenta activa y perfil local.
- **Excepción:** `POST/GET /api/narrative/partida/conversaciones-posibles` no tiene auth (`game/router.py:247-273`).

### 4.2 Endpoints de jugador — loop y grafos

Prefijo: `/api/narrative/v2/partida`.

| Método | Ruta | Request | Response | Motor |
|---|---|---|---|---|
| `POST` | `/iniciar` | `IniciarPartidaRequest`: `date`, `corte_elegida_ids[3]`, `cartas_iniciales_ids[3]` | `IniciarPartidaV2Response` | Ambos |
| `POST` | `/elegir-carta-mes` | `ElegirCartaMesRequest`: `date`, `carta_id` | `ElegirCartaMesV2Response` | Ambos |
| `POST` | `/decidir-evento` | `DecidirEventoRequest`: `date`, `opcion_id` | `DecidirEventoV2Response` | Solo V1 |
| `POST` | `/responder-conversacion` | `ResponderConversacionRequest`: `date`, `opcion_numero` | `ResponderConversacionV2Response` | Solo V1 |
| `POST` | `/avanzar-mes` | `AvanzarMesRequest`: `date` | `AvanzarMesV2Response` | Ambos |
| `GET` | `/estado?date=` | — | `EstadoTurnoResponse` (incluye `grafo_actual`) | Ambos |
| `POST` | `/avanzar-nodo` | `AvanzarNodoV2Request`: `date`, `opcion_id` | `EstadoGrafoV2Response` | V2 |
| `GET` | `/grafo-actual?date=` | — | `EstadoGrafoV2Response?` | V2 |
| `POST` | `/iniciar-evento-grafo?date=` | — | `EstadoGrafoV2Response` | V2, **sin guardas de fase** |
| `POST` | `/iniciar-conversacion-grafo?date=` | — | `EstadoGrafoV2Response?` | V2, **sin guardas de fase** |

Referencias: rutas en `game/router.py:94-216`; DTOs en `schemas/game_schemas.py:89-114,201-236` y `schemas/v2_graph_schemas.py:209-223`.

### 4.3 Endpoints de jugador — setup y modales

Prefijo: `/api/narrative/partida`.

| Método | Ruta | Request/Query | Response |
|---|---|---|---|
| `GET` | `/setup` | `date` | `SetupDesafioResponse` |
| `POST` | `/reiniciar` | `ReiniciarPartidaRequest` | `{success, message, eliminada}` |
| `POST` | `/conversaciones-posibles` | `ConversacionesPosiblesRequest` | `List[ConversacionResponse]` (público) |
| `GET` | `/conversaciones-posibles` | `personajes_ids`, `universo_id?` | `List[ConversacionResponse]` (público) |
| `GET` | `/historial` | `date` | `HistorialPartidaResponse` |
| `GET` | `/inventario` | `date` | `InventarioPartidaResponse` |
| `GET` | `/corte` | `date` | `CortePartidaResponse` |
| `GET` | `/finalizacion` | `date` | `FinalizacionPartidaResponse` |
| `GET` | `/evento-actual` | `date` | `EventoTurnoResponse?` |
| `GET` | `/conversacion-actual` | `date` | `ConversacionResponse?` |
| `GET` | `/resultado-actual` | `date` | `ResultadoResponse?` |
| `GET` | `/draft-actual` | `date` | `List[CartaResponse]` |

### 4.4 Endpoints admin — `/api/narrative/admin`

Todos con `get_current_admin`.

| Grupo | Rutas |
|---|---|
| Catálogo de reglas | `GET /catalogo-reglas` |
| Imágenes | `POST /upload-imagen?categoria=` |
| Universos | `GET/POST /universos`, `GET/DELETE /universos/{id}` |
| Personajes | `GET/POST /personajes`, `GET/DELETE /personajes/{id}` |
| Cartas | `GET/POST /cartas`, `GET/DELETE /cartas/{id}` |
| Resultados | `GET/POST /resultados`, `GET/DELETE /resultados/{id}` |
| Eventos V1 | `GET/POST /eventos`, `GET/DELETE /eventos/{id}` |
| Conversaciones V1 | `GET/POST /conversaciones`, `GET/DELETE /conversaciones/{id}` |
| Finalizaciones | `GET/POST /finalizaciones`, `GET/DELETE /finalizaciones/{id}` |
| Siembra de finales | `POST /universos/{id}/sembrar-finalizaciones` |
| Generador mensual | `POST /generar-mes` |
| Eventos V2 | `GET/POST /v2/eventos`, `GET/DELETE /v2/eventos/{id}` |
| Conversaciones V2 | `GET/POST /v2/conversaciones`, `GET/DELETE /v2/conversaciones/{id}` |
| Eventos especiales V2 | `GET/POST /v2/eventos-especiales`, `GET/DELETE /v2/eventos-especiales/{id}` |

### 4.5 Endpoints documentados que NO existen

| Documentación | Dice | Realidad |
|---|---|---|
| `docs_interna/ARQUITECTURA_JUEGOS_Y_NARRATIVO.md:187-188` | Endpoints legacy V1 ocultos (`/iniciar`, `/activa`, `/turno`, etc.) | No existen; el loop está en `/api/narrative/v2/partida`. |
| `docs/DEFINICIONES_POST_JUEGO_NARRATIVO.md` y `narrative_endpoints_post_specs.json` | `POST /api/narrative/partida/iniciar`, `/elegir-carta-mes`, `/decidir-evento`, `/responder-conversacion`, `/avanzar-mes` | Esos paths devuelven 404; los reales están bajo `/api/narrative/v2/partida`. |
| `docs/DOCUMENTACION_ENDPOINTS_MOTOR_GRAFOS_V2.md:873-915` | `POST /api/narrative/admin/v2/simular` valida grafos | No existe ruta ni validador. |
| Varias docs | Publicación/draft/preview | No hay campo `publicado` ni endpoints de publicación. |

### 4.6 Inconsistencias de contrato

- Fases reales en mayúsculas: `DRAFT_MENSUAL`, `TOMA_DECISION_EVENTO`, `RESOLVER_CONVERSACION`, `BALANCE_MES`, `FINALIZADA` (`enums.py:35-42`). La documentación usa minúsculas o nombres inexistentes.
- `status` real de la run: `in_progress`, `completed`, `game_over`. La documentación V2 muestra `CONTINUA`, `VICTORIA`, `DERROTA`.
- `GET /estado` y los modales siguen `EstadoTurnoResponse`, no `EstadoPartidaActivaResponse`.

---

## 5. Modelo de datos

### 5.1 Colecciones e índices

| Colección | Uso | Índices |
|---|---|---|
| `narrative_settings` | Universos y definición de recursos (`_id`, nombre, descripción, icono, imagen, `motor`, `recursos[]`). | `_id` |
| `narrative_characters` | Personajes: tags, afinidad inicial, efectos, metadata de conversaciones. | `universo_id` |
| `narrative_cards` | Cartas: categoría, tags, efectos. | `universo_id` |
| `narrative_events` | Eventos V1: opciones → resultados. | `universo_id` |
| `narrative_results` | Resultados V1: efectos e impacto de afinidad. | `universo_id` |
| `narrative_conversations` | Conversaciones V1 planas. | `universo_id` |
| `narrative_endings` | Derrotas por recurso; la victoria no se guarda acá. | `universo_id + recurso_clave` (no único) |
| `narrative_runs` | Estado vivo de la partida. | único `(user_id, date, game_id)`; `(user_id, date)` |
| `daily_challenges` | Desafío del día (`game_id="narrativo"`). | único `(game_id, date, difficulty)` |
| `user_attempts` | Intento diario. | único `(user_id, game_id, date)` |
| `narrative_v2_events` | Grafos de eventos V2. | **sin índice** |
| `narrative_v2_conversations` | Grafos de conversaciones V2. | **sin índice** |
| `narrative_v2_eventos_especiales` | Grafos de lealtad/traición. | **sin índice** |

### 5.2 Esquema V1

- **Universo** (`catalog_schemas.py:18-46`): `_id`, `nombre`, `descripcion`, `icono`, `imagen`, `motor` (`v1`/`v2`, default `v1`), `recursos[]` (`clave`, `nombre`, `icono`, `min`, `max`, `inicial`).
- **Personaje** (`catalog_schemas.py:56-73`): `_id`, `universo_id`, `nombre`, `titulo`, `imagen`, `descripcion`, `pros`, `cons`, `tags`, `afinidad_inicial`, `efectos[]`, `conversaciones[]`.
- **Carta** (`catalog_schemas.py:79-92`): `_id`, `universo_id`, `categoria` (`item|bonus|personaje`), `nombre`, `descripcion`, `imagen`, `tags`, `efectos[]`.
- **Resultado** (`catalog_schemas.py:102-115`): `_id`, `universo_id`, `titulo`, `texto`, `imagen`, `tipo_resultado`, `efectos[]`, `impacto_afinidad[]`.
- **Evento** (`catalog_schemas.py:138-151`): `_id`, `universo_id`, `titulo`, `descripcion`, `imagen`, `tags_tematicos`, `peso_base`, `opciones[]`; cada opción tiene `id`, `texto`, `es_secreta`, `condiciones[]`, `resultados_posibles[]`; cada resultado posible tiene `resultado_id`, `peso_base`, `modificadores_probabilidad[]`.
- **Conversación** (`catalog_schemas.py:171-183`): `_id`, `universo_id`, `titulo`, `requisitos[]`, `imagen`, `frases[]`, `decisiones[]` (cada decisión tiene `opcion`, `texto`, `condiciones[]`, `resultado_texto`, `impacto_afinidad[]`).
- **Finalización** (`catalog_schemas.py:189-202`): `_id`, `universo_id`, `recurso_clave?`, `tipo`, `titulo`, `texto`, `imagen`, `rango`.

### 5.3 Esquema V2

- **Evento V2** (`v2_graph_schemas.py:151-173`): `_id`, `universo_id`, `titulo`, `imagen`, `peso_base`, `tags_tematicos`, `requisitos_eventos_previos[]`, `requisitos_personajes[]`, `condiciones_disparo[]`, `nodo_raiz`, `nodos{}`.
- **Conversación V2** (`v2_graph_schemas.py:175-191`): `_id`, `universo_id`, `titulo`, `imagen`, `requisitos[]`, `condiciones_disparo[]`, `nodo_raiz`, `nodos{}`.
- **Evento especial V2** (`v2_graph_schemas.py:193-203`): `_id`, `universo_id`, `personaje_id`, `direccion` (`lealtad|traicion`), `titulo`, `imagen`, `nodo_raiz`, `nodos{}`.
- **Nodo** (`v2_graph_schemas.py:46-56`): `id`, `hablante_id` (`narrador` o `pj_*`), `texto`, `imagen?`, `es_final`, `opciones[]`, `resultado_texto`, `impactos_recursos[]`, `impactos_afinidad[]`, `impactos_tags[]`.
- **Opción** (`v2_graph_schemas.py:20-38`): `id`, `texto`, `siguiente_nodo?`, `desenlaces[{nodo,peso}]`, `condiciones[]`, `bloqueo_modo` (`deshabilitada|oculta`, string libre).
- **Aristas:** no hay colección. Se derivan de `opciones[].siguiente_nodo` y `opciones[].desenlaces[].nodo`.
- **Estado del grafo en la run:** `run.grafo_activo = {tipo, grafo_id, nodo_actual_id}`.
- **Tags:** `run.tags_activos[]`; se otorgan desde cartas/efectos y desde `impactos_tags` terminales. **No hay finales por tags.**
- **Afinidad:** `run.afinidad{personaje_id:int}`; clamp 0-100.

### 5.4 Run, challenge y attempts

**Run** (`setup_service.py:183-209`): `_id`, `user_id`, `date`, `game_id`, `universo_id`, `motor`, `mes_actual`, `fase_actual`, `status`, `recursos`, `afinidad`, `cartas_en_mano`, `tags_activos`, `turno_actual`, `eventos_jugados`, `conversaciones_jugadas`, `historial_mensual`, `updated_at`.

Campos V2 **no modelados** en `NarrativeRunSchema` (`game_schemas.py:55-83`): `grafo_activo`, `especiales_pendientes`, `eventos_especiales_jugados`, `motor`. El schema no se usa para validar documentos en reposo.

**Daily challenge narrativo:** `game_id="narrativo"`, `difficulty="normal"`, `config` con `universo_id`, `atributos_iniciales`, `setup_corte_ofrecidos_ids`, `setup_cartas_ofrecidas_ids`, `pool_cartas_mensuales_ids`, `pool_eventos_disponibles_ids`, `pool_conversaciones_ids`. `NarrativeDailyChallengeConfig` no se usa para validar y sus nombres no coinciden con el documento (`titulo`/`descripcion` vs `title`/`description`). `duracion_meses` se ignora; el juego hardcodea 12.

**user_attempts:** la sync narrativa escribe `status`, `attempts` (= mes), `stars`, `score`, `game_data`; **no escribe `grade`**, `remaining_attempts` ni actualiza `usuarios.puntos` (`endings_service.py:148-170`).

### 5.5 Validaciones Pydantic: qué sí y qué no

**Sí valida:** tipos y enums; campos obligatorios; estructura básica de nodos y opciones; `nodo_raiz` y `nodos{}` obligatorios.

**No valida:**

- Longitud exacta de corte/cartas: se valida a mano solo `len(...) != 3` y pertenencia al pool (`setup_service.py:153-164`). No valida unicidad ni existencia real de documentos.
- `IniciarPartidaRequest.date` es `str` sin regex; acepta fechas futuras o pasadas.
- `afinidad_inicial` sin rango 0-100; recursos sin `min <= max` ni `inicial` en rango.
- `DesenlaceNodoSchema.peso` no exige `> 0`; `siguiente_nodo` no se valida contra `nodos`; `bloqueo_modo` es string libre.
- No hay validador de grafo: raíz existente, punteros válidos, terminales alcanzables, aciclicidad, pesos positivos, coherencia de claves.
- `CondicionSchema.valor` acepta `int|float|str`; el runtime hace `float(...)` y puede lanzar `ValueError` → 500.
- No hay validación referencial: eventos pueden apuntar a resultados inexistentes; V2 a nodos inexistentes; personajes/cartas de otro universo.
- Los response models pueden fallar con 500 si un documento viejo no cumple el schema.

### 5.6 La colisión de `ImpactoAfinidadSchema` (commit `832563c`)

Antes existían dos clases homónimas: `catalog_schemas.ImpactoAfinidadSchema` (V1) y `v2_graph_schemas.ImpactoAfinidadSchema` (V2). `schemas/__init__.py` re-exportaba primero catálogo y después V2, generando ambigüedad de identidad y en OpenAPI. El commit eliminó la clase duplicada, hizo que V2 importe la de catálogo, quitó la re-exportación y agregó descripciones. Hoy hay una sola definición (`catalog_schemas.py:98`). Deuda residual: V2 depende del catálogo V1, lo que refuerza el acoplamiento.

---

## 6. Flujo V1 paso a paso

1. **Setup.** `GET /api/narrative/partida/setup?date=...` busca `daily_challenges` (`game_id="narrativo"`, `date`), carga el universo, 5 personajes y 5 cartas, y devuelve `tiene_partida_activa` si ya existe una run (`setup_service.py:77-115`).
2. **Inicio.** `POST /api/narrative/v2/partida/iniciar` con 3 personajes y 3 cartas. Valida longitud y pertenencia al pool (`setup_service.py:153-164`). Lee `motor` del universo (`:149-150`), crea la run, aplica `al_obtener` de personajes y cartas (`:211-218`), verifica colapso (`:221-234`) y sortea 3 cartas del pool mensual (`:236-240`).
3. **Draft mensual.** `elegir-carta-mes` exige `DRAFT_MENSUAL` y que la carta esté en `cartas_ofrecidas_ids` (`turn_service.py:76-81`). Agrega la carta, suma tags y aplica `al_obtener` (`:83-95`). Verifica colapso (`:98-109`).
4. **Selección de evento V1.** Toma `pool_eventos_disponibles_ids`, carga tags de la corte y arma un mock de cartas con **todos** los `tags_activos` (`:146-150`). `seleccionar_evento_mes` excluye jugados, recicla si se agotó el pool y pondera:
   - `peso_base`;
   - ×2.0 si comparte tag con la corte;
   - ×2.5 si comparte tag con “cartas”;
   - ×3.0 si hay recurso en crisis (<25) con tag coincidente (`event_director.py:13-66`).
5. **Cálculo de opciones.** `calcular_opciones_evento` evalúa condiciones solo para opciones secretas (`bloqueada = es_secreta and not cumple`), calcula pesos con modificadores y normaliza porcentajes (`event_director.py:68-143`). La respuesta incluye **todas** las opciones, incluidas las secretas bloqueadas, con texto y probabilidades.
6. **Decisión.** `decidir-evento` exige `TOMA_DECISION_EVENTO`, busca la opción y **solo si `es_secreta`** evalúa condiciones (`turn_service.py:207-223`). Sortea el resultado, aplica efectos e impacto de afinidad (`:230-243`), verifica colapso (`:245-258`), sortea conversación incidental con 40% (`:261-278`), marca la conversación como jugada **antes** de que el jugador responda (`:282-288`) y pasa a `RESOLVER_CONVERSACION` o `BALANCE_MES`.
7. **Conversación.** `responder-conversacion` exige `RESOLVER_CONVERSACION`, busca la decisión por `opcion_numero`, aplica solo `impacto_afinidad` y pasa a `BALANCE_MES` (`:319-350`). **No evalúa `decision.condiciones`.**
8. **Balance y transición.** `avanzar-mes` exige `BALANCE_MES` (`transition_service.py:59-60`), guarda el resumen en `historial_mensual` (`:66-76`), marca el evento como jugado (`:78-81`) y:
   - si `mes_actual >= 12`, marca `completed`, calcula rango por promedio de recursos y sincroniza `user_attempts` (`:84-100`);
   - si no, incrementa `mes_actual`, aplica `cada_mes` de corte y cartas (`:103-118`), verifica colapso (`:121-134`), sortea 3 cartas nuevas y resetea `turno_actual` (`:137-151`).
9. **Modales.** `historial`, `inventario`, `corte`, `finalizacion`, `evento-actual`, `conversacion-actual`, `resultado-actual`, `draft-actual` leen la run y el catálogo (`modals_service.py:46-217`).

### 6.1 Máquina de estados V1

```text
DRAFT_MENSUAL
  └─ elegir-carta-mes → TOMA_DECISION_EVENTO
TOMA_DECISION_EVENTO
  ├─ decidir-evento (40%) → RESOLVER_CONVERSACION
  └─ decidir-evento (60%) → BALANCE_MES
RESOLVER_CONVERSACION
  └─ responder-conversacion → BALANCE_MES
BALANCE_MES
  ├─ mes < 12 → DRAFT_MENSUAL
  └─ mes >= 12 → FINALIZADA / completed
Cualquier fase con recurso <= 0 → FINALIZADA / game_over
```

### 6.2 Persistencia

- Un único documento `narrative_runs` por `(user_id, date, game_id)`.
- Cada paso hace `find_one`, muta el dict completo y `replace_one` (`turn_service.py:203-294`, `transition_service.py:154`).
- Punteros persistidos: `turno_actual.evento_actual_id`, `opcion_elegida_id`, `resultado_obtenido_id`, `conversacion_actual_id`.
- No hay versión, bloqueo optimista ni transacción.
- `user_attempts` se escribe en otro documento, fuera de la misma transacción (`endings_service.py:148-170`).

---

## 7. Flujo V2 paso a paso

1. **Creación/reset.** Igual que V1: `POST /iniciar`, `POST /reiniciar`. La run guarda `motor="v2"` si el universo lo indica. `reiniciar` borra la run sin tocar `user_attempts` ni consumir vidas (`setup_service.py:117-125`).
2. **Draft y arranque del evento.** `elegir-carta-mes` aplica la carta y, si `run.motor == "v2"`, llama `graph_engine.sortear_evento_v2` con `pool_ids=None` (`turn_service.py:112-117`). El sorteo usa **todos** los eventos del universo, filtra por `eventos_jugados`, arcos previos, personajes requeridos y `condiciones_disparo`, y pondera por corte/cartas/crisis (`graph_engine.py:55-147`). Luego fija `turno_actual.evento_actual_id`, fase `TOMA_DECISION_EVENTO` e inicia el grafo (`turn_service.py:121-130`).
3. **Selección de nodo y transición.** `POST /avanzar-nodo`:
   - exige que la partida no esté `FINALIZADA` y que exista `grafo_activo` (`v2_graph_service.py:76-82`);
   - carga el grafo según `tipo` (`evento`, `conversacion`, `evento_especial`) (`graph_engine.py:39-53`);
   - valida nodo actual, opción y condiciones (`:327-362`);
   - resuelve destino por `desenlaces` ponderados o `siguiente_nodo` (`:365-383`);
   - si el destino es intermedio, solo actualiza `nodo_actual_id` (`:392-407`);
   - si es terminal, aplica impactos, marca el grafo como jugado, limpia `grafo_activo` y evalúa el resto (`:412-527`).
4. **Impactos terminales.** Recursos con clamp según universo (`:425-431`); afinidad con clamp 0-100 (`:434-439`); tags permanentes (`:442-445`); historial de jugados (`:448-453`).
5. **Derrota.** `verificar_colapso_recursos` busca un final por `(universo_id, recurso_clave)`, genera fallback si no existe, marca `game_over`/`FINALIZADA`, persiste y sincroniza `user_attempts` (`endings_service.py:24-84`; llamada en `graph_engine.py:459-476`).
6. **Eventos especiales por afinidad.** `_detectar_cruces_afinidad` detecta cruces de 95 (lealtad) y 15 (traición) (`graph_engine.py:245-264`). Encola `especiales_pendientes` con deduplicación (`:479-485`) y `_encadenar_especial_pendiente` busca el grafo por `(universo_id, personaje_id, direccion)` e inicia el primero disponible (`:266-303`). Si no hay grafo, el ítem se descarta.
7. **Conversación incidental.** Solo tras un evento, con 40% de probabilidad, sortea una conversación V2 de **todo el universo** y la inicia en `RESOLVER_CONVERSACION` (`:493-510`).
8. **Fin del grafo.** Si no hubo especial ni conversación, pasa a `BALANCE_MES` (`:512-527`). Si fue conversación, también pasa a `BALANCE_MES` (no hay conversación anidada).
9. **Finalización.** Derrota por recurso ≤0 en cualquier terminal; victoria al llegar a `mes_actual >= 12` en `avanzar-mes` (`transition_service.py:84-100`). La victoria calcula rango por promedio de recursos y usa textos hardcodeados (`endings_service.py:86-125`).
10. **Rehidratación.** `GET /grafo-actual` devuelve el nodo actual sanitizado; `GET /estado` incluye `grafo_actual` (`v2_graph_service.py:32-68`, `modals_service.py:144-157`).

### 7.1 “Desenlaces por tags”: no implementado

Los tags se usan para:

- condiciones `tiene_tag` en opciones/disparos (`rule_engine.py:50-53`);
- sinergias de sorteo (`graph_engine.py:129-139`);
- desbloqueo de opciones ocultas.

Los finales siguen siendo por recurso ≤0 o por 12 meses. **No existe un ending seleccionado por combinación de tags.** Si el producto esperaba “desenlaces por tags”, hoy no está implementado.

### 7.2 “Validación del grafo”: no implementada

Los CRUD V2 solo hacen `replace_one` del modelo Pydantic (`crud_service.py:226-262`). Pydantic valida tipos y campos obligatorios, pero no:

- que `nodo_raiz` exista en `nodos` (runtime 500, `graph_engine.py:212-214`);
- que cada `siguiente_nodo`/`desenlaces[].nodo` exista (runtime 500, `:378-383`);
- que nodos no finales tengan opciones y finales no;
- que haya al menos un terminal alcanzable;
- que no haya ciclos;
- que los pesos sean > 0 y sumen > 0 (si todos son 0, `random.choices` lanza `ValueError`, `:365-368`);
- que la clave del dict `nodos` coincida con `nodo.id`;
- que un nodo raíz no sea final (si lo es, sus impactos nunca se aplican porque el motor solo aplica impactos del **siguiente** nodo).

El endpoint `/v2/simular` documentado no existe. Los tests sintéticos toleran grafos incompletos, lo que confirma que no hay red de seguridad.

### 7.3 Cómo se evita (y cómo no) el estado inconsistente

**Lo que ayuda:**

- `grafo_activo` se persiste antes de cada paso intermedio, lo que permite F5.
- Las opciones se revalidan en servidor.
- El cliente no recibe `siguiente_nodo` ni `desenlaces`.
- Los impactos se aplican solo al llegar a un terminal.

**Lo que no se evita:**

- **Saltos de fase:** los endpoints manuales pueden iniciar un grafo desde `DRAFT_MENSUAL`, `BALANCE_MES`, `RESOLVER_CONVERSACION` o `FINALIZADA`. En `BALANCE_MES` se puede farmear recursos/afinidad/tags sin avanzar mes; en `FINALIZADA` se “revive” la partida.
- **Reroll de eventos:** iniciar un evento y luego otro antes de terminarlo descarta el primero sin registrarlo.
- **Conversación que salta el evento:** iniciar una conversación en `DRAFT_MENSUAL` permite avanzar mes sin carta ni evento.
- **Punteros obsoletos:** al terminar un evento no se limpian `turno_actual.evento_actual_id` ni `conversacion_actual_id`; al iniciar manual no se setean.
- **Historial incompleto:** el motor V2 nunca escribe `opcion_elegida_id`, `resultado_obtenido_id` ni `decision_conversacion_opcion`.
- **Estado/status contradictorio:** una partida `game_over`/`completed` puede volver a `TOMA_DECISION_EVENTO`; `status` y `fase_actual` quedan desalineados.
- **Concurrencia:** dos `avanzar-nodo` simultáneos leen el mismo nodo, aplican impactos y hacen `replace_one`; gana el último. Dos `decidir-evento` simultáneos pueden aplicar el resultado dos veces.
- **Sin transacción run + attempt:** si se persiste la derrota/victoria pero falla la sync, el progreso no se registra; al revés, un intento puede quedar registrado con una run no persistida.
- **Grafo roto:** si el admin borra el grafo o un nodo activo, `avanzar-nodo` devuelve 404/500 y `grafo-actual` devuelve `null`; el jugador queda sin salida salvo reiniciar.

---

## 8. Selección de motor y convivencia V1/V2

### 8.1 Cómo se elige

1. `iniciar_partida_v2` busca el desafío del día y el universo (`setup_service.py:139-150`).
2. Lee `universo_doc.get("motor", "v1")` y lo guarda en `run["motor"]`.
3. `elegir_carta_mes_v2` bifurca: `if run.get("motor") == "v2"` → grafo; si no → V1.
4. El motor queda “congelado” en la run: cambiar el universo después no migra partidas existentes.
5. El desafío diario **no** elige motor. `daily_challenges.config` solo tiene `universo_id` y pools.
6. **Problema operativo:** el seed de arranque reescribe el universo con el default `"v1"`, por lo que V2 se desactiva en cada reinicio.

### 8.2 Endpoints que usa cada motor

| Paso | V1 | V2 |
|---|---|---|
| Iniciar | `POST /api/narrative/v2/partida/iniciar` | Igual |
| Draft | `POST /elegir-carta-mes` → `evento_actual` | Igual → `grafo_actual` |
| Evento | `POST /decidir-evento` | `POST /avanzar-nodo` × N |
| Conversación | `POST /responder-conversacion` | `POST /avanzar-nodo` × N |
| Avanzar mes | `POST /avanzar-mes` | Igual |
| Estado/F5 | `GET /estado` + modales | Igual + `GET /grafo-actual` |
| Arranque manual | No existe | `POST /iniciar-evento-grafo`, `POST /iniciar-conversacion-grafo` |

### 8.3 Riesgos de convivencia

1. Los endpoints manuales permiten a un jugador V1 arrancar un grafo V2 y viceversa; `run.motor` no se actualiza.
2. Los personajes/cartas son compartidos: editar/borrar uno afecta a ambos motores. Eventos/conversaciones son independientes.
3. `eventos_jugados` y `conversaciones_jugadas` no distinguen motor; un `_id` reutilizado puede resolver el documento equivocado.
4. El estado no está versionado: los campos V2 no están en `NarrativeRunSchema`.
5. La documentación y los tests asumen contratos distintos.
6. V2 no es operable por defecto: sin seed V2 y con el seed V1 reseteando el motor.
7. Ambos escriben el mismo `user_attempts`, pero ninguno otorga puntos.

### 8.4 Deuda de migración

- Convertir 12 eventos V1 + 15 resultados a 7+ grafos V2; no hay herramienta.
- Convertir 16 conversaciones planas a grafos; no hay herramienta.
- Unificar el modelo de resultados (externo vs inline) o mantener dos caminos.
- Unificar pools: V2 ignora `daily_challenges.config` para eventos/conversaciones.
- Mover la selección de motor al desafío o a un campo explícito de versión.
- Resolver el seed automático y la persistencia del motor.
- Completar el contenido V2 a ≥12 eventos o implementar reciclaje.
- Completar historial V2 y modales.
- Integrar economía/vidas o declarar explícitamente que el narrativo está fuera.
- Actualizar documentación y tests.

---

## 9. Comportamiento actual vs. comportamiento esperado

> Las propuestas de “esperado” son recomendaciones. Las que dependen de producto están marcadas como **[decisión pendiente]**.

| Área | Actual | Esperado recomendado |
|---|---|---|
| **Motor oficial** | V1 por default; V2 no sembrado y desactivado en cada boot. | Definir V1 o V2 como oficial. Si V2: seed al arranque, no resetear `motor`, contenido suficiente. **[decisión pendiente]** |
| **Selección de motor** | Por universo; no por desafío. | Campo explícito de versión en el universo y/o challenge; runs con `motor` y `schema_version`. |
| **Contenido V2** | 7 eventos, sin reciclaje; 500 al mes 8. | ≥12 eventos o reciclaje controlado; validar contenido al sembrar. |
| **Máquina de estados** | Endpoints manuales sin guardas. | Toda transición valida fase, status, `run.motor` y `grafo_activo`. Los endpoints manuales siguen existiendo, pero rechazan fases inválidas con 409/400. |
| **Validación de grafos** | Solo Pydantic; runtime 500/soft-lock. | Validador estructural en escritura/publicación y endpoint de simulación. |
| **Autenticación del jugador** | Opcional; invitados comparten `user_id=0`. | Token válido para jugar; si se mantiene el modo invitado, identidad de sesión única y aislamiento. |
| **Economía** | No otorga puntos ni consume vidas. | Integración explícita: puntos al finalizar, vidas/intentos si aplica, o declarar fuera de la economía. **[decisión pendiente]** |
| **Historial V2** | Sin opción/resultado; modales V1 devuelven null. | Persistir decisión y desenlace; modales resuelven ambos motores. |
| **Pools V2** | Ignora pools diarios; usa todo el universo. | Respetar pools del challenge o documentar que V2 es global. |
| **Eventos especiales** | Repetibles; pendientes sin grafo se descartan. | Registrar jugados y evitar repetición; fallback visible. |
| **Admin** | CRUD sin validación referencial; borra contenido en uso. | Validar referencias, impedir borrado en uso y auditar cambios. **[decisión pendiente: soft delete]** |
| **Publicación** | Todo es live; no hay draft/publish. | Draft/publish o al menos validación antes de guardar. |
| **Seeds** | V1 pisa catálogo y motor en cada arranque; V2 no se ejecuta y no es idempotente por `$set` sobre `_id`. | Seeds opt-in/dev, `$setOnInsert`, sin pisar ediciones. |
| **Assets** | 52/57 rutas V1 faltantes; 1/2 V2; uploads efímeros. | Nombres consistentes (`eventos`, `cartas`, etc.), assets existentes y volumen persistente. |
| **Documentación** | Contradice el código en endpoints, fases, status y nombres de colecciones. | Una sola fuente de verdad; actualizar o eliminar docs obsoletas. |

---

## 10. Hallazgos priorizados

### Alta

**A1. El seed de arranque pisa el catálogo V1 y desactiva V2.**
`main.py:57-60` ejecuta `seed_narrative_game()` en cada arranque; `seed_narrative.py:60-72` hace upsert del universo sin `motor`, por lo que se aplica el default `"v1"`. Además reescribe personajes, cartas, resultados, eventos y conversaciones. Cualquier edición admin se pierde y V2 vuelve a V1.

**A2. V2 se queda sin eventos y bloquea la partida.**
7 eventos V2; `sortear_evento_v2` excluye `eventos_jugados` y no recicla. Al mes 8, `elegir-carta-mes` lanza 500. Una partida V2 de 12 meses es imposible con el contenido actual.

**A3. Los endpoints manuales de grafos rompen la máquina de estados.**
`iniciar_evento_mes_v2` e `iniciar_conversacion_mes_v2` no validan fase, status ni grafo activo; `iniciar_grafo_en_partida` sobrescribe `grafo_activo`. Permiten reroll, saltar draft/evento, farmear recursos y revivir partidas finalizadas.

**A4. Autenticación de jugador opcional y compartida.**
`_get_current_user_id` devuelve 0 sin validar token/servicio/activo; la run es `run_0_<fecha>`. Todos los invitados comparten estado; usuarios desactivados siguen jugando.

**A5. No hay validación estructural de grafos.**
`crud_service.py:226-262` solo hace `replace_one`; no existe el simulador documentado. Un grafo inválido produce 500 o soft-lock.

**A6. Ciclo lectura-modificación-escritura sin concurrencia ni transacciones.**
`turn_service.py:203-294` y `graph_engine.py:394-397,515` hacen `find_one` → mutar → `replace_one`. Dos requests simultáneos pueden perder una actualización o aplicar efectos dos veces. Run y `user_attempts` no son transaccionales.

**A7. `user_attempts` se sobrescribe y no es idempotente.**
Cada finalización hace upsert sin guardar el mejor resultado; `reiniciar` borra la run pero no el intento. Un reintento perdedor puede convertir un `completed` en `failed`.

**A8. El narrativo no otorga puntos ni consume vidas, y usa una escala incompatible.**
No actualiza `usuarios.puntos`; escribe score 1000/850/700/500/250; la economía espera 100/90/75/50/0. `puntos_por_juego.narrativo=80` no se usa.

**A9. Falta integridad referencial y un admin puede romper partidas activas.**
No se valida que `resultado_id`, `siguiente_nodo`, `desenlaces[].nodo`, personajes o cartas existan. Borrar contenido en uso produce 404/500 o fases sin salida.

**A10. Assets de seed rotos y uploads efímeros.**
52 de 57 rutas V1 no existen; `/assets/narrative/conversations/default.webp` de V2 tampoco. El seed usa carpetas inglesas mientras el backend sirve españolas. El compose no monta `app/static`; las imágenes subidas se pierden al recrear el contenedor.

**A11. Se puede jugar cualquier fecha, pasada o futura.**
`IniciarPartidaRequest.date` es `str` sin regex; `iniciar_partida_v2` solo busca el challenge de esa fecha. No se verifica “hoy”, suscripción ni `dias_desbloqueados`.

### Media

**M1. El init acepta IDs duplicados o inexistentes.** Solo valida longitud 3 y pertenencia al pool. Con `["elena","elena","marcus"]` la corte queda con 2 personajes; cartas duplicadas aplican efectos dos veces.

**M2. V2 ignora los pools diarios.** `pool_ids=None`; usa todo el universo. El admin no puede curar qué sale cada día en V2.

**M3. Reglas ECA muertas y condiciones no aplicadas.** `AMORTIGUAR_DANIO` está en catálogo/enum pero no se implementa. `EN_EVENTO_POSITIVO`, `EN_EVENTO_NEGATIVO` y `AL_FINAL_PARTIDA` se ofrecen pero nunca se despachan. Las condiciones de opciones V1 no secretas se ignoran; las de decisión de conversación también; las probabilidades `Personaje.conversaciones` no se usan.

**M4. Caché de recursos nunca se invalida.** `_RECURSOS_MAPA_CACHE` se llena en `setup_service.py:60-71`; `invalidar_cache_recursos_universo` existe pero ningún endpoint admin la llama.

**M5. Sinergia de cartas V1 distorsionada.** `cartas_activas_mock = [{"tags": run.get("tags_activos", [])}]` pasa todos los tags como una sola carta; el multiplicador ×2.5 se aplica casi siempre.

**M6. Eventos especiales repetibles y pendientes descartados.** `eventos_especiales_jugados` se registra pero nunca se consulta; un personaje que vuelve a cruzar 95/15 puede repetir el especial. Si no hay grafo, el pendiente se descarta.

**M7. Finales sembrados con recurso fantasma y victoria no editable.** `corte_medieval` no tiene `nobleza`, pero se crea `fin_corte_nobleza_cero`; la victoria se genera hardcodeada, no desde `narrative_endings`.

**M8. Configuraciones de desafío incompletas.** `generar_mes_narrativo` exige 5 personajes y 5 cartas, pero no eventos ni conversaciones. Un pool vacío produce 500 o draft bloqueado.

**M9. Seed V2 no idempotente por `$set` sobre `_id`.** La segunda ejecución falla y no actualiza el resto.

**M10. V2 no se siembra al arrancar y no activa el motor.** En un despliegue limpio, V2 no es jugable sin pasos manuales.

**M11. Historial y contrato V2 incompletos.** No se escribe `opcion_elegida_id`/`resultado_obtenido_id`; los modales V1 devuelven null para IDs V2; `status` real `in_progress` no coincide con `CONTINUA` de la documentación.

**M12. Tests desactualizados.** Tests admin sin token (401); `test_narrative_v2_game` fuerza `motor="v1"` y no prueba el ciclo V2.

**M13. Falta de índices V2.** No hay índices para `narrative_v2_events`, `narrative_v2_conversations` ni `narrative_v2_eventos_especiales`; los sorteos hacen `find` por `universo_id` sin índice.

**M14. Fuga de información en opciones secretas V1.** `calcular_opciones_evento` incluye todas las opciones, incluidas las secretas bloqueadas, con texto y probabilidades.

### Baja

- Documentación obsoleta o contradictoria.
- Schemas/enums muertos: `NarrativeRunSchema`, `NarrativeDailyChallengeConfig`, `TurnoSnapshot`, `HistorialMes`, `SETUP_CORTE/SETUP_CARTAS`, `DERROTA_GENERAL`, `CategoriaCartaEnum.PERSONAJE` sin lógica de reclutamiento, `PersonajeConversacionProbabilidad`.
- `duracion_meses` ignorado; se hardcodea 12.
- Pasivos de mes 1 y 12 no se aplican.
- Derrota por pasivos con `mes_actual` adelantado.
- Paginación admin inestable (sin sort, límite 500, skip/limit negativos).
- Validación de imágenes débil (sin límite propio, sin extensión, sin protección de decompression bombs).
- `conversaciones-posibles` público (spoilers).
- Invitados no sincronizan intento.
- Porcentajes mostrados vs sorteo real (0.0 vs 0.1).
- Múltiples finales para el mismo `(universo, recurso)`; `find_one` sin orden.
- Sin auditoría de cambios admin.
- Sin rate limiting ni idempotency keys en `iniciar`, `reiniciar`, `avanzar-nodo`, `decidir`.

---

## 11. Reglas para tocar routers sin romper el frontend

1. **No cambiar paths, métodos ni DTOs.** Mantener `/api/narrative/v2/partida/*`, `/api/narrative/partida/*` y `/api/narrative/admin/*`.
2. **No renombrar `*V2Response`.** Aunque sirven a ambos motores, el frontend ya los consume así.
3. **Agregar guardas de fase no cambia el contrato.** Devuelven 409/400 en casos que hoy son exploits; el camino feliz queda igual.
4. **No eliminar campos de respuesta.** Si el historial V2 agrega `opcion_elegida_id`, hacerlo opcional.
5. **La autenticación es un cambio de comportamiento.** Exigir token a los endpoints de jugador puede romper el modo invitado; decidir y coordinar.
6. **La lógica nueva va en services.** El router valida y delega; no mutar la run en el router.
7. **Los cambios de datos necesitan migración.** Agregar `schema_version`, `motor` a schemas o `grafo_activo` a `NarrativeRunSchema` sin romper runs viejas.
8. **Tests de caracterización antes de tocar.** Congelar respuestas de iniciar, draft, evento, conversación, avance y modales.
9. **No tocar la SPA admin sin coordinar.** El panel puede no enviar Bearer en todos los flujos; verificar.
10. **Mantener la compatibilidad de assets.** No cambiar URLs existentes sin alias.

---

## 12. Plan de refactor por fases

### Fase 0 — Red de seguridad

- Tests de caracterización del loop V1 y V2, setup, modales y admin.
- Documentar el contrato real (este documento).
- Verificar qué endpoints consume el frontend.

### Fase 1 — Extraer sin cambiar comportamiento

- Separar V1 y V2 en módulos internos con interfaces claras (`motor_v1`, `motor_v2`).
- Mover la selección de evento y el cálculo de opciones a servicios por motor.
- Eliminar duplicación de catálogo/CRUD solo si no cambia DTOs.
- Mantener routers y respuestas idénticas.

### Fase 2 — Cerrar agujeros de estado y seguridad

- Guardas de fase/status/`grafo_activo` en endpoints manuales y en todos los pasos.
- Validar `run.motor` antes de ejecutar un paso V1/V2.
- Autenticación de jugador o identidad de invitado aislada.
- Validación referencial en admin (no borrar contenido en uso).
- Idempotencia de finalización y mejor resultado en `user_attempts`.

### Fase 3 — Hacer V2 operable

- Seed V2 al arranque o comando explícito, idempotente.
- No resetear `motor` en el seed V1.
- Contenido ≥12 eventos o reciclaje controlado.
- Validador de grafos en escritura/publicación + endpoint de simulación.
- Respetar pools diarios o documentar que V2 es global.
- Completar historial V2 y modales.

### Fase 4 — Economía y producto

- Definir integración con puntos/vidas o declarar al narrativo fuera.
- Unificar escala de score o mapear rango → puntos.
- Definir si se permite reintentar y cómo se conserva el mejor resultado.
- Definir `duracion_meses` (12 fijo o configurable).

### Fase 5 — Operación y documentación

- Seeds opt-in y no destructivos.
- Assets consistentes y volumen persistente.
- Single source of truth documental.
- Índices V2.
- Auditoría admin y rate limiting.

---

## 13. Tests de caracterización recomendados

Mínimo antes de tocar routers:

1. `POST /api/narrative/v2/partida/iniciar` con 3+3 válidos, IDs duplicados, IDs inexistentes y fecha inválida.
2. `POST /elegir-carta-mes` en fase correcta e incorrecta, carta ofrecida y no ofrecida.
3. V1: `decidir-evento` con opción pública, secreta bloqueada y secreta habilitada; `responder-conversacion`; `avanzar-mes`.
4. V2: `avanzar-nodo` intermedio y terminal; `grafo-actual`; eventos especiales; conversación incidental.
5. Guardas: `iniciar-evento-grafo` en `DRAFT_MENSUAL`, `BALANCE_MES`, `FINALIZADA` (documentar comportamiento actual).
6. Admin: CRUD de universos/eventos V2, `generar-mes`, borrado de contenido en uso.
7. Persistencia: run con `motor`, `grafo_activo`, historial y status.

La estrategia completa está en [04-testing.md](04-testing.md).

---

## 14. Preguntas abiertas para el dueño

1. ¿V1 sigue siendo el motor oficial y V2 es experimental, o V2 debe ser el default?
2. ¿Cómo se opera V2 si el seed de arranque reescribe el universo con `motor="v1"`?
3. ¿El jugador debe poder jugar solo el día actual? ¿Cómo se bloquean fechas pasadas/futuras y cómo se integra `unlock-day`/Premium?
4. ¿El invitado (`user_id=0`) es un modo demo intencional? ¿Comparte run entre todos o cada sesión tiene identidad propia?
5. ¿La partida debe consumir vidas o intentos? ¿Reiniciar cuesta una vida?
6. ¿El narrativo debe otorgar puntos? ¿Con qué escala y quién acredita?
7. ¿Se permite reintentar y sobrescribir el intento diario? ¿Se conserva el mejor resultado?
8. ¿La duración es siempre 12 meses? ¿Se respeta `duracion_meses` o se elimina?
9. ¿V2 debe usar pools diarios o todo el universo?
10. ¿Los eventos especiales pueden repetirse?
11. ¿Las conversaciones pueden ocurrir en cualquier fase o solo después de un evento?
12. ¿Se necesita validador/simulador de grafos antes de publicar?
13. ¿Qué pasa si un admin borra contenido en uso? ¿Soft delete, versionado o bloqueo?
14. ¿Dónde viven las imágenes? ¿Repo, volumen, S3/CDN?
15. ¿Se migra el contenido V1 a V2 o se mantienen dos catálogos? ¿Quién escribe los 5 eventos V2 faltantes?

---

## 15. Anexo: documentación vs. implementación

| Documento | Afirmación | Realidad |
|---|---|---|
| `docs_interna/ARQUITECTURA_JUEGOS_Y_NARRATIVO.md:187-188` | Endpoints legacy V1 ocultos (`/iniciar`, `/activa`, `/turno`, etc.) | No existen; el loop está en `/api/narrative/v2/partida`. |
| `docs_interna/ARQUITECTURA...:85-86` | `status`: `in_progress` o `completed` | Derrota usa `game_over`. |
| `docs_interna/ARQUITECTURA...:142` | `EstadoPartidaActivaResponse` | No existe; es `EstadoTurnoResponse`. |
| `docs_interna/ARQUITECTURA...:60-64` | `user_attempts`: `completed`, `duration_seconds`, `attempts_count` | Usa `status`, no tiene `duration_seconds`, el campo es `attempts`. |
| `docs_interna/ARQUITECTURA...:80` | `corte_activa` eliminada | El init no la escribe, pero varios servicios aún tienen fallback. |
| `docs_interna/DIAGRAMAS...:26,31` | Colecciones `narrative_universes` y `narrative_finalizations` | Son `narrative_settings` y `narrative_endings`. |
| `docs_interna/DIAGRAMAS...:71,98,159` | Corte de 2 personajes y 2 cartas | Son 3 y 3. |
| `docs_interna/DIAGRAMAS...:35` | PK de `daily_challenges` = `game_id + date` | Incluye `difficulty`. |
| `docs_interna/DIAGRAMAS...:100,163-167` | Fases `DRAFT_CARTA`, `EVENTO`, `RESOLUCION` | Son `DRAFT_MENSUAL`, `TOMA_DECISION_EVENTO`, `BALANCE_MES`, etc. |
| `docs_interna/DIAGRAMAS...:128` | Victoria si `mes_actual > 12` | Se evalúa `>= 12`. |
| `docs_interna/DIAGRAMAS...:170` | `NarrativeTurnoDeltaResponse` | No existe; es `EstadoTurnoResponse`. |
| `docs/DOSSIER_REFACTOR_NARRATIVE.md:11-40` | Monolito `service.py` de 1.593 líneas, `admin_router.py`, `router_v2.py` | Esos archivos no existen; estructura dividida en `game/`, `admin/`, `schemas/`. |
| `docs/DOSSIER...:16` | V2 son wrappers de V1 | Falso: V2 usa `graph_engine` nativo. |
| `docs/DEFINICIONES_POST_JUEGO_NARRATIVO.md` | Loop en `/api/narrative/partida/*` | Está en `/api/narrative/v2/partida/*`. |
| `docs/DOCUMENTACION_ENDPOINTS_MOTOR_GRAFOS_V2.md:873-915` | `POST /api/narrative/admin/v2/simular` | No existe. |
| `docs/DOCUMENTACION...:843-845` | Alias `/upload-image` | Solo existe `/upload-imagen`. |
| `docs/DOCUMENTACION...:502` | `status: "CONTINUA"` | `run.status` real es `in_progress`. |
| `docs/DOCUMENTACION...:3` | “Estado: En producción” | V2 no se siembra al arrancar y el seed V1 resetea el motor. |
| `docs/ANALISIS_DIFF_V1_V2.md` | Fases en minúsculas | Son mayúsculas; `toma_decision_conversacion` no existe. |

**Documentos útiles:** `DOCUMENTACION_ENDPOINTS_MOTOR_GRAFOS_V2.md` describe bien el diseño V2 (salvo simulador/status/casing) y `ANALISIS_DIFF_V1_V2.md` explica conceptualmente la diferencia, aunque sus ejemplos no son contrato literal.
