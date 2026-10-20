# Auditoría 05 — Eficiencia y Rendimiento

- **Proyecto**: Mayores Actualizaciones (SIPI) — Backend FastAPI + MongoDB (Motor async)
- **Fecha**: 2026-10-19
- **Alcance**: todo el backend (`app/`), scripts de siembra, arranque, integración con servicios externos (RAE, SMTP), configuración de despliegue (Dockerfile, docker-compose, Caddyfile)
- **Metodología**: análisis estático exclusivamente (lectura de código con `read`/`grep`/`glob` y `shell` de solo lectura). **No se ejecutó la aplicación, no se corrieron benchmarks ni tests y no se modificó ningún archivo.** Los impactos son cualitativos (alto/medio/bajo) y las magnitudes citadas surgen de constantes del propio código (timeouts, sleeps, cantidad de días), no de mediciones.

---

## 1. Resumen ejecutivo (top 10 hotspots priorizados)

| # | Severidad | Hotspot | Ubicación | Por qué duele |
|---|-----------|---------|-----------|----------------|
| 1 | 🔴 Crítica | Cliente RAE **sincrónico** (`urllib` + `time.sleep`) invocado desde corrutinas async | `app/core/rae_client.py:115-190` (urlopen L157, sleep L183); llamadas en `wordle_generator.py:51`, `sopa_generator.py:179`, `crucigrama_generator.py:1071` | Cada definición bloquea el event loop hasta `3.5 s × 2 intentos × N candidatos` (+1.2 s de `time.sleep` en 429). Wordle/sopa/crucigrama lo invocan decenas/cientos de veces por mes generado. Un solo mes con la API lenta deja al servidor congelado minutos. |
| 2 | 🔴 Crítica | Generación mensual completa ejecutada **dentro del lifespan de arranque** | `app/main.py:36-42` → `service.py:590-631` → generadores | El arranque no termina hasta generar meses faltantes: incluye HTTP bloqueante a RAE, `asyncio.sleep` de 0.1–0.2 s por día (≈14 s por mes entre los 3 juegos) y backtracking de Sudoku/Crucigrama en CPU. Riesgo real de health-check fallido/tiempo de arranque no acotado. |
| 3 | 🔴 Crítica | Endpoint admin `generate-month` ejecuta la misma generación pesada **en el request path** con `force=True` por defecto | `daily_challenges/router.py:99-113`; `service.py:314-588` | Un clic de la Torre de Control bloquea el loop cientos de segundos (31 días × RAE con timeout + sleeps + CPU). No hay background task, lock ni timeout de request. |
| 4 | 🟠 Alta | Generadores CPU-bound (Sudoku y Crucigrama) en corrutinas async sin `to_thread`/executor | `sudoku_generator.py:33-112` (`_count_solutions`, límite 27 pistas); `crucigrama_generator.py:814-843` (carga indexa 236 KB JSON), `928-985` (backtracking CSP) | Sudoku ejecuta hasta 81 verificaciones de unicidad (cada una un solver completo); crucigrama indexa ~8.500 palabras y hace backtracking con poda por 150 candidatos. Todo en el hilo del event loop. |
| 5 | 🟠 Alta | `bcrypt` sincrónico dentro de handlers async (login/registro) | `security.py:7-27`, usados en `auth/service.py:76` y `:243` | ~50–100 ms de CPU bloqueante por intento de login/registro (por diseño lento). Ráfagas de logins serializan todo el servidor. Fix trivial: `asyncio.to_thread`. |
| 6 | 🟠 Alta | Procesamiento de imágenes Pillow (Lanczos + WebP `method=6`) en handler async | `narrative/admin/image_service.py:53-84` | Subir una imagen bloquea el loop segundos (compresión WebP de mayor costo). |
| 7 | 🟠 Alta | Persistencia de la caché RAE: **reescritura completa del JSON por cada palabra nueva** | `rae_client.py:53-60` (`json.dump` con `indent=2` sin escritura atómica) | O(n) por palabra → O(n²) por lote de generación; sin `os.replace` puede corromperse con 2 writers. La caché crecerá hacia miles de entradas. |
| 8 | 🟠 Alta | `get_current_user` trae el **documento completo** del usuario (sin proyección) en cada request autenticado | `dependencies.py:48` | Transfiere password hash y array `progresos` en cada llamada; además es una query extra por request. Proyección mínima + eventual caché corta. |
| 9 | 🟠 Alta | Seeds de Wordle/Sopa se ejecutan y **reescriben ~185 documentos en cada arranque** aunque ya existan | `seed_challenges.py:109-146`; `seed_sopa_letras.py:168-208` (llamados en `main.py:39-40`) | Cada deploy produce ~185 upserts con `$set` completo + `updated_at=now` (marca como modificado todo) y regeneración de grillas. Deberían verificar existencia y salir. |
| 10 | 🟡 Media | Rate limiter en memoria con diccionario **sin límite de crecimiento** y estado por proceso | `core/rate_limit.py:10-30` | `defaultdict(deque)` por `ip:path` que solo se limpia al re-visitar la misma clave → crecimiento de memoria ante escaneos con IPs variadas; con >1 worker los límites se multiplican y el bypass admin se evalúa por proceso. |

Hallazgos adicionales destacados: doble escritura completa del array `progresos` (`progreso/service.py:38-46,85-88`), doble lectura en el guardado de intentos (`user_attempts/service.py:71-82`), paginación con `skip` + `count_documents` con filtros sin índice (`usuario/service.py:54-59`), payloads de mes que incluyen soluciones (`daily_challenges/service.py:123-126`), SMTP sin reutilización de conexión en request path (`email_service.py:32,116`), y ausencia de coordinación multi-instancia del loop de 12 h (`main.py:50-62`).

---

## 2. Hallazgos por categoría

### 2.1 Bloqueos del event loop (sync/CPU-bound en async)

> Contexto: **todos los endpoints son `async def` y no hay un solo uso de `run_in_executor`/`asyncio.to_thread` en el proyecto** (grep global). Uvicorn corre en un único proceso (`Dockerfile:21`, sin `--workers`), por lo que cualquier operación sincrónica dentro de un handler congela *todas* las requests.

#### H-01 🔴 RAE client sincrónico (`urllib` + `time.sleep`) — CRÍTICA
- **Archivo:línea**: `app/core/rae_client.py:19-21, 115-190` (bloqueo en `:157` `urlopen(..., timeout=3.5)`, reintento de 429 en `:183` `time.sleep(1.2)`).
- **Cadena de llamadas** (todas dentro de corrutinas async):
  - `wordle_generator.py:51` (`generate_wordle_hints`) → 1+ fetches por día.
  - `sopa_generator.py:179` (`generate_sopa_hints`) → 4 fetches por día.
  - `crucigrama_generator.py:1071` (`_parse_and_build_challenge`) → hasta ~8 fetches por día (palabras sin pista curada).
  - Se ejecutan desde: `service.py:384,469,553` (generación mensual) → invocadas en `main.py:42` (startup), `main.py:55` (loop 12 h) y `daily_challenges/router.py:106-112` (request path admin).
- **Por qué es costoso**: cada fetch prueba varios candidatos (lema singular/plural/accentuado) y hasta 2 intentos por candidato; con la API caída o devolviendo 429, cada palabra puede costar ≥21 s de loop bloqueado (3 candidatos × 2 × 3.5 s) + sleeps. Un mes de Wordle (31 días) o Sopa (124 palabras) son cientos de segundos potenciales. Además `_save_definitions_cache()` (ver H-07) suma I/O sincrónico.
- **Impacto estimado**: **alto** (disponibilidad: durante startup/loop12h/generación admin toda la API queda sin responder).
- **Fix concreto**:
  1. Migrar a cliente async (`httpx.AsyncClient` con timeout total ~3-5 s, retries exponenciales, semáforo de concurrencia ~2-5) **o**, como paso inmediato de bajo riesgo, envolver `fetch_rae_definition` en `await asyncio.to_thread(...)` (y quitar `time.sleep` → `asyncio.sleep`).
  2. Añadir circuit breaker / “negative cache” (marcar palabra no encontrada un TTL) para no repetir timeouts.
  3. Mover la generación mensual a background task (ver H-03) y precomputar por lotes.

#### H-02 🔴 Arranque con generación pesada secuencial en el lifespan — CRÍTICA
- **Archivo:línea**: `app/main.py:33-42` (`await seed_*` y `await ensure_current_and_next_month_generated()`), `service.py:590-631` (bucle por juego/mes y generación secuencial), `service.py:409,493,577` (sleeps de 0.1–0.2 s por día), `seed_sudoku.py:12-24` (5 meses verificados).
- **Por qué es costoso**: el lifespan no completa hasta terminar. Si el mes actual o el siguiente están incompletos, se ejecuta: generación Sudoku (CPU, ver H-04) + por cada día de Wordle/Sopa/Crucigrama, llamadas RAE bloqueantes + sleeps artificiales. Piso aritmético: ~14 s solo de sleeps por mes (31×0.2 + 31×0.15 + 31×0.1) antes de contar RAE/CPU. `seed_sudoku_challenges` vuelve a chequear Ago–Dic 2026 en cada arranque.
- **Impacto estimado**: **alto** (arranque lento y no acotado; healthcheck de docker-compose con `start_period: 15s` puede declarar unhealthy).
- **Fix concreto**: ejecutar la generación/verificación **después** del `yield` como `asyncio.create_task`, o en un proceso/worker separado; gatear con flag (p. ej. `RUN_STARTUP_GENERATION=false` en prod); precomputar meses por cron; los seeds deben ser “check-first”.

#### H-03 🔴 Generación en el request path del endpoint admin — CRÍTICA
- **Archivo:línea**: `daily_challenges/router.py:99-113` (`force: bool = True` por defecto) → `service.py:314-420 / 422-504 / 506-588 / 189-272`.
- **Por qué es costoso**: un POST de la Torre de Control ejecuta el ciclo completo (hasta 31 días × (RAE + sleep) + CPU) dentro de la request, bloqueando el loop. Con `force=True` incluso README dice que refresca pistas RAE de todos los días.
- **Impacto estimado**: **alto** (DoS accidental desde el propio panel; timeout del proxy).
- **Fix concreto**: responder `202 Accepted` y encolar la tarea (`BackgroundTasks`, worker propio, o cola); añadir `asyncio.Lock` por `game_id+mes` para evitar ejecuciones concurrentes; cambiar el default a `force=False`; eliminar los `asyncio.sleep` una vez que el cliente RAE controle su propia tasa.

#### H-04 🟠 CPU-bound de generadores en el hilo del loop — ALTA
- **Archivo:línea**:
  - Sudoku: `sudoku_generator.py:33-64` (`_count_solutions` recursivo), `:99-112` (hasta 81 intentos de remoción con verificación de unicidad), `:66-80` (relleno por backtracking).
  - Crucigrama: `crucigrama_generator.py:814-843` `_init_word_index()` (lee y parsea `acentos_todas_palabras.json` de **236 KB** y construye `_LETTER_POS_INDEX` con múltiples `set`), `:910-985` backtracking CSP con MRV y hasta 150 candidatos por rama, `:1113-1121`.
- **Por qué es costoso**: son algoritmos de búsqueda; en el peor caso los tiempos son segundos por tablero × 30 días por mes. El indexado del diccionario ocurre **la primera vez que se genera un crucigrama** (lazy), que puede ser en medio de una request admin o del arranque.
- **Impacto estimado**: **alto** en generación; bajo en régimen normal (una vez generado el mes, no se recalcula).
- **Fix concreto**: `await asyncio.to_thread(generate_..., ...)` (o `ProcessPoolExecutor` para los generadores puros), precalentar `_init_word_index()` en el arranque (en thread) o moverlo a un módulo de datos compilado (p. ej. pickle/msgpack); considerar precomputar un año de tableros fuera de línea.

#### H-05 🟠 bcrypt sincrónico en login/registro — ALTA
- **Archivo:línea**: `app/core/security.py:16-26`; invocado en `auth/service.py:76` (`verify_password` en login-sistemas) y `:243` (`get_password_hash` en registro); también en arranque `init_db.py:73`.
- **Por qué es costoso**: bcrypt rounds=10 es deliberadamente costoso (~50–100 ms de CPU por llamada). En un solo worker, N logins concurrentes se serializan y bloquean también al resto de endpoints.
- **Impacto estimado**: **alto** bajo carga de autenticación; nulo si el tráfico es de baja concurrencia.
- **Fix concreto**: `await asyncio.to_thread(verify_password, ...)` / `to_thread(get_password_hash, ...)`; opcional: subir el pool de threads default (anyio 40) si se migran más bloqueos a threads.

#### H-06 🟠 Pillow (redimensión Lanczos + WebP method=6) en async — ALTA
- **Archivo:línea**: `app/features/narrative/admin/image_service.py:53-84` (lectura del upload en `:53`, `Image.open/convert` `:58-59`, `thumbnail` `:64`, `save(..., method=6)` `:78`).
- **Por qué es costoso**: decodificar + Lanczos + WebP lossy calidad 82 con `method=6` es la variante más lenta de compresión; fácilmente >1 s por imagen, bloqueando el loop.
- **Impacto estimado**: **medio** (solo panel admin, pero todo el mundo lo sufre).
- **Fix concreto**: `await asyncio.to_thread(procesar..., contenido)` o worker dedicado; bajar `method` a 4; límite de tamaño de entrada.

#### H-07 🟠 Reescritura completa del JSON de caché RAE por palabra — ALTA
- **Archivo:línea**: `rae_client.py:53-60` (`_save_definitions_cache`), llamado en `:177` tras cada nueva definición. Sin `os.replace` (no atómico) y con `indent=2`.
- **Por qué es costoso**: cada palabra nueva serializa *toda* la caché (hoy 49 KB; crecerá con miles de definiciones) → coste O(n) por palabra, O(n²) por lote; y dos instancias escribiendo a la vez pueden corromper el archivo (no hay lock ni rename atómico).
- **Impacto estimado**: **medio** ahora, **alto** cuando la caché crezca o con concurrencia de workers.
- **Fix concreto**: marcar “dirty” y persistir con debounce (p. ej. cada N palabras o cada 5 s) con `os.replace` sobre archivo temporal; o migrar la caché a MongoDB/SQLite con upsert incremental.

#### H-08 🟡 `random.seed()` global en generador de sopa — MEDIA
- **Archivo:línea**: `sopa_generator.py:117-118` (y duplicado en `seed_sopa_letras.py:114-115`).
- **Por qué -importa**: si en el futuro la generación se mueve a threads (recomendación H-04/H-01), `random.seed` global contamina el estado de `random` de todo el proceso y produce carreras. Además rompe la reproducibilidad si otro código usa `random` entre medio.
- **Impacto estimado**: **bajo hoy**, **medio** al paralelizar.
- **Fix concreto**: usar `rng = random.Random(seed)` local (como ya hace `crucigrama_generator.py:1114`).

#### H-09 🟡 `time.sleep` no existe en async salvo RAE, pero el patrón de sleeps de generación suma — BAJA/MEDIA
- **Archivo:línea**: `service.py:409` (0.2 s/día), `:493` (0.15), `:577` (0.1). Son `asyncio.sleep` (no bloquean el loop) pero **alargan** cualquier request/arranque.
- **Fix concreto**: eliminarlos al migrar a cliente RAE con rate limit propio; mientras tanto, no ejecutar en request path.

---

### 2.2 MongoDB

> Índices existentes revisados en `app/core/database.py:55-104`. Cruce con filtros reales por colección.

#### H-10 🟠 Lecturas sin proyección del usuario en cada request autenticado — ALTA
- **Archivo:línea**: `dependencies.py:48` (`find_one(query)` sin proyección); también `auth/service.py:56,98,145,167,209,297,344,376`; `progreso/service.py:9,52,94`; `usuario/service.py:71,81,119,163,268`; `usuario/router.py:125`.
- **Por qué es costoso**: transfiere el documento completo (incluye `password`, `codigo_acceso`, `progresos[]`) en cada autenticación; el array `progresos` crece con los cursos del usuario. Multiplica bytes por request y por endpoint.
- **Impacto estimado**: **medio** (escala con usuarios×cursos y con QPS).
- **Fix concreto**: proyección mínima en `get_current_user` (`{"id":1,"tipo_usuario":1,"activo":1,"name":1,"email":1}`) y en todos los `find_one({"id": ...})` que solo necesitan metadatos; evaluar caché en memoria con TTL corto e invalidación al modificar usuario.

#### H-11 🟡 `progresos` embebido: read-modify-write del array completo (y posible lost update) — MEDIA
- **Archivo:línea**: `progreso/service.py:9-46` (`crear_progreso` lee, muta y `$set` del array) y `:50-90` (`actualizar_progreso` ídem).
- **Por qué es costoso**: cada actualización de un curso reescribe **todos** los progresos del usuario (documento crece, escritura O(n)); dos requests concurrentes pueden pisarse (lost update). Además hace 2 queries por operación (lectura + escritura).
- **Impacto estimado**: **medio** (crece con cursos por usuario; riesgo de datos).
- **Fix concreto**: actualización dirigida con `arrayFilters`, p. ej. `update_one({"id": uid, "progresos.cursoId": cid}, {"$set": {"progresos.$.progreso": ...}})` con fallback `$push` (upsert); o mover `progresos` a colección propia con índice único `(usuarioId, cursoId)`.

#### H-12 🟡 Doble lectura en el guardado de intentos — MEDIA-BAJA
- **Archivo:línea**: `user_attempts/service.py:71` (`find_one`) + `:74-82` (`find_one_and_update`). El filtro es igual y está indexado (`database.py:77-81`), pero son 2 round-trips + el `$inc` de puntos (`:85-95`) es un tercer viaje no transaccional.
- **Impacto estimado**: **bajo-medio** (hot path: se llama en cada fin de partida de cada juego).
- **Fix concreto**: usar solo `find_one_and_update` con `return_document=ReturnDocument.BEFORE` para conocer el estado previo en una operación (la API de Motor lo devuelve en el mismo viaje); proyectar solo `status`; si se requiere atomicidad de puntos, `update` condicional o transacción.

#### H-13 🟡 Paginación con `skip` + `count_documents` con filtros sin índice — MEDIA
- **Archivo:línea**: `usuario/service.py:54-59` (`count_documents(query)` + `find().sort("id").skip(skip).limit(limit)`); router expone `skip` (`usuario/router.py:26`).
- **Por qué es costoso**: (a) `skip` grandes obligan a recorrer y descartar N documentos; (b) los filtros `activo`, `black`, `tipo_usuario` **no tienen índice** (solo hay índices por `email`, `codigo_acceso`, `id`, `name`, `date_start` en `database.py:59-65`); (c) el `count_documents` corre el mismo filtro una segunda vez; (d) la búsqueda `nombre` usa regex `$options: "i"` no anclada, que no puede usar índice (full scan de `usuarios`).
- **Impacto estimado**: **medio** (admin; crece con la base de usuarios).
- **Fix concreto**: índices para filtros reales (`tipo_usuario`, `activo`, `black`, y compuestos con `id` para el sort, p. ej. `(activo, id)`); paginación por keyset (`id < last_id`) en lugar de `skip`; documentar que la búsqueda por nombre sea con prefijo (`^term`) o índice de texto; usar `estimated_document_count` o `count` cacheado si el total exacto no es crítico.

#### H-14 🟡 `to_list(None)` sin límite en servicios narrativos — MEDIA-BAJA
- **Archivo:línea** (20 ocurrencias): `narrative/game/turn_service.py:114,119,144,237`; `setup_service.py:169,172,239`; `transition_service.py:107,108,155`; `modals_service.py:66,81,124,132,170,214`; `admin/challenge_service.py:133-136`.
- **Por qué es costoso**: hoy los `$in` son de pocos ids o filtros de universo (colecciones chicas), pero un `to_list(None)` es un unbounded read: si el catálogo crece (o un `pool_*_ids` se ensucia), la respuesta crece sin control.
- **Impacto estimado**: **bajo hoy**, **medio** con catálogos grandes.
- **Fix concreto**: `to_list(length=50/100)` explícito + proyecciones (`{"titulo":1,"tags":1,...}`) en los usos que solo necesitan subcampos (p. ej. `turn_service.py:116-119` ya proyecta bien).

#### H-15 🟡 Payloads de mes con config completa (incluye soluciones) — MEDIA
- **Archivo:línea**: `daily_challenges/service.py:123-126` (`find(query)` sin proyección) y `schemas.py:11-28` (`config: Dict[str, Any]`). Para Sudoku cada doc trae `solution` + 3 tableros + `clues`; un mes son 28–31 documentos grandes.
- **Por qué es costoso**: más bytes por request (Caddy comprime, pero el costo de serialize/compress se paga en cada llamada), y además expone la solución al cliente (riesgo funcional/abuso).
- **Impacto estimado**: **medio** (payload y seguridad lógica).
- **Fix concreto**: proyección/transformación para excluir `config.solution` en endpoints de jugador (dejar la solución solo en endpoints de validación server-side); cachear la respuesta mensual (es inmutable una vez generada) con ETag o caché en memoria por `(game_id, year, month)`.

#### H-16 🟡 Múltiples round-trips secuenciales por request narrativo — MEDIA-BAJA
- **Archivo:línea**: `modals_service.py:111-155` (`obtener_turno_actual`: 1 run + draft + evento + resultado + conversación + resultados del evento = hasta 6 queries secuenciales), `turn_service.py:71-147` (run, carta, recursos, challenge, eventos, personajes, resultados = ~7), `setup_service.py:80-103` (5), `decidir_evento_v2` (`turn_service.py:173-237`, ~6).
- **Por qué es costoso**: latencias sumadas (cada query es un round-trip independiente); podrían resolverse con `$in` y `aggregate $lookup` o cacheadas (catálogo narrativo cambia raramente).
- **Impacto estimado**: **bajo-medio** (colecciones pequeñas; impacto real en móviles/alta latencia).
- **Fix concreto**: cachear en memoria el catálogo estático (`narrative_characters/cards/events/results/conversations`) con invalidación desde el admin (ya existe el patrón `_RECURSOS_MAPA_CACHE` e `invalidar_cache_recursos_universo` en `setup_service.py:51-58` — extenderlo); o `$in` múltiple + armado en el servicio.

#### H-17 🟢 Ausencia de índices detectada vs. filtros reales (consolidado)
- `usuarios`: filtros `activo`, `black`, `tipo_usuario` sin índice (`usuario/service.py:43-52`); `update_many` de migración por `estado_id` inexistente escanea toda la colección en cada arranque (`init_db.py:51-58`). → añadir índices simples/compuestos.
- `daily_challenges`: `count_documents` por `game_id + rango de date` usa el índice `(game_id, date, difficulty)` (`database.py:69-73`), correcto. Sin hallazgos.
- `user_attempts`: queries y sort cubiertos por `(user_id, game_id, date)` y `(user_id, date)` — correcto.
- `narrative_runs`: queries por `(user_id, date, game_id)` cubiertas — correcto.
- `counters`: `_id` — correcto.
- **Impacto**: bajo ahora, medio si crece el padrón de usuarios.

---

### 2.3 Arranque / operación

#### H-18 🟠 Seeds idempotentes “a medias”: reescriben todo en cada arranque — ALTA
- **Archivo:línea**: `main.py:37-41`; `seed_challenges.py:109-146` (93 upserts Wordle con `$set` completo); `seed_sopa_letras.py:168-208` (~92 upserts Sopa, regenerando grilla con `generate_word_search`); `seed_sudoku.py:12-24` (5 `count_documents` + posible generación completa).
- **Por qué es costoso**: ~185 escrituras + CPU de grillas + I/O en *cada* arranque/deploy, aunque nada haya cambiado; además sobreescribe las pistas RAE de Wordle con las estáticas y refresca `updated_at` de todo (pierde semántica de “actualizado”).
- **Impacto estimado**: **alto** en ciclos de despliegue (arranque varios segundos + carga Mongo innecesaria); acumulativo.
- **Fix concreto**: patrón check-first: `count_documents({"game_id":..., "date": {"$in": fechas}})` y salir si ya están; o `bulk_write` + `$setOnInsert` para inmutables; idealmente mover seeds a comando CLI y no al lifespan.

#### H-19 🟠 Loop de 12 h sin control de concurrencia ni locking — ALTA (escala)
- **Archivo:línea**: `main.py:50-62` (`_auto_check_loop` con `asyncio.sleep(43200)`), `service.py:590-631` (verificación/generación de mes actual y siguiente por los 4 juegos, secuencial).
- **Por qué es costoso**: la primera ejecución tras un mes incompleto bloquea el loop (RAE + CPU + sleeps); con 2+ workers/instancias, el loop se duplica (4 juegos × N instancias) y puede generar simultáneamente los mismos documentos (upserts, no corrupción, pero trabajo y RAE duplicados + riesgo de 429).
- **Impacto estimado**: **alto** con múltiples workers; medio en single-worker al cambiar de mes.
- **Fix concreto**: mover a scheduler externo (cron) o implementar lease en Mongo (`find_one_and_update` con `locked_until`) antes de generar; ejecutar la generación en thread/worker y no en el loop; una sola instancia “generadora”.

#### H-20 🟡 Estáticos y assets: FastAPI vs Caddy — MEDIA
- **Archivo:línea**: `main.py:140-170` (monta `/admin` SPA y `/assets/narrative` con `StaticFiles`); `Caddyfile:33-43` (solo proxya `/api* /usuario* /progreso* /cursos* /payment* /health* /actuator*`; el resto va a `/srv` del frontend).
- **Por qué es costoso/riesgoso**: las imágenes subidas por `image_service.py:71-83` se guardan en el filesystem **del contenedor backend**, pero Caddy no rutea `/assets/*` al backend ni comparte volumen → en producción pueden resolverse contra `/srv` (404 → fallback `index.html`) o, si llegan al backend (dev/proxy), el tráfico de media pasa por el proceso Python sin caché de Caddy ni compresión (los `.webp` ya están comprimidos, pero se pierde caché/`immutable`).
- **Impacto estimado**: **medio** (rendimiento de carga de imágenes y un posible bug funcional).
- **Fix concreto**: ruta Caddy `handle_path /assets/narrative/* → reverse_proxy backend:8082` (o volumen compartido `./app/static/narrative:/srv/assets/narrative:ro`) con `header Cache-Control "public, max-age=31536000, immutable"`; verificar `/admin` ídem (si la SPA admin no está en `dist`, Caddy debe proxear `/admin*`).

#### H-21 🟢 `init_indexes` en cada arranque — BAJO
- **Archivo:línea**: `database.py:20-25,55-104` (16 `create_index` secuenciales; `create_index` es idempotente pero emite comandos).
- **Impacto**: bajo (decenas/cientos de ms).
- **Fix**: aceptar; o cachear el resultado en una colección de metadatos para saltar en restarts (no vale la pena salvo arranques muy frecuentes).

#### H-22 🟢 `generar_mes_narrativo` (admin) secuencial — BAJO (no arranque)
- **Archivo:línea**: `admin/challenge_service.py:126-204` (carga catálogos completos `to_list(None)` L133-136; 28-31 `replace_one` secuenciales L185-189).
- **Impacto**: bajo (operación admin mensual); **fix**: `bulk_write` en lotes y proyección de ids.

---

### 2.4 Servicios externos (RAE, SMTP)

#### H-23 🟠 SMTP: conexión nueva por correo, esperada en request path — ALTA/MEDIA
- **Archivo:línea**: `email_service.py:32-39` y `:116-123` (`aiosmtplib.send(..., start_tls=True)` abre conexión, TLS y autenticación cada vez); invocado y **esperado** en `auth/service.py:186-191` (magic link), `:218`, `:275`, `:358`, `:402` (registro y reenvíos).
- **Por qué es costoso**: handshake TLS + auth con Brevo ≈ 0.5–2 s por correo añadidos a la latencia del endpoint (no bloquea el loop, pero el usuario espera); sin reutilización de conexión no hay pipelining; `timeout` default de aiosmtplib (10 s) puede colgar el request.
- **Impacto estimado**: **medio-alto** en registro/flujo de acceso (percepción de lentitud y timeouts).
- **Fix concreto**: mover el envío a `BackgroundTasks` (responder 200 y enviar después) y/o cliente SMTP persistente con pool; añadir `timeout=` explícito; registrar métricas de duración. Ojo: el flujo de registro devuelve el código en logs como fallback (`email_service.py:43`), revisar que el cambio a background no rompa esa lógica.

#### H-24 🟡 RAE sin autenticación probable (más 429 ⇒ más sleeps) — MEDIA
- **Archivo:línea**: `config.py:32` (`RAE_API_KEY` default `""`), `rae_client.py:145-149` (cabecera solo si hay key), `.env.example` no incluye `RAE_API_KEY`.
- **Por qué es costoso**: sin API key, la cuota anónima se agota → respuestas 429 → `time.sleep(1.2)` bloqueante (H-01) → generación aún más lenta.
- **Impacto estimado**: **medio** (condiciona H-01).
- **Fix**: configurar `RAE_API_KEY`; añadir manejo de 429 sin `sleep` bloqueante y backoff asíncrono; registrar tasa de fallos.

#### H-25 🟢 Timeouts y retries RAE — correcto pero mejorable — BAJO
- `timeout=3.5` y 2 intentos existen (`rae_client.py:155-157`). El problema no es la ausencia de timeout sino que se ejecuta sincrónicamente (H-01). Añadir retry con jitter y límite global por lote.

---

### 2.5 Caché y memoria

#### H-26 🟠 Rate limiter in-memory: crecimiento sin límite y estado por proceso — ALTA (escala)
- **Archivo:línea**: `core/rate_limit.py:7-32` (`defaultdict(deque)` global, lock de `threading` en dependencia async `:15`), claves `ip:path` creadas para siempre (`:55-56`).
- **Por qué es costoso/peligroso**: (a) un escáner con IPs variables hace crecer `_history` indefinidamente (memory leak); (b) no hay purga global periódica (solo al re-visitar la misma clave); (c) con 2+ workers los límites son por proceso (se multiplican) y el estado no se comparte; (d) `X-Forwarded-For` se toma del primer valor sin validar (spoofeable → bypass de límites por IP).
- **Impacto estimado**: **alto** en escalado horizontal; **medio** en single-worker con tráfico anómalo.
- **Fix concreto**: purga periódica (task que recorra y elimine deques vacíos/vencidos) o limitador con TTL (ej. `cachetools.TTLCache`/`itsdangerous`); usar Redis si hay múltiples procesos; normalizar/limitar la cantidad de buckets por IP; considerar SlowAPI/FastAPI-Limiter como dependencia estándar.

#### H-27 🟡 Caches globales: ciclo de vida y coherencia — MEDIA
- **Archivo:línea**: `rae_client.py:34-75` (`_DEFINICIONES_CACHE`, `_ACENTOS_MAP`), `crucigrama_generator.py:810-843` (`_WORDS_BY_LEN`, `_LETTER_POS_INDEX`), `wordle_generator.py:25-44` (`_WORD_POOL`), `setup_service.py:51-58` (`_RECURSOS_MAPA_CACHE`).
- **Por qué importa**: son caches por proceso cargadas lazy; con más de un worker cada proceso mantiene su copia (memoria ×N) y la invalidación del admin (`invalidar_cache_recursos_universo`) **solo afecta al proceso que atiende la edición** → el resto sirve datos obsoletos hasta reiniciar. El diccionario del crucigrama puede ocupar varios MB por proceso.
- **Impacto estimado**: **medio** (escala/consistencia), **bajo** en single-worker.
- **Fix concreto**: documentar el supuesto “1 worker”; si se escala, invalidación vía pub/sub (Redis/Change Streams de Mongo) o TTL; comprimir `_LETTER_POS_INDEX` (por palabra no por celda) y medir memoria; cargar el índice de palabras en el arranque mediante thread para no pagarlo en caliente.

#### H-28 🟢 `_load_definitions_cache` en cada fetch — BAJO
- **Archivo:línea**: `rae_client.py:37-51, 123`. Devuelve el global tras la primera carga; correcto, pero se vuelve a llamar en cada `fetch` y en `crucigrama_generator.py:923`. Costo despreciable; solo tenencia de referencia.
- **Fix**: opcional, guardar `bool` de cargado o `functools.lru_cache`.

#### H-29 🟢 Estado global mutable adicional — BAJO
- `Database` singleton (`database.py:8-18`) se crea en import; `get_database()` crea cliente sin `ping` si no se inicializó (solo scripts). Sin fuga observable. No requiere acción.

---

### 2.6 Escalabilidad (2+ workers / instancias)

> Situación actual: **1 worker** (`Dockerfile:21` sin `--workers`), 1 réplica backend (`docker-compose.yml:37-69`). Los puntos siguientes son riesgos latentes si se escala.

| Riesgo | Ubicación | Efecto con N>1 |
|--------|-----------|----------------|
| Rate limiting por proceso | `core/rate_limit.py:10-56` | Límites efectivos ×N; el atacante reparte tráfico; el bypass admin se evalúa de nuevo por proceso (sin costo relevante). |
| Loop 12 h duplicado | `main.py:50-62` | N generaciones simultáneas del mismo mes → CPU/RAE ×N, posibles ráfagas de 429. |
| Seeds reejecutados | `main.py:37-41` | N × ~185 upserts en cada deploy. |
| Caché RAE en archivo JSON | `rae_client.py:53-60` | Escrituras concurrentes sin lock → JSON corrupto (pérdida de toda la caché). |
| Caches en memoria divergentes | `setup_service.py:51-58` | Cambios del admin no visibles en otros procesos. |
| Contadores/`counters` | `database.py:32-44` | Es atómico en Mongo; **no hay problema**. |
| `replace_one` de runs narrativos | `turn_service.py:100,137,264`, `transition_service.py:88,122,152`, `setup_service.py:219,235` | Dos requests concurrentes del mismo usuario pueden pisarse (read-modify-write sin versión). Con 1 worker y un usuario secuencial no ocurre; con workers múltiples sí. Añadir `version` + `$set` condicional (`filter={"version": n}` + `$inc`). |

Además: al no usarse endpoints `def` (sync) no aplica el threadpool anyio por defecto (40 hilos); si se migran bloqueos a `to_thread`, monitorear saturación del pool (bcrypt/IP/RAE podrían competir).

---

## 3. Recomendaciones ordenadas por esfuerzo/impacto

### Quick wins (horas, cambio pequeño, impacto visible)

1. **Envolver los bloqueos sync en `asyncio.to_thread`** (sin cambiar librerías):
   - `fetch_rae_definition` en sus 3 llamadores (`wordle_generator.py:51`, `sopa_generator.py:179`, `crucigrama_generator.py:1071`);
   - `verify_password`/`get_password_hash` (`security.py`) en `auth/service.py:76,243`;
   - `procesar_y_guardar_imagen_narrativa` (`image_service.py:53-84`).
2. **Quitar `time.sleep(1.2)` de `rae_client.py:183`** y reemplazarlo por nada (se ejecutará en thread) o `asyncio.sleep` si se migra a async; durante los reintentos, marcar 429.
3. **Cambiar el orden del lifespan**: tras `connect_to_mongo()`, lanzar seeds/ensure como `asyncio.create_task` (o gatear con variable de entorno) para que la app quede servible; los seeds de Wordle/Sopa deben **check-first** (si la fecha ya existe, `continue`).
4. **`force=False` por defecto** en `daily_challenges/router.py:103` y devolver `202` con `BackgroundTasks` para `generate-month`.
5. **Persistencia de caché RAE con debounce + `os.replace`** (`rae_client.py:53-60`).
6. **Proyección mínima en `get_current_user`** (`dependencies.py:48`) y en las lecturas de usuario que no necesitan `progresos`/`password`.
7. **Purga periódica del rate limiter** o migrar a un limitador con TTL; documentar 1 worker.
8. **Índices para filtros del listado de usuarios** (`tipo_usuario`, `activo`, `black`, compuestos con `id`); `estado_id` para el `update_many` de arranque.

### Mejoras de fondo (días)

9. **Cliente RAE async** (`httpx.AsyncClient`) con timeout total, retries exponenciales con jitter, semáforo de concurrencia y negative cache; eliminar sleeps de `service.py`.
10. **Mover toda la generación de desafíos a un worker/cola** (proceso separado o endpoint admin asíncrono con estado de job), con lock por `(game_id, year, month)` en Mongo; mismo tratamiento para el tick de 12 h con lease.
11. **Precomputar/persistir** Wordle/Sopa/Crucigrama/Sudoku fuera de ventana de generación; congelar meses ya generados y servir desde caché/ETag.
12. **`$in`/aggregation y caché del catálogo narrativo** para reducir 5-7 round-trips por request a 1-2; extender `_RECURSOS_MAPA_CACHE` con invalidación.
13. **Endpoints de jugador sin `config.solution`** y payloads mínimos por juego.
14. **Reescribir `progresos` con updates dirigidos** (`arrayFilters`) o colección aparte; idem intentos con una sola operación.
15. **SMTP**: background task + conexión reutilizada.
16. **Revisar ruteo Caddy** de `/assets/narrative` y `/admin` con volumen compartido + `Cache-Control immutable`.

### Deuda estructural / opcional

17. Sustituir el limitador por Redis/SlowAPI si habrá N workers.
18. Contenerización: si se usa `--workers`, agregar lock distribuido para seeds/loop y revisar `_LETTER_POS_INDEX` (memoria ×N).
19. Migrar la caché RAE a Mongo/SQLite si supera ~1 MB.
20. Reducir `WebP method=6` a 4-5 y/o mover a worker.

---

## 4. Riesgos, supuestos y preguntas abiertas

### Supuestos del análisis
- **Despliegue single-worker**: se deduce de `Dockerfile:21` (sin `--workers`) y 1 servicio backend en `docker-compose.yml`. Todos los puntos de la sección 2.6 quedan latentes bajo este supuesto.
- **Caddy es el único portero** (`docker-compose.yml:3-34`) y no proxya `/assets/*` ni `/admin*` al backend. Si en producción existiera otro proxy/volumen compartido, H-20 cambia de severidad.
- **La RAE es la única dependencia HTTP externa** del código de aplicación (`urllib` es el único cliente HTTP además de SMTP). Se asumió que `RAE_API_KEY` puede estar vacía (no en `.env.example`).
- **Volumen de datos**: usuarios/catálogos narrativos pequeños hoy (≈decenas-cientos); `daily_challenges` crece a ~1.500 docs/año (4 juegos × 365). Nada indica borrados/archivado.
- **No se inspeccionó `.env` real** (solo `.env.example`) para no exponer secretos; valores como `SMTP_PASSWORD` importan para H-23.

### Riesgos identificados
- **Disponibilidad**: combinación H-01 + H-02 + H-03 = ventanas de segundos/minutos con el event loop bloqueado (healthcheck puede fallar y reiniciar el contenedor en bucle si el mes está incompleto).
- **Integridad de datos**: JSON de caché RAE sin escritura atómica; read-modify-write de `progresos` y de `narrative_runs` (lost updates con concurrencia).
- **Seguridad relacionada con rendimiento**: CORS `allow_origin_regex=r"^https?://.*$"` con `allow_credentials=True` (`main.py:94-95`), bypass del rate limit vía `X-Forwarded-For` falsificado (`rate_limit.py:49-53`), y soluciones de Sudoku/Crucigrama expuestas en respuestas de jugador (H-15). Se mencionan aquí por su vínculo con abuso y con el propio limitador; el detalle profundo corresponde a una auditoría de seguridad.
- **Costos**: 12 h loop + generación admin pueden multiplicar llamadas RAE y SMTP bajo reintentos.

### Preguntas abiertas
1. ¿Cuántos usuarios concurrentes/alumnos activos se esperan? Determina si bcrypt (H-05) y el listado admin (H-13) son urgentes.
2. ¿La `RAE_API_KEY` está configurada en producción? ¿Cuál es la tasa real de 429/timeouts?
3. ¿Se prevé escalar a `--workers >1` o múltiples réplicas? De lo contrario, H-19/H-26/H-27 bajan de prioridad pero igual conviene blindar seeds y loop.
4. ¿La generación de meses se dispara manualmente desde la Torre de Control con frecuencia? (default `force=True` es peligroso).
5. ¿Dónde se sirven finalmente `/assets/narrative/*` y `/admin` en producción: Caddy, backend o un CDN? ¿Se copian las imágenes del backend a `/srv`?
6. ¿El frontend consume `/api/challenges/month` con `until_today`? ¿Se usa todo el `config` o bastaría un resumen?

---

### Anexo A — Inventario rápido de llamadas bloqueantes encontradas
| Operación bloqueante | Ubicación | Invocada desde (async) |
|---|---|---|
| `urllib.request.urlopen` (hasta 3.5 s ×2 intentos × candidatos) | `rae_client.py:157` | `wordle_generator.py:51`, `sopa_generator.py:179`, `crucigrama_generator.py:1071` → startup/loop/endpoint |
| `time.sleep(1.2)` en 429 | `rae_client.py:183` | idem |
| `json.dump` completo de la caché | `rae_client.py:58` | tras cada definición nueva |
| `open()+json.load` 236 KB + indexado | `crucigrama_generator.py:829-837` | primera generación de crucigrama |
| `bcrypt.checkpw/hashpw` (~50-100 ms) | `security.py:16-26` | login/registro/arranque |
| PIL decode + LANCZOS + WebP | `image_service.py:58-78` | upload admin |
| Backtracking Sudoku (unicidad ×81) | `sudoku_generator.py:33-112` | generación de mes (startup/endpoint) |
| Backtracking CSP Crucigrama (150×rama) | `crucigrama_generator.py:928-985` | generación de mes |
| `random.seed` global | `sopa_generator.py:118`, `seed_sopa_letras.py:115` | generación de sopa/seeds |

### Anexo B — Métricas sugeridas para validar (cuando se pueda ejecutar)
- Duración del lifespan (`startup` → primera request) y número de documentos escritos por arranque.
- p95 de latencia de `/api/auth/login-sistemas` y `/api/auth/register` (bcrypt + SMTP).
- Duración de `generate-month` por juego; cantidad de llamadas RAE y colisiones 429 (log `[RAE]`).
- Memoria del proceso tras N días (rate limiter, cachés, `definiciones_cache.json`).
- Tamaño de payload de `/api/challenges/month?game_id=sudoku`.
- Tiempo del tick de 12 h (log `[AUTOGENERACIÓN]`).
