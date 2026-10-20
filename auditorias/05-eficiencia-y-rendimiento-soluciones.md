# 05 — Eficiencia y Rendimiento: Plan de Soluciones

- **Proyecto**: Mayores Actualizaciones (SIPI) — Backend FastAPI + MongoDB (Motor async)
- **Ruta raíz**: `C:\Users\nmonti\Desktop\proyectos\backend\mayores_actualizacionesSIPI-BACK`
- **Basado en**: [Auditoría 05 — Eficiencia y Rendimiento](05-eficiencia-y-rendimiento.md) (29 hallazgos H-01..H-29), con insumos de [00 — Informe consolidado](00-informe-consolidado.md) y [02 — Persistencia y flujo de datos](02-persistencia-y-flujo-de-datos.md).
- **Fecha**: 19/10/2026
- **Estado**: **PLANIFICACIÓN — NADA DE ESTO ESTÁ IMPLEMENTADO AÚN.** Este documento describe *cómo* se resolvería cada hallazgo. No se modificó código, tests ni configuración; no se ejecutó la app, ni benchmarks, ni la base de datos. Todas las referencias `archivo:línea` corresponden al estado auditado.
- **Alcance del plan**: event loop, generación de desafíos, RAE, CPU-bound, MongoDB (lecturas/proyecciones/paginación/seeds), cachés, escalabilidad N>1, SMTP, Caddy y plan de validación.

---

## 1. Resumen ejecutivo y estrategia

El informe 05 identifica tres causas raíz que explican casi todos los problemas de rendimiento:

1. **Trabajo pesado dentro del event loop**: el cliente RAE es sincrónico (`urllib` + `time.sleep`), los generadores (Sudoku, Crucigrama, Sopa, Wordle) son CPU-bound, y bcrypt/Pillow son bloqueantes. Con **un solo worker uvicorn**, cualquier operación bloqueante congela *toda* la API (`Dockerfile:21`, sin `--workers`).
2. **Generación pesada en rutas críticas**: el lifespan (`app/main.py:36-42`) y el endpoint admin `generate-month` (`daily_challenges/router.py:99-113`, `force=True` por defecto) ejecutan la generación mensual completa (RAE + sleeps + CPU) antes de responder.
3. **Estado y datos sin disciplina de escala**: `get_current_user` trae el documento completo, cachés en memoria sin invalidación/limpieza, caché RAE reescrita completa por palabra, seeds que reescriben ~185 documentos por arranque, paginación `skip`+`count` sin índices.

### Estrategia (quick wins primero)

| Orden | Movimiento | Efecto |
|---|---|---|
| 1 | **Desbloquear el event loop** con `asyncio.to_thread` (RAE, generadores, bcrypt, Pillow) y quitar `time.sleep` | La API deja de congelarse; mejora visible en horas de trabajo |
| 2 | **Sacar la generación del camino crítico**: lifespan no bloqueante + `generate-month` con `force=False` por defecto y en background con estado consultable | Arranque y panel admin dejan de degradar la disponibilidad |
| 3 | **RAE async con caché de dos niveles** (memoria + archivo atómico con TTL), batching de palabras y fallback | Generación de meses viable sin depender de la latencia de la RAE |
| 4 | **Datos**: proyecciones, índices/paginación, una sola operación por intento, seeds check-first | Menos bytes, menos round-trips, arranques predecibles |
| 5 | **Cachés y coordinación N>1**: rate limiter acotado, invalidación por versión, locks en Mongo, decisión futura de Redis | Habilita escalar workers/réplicas sin duplicar trabajo |

**Cifra orientativa**: Fases 0–2 (todo lo que resuelve los hotspots con impacto real) ≈ **4 a 6 semanas-persona**; Fase 3 (escala estructural, Redis/proceso de generación) ≈ **1 a 3 semanas-persona** adicionales, sujeta a decisión. Estimaciones gruesas (±50%), sin contar los planes 01/02/03/06 con los que hay dependencias.

### Coordinación con otros planes (no pisar soluciones)

- **Plan 02 (persistencia)**: es dueño del diseño final de índices, atomicidad de `progresos`/`narrative_runs` y manejo de errores de arranque (A1/A2/A8 de 02). Este plan **no duplica** la lista de índices: aporta los criterios que esos índices deben cumplir (paginación/orden/seeds). MON-2/MON-4/MON-6 se ejecutan en conjunto con 02.
- **Plan 03 (seguridad)**: la auth del admin es requisito para exponer `generate-month` en background con estado y para el endpoint admin de payloads (PAY-1). El fix de `X-Forwarded-For` y del PIN pertenece a 03; acá solo se mitiga el crecimiento del limiter.
- **Plan 01 (arquitectura)**: la extracción de generadores/duplicación de Sopa (seed vs generador) y la modularización del narrativo simplifican CPU-3 y MON-3.
- **Plan 06 (testing)**: los criterios de aceptación de cada solución se apoyan en los tests/contract tests que define 06; sin ellos, "no romper comportamiento" es solo una intención.

---

## 2. Principios rectores

1. **No romper comportamiento observable.** Todos los cambios preservan contratos del frontend salvo los explícitamente marcados (p. ej. `generate-month` 202 + estado; payload de jugador sin solución). Los cambios de contrato requieren actualización conjunta del cliente y quedan listados en §7.
2. **Quick wins primero, con flag y rollback.** Cada cambio relevante va detrás de una variable de entorno o es trivialmente revertible (`git revert` + flag). Nada exige migración de datos irreversible.
3. **Medir después de implementar (con baseline previo).** No se micro-optimiza a ciegas: antes de tocar cada hotspot se captura una línea base en un entorno de prueba autorizado; cada solución define criterios de aceptación medibles (§6). *En esta etapa de planificación no se ejecuta nada.*
4. **Lo bloqueante no vive en el event loop.** Regla general para todo el backend: si una operación tarda > ~10 ms de CPU o hace I/O sincrónico, va a `asyncio.to_thread`/executor o se refactoriza a async.
5. **La generación es un job, no una request.** La generación mensual y el tick de 12 h se ejecutan fuera del request path, con idempotencia y lock en Mongo; nunca antes del `yield` del lifespan.
6. **Una sola fuente de verdad para coordinación N>1.** Locks/leases en MongoDB (ya es infraestructura existente). Redis queda como **decisión futura** explícita (§7), no como dependencia de este plan.
7. **Nada nuevo sin necesidad.** Se propone `httpx` (cliente RAE async) por ser estándar y liviano; cualquier otra dependencia (Redis, cachetools, etc.) se evalúa y decide antes de agregarla.
8. **Cambios chicos, verificables y en orden.** Cada solución lista archivos, pasos, aceptación, riesgos y rollback para poder ejecutarse de a una y validarse por separado.

---

## 3. Tabla resumen

**Leyenda** — Impacto: alto/medio/bajo (según informe 05). Esfuerzo: S (horas–1 día), M (1–3 días), L (3+ días). Fase: 0 quick wins, 1 respuesta/background, 2 datos/consistencia, 3 escala estructural.

| Hallazgo | Solución(es) | Impacto | Esfuerzo | Riesgo | Fase |
|---|---|---|---|---|---|
| H-01 RAE sincrónico (`urlopen`+`time.sleep`) | RAE-1 (thread/quitar sleep), RAE-2 (httpx async + batch) | Alto | S / M | Medio (cambio de cliente HTTP) | 0 / 1 |
| H-02 Generación en el lifespan | GEN-1 (task post-arranque + flag) | Alto | S | Bajo | 0 |
| H-03 Generación en request path (`force=True`) | GEN-2 (202 + job + lock + force=False) | Alto | M | Medio (contrato admin) | 0–1 |
| H-04 CPU-bound Sudoku/Crucigrama en loop | CPU-2 (to_thread), CPU-3 (precómputo/límites/proceso) | Alto | S / L | Medio (concurrencia de hilos) | 1 / 2 |
| H-05 bcrypt sincrónico | CPU-1 (`to_thread`) | Alto | S | Bajo | 0 |
| H-06 Pillow WebP en async | CPU-1 (`to_thread`, método WebP) | Alto | S | Bajo | 0 |
| H-07 Caché RAE reescrita completa | RAE-3 (dos niveles, `os.replace`, debounce, TTL) | Alto | M | Bajo | 1 |
| H-08 `random.seed()` global | CPU-2 (`random.Random(seed)` local) | Bajo (hoy) / Medio (con hilos) | S | Bajo | 1 |
| H-09 `asyncio.sleep` de generación | RAE-2/GEN-3 (eliminar sleeps al haber rate limit propio) | Medio | S | Bajo | 1 |
| H-10 `get_current_user` sin proyección | MON-1 (proyección mínima) | Alto | S | Bajo | 0 |
| H-11 `progresos` read-modify-write | MON-2 (update dirigido `arrayFilters`/$push guardado) | Medio | M | Medio (semántica de conflicto) | 2 |
| H-12 Doble lectura en intentos | MON-2 (una sola `find_one_and_update`) | Medio | M | Bajo | 2 |
| H-13 Paginación `skip`+`count` sin índice | MON-4 (keyset + índices, coord. plan 02) | Medio | M | Medio (contrato admin) | 2 |
| H-14 `to_list(None)` | MON-5 (límites + proyecciones) | Bajo–Medio | S | Bajo | 2 |
| H-15 Payloads de mes con solución | PAY-1 (endpoint jugador sin solución + admin + caché/ETag) | Medio | M | Medio (contrato) | 2 |
| H-16 5–7 round-trips narrativo | MON-3 (`$in`/gather + catálogo cacheado), CAC-2 | Bajo–Medio | S / M | Medio (consistencia caché) | 2 |
| H-17 Ausencia de índices puntuales | MON-4/IDX-1 (coord. plan 02 dueño de índices) | Medio si crece | S | Bajo | 2 |
| H-18 Seeds reescriben ~185 docs por arranque | MON-6 (check-first + `bulk_write` + `$setOnInsert`), GEN-1 | Alto | S–M | Bajo | 0 / 2 |
| H-19 Loop 12 h sin coordinación | GEN-3 (lease Mongo, single scheduler) | Alto (N>1) | M | Medio | 2 |
| H-20 Caddy no rutea `/assets/narrative` | CAD-1 (ruta + `Cache-Control immutable` + volumen) | Medio | S | Bajo | 1 |
| H-21 `init_indexes` en cada arranque | IDX-1 (try/except por índice; aceptar costo) | Bajo | S | Bajo | 2 |
| H-22 `generar_mes_narrativo` secuencial | MON-6 (bulk + proyección de ids) | Bajo | S–M | Bajo | 2 |
| H-23 SMTP sin pooling en request path | EXT-1 (background + timeout; pooling fase 2) | Medio–Alto | S–M | Medio (entrega de correos) | 1 |
| H-24 RAE sin API key (más 429) | RAE-2 (manejo 429 async + métricas); config key (decisión §7) | Medio | S | Bajo | 1 |
| H-25 Timeouts/retries RAE mejorables | RAE-2 (retry con backoff+jitter, límite por lote) | Bajo | S | Bajo | 1 |
| H-26 Rate limiter sin límite de crecimiento | CAC-1 (purga periódica + cap + TTL; store compartido en 3) | Alto (N>1) | S | Bajo | 0 / 3 |
| H-27 Cachés globales sin invalidación | CAC-2 (versión + TTL corto + tamaños acotados) | Medio | M | Medio | 2 |
| H-28 `_load_definitions_cache` por fetch | RAE-3 (flag de cargado/`lru_cache`) | Bajo | S | Bajo | 1 |
| H-29 Estado global mutable (DB singleton) | Sin acción (documentado) | Bajo | — | — | — |

---

## 4. Soluciones detalladas

> Formato de cada solución: **Enfoque** (qué se haría, sin aplicarlo) · **Archivos a tocar** · **Pasos** · **Criterios de aceptación** · **Riesgos y mitigación** · **Rollback** · **Dependencias** · **Esfuerzo/Impacto**.

### 4.1 Cliente RAE (H-01, H-07, H-09, H-24, H-25, H-27, H-28)

#### RAE-1 — Desbloquear el event loop ya: quitar `time.sleep` y sacar la latencia RAE del hilo principal (Fase 0, esfuerzo S, impacto alto)

- **Enfoque**: paso inmediato de bajo riesgo sin cambiar de librería.
  1. Eliminar `time.sleep(1.2)` de `rae_client.py:183` (reintento 429): en el escenario transitorio devolver `None` rápido y registrar el 429; el reintento con backoff real llega con RAE-2. Si se quiere conservar el reintento antes de RAE-2, que sea un segundo intento inmediato (sin sleep) o `time.sleep` **dentro de un thread** (nunca en el loop).
  2. Mover la frontera de bloqueo al contexto async que corresponda: mientras los generadores sigan siendo funciones sync, el offload se hace al invocarlos completos desde `service.py` con `await asyncio.to_thread(...)` (es exactamente CPU-2; ver 4.3). Si se prefiere un cambio aún más chico, envolver en `to_thread` los 3 puntos de llamada que ya son alcanzables desde código async (no es posible llamar `await` dentro de los generadores sync: por eso la unidad de offload es el generador).
  3. Añadir flag de emergencia `RAE_ENABLED` (default `true`): con `false`, `fetch_rae_definition` devuelve `None` y los generadores usan pistas de fallback (comportamiento ya existente en `wordle_generator.py:56-59`, `sopa_generator.py:182-183`).
- **Archivos a tocar**: `app/core/rae_client.py` (sleep, flag), `app/features/daily_challenges/service.py` (offload de generadores, ver CPU-2).
- **Pasos**: quitar el sleep → agregar flag `RAE_ENABLED` → cubrir con un caso de prueba manual documentado (definición cacheada vs fallback) → recién después tocar la frontera de threads (CPU-2).
- **Criterios de aceptación**: durante una generación con RAE lenta/caída, `/health` responde en < 250 ms p95; el log no muestra `[RAE] Esperando 1.2s` en el hilo del loop; el resultado funcional (pistas/definiciones) no cambia cuando la RAE responde.
- **Riesgos y mitigación**: más 429 al no esperar → mitigado porque el reintento real llega en RAE-2 y porque `RAE_ENABLED=false` permite apagar la dependencia; si el offload se hace mal (llamar sync dentro de async), no hay mejora → criterio verificable con log de `threading.current_thread().name`.
- **Rollback**: restaurar el sleep y quitar el flag (cambio de pocas líneas).
- **Dependencias**: CPU-2 (frontera de threads); RAE-2 lo sustituye de forma estructural.
- **Esfuerzo/Impacto**: **S / alto**.

#### RAE-2 — Cliente RAE asíncrono con timeout, retry, semáforo, batching y fallback (Fase 1, esfuerzo M, impacto alto)

- **Enfoque**: reemplazar `urllib`+`time.sleep` por un cliente `httpx.AsyncClient` único y reutilizable (creado en el lifespan, cerrado en shutdown) con:
  - **Timeout**: total ~3.5–5 s (`httpx.Timeout(4.0, connect=2.0)`), explícito y documentado.
  - **Retry**: máximo 2 intentos por candidato con backoff exponencial + jitter (0.5 s, 1 s ± 30%), solo para 429/5xx/errores de red; honrar `Retry-After` cuando venga; **nada de sleep bloqueante**.
  - **Concurrencia**: `asyncio.Semaphore(3)` para acotar llamadas simultáneas a la RAE (protege la cuota y ordena el tráfico); `httpx.Limits(max_connections=5, max_keepalive_connections=2)`.
  - **Circuit breaker + negative cache**: tras N fallos consecutivos (p. ej. 5 en 30 s), abrir el circuito por M minutos (p. ej. 10): todas las consultas devuelven `None` sin pegarle a la RAE; cada palabra no encontrada/fallida se registra con TTL corto (1–6 h) para no repetir el costo. Métricas por log: llamadas, cache hits, 429, timeouts, circuito abierto.
  - **Batching de palabras**: nueva función `fetch_many(words) -> Dict[str, Optional[str]]` que deduplica, saltea lo que ya está en caché, consulta el resto con el semáforo y devuelve un mapa. La generación mensual **junta primero todas las palabras del mes** (Wordle: 31; Sopa: 31×4; Crucigrama: 31×N) y hace un solo lote antes de la parte CPU. Los generadores dejan de llamar `fetch_rae_definition` palabra por palabra: reciben un mapa de definiciones ya resuelto (o lo piden a un helper async antes del cómputo).
  - **Fallback sin RAE**: política explícita: si RAE-2 no consigue definición en el lote (o el circuito está abierto), los generadores usan la pista estática/fallback existente (Sopa ya lo hace; Wordle usa vocales+última letra; Crucigrama cae a pistas curadas). El flujo de generación **nunca falla por la RAE**.
  - **Separación CPU/IO**: con el mapa de definiciones ya resuelto en async, el armado del desafío (CPU puro) se ejecuta en thread (CPU-2), sin I/O dentro del thread.
- **Archivos a tocar**: `app/core/rae_client.py` (reescritura del fetch y de la carga de acentos), `app/features/daily_challenges/wordle_generator.py`, `sopa_generator.py`, `crucigrama_generator.py` (consumir batch), `app/features/daily_challenges/service.py` (orquestación del lote), `app/main.py` (crear/cerrar el cliente, o helper `close_http_clients`).
- **Pasos**: (1) introducir `fetch_many` async conviviendo con el fetch sync (feature flag `RAE_ASYNC_ENABLED`); (2) migrar Sopa (más palabras por día) y probar equivalencia; (3) migrar Wordle y Crucigrama; (4) apagar el path sync y borrar el sleep; (5) eliminar los `asyncio.sleep` de `service.py:409/493/577` (ver GEN-3), que existían para no saturar la RAE.
- **Criterios de aceptación**: 0 llamadas bloqueantes al loop (verificable con lag del loop durante generación); duplicados de consulta por palabra = 0 dentro de un lote (métrica de cache hits + llamadas); un mes de Crucigrama con RAE caída termina con fallback y sin excepciones; 429 no produce pausas > 1 s por palabra (backoff máximo configurable); tiempo de generación de un mes con la RAE sana no aumenta vs. línea base sync (medido, no estimado).
- **Riesgos y mitigación**: cambio de cliente HTTP puede alterar headers/UA → mantener `User-Agent` y `X-API-Key` iguales; semáforo demasiado bajo alarga la generación → valor configurable (`RAE_MAX_CONCURRENCY`); circuit breaker enmascara una RAE recuperada → half-open con 1 sonda tras el periodo.
- **Rollback**: flag `RAE_ASYNC_ENABLED=false` vuelve al path sync envuelto en thread (RAE-1/CPU-2). No hay migración de datos.
- **Dependencias**: RAE-3 (la caché es parte del mismo módulo), CPU-2 (separación CPU/IO), plan 03 (política de secretos de `RAE_API_KEY`), decisión de hardware de §7 (¿hay key?).
- **Esfuerzo/Impacto**: **M / alto**.

#### RAE-3 — Caché de dos niveles con escritura atómica, TTL, debounce y negative cache (Fase 1, esfuerzo M, impacto medio-alto)

- **Enfoque**:
  - **Nivel 1 (memoria)**: diccionario en proceso con cota (p. ej. `cachetools.TTLCache(maxsize=10_000, ttl=90 días)` para definiciones encontradas; `TTLCache(maxsize=5_000, ttl=6 h)` para negativas/fallos). Si no se agrega dependencia, diccionario + LRU casero + expiración por entrada.
  - **Nivel 2 (archivo JSON)**: `definiciones_cache.json` con **escritura atómica**: se serializa a `definiciones_cache.json.tmp` en el mismo directorio y se hace `os.replace(tmp, final)` (atómico en POSIX/NTFS). **Debounce**: marcar `dirty` y persistir como máximo cada 5 s o cada 20 entradas nuevas (evita el O(n²) actual de `json.dump` por palabra, H-07). Un `asyncio.Lock` o `threading.Lock` serializa el volcado.
  - **TTL y versión de caché**: entrada con `_meta` (`version`, `saved_at`); TTL largo para definiciones (90 días) y corto para negativas. Al cargar, descartar entradas vencidas para que el archivo no crezca sin control.
  - **Formato**: quitar el `indent=2` (menos bytes y más rápido); considerarlo solo si hace falta inspección manual (alternativa: comando CLI que lo formatea).
  - **`_load_definitions_cache` una sola vez** (H-28): flag booleano de cargado o `functools.lru_cache`; idem `_load_acentos_map`.
  - **N>1 (Fase 2/3)**: con más de un proceso, el archivo sigue siendo seguro por la escritura atómica (last-write-wins aceptable en una caché), pero cada proceso tiene su nivel 1 y el archivo vive en el filesystem del contenedor (efímero). Decisión futura: mover la caché a Mongo (`rae_definitions`, upsert `$setOnInsert`) o montar volumen; se decide en §7 y se implementa en Fase 3 (ver ESC-1).
- **Archivos a tocar**: `app/core/rae_client.py` (única pieza central; expone `get_cached`, `put_cached`, `flush_if_dirty`), tarea periódica de flush (puede colgarse de la tarea de mantenimiento de GEN-1) para no perder el debounce al apagar.
- **Pasos**: (1) implementar nivel 1 con cota; (2) escritura atómica + debounce; (3) TTL y limpieza al cargar; (4) test manual con archivo corrupto (debe degradar a caché vacía + warning, comportamiento ya existente que se preserva); (5) evaluar migración a Mongo cuando el archivo supere ~1 MB (métrica).
- **Criterios de aceptación**: `json.dump` completo ≤ 1 vez cada 5 s durante una generación (hoy es 1 por palabra); 0 ventanas de archivo corrupto tras matar el proceso a mitad de escritura (prueba con kill durante generación); el archivo nunca supera un tamaño objetivo (p. ej. 5 MB) y purga entradas vencidas; `_load_definitions_cache` no re-lee disco en cada fetch.
- **Riesgos y mitigación**: debounce puede perder el último flush si el proceso muere → flush también en shutdown y cada 5 s como máximo, con `os.replace` el peor caso es perder las últimas ~20 entradas, no corromper; caché negativa demasiado agresiva oculta definiciones recuperables → TTL 1–6 h configurable y sonda cada N fallos.
- **Rollback**: flag `RAE_CACHE_V2=false` vuelve a la persistencia por escritura directa (no atómica) manteniendo compatibilidad de formato (el formato no cambia, solo el guardado).
- **Dependencias**: RAE-2; CAC-2 comparte el patrón "flag de versión"; ESC-1 para la decisión multi-proceso.
- **Esfuerzo/Impacto**: **M / medio-alto**.

### 4.2 Generación mensual pesada (H-02, H-03, H-09, H-18, H-19)

#### GEN-1 — Arranque no bloqueante: seeds y generación como tarea de mantenimiento post-listening (Fase 0, esfuerzo S, impacto alto)

- **Enfoque**: el lifespan deja de esperar la generación. Secuencia propuesta:
  1. En el lifespan (antes del `yield`) quedan solo los pasos **rápidos y necesarios para servir**: `connect_to_mongo()` + `init_indexes()` + `seed_estados_usuario()` + `seed_default_admin()`, cada uno con `try/except` + log (coord. plan 02 A8; un fallo ya no debe impedir el arranque del resto).
  2. El bloque pesado (`seed_wordle_challenges`, `seed_sopa_letras_challenges`, `seed_sudoku_challenges`, `ensure_current_and_next_month_generated`, `sembrar_finalizaciones_default`) se mueve a una corrutina `_startup_maintenance()` lanzada con `asyncio.create_task(...)` (guardar referencia y cancelar en shutdown, igual que hoy con `checker_task`), con un pequeño delay inicial (p. ej. 3–5 s) para que el healthcheck pase primero.
  3. Flags: `STARTUP_GENERATION_ENABLED` (default `true`), `STARTUP_SEEDS_ENABLED` (default `true`). Con `false`, el arranque solo conecta/indexa/siembra lo mínimo y la generación queda a cargo del scheduler (GEN-3) o de un runbook manual.
  4. `_startup_maintenance` ejecuta cada paso con `try/except` individual y log de duración; un fallo de la RAE ya no tumba el arranque (hoy sí, A8 de 02).
- **Archivos a tocar**: `app/main.py` (lifespan), tareas `app/features/daily_challenges/service.py:590-631` (sin cambios de lógica en este paso), seeds en `app/scripts/`.
- **Pasos**: extraer el bloque pesado a una función async → lanzarla como task → agregar flags → validar que `/health` responde con la generación aún en curso (log de secuencia) → cubrir con test de arranque (plan 06).
- **Criterios de aceptación**: `/health` responde 200 en < 2 s desde que el puerto escucha, aunque la generación tarde minutos; el lifespan completa en < 5 s con `STARTUP_GENERATION_ENABLED=true`; con `false`, el proceso queda listo sin generar y el log indica que el mantenimiento está deshabilitado; ninguna excepción de la task queda sin loguear.
- **Riesgos y mitigación**: tareas huérfanas si el proceso muere → mantener referencia + cancel en shutdown + logs de inicio/fin; la generación temprana compite con tráfico de arranque → el delay inicial y el semáforo RAE-2 lo acotan; doble generación con N>1 → la resuelve GEN-3 (lease) y GEN-2 (lock).
- **Rollback**: flag `STARTUP_GENERATION_ENABLED=false` + revertir el orden del lifespan (vuelve al arranque bloqueante actual).
- **Dependencias**: MON-6 (seeds check-first: sin esto, la task no bloqueante sigue reescribiendo 185 docs), GEN-3 (coordinación N>1), plan 02 A8.
- **Esfuerzo/Impacto**: **S / alto**.

#### GEN-2 — `generate-month` como job de background con estado consultable, lock por mes y `force=False` por defecto (Fase 0–1, esfuerzo M, impacto alto)

- **Enfoque**:
  1. **Quick win (Fase 0)**: cambiar `force: bool = Query(True)` a `Query(False)` en `daily_challenges/router.py:103`. Regenerar pasa a ser una acción explícita.
  2. **Estructural (Fase 1)**: el endpoint responde **202 Accepted** con `{job_id, status:"queued", game_id, year, month}` y la generación corre fuera del request:
     - Colección `generation_jobs` en Mongo: `{_id: job_id, game_id, year, month, force, status: queued|running|done|error|partial, requested_by, created_at, started_at, finished_at, generated_count, processed_days, total_days, errors[], locked_until}` con índice TTL (p. ej. 30 días) y los jobs activos visibles para el panel.
     - **Lock por `(game_id, year, month)`**: antes de aceptar un job se intenta `find_one_and_update` sobre `generation_locks` (`_id: "gen:game:year-month"`, `$setOnInsert` + `locked_until = now + lease`); si ya hay lock vigente, se devuelve **409 Conflict** con el `job_id` en curso (o se devuelve el job existente si es idempotente el pedido, a definir en §7). El lock usa lease (p. ej. 30 min renovable) para no quedar trabado si el proceso muere.
     - **Ejecución**: el proceso que atiende crea la task; la task re-adquiere/renueva el lease, ejecuta la generación día por día (idempotente: los `skip` por día existentes se conservan), actualiza progreso en el job doc y libera el lock al terminar. En N>1 cualquier instancia puede ser la ejecutora, pero **solo una** por combinación clave gracias al lock.
     - **Reaper**: tarea periódica (cada 5 min) que marca `error` los jobs `running` con lease vencido (opcionalmente los reencola).
     - **Estado consultable**: `GET /api/challenges/admin/generate-month/status/{job_id}` (y listado de jobs recientes) con auth de admin (dependencia plan 03). Mientras la auth no exista, el plan 03 debe cerrarse **antes** de exponer este endpoint.
     - **Validaciones**: whitelist de `game_id`, rango de meses acotado (p. ej. solo dentro de [mes actual−1, mes actual+2] para no admins) y límite de jobs concurrentes por proceso.
     - **Fallo parcial tolerante**: un día que falle no aborta el mes; se registra en `errors[]` y el job termina `partial` con el detalle (hoy cualquier excepción corta todo).
- **Archivos a tocar**: `app/features/daily_challenges/router.py`, `app/features/daily_challenges/service.py`, nuevo `app/features/daily_challenges/jobs.py` (o `generation_service.py`), `app/core/database.py` (índices TTL/locks se definen con plan 02), `app/main.py` (reaper en la task de mantenimiento).
- **Pasos**: force=False (ya en Fase 0) → crear colección/job doc + lock → implementar executor idempotente con progreso → endpoint de estado → reaper → actualizar la Torre de Control (fuera de este repo: coordinar frontend) → pruebas de doble submit concurrente.
- **Criterios de aceptación**: el POST responde en < 500 ms (202) sin bloquear el loop; dos submits concurrentes del mismo `(game_id, mes)` producen **un solo** job ejecutado (el segundo recibe 409 o el mismo job); un mes completo ya generado con `force=false` termina `done` con `generated_count=0`; matar la instancia a mitad deja el job recuperable (lease) y no bloquea futuros submits; `/health` p95 estable durante toda la generación.
- **Riesgos y mitigación**: jobs zombis → lease + reaper; doble ejecución por carrera de reaper → el lock con `find_one_and_update` es la autoridad; cambio de contrato para el panel → coordenar con frontend y mantener una respuesta de compatibilidad temporal (opción: modo `sync=true` temporal detrás de flag para paneles viejos, deprecado); generación sin auth sigue siendo superficie sensible → plan 03 primero.
- **Rollback**: flag `GENERATE_MONTH_ASYNC=false` restaura el comportamiento síncrono (202→200) manteniendo `force=false`; los jobs docs no estorban (TTL).
- **Dependencias**: RAE-1/2 y CPU-2 (para que el job no bloquee igual), GEN-3 (lease compartido), plan 02 (índices/TTL), plan 03 (auth admin), frontend Torre de Control.
- **Esfuerzo/Impacto**: **M / alto**.

#### GEN-3 — Tick de 12 h con lease/single-scheduler y sin sleeps artificiales (Fase 2, esfuerzo M, impacto alto en N>1)

- **Enfoque**:
  1. Reemplazar `_auto_check_loop` (`main.py:50-62`) por una tarea que (a) corre su primera verificación poco después del arranque (p. ej. 10 min después de `_startup_maintenance`, con jitter ±10%), y (b) repite cada 12 h. Hoy duerme **primero** (si el arranque falla, no se reintenta hasta 12 h — A8 de 02).
  2. **Coordinación N>1**: antes de ejecutar `ensure_current_and_next_month_generated`, adquirir un lease en Mongo (`scheduler_lease` con `_id: "auto_ensure"`, `locked_until`); si otra instancia lo tiene, salir logueando `skip`. El lease se renueva durante la ejecución y se libera al final. Alternativa soportada: `AUTO_GENERATION_ENABLED=false` en todas las instancias y un cron externo que llame a un comando/endpoint (runbook), decisión en §7.
  3. **Jitter y backoff**: intervalo 12 h ± jitter; ante excepción, reintento con backoff exponencial acotado (hoy duerme 1 h fijo) y registro del error.
  4. **Eliminar los `asyncio.sleep` por día** de `service.py:409/493/577` una vez que RAE-2 esté en producción (el rate limit propio reemplaza la pausa). Mientras RAE-2 no esté, los sleeps se mantienen pero el loop ya no está bloqueado por RAE (RAE-1/CPU-2).
  5. El tick reutiliza el mismo executor/lock de GEN-2 para no duplicar lógica: `ensure_...` pasa a encolar jobs por juego/mes faltante en vez de generar inline.
- **Archivos a tocar**: `app/main.py`, `app/features/daily_challenges/service.py` (ensure + sleeps), nuevo `app/core/locks.py` (helper de lease reutilizable por GEN-2/GEN-3/seeds).
- **Pasos**: helper de lease → migrar el loop → encolar jobs en vez de generar inline → quitar sleeps → prueba con dos instancias simuladas (dos procesos locales) verificando que solo una ejecuta.
- **Criterios de aceptación**: con 2 procesos, exactamente 1 ejecuta el tick y el otro loguea `skip` (prueba controlada); primera verificación ≤ 15 min tras el arranque; no hay generaciones duplicadas del mismo mes (comparar `generated_count`/jobs); duración del tick acotada y registrada.
- **Riesgos y mitigación**: relojes desfasados entre contenedores → lease basado en hora del **servidor Mongo** (`$$NOW`/`$currentDate`) o tolerancia amplia; lease demasiado corto → renovación periódica durante la ejecución; si Mongo no está, el tick se saltea con log (la API sigue).
- **Rollback**: `AUTO_GENERATION_ENABLED=false` y `git revert` del loop (el comportamiento anterior vuelve con un solo worker).
- **Dependencias**: GEN-2 (executor/lock), plan 02 A8, decisión §7 sobre scheduler externo vs lease.
- **Esfuerzo/Impacto**: **M / alto (N>1), medio (single-worker)**.

### 4.3 CPU-bound en el event loop (H-04, H-05, H-06, H-08)

#### CPU-1 — bcrypt y Pillow a `asyncio.to_thread` (Fase 0, esfuerzo S, impacto alto)

- **Enfoque**: envolver las llamadas sincrónicas puntuales sin cambiar su lógica:
  - `verify_password` / `get_password_hash` en `app/features/auth/service.py:76` y `:243` (y el uso de arranque en `init_db.py:73`) → `await asyncio.to_thread(verify_password, ...)` / `to_thread(get_password_hash, ...)`. Opcional: cambiar la firma de `security.py` a `async def verify_password(...)` que internamente use `to_thread` (una sola vez, sin tocar cada llamador) — se elige esta variante si hay más de 2 llamadores.
  - Pillow en `narrative/admin/image_service.py:53-84`: extraer el cuerpo CPU/IO a `def _procesar_imagen(contenido, cat_lower) -> dict` (todo sync: decode, resize LANCZOS, save WebP) y llamar `await asyncio.to_thread(_procesar_imagen, contenido, cat_lower)`. El `await file.read()` ya es async y se mantiene antes.
  - Ajustes de costo: `method=6` → configurable (`WEBP_METHOD`, default 4–6); límite de tamaño de entrada (p. ej. 10 MB, alineado con Caddy `max_size 10MB`); no re-codificar si el archivo ya es WebP y cumple dimensiones (opcional).
- **Archivos a tocar**: `app/core/security.py` (si se opta por firmas async), `app/features/auth/service.py`, `app/scripts/init_db.py`, `app/features/narrative/admin/image_service.py`, `app/core/config.py` (flags nuevos).
- **Pasos**: envolver bcrypt → envolver Pillow → agregar límite de tamaño y flag de método WebP → medir lag del loop en login y upload.
- **Criterios de aceptación**: 10 logins concurrentes no elevan `/health` p95 por encima de ~200 ms (hoy se serializan ~0.5–1 s); un upload de imagen de 8–10 MB no congela otras requests (mismo criterio de lag); el hash sigue siendo verificable (compatibilidad `$2a$/$2b$` intacta); la imagen resultante mantiene dimensiones/calidad equivalentes (comparación visual/manual).
- **Riesgos y mitigación**: el threadpool default de anyio (40 hilos) se comparte con RAE/generadores → definir semáforos por clase (CPU-2) y, si se satura, subir `total_tokens` de forma medida; `to_thread` no reduce la CPU total, solo libera el loop → el límite `cpus: 1.50` del compose sigue siendo el techo real (coord. ESC-1).
- **Rollback**: revertir los `await to_thread(...)` (2–3 puntos) detrás de flag `THREADED_BLOCKING=false` si se quiere mitigación instantánea.
- **Dependencias**: plan 06 (test de login/registro existente o nuevo), ESC-1 (dimensionar pool).
- **Esfuerzo/Impacto**: **S / alto**.

#### CPU-2 — Generadores CPU-bound fuera del loop + `random.Random` local (Fase 1, esfuerzo S–M, impacto alto)

- **Enfoque**: mover la ejecución completa de los generadores a threads, con una estrategia por etapas:
  1. **Etapa rápida (compatible con RAE-1)**: en `service.py`, cada día se genera con `await asyncio.to_thread(generate_sudoku_for_date, date_str)`, `to_thread(generate_wordle_challenge, ...)` + `to_thread(generate_wordle_hints, ...)`, `to_thread(generate_sopa_challenge_for_date, ...)`, `to_thread(generate_crucigrama_challenge_for_date, ...)`. Mientras RAE siga sync, el thread cubre también la latencia de red (no bloquea el loop, ocupa un hilo).
  2. **Etapa estructural (con RAE-2)**: separar por generador la **parte I/O** (batch RAE async, en el loop) de la **parte CPU pura** (thread). Wordle/Sopa/Crucigrama reciben `definitions: Dict[str,str]` ya resueltas; la parte de cárcel/llave es determinista y sin I/O.
  3. **Corrección de concurrencia (H-08)**: reemplazar `random.seed(seed)` global en `sopa_generator.py:117-118` y `seed_sopa_letras.py:114-115` por `rng = random.Random(seed)` local y usar `rng` en `shuffle/choice` (como ya hace crucigrama en `:1114`). Es requisito para no contaminar el narrativo ni tener carreras al usar hilos.
  4. **Precalentamiento**: cargar `_init_word_index()` del crucigrama (236 KB + índices) y `_load_word_pool()` en la tarea de mantenimiento (dentro de `to_thread`), no lazy en medio de una request del admin (H-04); si el precalentamiento falla, el lazy actual sigue funcionando como fallback.
- **Archivos a tocar**: `app/features/daily_challenges/service.py`, `sudoku_generator.py`, `wordle_generator.py`, `sopa_generator.py`, `crucigrama_generator.py`, `app/scripts/seed_sopa_letras.py`, `app/main.py` (precalentamiento en mantenimiento).
- **Pasos**: random local primero (independiente) → to_thread por día en los 4 generadores → verificar determinismo (misma fecha ⇒ mismo tablero) → separar batch RAE (RAE-2) → precalentamiento → pruebas de concurrencia (dos generaciones simultáneas no se contaminan).
- **Criterios de aceptación**: durante la generación de un mes de Crucigrama/Sudoku, `/health` p95 < 300 ms y ninguna request normal supera ~1 s (lag del loop medido); los tableros generados para las mismas fechas antes/después son idénticos (test de regresión determinista por juego); dos generaciones concurrentes con la misma semilla producen el mismo resultado (sin contaminación de RNG).
- **Riesgos y mitigación**: el pool de hilos puede agotarse (generadores largos + bcrypt + Pillow + RAE) → separar generación en su propio executor (`ThreadPoolExecutor(max_workers=2)`) o directamente en proceso (CPU-3) y usar semáforo; GIL: el Sudoku/Crucigrama son Python puro, el thread no acelera el cómputo, solo libera el loop (aceptable para el objetivo: no congelar la API); tableros deterministas dependen de RNG → test dorado por fecha.
- **Rollback**: flag `GENERATORS_IN_THREAD=false` vuelve a la llamada directa.
- **Dependencias**: RAE-2 (etapa 2), CPU-3 (proceso), plan 01 (unificar el generador de Sopa duplicado — el fix de random debe aplicarse en ambos hasta que se unifique).
- **Esfuerzo/Impacto**: **S–M / alto**.

#### CPU-3 — Precómputo de artefactos, límites de trabajo por request y proceso separado (Fase 2, esfuerzo L, impacto medio)

- **Enfoque**:
  - **Artefactos estáticos**:
    - Índice del crucigrama: evaluar serializar `_WORDS_BY_LEN`/`_LETTER_POS_INDEX` con `pickle`/`msgpack` a `app/data/derived/` en tiempo de build, con invalidación por `mtime`/hash del diccionario. Medir antes/después: el índice vive en memoria por proceso (varios MB, H-27); el objetivo es no pagar su construcción en caliente y acotar memoria si se rediseña "por palabra" en vez de "por celda".
    - Tableros base: los templates de crucigrama ya son estáticos (`CRUCIGRAMA_TEMPLATES`); extender la idea: precomputar offline (script) los puzzles de un horizonte (p. ej. 12 meses) y persistirlos como artefactos versionados en Mongo/JSON, dejando la generación online solo como fallback. Es la misma familia que "precomputar un año de tableros" del informe 05.
  - **Límites de trabajo por request**:
    - Presupuesto por día y por mes: `asyncio.wait_for(to_thread(gen, ...), timeout≈30–60 s)` con fallo aislado por día (se registra y continúa); el mes no queda a medias silenciosamente.
    - Ventana de generación permitida (p. ej. [actual−1, actual+2]) para pedidos no admins; fuera de ventana → 400.
    - Tope de candidatos/iteraciones del backtracking configurable (`CRUCIGRAMA_MAX_CANDIDATES=150` hoy) + deadline interno (el solver corta y reintenta con otra plantilla antes que bloquear el hilo minutos).
    - Máximo de jobs de generación concurrentes por proceso (semáforo) para que la generación no monopolice el pool de threads.
  - **Proceso separado (donde aplique)**: para generación masiva offline o "rellenar el año", usar un proceso dedicado (contenedor `generation-worker` o `ProcessPoolExecutor`) con los generadores puros, dejando al API solo el disparo y la lectura de estado (GEN-2). Ventaja: aislamiento de CPU/GIL y de crashes. Se decide en Fase 2/3 con la métrica de lag bajo generación (si `--workers` o procesos se justifican).
- **Archivos a tocar**: `app/features/daily_challenges/crucigrama_generator.py` (índice serializable + límites), `sudoku_generator.py` (presupuesto), nuevo script `app/scripts/build_artifacts.py`, `app/core/config.py` (límites), compose/Dockerfile (si se separa worker, coord. plan 04).
- **Pasos**: medir costo de `_init_word_index` en caliente → prototipo de artefacto serializado + benchmark (cuando se autorice ejecutar) → límites por request → script de precómputo offline → evaluación de proceso separado con resultados de lag/CPU.
- **Criterios de aceptación**: primer crucigrama tras un reinicio no paga el indexado completo en una request de usuario (índice precargado o carga < 200 ms medidos); un día problemático no excede su presupuesto y el job reporta el error parcial; los límites devuelven 400/timeout controlado en vez de colgar la request; si se adopta proceso separado: p95 del API durante generación ≤ p95 en reposo + margen acordado (p. ej. +20%).
- **Riesgos y mitigación**: artefactos desactualizados respecto del diccionario → invalidación por hash + regeneración en build (CI, plan 06); precómputo masivo desincronizado con la curaduría (seeds manuales pisan fechas) → el precómputo respeta `force=false` y no pisa documentos existentes; timeout por día puede dejar meses incompletos → job `partial` + reintento en el tick.
- **Rollback**: los límites son flags; el artefacto es opcional (si no existe, se construye en caliente como hoy); el proceso separado se apaga con `GENERATION_WORKER=false` y vuelve al inline/thread.
- **Dependencias**: CPU-2, GEN-2, plan 01 (módulos de generación desacoplados para poder moverlos a un worker), plan 04 (si el worker se materializa como servicio).
- **Esfuerzo/Impacto**: **L / medio**.

### 4.4 MongoDB: lecturas, N+1, paginación, seeds (H-10, H-11, H-12, H-13, H-14, H-16, H-17, H-18, H-22)

> Los índices son **responsabilidad del plan 02** (dueño del inventario y del hardening de `init_indexes`). Este plan especifica qué necesita cada consulta para que 02 los cree; no se duplica la definición de índices.

#### MON-1 — Proyección mínima en `get_current_user` y lecturas de usuario (Fase 0, esfuerzo S, impacto alto)

- **Enfoque**: en `app/core/dependencies.py:48`, cambiar `find_one(query)` por `find_one(query, {"_id":0,"id":1,"tipo_usuario":1,"activo":1,"black":1,"name":1,"email":1,"estado_id":1})`. Verificado por grep: los consumidores de `get_current_user` solo usan `id`, `tipo_usuario` y `activo` (`dependencies.py:69`, `usuario/router.py:86`, `progreso/router.py:19/34/47`), por lo que la proyección es segura. Aplicar el mismo criterio a los `find_one({"id": ...})` internos que solo leen metadatos (`usuario/service.py`, `progreso/service.py` para validar existencia): proyectar al menos las claves leídas. **No** tocar el login (`auth/service.py`) que sí necesita `password`.
  - Opcional (evaluar, no quick win): caché en memoria de 5–10 s por `id` con invalidación en updates de usuario — solo si la medición muestra que la query por request duele; con N>1 requiere invalidación por versión (CAC-2) o TTL corto.
- **Archivos a tocar**: `app/core/dependencies.py` (principal), `app/features/usuario/service.py`, `app/features/progreso/service.py` (proyecciones puntuales).
- **Pasos**: grep de consumidores → proyección en `get_current_user` → correr los tests existentes + smoke manual de cada router autenticado → medir bytes/tiempo (profiler Mongo cuando se autorice).
- **Criterios de aceptación**: mismo comportamiento funcional en todos los endpoints autenticados; el documento leído ya no incluye `password`, `codigo_acceso` ni `progresos[]` (verificable con `explain`/profiler); reducción medible de bytes transferidos por request.
- **Riesgos y mitigación**: algún endpoint futuro asuma el doc completo → documentar en el docstring del dependency la proyección garantizada y qué hacer si se necesita más (query explícita); tests de contrato (plan 06) lo detectarían.
- **Rollback**: revertir la proyección (1 línea).
- **Dependencias**: plan 02 (criterios de proyección), plan 03 (el hash de password no debe viajar “por las dudas”).
- **Esfuerzo/Impacto**: **S / alto**.

#### MON-2 — `progresos` con update dirigido y guardado de intentos en una sola operación (Fase 2, esfuerzo M, impacto medio)

- **Enfoque**:
  - **Progresos (H-11)**: eliminar el read-modify-write del array completo (`progreso/service.py:29-46,59-88`):
    - Update de un ítem existente: `update_one({"id": uid, "progresos.cursoId": cid}, {"$set": {"progresos.$.progreso": ..., "progresos.$.completado": ..., "progresos.$.examenPuntos": ..., "progresos.$.updatedAt": now}})`.
    - Insert de uno nuevo: `update_one({"id": uid, "progresos.cursoId": {"$ne": cid}}, {"$push": {"progresos": nuevo_item}})` — el filtro `$ne` hace atómica la protección contra duplicados; si `matched_count == 0` y el curso no existía, se reintenta el update dirigido (o se reporta carrera con 409).
    - El `id` interno del progreso sale de `counters` solo en el insert real (hoy se reserva aunque el ítem ya exista → huecos).
  - **Intentos (H-12)**: en `user_attempts/service.py:71-82`, eliminar el `find_one` previo y usar **una sola** `find_one_and_update(..., return_document=ReturnDocument.BEFORE)` (Motor lo soporta): el documento `BEFORE` da el estado previo (`was_already_completed`) y el `AFTER`/`BEFORE` completan la respuesta. Proyectar `{"status":1}` para ese chequeo. La actualización de puntos sigue siendo una segunda escritura condicional (`$inc` solo si el intento pasa a `completed` por primera vez) — su idempotencia plena y la validación server-side del score son de los planes 02/03; acá solo se quita el round-trip y se hace explícito el orden.
- **Archivos a tocar**: `app/features/progreso/service.py`, `app/features/user_attempts/service.py`.
- **Pasos**: reescribir `actualizar_progreso`/`crear_progreso` con updates dirigidos → test de concurrencia (dos actualizaciones de cursos distintos no se pisan) → reescribir `save_user_attempt` con `BEFORE` → test de flujo repetido (mismo POST dos veces no duplica puntos).
- **Criterios de aceptación**: el array completo deja de reescribirse (profiler: update con `$set` de rutas puntuales); dos cursos actualizados concurrentemente conservan ambos cambios (test); un intento repetido no vuelve a sumar puntos; mismo contrato de respuesta.
- **Riesgos y mitigación**: `arrayFilters`/posición `$` requieren matchear el elemento correcto → usar el filtro con `progresos.cursoId` y validar `matched_count`; cambios de semántica de conflictos → documentar last-write-wins por campo (coherente con plan 02 A2).
- **Rollback**: revertir a la implementación anterior (no hay migración de datos).
- **Dependencias**: plan 02 (A2/M3: dueño de la semántica de progresos e intentos), plan 03 (score confiable), plan 06 (tests de concurrencia).
- **Esfuerzo/Impacto**: **M / medio**.

#### MON-3 — Reducir round-trips del narrativo y cachear catálogo estático (Fase 2, esfuerzo S–M, impacto bajo-medio)

- **Enfoque**:
  - Donde hoy hay cadenas de `find_one`/`to_list` secuenciales (`modals_service.py:111-155`, `turn_service.py:71-147/173-237`, `setup_service.py:80-103`), agrupar las lecturas independientes con `asyncio.gather` y `$in` (las dependencias ya se usan en parte) para que la latencia sea la del máximo, no la suma. Objetivo: ~7 round-trips → 2–3.
  - Extender el patrón existente `_RECURSOS_MAPA_CACHE` (`setup_service.py:51-58`) a los catálogos estáticos por universo (personajes, cartas, eventos, resultados, conversaciones) con: TTL (p. ej. 60 s), cota de tamaño y **versión** (CAC-2). No cachear datos por usuario/run (solo catálogo).
  - Proyecciones: pedir solo los subcampos que el servicio usa (varios ya lo hacen; aplicarlo en los que traen el doc completo).
- **Archivos a tocar**: `app/features/narrative/game/{turn_service,setup_service,transition_service,modals_service}.py`.
- **Pasos**: medir cantidad de queries por endpoint (log/profiler) → agrupar por endpoint → introducir caché de catálogo con invalidación → comparar.
- **Criterios de aceptación**: conteo de queries por request ≤ 3 en los endpoints objetivo; misma respuesta funcional; p95 de un turno en red de alta latencia mejora (medido); la edición del admin se refleja dentro del TTL (prueba con 2 procesos en N>1).
- **Riesgos y mitigación**: caché obsoleta tras editar el admin → CAC-2 (versión/TTL) y limpieza desde `crud_service`; `gather` con excepciones → `return_exceptions` controlado o try por rama.
- **Rollback**: flag `NARRATIVE_CATALOG_CACHE=false` y revertir los `gather` (aislados por función).
- **Dependencias**: CAC-2, plan 01 (modularización del narrativo), plan 02 A4/M5 (guards de datos faltantes).
- **Esfuerzo/Impacto**: **S–M / bajo-medio**.

#### MON-4 — Paginación keyset + índices requeridos + conteo eficiente (Fase 2, esfuerzo M, impacto medio)

- **Enfoque** (coord. plan 02):
  - **Keyset**: además del `skip` actual (compatibilidad), aceptar `last_id` (`orden=desc` → `id < last_id`; `asc` → `id > last_id`) y devolver `next_cursor` en la respuesta. La primera página sigue igual; las profundas dejan de escanear.
  - **Conteo**: si no hay filtros, `estimated_document_count()`; con filtros, mantener `count_documents` pero con índice que lo cubra; opcional caché de total por 10–30 s (solo admin).
  - **Índices requeridos a coordinar con 02**: simples/compuestos para los filtros reales de `usuario/service.py`: `(activo, id)`, `(tipo_usuario, id)`, `(black, id)`, `(estado_id)`; el sort siempre es por `id`, por eso el compuesto con `id`.
  - **Búsqueda por nombre (regex no anclada)**: no puede usar índice. Opciones: (a) anclar a prefijo `^term` (cambio de semántica de búsqueda → decisión de producto §7), (b) índice de texto (`name`/`email`) con `$text` (orden y paginación cambian), (c) dejar como está y documentar el costo. Se propone (a) como default moderno con aviso en el panel; el plan no la implementa sin decisión.
  - `init_db.py:51-58` (`update_many` por `estado_id`): con índice `(estado_id)` deja de escanear; es parte de la lista de 02.
- **Archivos a tocar**: `app/features/usuario/service.py`, `app/features/usuario/router.py` (parámetro `last_id`/`next_cursor`), `app/core/database.py` (solo si 02 lo delega; lo ideal es que 02 centralice).
- **Pasos**: acordar con 02 la lista de índices → agregar keyset manteniendo `skip` → conteo eficiente → probar con dataset sembrado (10k+ usuarios, cuando se autorice) midiendo antes/después.
- **Criterios de aceptación**: página profunda (p. ej. offset 5000) con `last_id` no degrada linealmente (comparar `explain`/tiempo vs `skip`); los filtros usan índice (plan ganador sin `COLLSCAN` cuando hay filtro); respuesta retrocompatible para el panel actual (agrega campos, no quita).
- **Riesgos y mitigación**: el panel muestra total exacto → mantener conteo exacto con filtros; orden por `id` no estable si hay inserts concurrentes → keyset es consistente por definición, documentar que nuevas altas pueden aparecer/desaparecer entre páginas (aceptable en admin).
- **Rollback**: quitar el parámetro `last_id` (el camino `skip` sigue existiendo).
- **Dependencias**: plan 02 (índices y M10 `init_indexes` por índice), plan 06 (dataset de prueba), decisión §7 sobre búsqueda.
- **Esfuerzo/Impacto**: **M / medio**.

#### MON-5 — `to_list(None)` → límites explícitos y proyecciones (Fase 2, esfuerzo S, impacto bajo-medio)

- **Enfoque**: en las ~20 ocurrencias relevadas (`turn_service.py:114,119,144,237`; `setup_service.py:169,172,239`; `transition_service.py:107,108,155`; `modals_service.py:66,81,124,132,170,214`; `admin/challenge_service.py:133-136`), reemplazar `to_list(None)` por `to_list(length=N)` con N basado en el tamaño real del pool (p. ej. 50–100) y agregar proyección `{campo1:1, campo2:1}`. Donde el `$in` viene de pools del universo, agregar un tope defensivo y log si se supera (indica dato sucio).
- **Archivos a tocar**: los servicios narrativos listados.
- **Pasos**: inventariar cada uso con su tamaño máximo esperado → poner límite + proyección → test de que la respuesta no cambia con los catálogos actuales.
- **Criterios de aceptación**: 0 `to_list(None)` en el código (grep); ninguna respuesta actual cambia; si un pool supera el tope, queda log de advertencia.
- **Riesgos y mitigación**: truncar datos legítimos → límite configurable y log en vez de corte silencioso; preferir `length` generoso al inicio.
- **Rollback**: revertir límites (aislado).
- **Dependencias**: plan 01/02 (catálogos y pools), CAC-2 si además se cachea.
- **Esfuerzo/Impacto**: **S / bajo-medio**.

#### MON-6 — Seeds check-first + `bulk_write` + `$setOnInsert` (Fase 0 y 2, esfuerzo S–M, impacto alto)

- **Enfoque**:
  - **Check-first (Fase 0)**: antes de recorrer, `count_documents({"game_id": ..., "date": {"$in": fechas}})`; si ya están todas, `return` con log (0 escrituras). Si faltan algunas, procesar solo las faltantes (hoy se reescriben ~185 docs con `$set` completo y `updated_at=now` en cada arranque, H-18).
  - **No pisar**: cambiar `$set` por `$setOnInsert` para el documento completo en los seeds curados (Wordle/Sopa): si la fecha ya existe (generada por admin, jugada o editada), no se toca. Mantener un escape `ALLOW_SEED_OVERWRITE=true` para reposiciones planificadas (y que ese caso sí actualice).
  - **Bulk**: reemplazar los upserts uno por uno por `bulk_write([UpdateOne(...)], ordered=False)` en lotes de ~100–200 (aplica a seeds y a `generar_mes_narrativo`, H-22); en narrativo, cargar catálogos con proyección de `_id`s y escribir en bulk.
  - **Semántica de `updated_at`**: con `$setOnInsert` deja de refrescarse en cada deploy (recupera el significado de "actualizado" — consistente con plan 02 A6).
  - **Ubicación**: idealmente los seeds curados salen del lifespan a un comando CLI/runbook (decisión §7); hasta entonces, quedan detrás de `STARTUP_SEEDS_ENABLED` (GEN-1) y check-first.
- **Archivos a tocar**: `app/scripts/seed_challenges.py`, `app/scripts/seed_sopa_letras.py`, `app/scripts/seed_sudoku.py` (ya tiene `force=false`, mantener), `app/features/narrative/admin/challenge_service.py` (`generar_mes_narrativo`), `app/main.py` (flag).
- **Pasos**: check-first en los 3 seeds → `$setOnInsert` → bulk → medir "documentos escritos por arranque" (debe pasar de ~185 a 0 con datos presentes) → evaluar mover a CLI.
- **Criterios de aceptación**: con la base ya sembrada, un reinicio escribe **0 documentos** de juegos (métrica de profiler/logs); un arranque en base vacía sigue sembrando todo correctamente; ediciones manuales de una fecha ya no se pisan; `generar_mes_narrativo` usa ≤ N/100 operaciones bulk.
- **Riesgos y mitigación**: `$setOnInsert` impide corregir datos erróneos vía seed → flag de overwrite explícito + runbook; la duplicación de Sopa (seed vs generador, plan 01/02 A6) puede dejar grillas distintas → se resuelve unificando en 01, este plan solo evita el pisotazo.
- **Rollback**: revertir a `$set` (o usar `ALLOW_SEED_OVERWRITE=true` como mitigación inmediata).
- **Dependencias**: GEN-1 (timing), plan 02 A6 (dueño de la política de seeds), plan 01 (unificar Sopa).
- **Esfuerzo/Impacto**: **S–M / alto**.

### 4.5 Cachés y memoria (H-26, H-27, H-28)

#### CAC-1 — Rate limiter acotado: purga periódica, tope de buckets y TTL (Fase 0; store compartido en Fase 3) (esfuerzo S, impacto medio-alto)

- **Enfoque**:
  - **Purga (Fase 0)**: tarea periódica (p. ej. cada 2–5 min, dentro de la task de mantenimiento de GEN-1) que recorra `self._history` y elimine deques vacíos o con todas las marcas fuera de la ventana; log de cuántas claves se purgan.
  - **Cota de memoria**: `MAX_KEYS` (p. ej. 10_000) + `MAX_BUCKETS_PER_IP` (p. ej. 20): al superar, evictar las claves más antiguas (LRU/orden por último uso) en vez de crecer sin límite; alternativa directa: `cachetools.TTLCache` con `ttl = max window` (una entrada por `ip:path` se descarta sola; si se agrega la dependencia, decisión §7).
  - **Claves**: normalizar (sin query string), y no confiar ciegamente en el primer valor de `X-Forwarded-For` (spoofeable, informe 03): usar el último salto confiable cuando exista proxy conocido (Caddy) o la IP del socket si no hay proxy — el fix definitivo de confianza de proxy pertenece al plan 03.
  - **N>1 (Fase 3, ESC-1)**: con más de un worker los límites se multiplican ×N y el estado no se comparte. Opciones: (a) **sticky sessions** en el LB (mitiga, no corrige), (b) **store compartido**: Redis con contador por ventana (decisión futura), (c) limitador basado en Mongo (posible pero más caro; no recomendado para alta frecuencia). Mientras haya 1 worker, documentar el supuesto.
- **Archivos a tocar**: `app/core/rate_limit.py` (principal), `app/main.py` (tarea de purga), `app/core/config.py` (límites), eventualmente `docker-compose`/decisión si es Redis.
- **Pasos**: implementar purga + cap → log de tamaño del diccionario → prueba sintética de IPs variadas (cuando se autorice ejecutar) midiendo RSS y cantidad de claves → documentar supuesto 1 worker → decidir Redis en ESC-1.
- **Criterios de aceptación**: con 100k claves sintéticas, el diccionario no supera `MAX_KEYS` y la memoria del proceso se estabiliza (medición con `docker stats`/`tracemalloc`); los límites siguen funcionando (429 donde corresponde); los 429 devuelven `Retry-After` correcto.
- **Riesgos y mitigación**: evictar una IP activa le regala ventana → evicción por LRU y cap generoso; la purga compite con requests → es O(claves) breve y corre cada minutos; no mete el fix de spoofing → queda en plan 03 y se documenta la limitación.
- **Rollback**: quitar la tarea de purga y el cap (2 puntos); la lógica de límite no cambia.
- **Dependencias**: plan 03 (confianza de XFF y PIN/abuso), ESC-1 (Redis/sticky), plan 06 (test de carga).
- **Esfuerzo/Impacto**: **S / medio-alto** (alto si se escala a N>1 sin store compartido).

#### CAC-2 — Caché de recursos narrativos con invalidación por versión y tamaños acotados (Fase 2, esfuerzo M, impacto medio)

- **Enfoque**:
  - Hoy `invalidar_cache_recursos_universo` (`setup_service.py:51-58`) solo limpia el proceso que atiende la edición; con N>1 el resto sirve datos obsoletos hasta reiniciar. Propuesta:
    1. Agregar un campo `version`/`updated_at` en el documento de universo/settings (o un doc `cache_versions` por universo) que se incrementa en cada edición del admin (`crud_service`).
    2. Las cachés en memoria guardan `(version, data)`; en cada lectura se compara la versión (lectura barata por `_id` con proyección) y se recarga solo si cambió; además TTL máximo (p. ej. 60 s) como red de seguridad.
    3. Cotas: límite de universos cacheados (p. ej. 8) y de tamaño por entrada; las cachés existentes (`_RECURSOS_MAPA_CACHE`, `_WORDS_BY_LEN`/`_LETTER_POS_INDEX`, `_WORD_POOL`) pasan a tener política explícita de carga/tiempo de vida.
  - **Carga en arranque**: los artefactos estáticos (índice del crucigrama, pool de palabras) se precalientan en thread en la task de mantenimiento (CPU-2), no lazy en request.
  - **N>1**: la consistencia se logra con versión + TTL (convergencia en ≤60 s); Redis/pub-sub queda para Fase 3 si se exige invalidación inmediata (decisión §7).
- **Archivos a tocar**: `app/features/narrative/game/setup_service.py`, `app/features/narrative/admin/crud_service.py` (bump de versión), `app/features/daily_challenges/crucigrama_generator.py` y `wordle_generator.py` (política de carga), `app/core/database.py` (índice por `_id` ya es implícito).
- **Pasos**: agregar versión/bump → comparación en lectura → TTL de seguridad → cotas → prueba con 2 procesos (editar en uno y leer en el otro: converge ≤ TTL) → medir memoria de `_LETTER_POS_INDEX`.
- **Criterios de aceptación**: una edición del admin es visible en todos los procesos dentro del TTL declarado (prueba N=2 cuando se autorice); la memoria por proceso no crece sin cota con universos de prueba; invalidación local sigue siendo inmediata cuando el TTL no venció.
- **Riesgos y mitigación**: carrera entre bump y lectura → la versión se lee antes y después de cargar (double-check) o se acepta la ventana de TTL; costo de la lectura de versión por request → una query chica por `_id` con proyección (o refresco pasivo cada X usos); memoria ×N → cotas medidas.
- **Rollback**: volver a la caché sin versión + TTL 0 (invalidación manual como hoy).
- **Dependencias**: MON-3 (mismo catálogo), CPU-2 (precalentamiento), ESC-1 (Redis si se quiere inmediata), plan 01 (crud_service es el punto de invalidación).
- **Esfuerzo/Impacto**: **M / medio**.

### 4.6 Escalabilidad N>1 (tabla de riesgos del informe 05, sección 2.6)

#### ESC-1 — Plan de escalado: locks en Mongo, caches convergentes, workers recomendados y decisión Redis (Fase 3, esfuerzo M–L, impacto alto como habilitante)

- **Enfoque** (no se ejecuta ahora; define el marco):
  1. **Estado actual**: 1 worker uvicorn (`Dockerfile:21`), 1 réplica (`docker-compose.yml`). El rate limit es por proceso, el loop de 12 h se duplica, las cachés divergen y la caché RAE en archivo puede corromperse sin escritura atómica.
  2. **Qué resuelve este plan sin cambiar de infraestructura** (se implementa en Fases 0–2):
     - Rate limiter acotado y documentado como por-proceso (CAC-1); fix definitivo de store compartido solo si se necesita N>1.
     - Scheduler único con lease en Mongo (GEN-3) y locks por mes (GEN-2): sin duplicar generación ni RAE.
     - Cachés convergentes por versión + TTL (CAC-2); caché RAE con escritura atómica (RAE-3) y, si se decide, migrada a Mongo.
     - Seeds check-first + `$setOnInsert` (MON-6): un deploy multi-instancia ya no reescribe 185 docs ×N.
     - `narrative_runs` con `replace_one` completo (plan 02 A2) y `usuarios.progresos` (MON-2) quedan corregidos por sus planes para soportar concurrencia.
  3. **Decisión a tomar** (§7): (a) **quedarse en 1 worker** y escalar verticalmente (más CPU/RAM por contenedor) — lo más simple y suficiente si la concurrencia es baja; (b) **N workers/réplicas + Redis** para rate limit, locks y pub/sub de invalidación; (c) N workers con **sticky sessions** (solo mitiga rate limit; no coordina generación ni cachés).
  4. **Workers uvicorn recomendados**: hoy `--workers 1`. Si se escala: subir de a un worker por vez (`--workers 2` con el límite `cpus: 1.50` actual, que es el techo real; más workers solo si se sube el límite), verificando lag y memoria por proceso (`_LETTER_POS_INDEX` ×N); conexiones Mongo por worker (pool default, dimensionar); Uvicorn `--limit-concurrency` para backpressure opcional. Alternativa: gunicorn con workers uvicorn si se quiere recarga ordenada.
  5. **Qué NO hacer**: activar `--workers` o réplicas antes de tener GEN-2/GEN-3/CAC-2/RAE-3/MON-6 resueltos (duplicaría RAE, corrompería la caché y multiplicaría el rate limit).
- **Archivos a tocar**: `Dockerfile`/`docker-compose.yml` (solo si se decide escalar), `app/core/rate_limit.py`, `app/core/locks.py` (nuevo, usado por GEN-2/GEN-3), documentación de operación.
- **Pasos**: cerrar Fases 0–2 → decidir (a)/(b)/(c) en §7 → si (b): sumar Redis al compose + migrar rate limit y opcionalmente locks/pub-sub → prueba de 2 réplicas con carga (cuando se autorice) midiendo duplicaciones y lag.
- **Criterios de aceptación**: con 2 instancias, no hay generación duplicada ni escritura concurrente insegura (RAE/seeds); rate limit efectivo ≤ suma declarada (documentado) o exacto si Redis; cachés convergen dentro del TTL; el p95 bajo carga no se degrada por coordinación.
- **Riesgos y mitigación**: Redis agrega infraestructura y un punto de falla → si se adopta, TTL/fallback a memoria para no tumbar la API si Redis cae; sticky sessions ocultan el problema → preferir lock/estado compartido en Mongo que ya existe; workers × memoria → medir antes de multiplicar; conexiones Mongo ×N → dimensionar pool/límites.
- **Rollback**: volver a 1 worker/réplica es inmediato; Redis es aditivo (quitar servicio y flag).
- **Dependencias**: GEN-2, GEN-3, CAC-1, CAC-2, RAE-3, MON-2/6; plan 02 (A2/índices), plan 04 (si la separación de servicios redefine workers), decisión §7.
- **Esfuerzo/Impacto**: **M–L / alto (habilitante)**.

### 4.7 Externos y varios (H-15, H-20, H-21, H-23, H-29)

#### EXT-1 — SMTP: envío en background, timeout explícito y pooling evaluado (Fase 1–2, esfuerzo S–M, impacto medio-alto)

- **Enfoque**:
  - **Timeouts explícitos**: pasar `timeout=10` (o configurable) a `aiosmtplib.send` en `email_service.py:32-39` y `:116-123` para que un SMTP colgado no retenga la request.
  - **Background**: los envíos de `auth/service.py:186-191, 218, 275, 358, 402` pasan a ejecutarse después de responder (`BackgroundTasks` de FastAPI o `asyncio.create_task` con manejo de excepción); la respuesta al usuario no espera el handshake TLS (~0.5–2 s). **Atención al fallback actual**: `email_service.py:43-44` loguea el enlace/código si falla el envío; con background hay que decidir la política (log + reintento acotado + opción "reenviar código" ya existente) y **no** loguear el PIN en claro (plan 03 B4). El flujo de registro debe seguir funcionando si el envío falla (hoy ya lo hace: `return False` no rompe).
  - **Pooling (Fase 2)**: `aiosmtplib` abre y cierra por envío; evaluar reutilización: (a) mantener una conexión persistente con lock y reconnect/health-check (riesgo: conexión caída bloquea), o (b) seguir con conexión por correo en background (suficiente si el volumen es bajo). Decisión §7 con datos de volumen; si se elige (a), hacerlo con reconexión y métricas.
  - **Métricas**: duración del envío, tasa de fallos, reintentos (log estructurado).
- **Archivos a tocar**: `app/features/auth/email_service.py`, `app/features/auth/service.py` (llamadores), `app/core/config.py` (timeout/flag `SMTP_POOLING_ENABLED`).
- **Pasos**: timeout → background en los 5 puntos → política de fallo/log → medir latencia de register/magic-link antes/después → evaluar pooling.
- **Criterios de aceptación**: `/api/auth/register` y magic-link responden sin esperar al SMTP (latencia baja ~0.5–2 s medidos); un SMTP caído no altera la respuesta ni cuelga (timeout visible en log); 0 PIN en logs (coord. plan 03); los correos siguen llegando (prueba con casilla real cuando se autorice).
- **Riesgos y mitigación**: envío en background puede perderse si el proceso muere → cola persistente es overkill para este volumen; mitigar con log + reenvío manual por el flujo existente; duplicados si se reintenta a ciegas → reintento máximo 1 con marca.
- **Rollback**: flag `SMTP_BACKGROUND=false` vuelve al envío en request.
- **Dependencias**: plan 03 (PIN/logs, abuso), decisión de volumen de correo §7.
- **Esfuerzo/Impacto**: **S–M / medio-alto**.

#### PAY-1 — Payloads mensuales sin soluciones + endpoint admin separado + caché/ETag (Fase 2, esfuerzo M, impacto medio)

- **Enfoque**:
  - **Separar por audiencia**: los endpoints de jugador (`GET /api/challenges/month`, `/date`, `/today`, `/range`) responden con proyección/transformación que **excluye `config.solution`** (Sudoku: quitar `solution`, dejar `boards` + `clues`; otras claves equivalentes por juego). Un endpoint nuevo de admin (`GET /api/challenges/admin/month` o `?include_solution=true` restringido) devuelve el documento completo, con auth de admin (dependencia plan 03). Antes de tocar: verificar en el frontend actual si la solución se usa para validar localmente; si sí, esa validación debe pasar a servidor (el flujo de validación server-side ya existe para Sudoku; plan 03/06 coordinan).
  - **Caché de mes**: el contenido de un mes ya generado es inmutable (`force=false`); cachear la respuesta serializada por `(game_id, year, month, difficulty)` con cota (p. ej. 32 entradas) e invalidar/omitir si el mes está incompleto; `ETag` derivado de `max(updated_at)` del mes → responder 304 cuando no cambió (sirve para el panel y para clientes móviles).
  - **until_today**: no cachear la variante "hasta hoy" (cambia a diario) o cachear con clave por fecha del día.
- **Archivos a tocar**: `app/features/daily_challenges/service.py` (`get_month_challenges`, `get_challenge_by_date`), `app/features/daily_challenges/router.py` (endpoints), `app/features/daily_challenges/schemas.py` (schema de admin vs jugador).
- **Pasos**: medir tamaño de payload actual por juego (baseline) → proyección sin solución + endpoint admin → caché/ETag en memoria con cota → coordinar frontend (Torre de Control y juego) → pruebas de contrato.
- **Criterios de aceptación**: el payload de `/month?game_id=sudoku` deja de incluir la solución (test) y reduce tamaño medible (p. ej. ≥ 30%, medir); el admin sigue pudiendo ver/regenerar con solución; con ETag, la segunda llamada idéntica responde 304 y no re-serializa.
- **Riesgos y mitigación**: romper la validación del cliente → coordinar y versionar el cambio (feature flag `MONTH_PAYLOAD_STRIP_SOLUTION`); caché sirviendo un mes regenerado → invalidar por `updated_at`/versión y TTL corto para la variante hasta-hoy.
- **Rollback**: flag de strip y caché off (una línea).
- **Dependencias**: plan 03 (auth admin del endpoint completo; validación server-side del score), plan 06 (contratos), frontend.
- **Esfuerzo/Impacto**: **M / medio**.

#### CAD-1 — Caddy: rutear `/assets/narrative` y `/admin` al backend con caché inmutable (Fase 1, esfuerzo S, impacto medio)

- **Enfoque**: en `Caddyfile`, agregar un matcher para `/assets/narrative/*` que haga `reverse_proxy backend:8082` con `header Cache-Control "public, max-age=31536000, immutable"` (los nombres de archivo ya incluyen uuid/hash → seguros para inmutable). Idem `/admin*` hacia el backend si la SPA admin no está en `dist`. Alternativa (si se prefiere offload total): volumen compartido `./app/static/narrative:/srv/assets/narrative:ro` servido por `file_server` (sin pasar por Python); requiere que el backend escriba en el volumen (plan 02 A5: persistencia de imágenes).
  - Verificar el orden de los matchers en Caddy: `/api*`, etc. hoy tienen prioridad; la nueva ruta no debe caer en el `try_files → /index.html` actual (hoy las imágenes pueden devolver 404/HTML).
- **Archivos a tocar**: `Caddyfile` (principal), `docker-compose.yml` solo si se elige volumen compartido y persistencia (coord. plan 02 A5).
- **Pasos**: agregar matcher + headers → prueba local (imaginar request a `/assets/narrative/personajes/archivo.webp` → 200 con `Cache-Control`) → decidir proxy vs volumen según A5 §7.
- **Criterios de aceptación**: una imagen subida se sirve por Caddy con 200 y `Cache-Control: public, max-age=31536000, immutable`; no responde el `index.html` de la SPA; `/admin/` carga la Torre de Control; el tráfico de media no atraviesa Python innecesariamente (validar con logs).
- **Riesgos y mitigación**: cachear 404s o HTML → matcher específico `/assets/narrative/*` y solo 2xx; imágenes efímeras si no hay volumen (A5) → coordinar con 02 antes de anunciar persistencia.
- **Rollback**: quitar el bloque del Caddyfile (recarga de Caddy).
- **Dependencias**: plan 02 A5 (volumen/persistencia), EXT-2 del mismo plan, verificación de despliegue.
- **Esfuerzo/Impacto**: **S / medio**.

#### IDX-1 — `init_indexes`: un `try/except` por índice y log por resultado (Fase 2, esfuerzo S, impacto bajo)

- **Enfoque**: en `database.py:55-104`, envolver **cada** `create_index` en su propio `try/except` con log del índice y del error (hoy un solo `try` global: el primer error saltea todos los índices restantes silenciosamente, M10 de 02). Opcional: registrar en una colección de metadatos el resultado para un health-check simple. El costo normal (16 `create_index` idempotentes por arranque, H-21) se acepta; no vale la complejidad de saltarlo salvo arranques muy frecuentes.
- **Archivos a tocar**: `app/core/database.py`.
- **Pasos**: try/except por índice → log de éxito/fallo → exponer estado en `/health` (opcional, coord. plan 02).
- **Criterios de aceptación**: forzando un error en un índice (test), los restantes se crean igual y el log dice cuál falló; el arranque no cambia de duración significativamente.
- **Riesgos y mitigación**: ninguno relevante; un índice faltante deja de ser invisible.
- **Rollback**: revertir el bloque (aislado).
- **Dependencias**: plan 02 (M10, inventario de índices), MON-4 (índices nuevos entran por este mecanismo).
- **Esfuerzo/Impacto**: **S / bajo**.

#### H-29 — Estado global mutable (`Database` singleton)

- **Enfoque**: sin acción. El singleton se crea en import y `get_database()` puede crear cliente sin `ping` solo en scripts; no hay fuga observable. Se documenta como decisión consciente (coherente con el informe 05) y se revisa si el plan 04 separa servicios.
- **Dependencias**: plan 01/04 (si cambia el ciclo de vida de clientes).

---

## 5. Roadmap por fases

> Orden pensado para que cada fase reduzca riesgo operativo real y no bloquee a las siguientes. Esfuerzos por persona; se pueden paralelizar soluciones de temas distintos.

### Fase 0 — Quick wins (1 semana calendario, ~2–4 días-persona)

| Orden | Solución | Qué cambia | Verificación mínima |
|---|---|---|---|
| 1 | RAE-1 | quitar `time.sleep`, flag `RAE_ENABLED` | `/health` responde durante generación con RAE lenta |
| 2 | CPU-1 | bcrypt y Pillow a `to_thread` | logins/upload no congelan otras requests |
| 3 | GEN-1 | seeds/generación fuera del lifespan como task + flags | `/health` < 2 s con generación en curso |
| 4 | MON-1 | proyección en `get_current_user` | contrato autenticado intacto; menos bytes |
| 5 | GEN-2 (paso 1) | `force=False` por defecto | regenerar exige gesto explícito |
| 6 | MON-6 (paso 1) | seeds check-first + `$setOnInsert` | 0 escrituras de seeds en reinicio con datos |
| 7 | CAC-1 (paso 1) | purga periódica + cap del rate limiter | memoria estable con claves sintéticas |

**Salida de fase**: la API ya no se congela por RAE/CPU/bcrypt/Pillow; el arranque no bloquea; regeneraciones accidentales cesan. Riesgo de fase: bajo (todo con flags/cambios chicos).

### Fase 1 — Respuesta, background y RAE async (~2 semanas, ~7–10 días-persona)

| Orden | Solución | Qué cambia |
|---|---|---|
| 1 | RAE-2 | cliente httpx async, retry/backoff, semáforo, batch, circuit breaker, fallback |
| 2 | RAE-3 | caché dos niveles con `os.replace`, debounce, TTL, negative cache |
| 3 | CPU-2 | generadores en thread + `random.Random` local + precalentamiento |
| 4 | GEN-2 (completo) | `generate-month` 202 + job + lock por mes + estado consultable (requires plan 03 auth) |
| 5 | EXT-1 (paso 1) | SMTP con timeout + envío en background |
| 6 | CAD-1 | Caddy sirve `/assets/narrative` y `/admin` con caché inmutable |

**Salida de fase**: generación de meses viable sin congelar la API, panel admin con jobs asíncronos, latencias de registro/magic-link sin SMTP en el camino crítico.

### Fase 2 — Datos, consistencia y cachés (~3 semanas, ~10–14 días-persona)

| Orden | Solución | Qué cambia |
|---|---|---|
| 1 | MON-2 | `progresos` con updates dirigidos + intentos en una operación |
| 2 | MON-3 | narrativo con `$in`/`gather` + catálogo cacheado |
| 3 | MON-4 | keyset pagination + índices (con plan 02) + conteo eficiente |
| 4 | MON-5 | `to_list` con límites + proyecciones |
| 5 | MON-6 (bulk) | seeds/generación narrativa con `bulk_write` |
| 6 | CAC-2 | caché de recursos con versión + TTL + cotas |
| 7 | GEN-3 | tick 12 h con lease, sin sleeps artificiales |
| 8 | PAY-1 | payload de jugador sin soluciones + endpoint admin + ETag/caché |
| 9 | EXT-1 (pooling) e IDX-1 | pooling SMTP evaluado; `init_indexes` robusto |
| 10 | CPU-3 | artefactos precomputados y límites por request (primera parte) |

**Salida de fase**: datos consistentes, payloads acotados, arranques/ticks predecibles, cachés convergentes con N>1 (a nivel lógica).

### Fase 3 — Escala estructural (opcional, decisión §7; ~1–3 semanas, variable)

| Orden | Solución | Qué cambia |
|---|---|---|
| 1 | CPU-3 (proceso separado) | worker/proceso dedicado para generación masiva |
| 2 | ESC-1 | decisión 1 worker vs N+Redis vs sticky; implementación elegida |
| 3 | RAE-3 (Mongo/volumen) | caché RAE compartida entre procesos si >1 worker o >1 MB |
| 4 | Precompute offline | año de tableros/artefactos fuera de la ventana de generación |

**Salida de fase**: el sistema queda listo para escalar horizontalmente o se documenta formalmente que se escala solo vertical.

### Resumen de esfuerzo

| Fase | Esfuerzo | Impacto agregado |
|---|---|---|
| 0 | ~2–4 días-persona | Desbloqueo inmediato del event loop y del arranque |
| 1 | ~7–10 días-persona | RAE async + background real + SMTP + assets |
| 2 | ~10–14 días-persona | Datos, consistencia y cachés acotadas |
| 3 | ~1–3 semanas-persona (decisión-dependiente) | Escala horizontal habilitada |
| **Total** | **~4–6 semanas-persona (fases 0–2) y ~6–9 con fase 3** | ±50%, sin contar planes 01/02/03/06 |

---

## 6. Plan de verificación y métricas

> **Nada de esto se ejecuta ahora.** Esta sección define *cómo* se medirá cuando la implementación sea autorizada: primero línea base (antes), luego cambio, luego comparación (después), sobre el mismo entorno y dataset.

### 6.1 Métricas a instrumentar/capturar

| # | Métrica | Fuente propuesta | Umbral de referencia |
|---|---|---|---|
| M1 | Duración del lifespan (conexión → primera request posible) | logs con timestamps (`AppMain`), o middleware de arranque | Fase 0: < 5 s con generación habilitada y < 2 s con `STARTUP_GENERATION_ENABLED=false` |
| M2 | Tiempo hasta `/health` 200 tras `docker compose up` | healthcheck + logs | < 2 s tras escuchar el puerto |
| M3 | p50/p95/p99 de latencia por endpoint clave | middleware liviano de tiempos (nuevo, opcional) + logs de acceso; o runner tipo k6/Locust | Línea base primero; objetivos relativos por endpoint (ver 6.3) |
| M4 | **Lag del event loop** durante generación | tarea que mide `loop.time()` drift (p. ej. sleep 100 ms y reporta desvío) o `py-spy`/`asyncio` debug | p95 < 300 ms durante generación (hoy: congelamientos de segundos) |
| M5 | Llamadas RAE / cache hits / 429 / timeouts / circuito abierto | contadores en logs `[RAE]` estructurados | 0 llamadas duplicadas por palabra en un lote; 429 con backoff ≤ 1 s |
| M6 | Documentos escritos por arranque | profiler Mongo (`setProfilingLevel(1, {slowms:0})` contra colecciones de seeds en entorno de prueba) o logs de seeds | 0 escrituras de seeds con datos presentes |
| M7 | Duración de `generate-month` por juego y estado del job | job doc (`generation_jobs`) + logs | POST < 500 ms (202); job con progreso y fin `done/partial` |
| M8 | Duración del tick de 12 h y ejecuciones concurrentes | logs `[AUTOGENERACIÓN]` + lease | 1 ejecución por tick con N instancias |
| M9 | Memoria del proceso (RSS) y claves del rate limiter | `docker stats`/`tracemalloc` + log de purga | RSS estable tras N días; claves ≤ `MAX_KEYS` |
| M10 | Tamaño de payloads (`/api/challenges/month` por juego) | medición directa del JSON | reducción ≥ 30% al quitar solución (medir caso a caso) |
| M11 | Query count por request en narrativo | contador de operaciones (warehouse de tests) o profiler | ≤ 3 en endpoints objetivo |
| M12 | Latencia de `register` / `login-sistemas` / magic-link | M3 | sin espera SMTP en respuesta; bcrypt fuera del loop |
| M13 | Round-trips Mongo y uso de índices | `explain("executionStats")` sobre consultas reales | 0 `COLLSCAN` en filtros con índice; proyecciones presentes |
| M14 | 304/ETag en endpoints mensuales | logs de acceso | segunda llamada idéntica → 304 |

### 6.2 Procedimiento de medición ANTES/DESPUÉS (cuando se autorice ejecutar)

1. **Entorno congelado**: mismo compose, mismos límites (`cpus: 1.5`, `memory: 1024M`), mismo dataset sembrado (incluye generar antes un mes completo de los 4 juegos para tener dónde leer) y misma versión de Mongo.
2. **Línea base (antes)**: con el código actual, correr el escenario de carga acordado (p. ej. 5–20 usuarios virtuales: mezcla de `/health`, `/api/challenges/month`, `/api/games/attempts`, `/api/auth/login-sistemas`) durante 5–10 min en reposo y con una generación de mes corriendo en paralelo (para exponer los congelamientos). Capturar M1–M14 como corresponda; repetir 3 veces y usar mediana.
3. **Cambio**: implementar **una** solución (o grupo coherente) con su flag.
4. **Después**: repetir exactamente el escenario 2; comparar medianas y p95.
5. **Regresión funcional**: correr los tests de contrato definidos en el plan 06 (los 2 existentes + los que se agreguen durante la implementación) antes y después de cada fase.
6. **Evidencia**: guardar logs/mediciones en `auditorias/mediciones/` (o carpeta acordada) — sin tocar producción.

### 6.3 Criterios de aceptación por cambio (resumen consolidado)

| Cambio | Criterio medible |
|---|---|
| RAE-1/2/3 | M4 estable durante generación; M5 con cache hits > 0 y 429 con backoff; fallback sin excepción con RAE caída |
| GEN-1 | M1/M2 según umbrales; M6 sin sorpresas de seeds |
| GEN-2 | M7: POST < 500 ms, un solo job por clave, reaper recupera leases vencidos |
| GEN-3 | M8: 1 ejecución por tick con 2 instancias |
| CPU-1/2 | M4 p95 < 300 ms con generación y ráfaga de logins/upload |
| MON-1 | M13: proyección aplicada; payload de usuario sin `password`/`progresos` |
| MON-2 | M11/M13: 1 round-trip para intento; array de progresos no reescrito |
| MON-4 | M13: sin `COLLSCAN` en listado admin; keyset no degrada linealmente |
| MON-6 | M6: 0 escrituras con datos presentes |
| CAC-1 | M9: memoria estable, claves ≤ cap |
| CAC-2 | Edición visible en ≤ TTL con 2 procesos |
| PAY-1 | M10 reducción de payload; M14 304; solución ausente en endpoints de jugador |
| EXT-1 | M12: respuesta sin espera SMTP; timeout logueado con SMTP caído |

> Los umbrales absolutos (p. ej. "p95 < 300 ms") se ajustan a la línea base real: si el hardware del entorno de prueba es más lento que producción, se usan comparaciones relativas (antes vs después) y el criterio "no empeora + mejora el bloqueo".

### 6.4 Qué no se puede validar en esta etapa

- Nada de lo anterior se ejecutó: todas las magnitudes del informe 05 y de este plan son aritmética de constantes del código, no mediciones.
- La frecuencia real de 429/timeouts de la RAE, el volumen de usuarios concurrentes, el tamaño real de `definiciones_cache.json` en producción y el uso del frontend de `config.solution` son incógnitas (§7) que afectan la prioridad de RAE-2, PAY-1 y ESC-1.
- La validación N>1 requiere un entorno con 2 procesos/réplicas: se hará en la fase correspondiente, nunca en producción primero.

---

## 7. Preguntas abiertas y decisiones necesarias

| # | Pregunta | Impacto en el plan | Momento de decidir |
|---|---|---|---|
| D1 | ¿Se escalará a más de 1 worker/réplica? ¿Se acepta Redis como dependencia futura? | Define ESC-1 (a/b/c), CAC-1 y RAE-3 (Mongo vs archivo) | Antes de Fase 3; idealmente al cerrar Fase 1 |
| D2 | ¿Está configurada `RAE_API_KEY` en producción? ¿Cuál es la cuota y la tasa real de 429/timeouts? | Prioridad de RAE-2 y tamaño de lotes/semáforo | Antes de Fase 1 |
| D3 | ¿Se acepta cambiar el contrato de `generate-month` (202 + estado, `force=false` por defecto) y actualizar la Torre de Control? | GEN-2 completo; sin esto, solo queda el cambio de default | Antes de Fase 1 |
| D4 | ¿La auth del admin (plan 03) puede cerrarse antes de exponer jobs/endpoints admin nuevos? | GEN-2 y PAY-1 dependen de ella | Bloqueante de GEN-2 completo |
| D5 | ¿Los seeds curados pueden salir del lifespan a un comando CLI/runbook? | MON-6/GEN-1 (diseño final) | Fase 2 |
| D6 | ¿Caddy rutea `/assets/narrative` al backend o se comparte volumen con el frontend? ¿Se agrega el volumen persistente (plan 02 A5)? | CAD-1 (proxy vs volumen) y persistencia de imágenes | Fase 1 |
| D7 | ¿Se acepta quitar `config.solution` de los endpoints de jugador (y validar server-side)? ¿El frontend lo usa localmente? | PAY-1 (contrato) y plan 03/06 | Antes de Fase 2 |
| D8 | ¿La búsqueda por nombre pasa a prefijo/texto (cambio de semántica) o se documenta el full scan? | MON-4 | Fase 2 |
| D9 | ¿La generación masiva se moverá a un proceso/contenedor dedicado (plan 04) o alcanza hilos? | CPU-3/ESC-1 | Fase 2–3 |
| D10 | ¿Cuál es el volumen de correos (register/reenvíos) que justifica pooling SMTP? | EXT-1 (pooling sí/no) | Fase 2 |
| D11 | ¿TTL aceptables para las cachés (RAE 90 días, negativa 1–6 h, catálogo 60 s, mes inmutable)? | RAE-3, CAC-2, PAY-1 | Fase 1–2 |
| D12 | ¿Se formaliza el lag del event loop (M4) como métrica permanente con alerta? | §6 (instrumentación) | Fase 0–1 |
| D13 | ¿El tick de 12 h queda como lease interno o se reemplaza por cron externo? | GEN-3 | Fase 2 |
| D14 | ¿Se sincroniza la TZ de negocio (M1 de 02) antes de tocar generación/limpieza? | RAE-3/PAY-1/GEN-* (fechas de borde) | Antes de Fase 2 |

---

### Nota final

Este documento es un **plan** derivado del informe 05: no se implementó nada, no se modificó código ni configuración, y no se ejecutaron pruebas, benchmarks ni consultas a la base de datos. Cada solución queda lista para priorizarse, estimarse en detalle y ejecutarse de a una con sus flags, criterios de aceptación y rollback. Los puntos donde este plan toca dominios de otros informes (índices de 02, auth de 03, modularización de 01, tests de 06) están marcados como dependencias para evitar soluciones pisadas.

*Fin del plan — Auditoría 05 (soluciones), 19/10/2026.*




