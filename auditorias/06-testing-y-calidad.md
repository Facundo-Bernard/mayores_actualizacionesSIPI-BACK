# Auditoría 06 — Testing y Calidad

- **Proyecto:** `mayores_actualizacionesSIPI-BACK` (FastAPI + MongoDB)
- **Ruta auditada:** `C:\Users\nmonti\Desktop\proyectos\backend\mayores_actualizacionesSIPI-BACK`
- **Fecha:** 2026-10-19
- **Método:** auditoría estática, solo lectura (lectura de código, greps y conteos). **No se ejecutaron tests, la aplicación, ni se tocó base de datos alguna.** No se modificó ningún archivo del proyecto.
- **Alcance:** `app/`, `tests/`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `docs_interna/`.

> Este informe cubre la dimensión "testing y calidad". Varios hallazgos exceden lo estrictamente técnico de pruebas porque condicionan la estrategia de testeo (endpoints sin autorización, scoring confiado al cliente, concurrencia sin cubrir). Se documentan aquí con severidad y evidencia `archivo:línea`.

---

## 1. Resumen ejecutivo

El proyecto tiene **2 (dos) archivos de test** en total: `tests/test_narrative_game.py` (104 líneas) y `tests/test_narrative_v2_game.py` (134 líneas). Cubren únicamente el camino feliz del juego narrativo V2 contra la **base de datos MongoDB real configurada en `.env`**, dependen de la fecha real del sistema y dejan datos en la base. No existe ningún test para `auth`, `usuario`, `progreso`, `daily_challenges` (API y generadores) ni `user_attempts`.

No hay infraestructura de testing: `requirements.txt` (líneas 1-15) **no declara `pytest`, `httpx`, `pytest-asyncio` ni `mongomock-motor`**; no hay `conftest.py`, `pytest.ini`, `pyproject.toml` ni configuración de linters; no hay pipeline de CI (no existe carpeta `.github/`). Los tests solo pueden ejecutarse manualmente (`asyncio.run`), contra la DB de desarrollo y con efectos destructivos (`tests/test_narrative_game.py:54`, `tests/test_narrative_v2_game.py:42` borran runs del usuario 0 del día).

Los mayores riesgos de calidad detectados son de **autorización y confianza**: los 32 endpoints de la torre de control narrativa (`app/features/narrative/admin/router.py` — sin un solo `Depends` de autenticación) y los endpoints de administración/upsert de desafíos (`app/features/daily_challenges/router.py:77-113`) están expuestos sin autenticación; la lectura de intentos ajena es posible por IDOR (`app/features/user_attempts/router.py:53-99`); el puntaje se calcula 100% en el cliente y se suma a los puntos del usuario sin validación (`app/features/user_attempts/service.py:85-93`); y el rate limit es evadible falsificando `X-Forwarded-For` (`app/core/rate_limit.py:49-53`), con un PIN de acceso de 6 dígitos que ya es solo numérico (`app/features/auth/service.py:238`).

La estrategia recomendada es una pirámide por fases: **Fase 0** habilitadores (dependencias de test, `conftest.py`, DB efímera, fechas congeladas, mocks de RAE/SMTP), **Fase 1** unit de servicios y generadores deterministas, **Fase 2** integración API con `httpx.AsyncClient` + `ASGITransport` y Mongo mockeado/efímero, **Fase 3** E2E del narrativo y regresión de seeds, **Fase 4** matriz de autorización/seguridad y contratos, **Fase 5** CI con cobertura y lint. Sin la Fase 0, cualquier corrección de los hallazgos críticos se hará sin red de seguridad.

**Fortalezas a preservar:** microestructura por features consistente (`app/features/*`), esquemas Pydantic de validación, checks de RLS/IDOR manuales en `progreso` (`app/features/progreso/router.py:19,34,47`) y `usuario` (`app/features/usuario/router.py:86`), rate limiting presente en todos los endpoints de auth (`app/features/auth/router.py:20,28,50,59,67,75`), índices únicos definidos para las colecciones críticas (`app/core/database.py:61-94`) y dos tests E2E que ya validan un ciclo completo de 12 meses del narrativo.

---

## 2. Inventario de tests existentes

### 2.1 Panorama

| Archivo | Líneas | Tipo | Framework | DB/Red | Ejecución |
|---|---|---|---|---|---|
| `tests/test_narrative_game.py` | 104 | Integración E2E (API narrativa vía ASGI) | `asyncio.run` manual, `httpx.AsyncClient` | MongoDB real de `.env` | Manual: `python tests/test_narrative_game.py` |
| `tests/test_narrative_v2_game.py` | 134 | Integración E2E (ciclo V2 completo 12 meses) | `asyncio.run` manual, `httpx.AsyncClient` | MongoDB real de `.env` | Manual: `python tests/test_narrative_v2_game.py` |

No hay `tests/conftest.py`, `tests/__init__.py`, `pytest.ini`, `tox.ini`, `pyproject.toml`, `setup.cfg` ni `Makefile`. Existe `.pytest_cache/` (mtime 2026-10-15 12:39:23), lo que indica que puntualmente se corrió `pytest` sobre estos archivos, sin que el proyecto declare `pytest` como dependencia.

### 2.2 `tests/test_narrative_game.py`

Qué hace (con evidencia):

1. Wrapper síncrono que llama `asyncio.run` (`:17`) sobre `_ejecutar_pruebas_consultas`.
2. Conecta a la Mongo real: `await connect_to_mongo()` + `get_database()` (`:20-21`). Usa `settings.MONGODB_URL`/`settings.MONGODB_DB_NAME` de `.env`.
3. Si `narrative_characters` está vacía, ejecuta el seed completo `seed_narrative_game()` (`:24-25`).
4. Busca el desafío narrativo de **hoy** (`datetime.datetime.now()`, `:27-28`); si no existe, genera el mes en curso con `generar_mes_narrativo(...)` (`:30-32`). Dependencia fuerte de la fecha real y del estado de la base.
5. Borra la run previa del usuario 0 para hoy (`:54`) y valida `GET /api/narrative/partida/setup` (`:56-61`).
6. Inicia partida V2 con 3 corte + 3 cartas (`:64-73`), consulta modales `/corte`, `/inventario`, `/historial` (`:77-92`) y reinicia la partida (`:95-97`).
7. Verifica que el setup vuelve a `tiene_partida_activa=False` (`:100-102`) y cierra la conexión (`:104`).

Problemas:

- **Usa el usuario invitado 0** (no envía `Authorization`): nunca prueba un usuario autenticado.
- **Destructivo sobre la DB configurada**: borra documentos reales (`:54`) y puede disparar seeds (`:25`) y generación mensual (`:32`) sobre datos de desarrollo.
- **Depende del reloj**: la fecha de hoy define desafío y run (`:27`, `:52`).
- **Sin teardown**: si falla a mitad, deja la run activa creada.
- **Assertions superficiales**: solo status codes, conteos y fases; no valida la matemática del motor de reglas ni la consistencia final de recursos.

### 2.3 `tests/test_narrative_v2_game.py`

Qué hace (con evidencia):

1. Mismo patrón: `asyncio.run` (`:21`), conexión real (`:24-25`), seed condicional (`:28-29`), generación del mes si falta (`:34-37`).
2. Borra la run de hoy del usuario 0 (`:42`) y toma corte/cartas de la config del challenge (`:45-46`).
3. Inicia partida V2 **con `Authorization: Bearer fake_token`** (`:56` y comentario `# user_id 0`): el token es inválido, por lo que `_get_current_user_id` cae al default 0 (`app/features/narrative/game/router.py:64-76`). Prueba, de nuevo, el camino invitado.
4. Recorre hasta 12 meses aplicando el ciclo `elegir-carta-mes` → `decidir-evento` → `responder-conversacion` (si aplica) → `avanzar-mes` (`:65-124`), con cortes por `FINALIZADA` (colapso de recursos).
5. Al final exige `fase_actual == "FINALIZADA"` y `finalizacion` no nula, con rangos `S/A/B/C` si completó o `F` si no (`:127-132`).
6. Cierra la conexión (`:134`). No limpia la run finalizada.

Problemas: mismos que 2.2, más el riesgo de **falso verde/rojo por estado previo de la DB** (la config del challenge de hoy condiciona todo el flujo) y la imposibilidad de correr ambos tests en paralelo (comparten `user_id=0` + fecha).

### 2.4 Infraestructura de testing ausente

| Elemento | Estado | Evidencia |
|---|---|---|
| `pytest` / `pytest-asyncio` | No declarados | `requirements.txt:1-15` |
| `httpx` | Usado por tests, no declarado | `tests/test_narrative_game.py:3`, `requirements.txt` |
| `mongomock-motor` / testcontainers | Ausente | `requirements.txt` |
| `conftest.py` / fixtures | Ausente | No existe en `tests/` (solo 2 archivos `.py` + `__pycache__`) |
| Config pytest / markers | Ausente | No hay `pytest.ini`/`pyproject.toml`/`setup.cfg` en la raíz |
| Linter/formatter | Ausente | No hay `ruff`/`black`/`flake8` configurado |
| CI/CD | Ausente | No existe `.github/` ni equivalente |
| Pins de dependencias | Ausente (todo `>=`) | `requirements.txt:1-15` |
| Aislamiento de DB de test | Ausente | Tests usan `connect_to_mongo()` → `.env` real (`tests/test_narrative_v2_game.py:24`) |
| Versión de Python | Inconsistente | `Dockerfile:1` (3.12-slim) vs `__pycache__` CPython 313 en `.venv` |

---

## 3. Mapa de riesgo/cobertura por feature

Escala de riesgo: **Crítico / Alto / Medio / Bajo**. Prioridad: **P0** (bloqueante: sin tests y con riesgo activo), **P1** (alta), **P2** (media), **P3** (baja).

| Feature / módulo | Superficie principal | Tests actuales | Riesgo | Prioridad |
|---|---|---|---|---|
| **auth** | 8 endpoints: login sistemas, login PIN, verificar token, magic link, register, verificar/reenviar código, modificar email (`app/features/auth/router.py:18-79`); lógica en `app/features/auth/service.py` | **0** | **Alto** — es el portón del sistema; PIN de 6 dígitos, errores de email tragados, carrera de registro, códigos provistos por el cliente sin validar (`service.py:234-241`, `schemas.py:29`) | **P0** |
| **usuario** | Listado admin con filtros/paginación, catálogo de estados, cambiar estado, perfil (self/admin), toggles, crear usuario, magic-link (`app/features/usuario/router.py:23-122`) | **0** | **Medio-Alto** — operaciones admin sin tests de permisos ni de paginación/filtros | **P1** |
| **progreso** | 3 endpoints con check manual RLS/IDOR (`app/features/progreso/router.py:13-52`) | **0** | **Medio** — la lógica RLS es correcta en lectura, pero no tiene regresión automatizada | **P1** |
| **daily_challenges — API** | `GET /today`, `/month`, `/range`, `/date/{date}`, `POST` upsert, `/admin/status`, `/admin/generate-month` (`app/features/daily_challenges/router.py:24-113`) | **0** | **Alto** — 3 endpoints de escritura/admin **sin auth** (`:77-83,85-93,95-113`); topes de mes y 404 de fechas sin cubrir | **P0** |
| **daily_challenges — generadores** | `wordle_generator.py`, `sudoku_generator.py`, `sopa_generator.py`, `crucigrama_generator.py`; seeds `app/scripts/seed_*.py` | **0** | **Alto** — determinismo por fecha, unicidad de soluciones y correctitud de puzzles sin ninguna verificación; llaman a RAE (`wordle_generator.py:12-13,51`; `sopa_generator.py:11,179`) | **P1** |
| **user_attempts** | `POST ""` (upsert + puntos), `GET /date/{date}`, `GET ""` por mes (`app/features/user_attempts/router.py:30-99`) | **0** | **Crítico-Alto** — IDOR de lectura por `user_id` query (`router.py:56-60,76-83`), score/estrellas confiados al cliente (`schemas.py:15-17`), `$inc` de puntos duplicable ante concurrencia (`service.py:71-93`) | **P0** |
| **narrative — partida V2** | ~14 endpoints (`app/features/narrative/game/router.py:82-...`): iniciar, elegir carta, decidir evento, conversación, avanzar, modales, setup, reiniciar | Parcial (2 E2E camino feliz, solo invitado 0) | **Alto** — sin tests de autenticado, concurrencia (doble submit), idempotencia ni aislamiento entre usuarios; servicios con read-modify-write sin locking (`setup_service.py:139-182`, `turn_service.py`, `transition_service.py`, `endings_service.py`) | **P0** |
| **narrative — engine** | `engine/rule_engine.py`, `engine/event_director.py`; finales en `game/endings_service.py` | **0** | **Alto** — el corazón lógico del juego (condiciones, acciones, sorteos, rangos S/A/B/C/F) no tiene ni un test unitario | **P1** |
| **narrative — admin** | **32 endpoints** CRUD + upload + generar mes + finalizaciones (`app/features/narrative/admin/router.py:70-311`) | 2 lecturas incidentales por el test E2E (`test_narrative_game.py:37,46`) | **Crítico** — **cero autenticación** (verificado: no hay `Depends`/`get_current_admin` en todo el archivo) | **P0** |
| **narrative — seeds/config** | `app/scripts/seed_narrative.py` (1.789 líneas), `admin/challenge_service.py` (`generar_mes_narrativo`, `sembrar_finalizaciones_*`) | Indirecto: el test siembra si la colección está vacía (`test_narrative_*.py:24-25/28-29`) | **Medio** — seed gigante usado por tests pero no en startup; idempotencia no verificada | **P2** |
| **Infra de arranque** | `lifespan` en `app/main.py:32-68`: seeds de desafíos, admin, estados, `ensure_current_and_next_month_generated()` (RAE + `sleep(0.2)` en `daily_challenges/service.py:409`), loop de 12 h (`:50-62`); `init_indexes()` que traga excepciones (`app/core/database.py:103-104`) | **0** | **Alto** — arranque con efectos secundarios y red externa; si falla la red, el arranque queda degradado silenciosamente | **P1** |
| **Deploy (Docker)** | `Dockerfile:1-21` (sin stage de tests), `docker-compose.yml:37-97` (Mongo sin auth, backend sin puerto publicado, uploads no persistentes: solo `mongo_data` en `:99-100`) | **0** (sin smoke test) | **Medio** — no hay verificación automatizada de que la imagen arranca ni de healthchecks | **P2** |
| **docs_interna** | 5 guías | **0** (sin contract tests) | **Bajo-Medio** — documentación desincronizada del código (ver H-12) | **P3** |

**Top 10 riesgos sin cobertura** (ordenados):

1. Endpoints de escritura sin autenticación: 32 de narrativa admin + 3 de daily_challenges (`narrative/admin/router.py`, `daily_challenges/router.py:77-113`).
2. IDOR de lectura de intentos ajenos (`user_attempts/router.py:56-68,76-99`).
3. Puntos y resultados calculados en el cliente (`user_attempts/service.py:85-93`, `schemas.py:15-17`).
4. Invitado narrativo compartido (`user_id=0`) — colisiones y resets entre anónimos (`narrative/game/router.py:64-76`; `setup_service.py:181`).
5. Rate limit evadible + PIN numérico de 6 dígitos (`core/rate_limit.py:49-53`; `auth/service.py:238`).
6. Carreras de concurrencia sin tests: doble submit narrativo, `$inc` de puntos, registro de usuario (`service.py:71-93`, `setup_service.py:139-182`, `auth/service.py:237-241`).
7. Generadores de puzzles sin verificación de correctitud/determinismo (4 juegos).
8. Motor de reglas y finales del narrativo sin unit tests.
9. Arranque dependiente de red RAE y seeds con efectos masivos (`main.py:42`; `service.py:376,409`).
10. Tests actuales no reproducibles en limpio ni aislados de la DB de desarrollo.

---

## 4. Estrategia de testeo recomendada por fases

### Fase 0 — Habilitadores (1–2 días)

1. **Declarar dependencias de test**: crear `requirements-dev.txt` (o extras) con `pytest`, `pytest-asyncio`, `httpx` (ya se usa), `mongomock-motor`, `freezegun` (o inyección de reloj), `respx` (mock HTTP para RAE), `pytest-cov` y un linter (`ruff`). Fijar versión de Python soportada (resolver 3.12 vs 3.13).
2. **`tests/conftest.py`** con:
   - Fixture `db` usando `mongomock-motor` (o testcontainers `mongo:7.0` si se quiere paridad real), parcheando `app.core.database.db_instance`/`get_database`.
   - Fixture `client` con `httpx.AsyncClient(transport=ASGITransport(app))` y **lifespan desactivado** (los seeds de `main.py:36-48` no deben correr en tests).
   - Fixtures `auth_headers(user)` / `admin_headers` que insertan usuarios en la DB de test y generan JWT con `create_access_token`.
   - Fixture `frozen_today` para congelar la fecha (`datetime` monkeypatch) y helper `seed_catalog` que inserta universo/personajes/cartas mínimos.
   - Marker `integration` que exija `TEST_MONGODB_URL` con nombre de DB terminado en `_test` y **skip** si no está; guardia dura: ningún test puede tocar `settings.MONGODB_DB_NAME` real.
   - Mocks de red: `respx` para RAE y monkeypatch de `aiosmtplib`/`email_service` para SMTP.
3. **Config**: `pyproject.toml` con `[tool.pytest.ini_options]` (`asyncio_mode=auto`, markers, `testpaths=tests`), reglas de lint, y `pytest.ini` mínimo si se prefiere.
4. **Reescribir los 2 tests existentes** sobre esta base: fecha congelada, DB efímera, seed programático y sin efectos sobre datos reales.

### Fase 1 — Unit tests de servicios y generadores (sin HTTP)

- **auth/service.py**: registro con email duplicado y con cuenta pendiente (`:209-229`); código provisto vs generado (`:234-241`); colisión de código (esperar manejo de `DuplicateKeyError`, no 500); login código inexistente/pendiente/inactivo/ok (`:98-117`); verificación y reenvío de códigos; modificar email; expiración/validez de token (`core/security.py`).
- **user_attempts/service.py**: idempotencia del upsert (mismo `user_id/game_id/date` no duplica); `was_already_completed` no vuelve a sumar puntos (`:71-72,85`); `score<=0` no suma; `status=failed` no suma; límites de mes (febrero, bisiestos, `calendar.monthrange` `:125-127`).
- **daily_challenges/service.py + generadores**: determinismo (misma fecha ⇒ mismo puzzle); validación de soluciones (sudoku válido/único, palabras presentes en sopa, longitudes de crucigrama, wordle con palabra en diccionario); tope de días del mes (`:226,361,458`); `get_challenges_monthly_status`.
- **narrative/engine**: condiciones/acciones del catálogo (`engine/rule_engine.py`, `admin/rules_catalog.py`), sorteo de eventos (`event_director.py`), rangos de finales y umbrales (`endings_service.py`), costos pasivos y colapso (`transition_service.py`).
- **narrative/admin/challenge_service.py**: `generar_mes_narrativo` genera 1 challenge/día y no pisa configs existentes salvo lo esperado; `sembrar_finalizaciones_*` idempotente.

### Fase 2 — Integración API (ASGI + DB mock/efímera)

- **auth**: registro→verificar→login (email mockeado); 429 del rate limit con `X-Forwarded-For` controlado; 401/403 por estado de cuenta.
- **usuario**: matriz de permisos (admin/alumno/otro) en cada endpoint; paginación (`limit/skip/orden`, filtros por nombre, fechas, tipo, black, activo).
- **progreso**: matriz RLS self/admin/tercero → 403 (`progreso/router.py:19,34,47`).
- **user_attempts**: guardar sin identidad → 401 (`router.py:41-45`); lectura solo del propio usuario (test que fije el comportamiento correcto para el IDOR); suma de puntos exacta.
- **daily_challenges**: `/today`, `/month` (topes), `/range`, `/date/{date}` (404 en fecha inválida); upsert y admin (cuando tengan auth, 401/403).
- **narrative V2**: ciclo completo con **usuario autenticado** (no solo invitado); doble submit concurrente (`asyncio.gather` de 2 requests iguales) ⇒ un único efecto; dos usuarios jugando en paralelo ⇒ runs aisladas; `reiniciar` idempotente.

### Fase 3 — E2E y regresión de datos

- Portar los dos tests actuales a la infraestructura nueva (fechas congeladas, DB efímera, seed determinista) y mantenerlos como smoke E2E del narrativo.
- Invariantes del ciclo V2: un evento por mes, secuencia de fases válida, conservación/balance de recursos, final coherente con `status` y rango.
- **Seeds**: idempotencia de `init_db.py`, `seed_challenges.py`, `seed_sudoku.py`, `seed_sopa_letras.py` y `seed_narrative.py` (correr 2 veces ⇒ mismo estado); conteos esperados. `seed_narrative.py` (1.789 líneas) solo es invocado por los tests: decidir si se testea como herramienta o se elimina del repo de producción (H-13).
- **Smoke de arranque**: `lifespan` con DB mock y RAE/SMTP mockeados ⇒ arranca sin red; valida además que `init_indexes` no trague errores (H-09).

### Fase 4 — Seguridad, abuso y contratos

- **Matriz de autorización generada** (endpoint × rol esperado) recorriendo `app.routes`: hoy los endpoints admin de narrativa/challenges no tienen candado — la matriz debe fallar hasta que se corrija (H-01/H-02).
- **Rate limiting**: tests con IP simulada rota (`X-Forwarded-For` rotativo) que primero documenten el bypass (H-06) y luego lo fijen corregido; fuerza bruta de PIN.
- **CORS**: asserts de preflight para origins permitidos/rechazados (H-07).
- **Contratos/OpenAPI**: snapshot de `openapi.json` y verificación de status codes y parámetros documentados en `docs_interna/` (H-12: `fecha` vs `date`, 404 vs 401, 201 vs 200).

### Fase 5 — Calidad continua

- CI (GitHub Actions u equivalente) con job: lint + unit + integración (service container `mongo:7.0`) + coverage mínimo incremental.
- Pins/lock de dependencias; matriz de versión Python alineada con Docker.
- Pre-commit con formatter/linter; limpieza de `__pycache__` obsoletos y del `.pytest_cache` sin config.

**Anti-patrones a erradicar** (hoy presentes): tests contra la DB de desarrollo, dependencia del reloj real, red externa (RAE/SMTP) en el camino crítico, tests destructivos como única regresión, y ejecución manual vía `asyncio.run` sin runner.

---

## 5. Hallazgos de calidad con severidad

Severidad: **Crítica** (explotable/hoy sin control), **Alta**, **Media**, **Baja**.

### 5.1 Tabla resumen

| ID | Severidad | Hallazgo | Evidencia principal |
|---|---|---|---|
| H-01 | **Crítica** | 32 endpoints de narrativa admin sin autenticación | `app/features/narrative/admin/router.py:64-311` |
| H-02 | **Alta** | Upsert y endpoints admin de daily_challenges sin autenticación | `app/features/daily_challenges/router.py:77-113` |
| H-03 | **Alta** | IDOR de lectura en user_attempts (lectura de intentos ajenos) | `app/features/user_attempts/router.py:53-99` |
| H-04 | **Alta** | Puntaje/estrellas confiados al cliente; puntos duplicables | `app/features/user_attempts/schemas.py:15-17`, `service.py:85-93` |
| H-05 | **Alta** | Invitado narrativo comparte `user_id=0` (colisión y resets) | `app/features/narrative/game/router.py:64-76`, `setup_service.py:181` |
| H-06 | **Alta** | Rate limit evadible con `X-Forwarded-For` + PIN numérico de 6 dígitos | `app/core/rate_limit.py:49-53`, `app/features/auth/service.py:238` |
| H-07 | **Media** | CORS con regex universal + credenciales | `app/main.py:94-95` |
| H-08 | **Media** | Secretos/credenciales por defecto hardcodeados | `app/core/config.py:14,27-28,38`, `app/scripts/init_db.py:80` |
| H-09 | **Media** | Carreras de concurrencia sin cobertura y sin manejo de `DuplicateKeyError` | `auth/service.py:237-241`, `setup_service.py:139-182`, `database.py:90-104` |
| H-10 | **Media** | Infra de testing inexistente: tests no reproducibles ni aislados | `requirements.txt:1-15`, `tests/*` |
| H-11 | **Media** | Tests destructivos contra DB real y dependientes de fecha/estado | `tests/test_narrative_game.py:20-32,54`, `tests/test_narrative_v2_game.py:24-42,56` |
| H-12 | **Baja** | Documentación desincronizada del código | `docs_interna/DIAGRAMAS_ARQUITECTURA_NARRATIVO.md:94,143,147,157`, `GUIA_INTEGRACION_FRONTEND_AUTH.md:62,154` |
| H-13 | **Baja** | Higiene de repo: `.pyc` huérfanos, imports duplicados, versiones divergentes | `app/features/narrative/__pycache__/*` (router/router_v2/service), `app/main.py:100-102,143`, `Dockerfile:1` |
| H-14 | **Baja** | 18 usos de `except Exception` con excepciones tragadas/avisos | `app/main.py:47-48`, `user_attempts/service.py:94-95`, `database.py:103-104` |

### 5.2 Detalle por hallazgo

#### H-01 — Crítica: narrativa admin sin autenticación

- **Evidencia:** `app/features/narrative/admin/router.py` define el router en `:64` y expone 32 endpoints entre `:70` y `:311` (catálogo, upload de imágenes, CRUD de universos/personajes/cartas/resultados/eventos/conversaciones/finalizaciones, generación mensual, siembra de finales). Grep de `Depends|get_current|require_admin|security` en el archivo: **sin coincidencias**. El router se monta sin dependencias globales en `app/main.py:124`.
- **Impacto:** cualquier cliente puede crear/borrar/añadir el catálogo del juego, subir imágenes y regenerar el mes; integridad y disponibilidad del juego comprometidas. Además, impide escribir tests de autorización porque no hay autorización que probar.
- **Recomendación:** aplicar `Depends(get_current_admin)` a nivel router o por endpoint (existe y funciona: `app/core/dependencies.py:63-74`); añadir test de matriz authz (401 sin token, 403 alumno, 200 admin).

#### H-02 — Alta: daily_challenges sin auth en escritura/admin

- **Evidencia:** `POST /api/challenges` (upsert de desafío) `app/features/daily_challenges/router.py:77-83`; `GET /admin/status` `:85-93`; `POST /admin/generate-month` `:95-113` (con `force=True` por defecto, `:103`). Sin `Depends` en ninguno.
- **Impacto:** se pueden alterar desafíos diarios (p. ej. soluciones) o forzar regeneraciones masivas (CPU + llamadas RAE con sleeps, `daily_challenges/service.py:376,409`, `wordle_generator.py:51`).
- **Recomendación:** `get_current_admin`; tests 401/403/200.

#### H-03 — Alta: IDOR de lectura en user_attempts

- **Evidencia:** `app/features/user_attempts/router.py:59-60` (y `:82-83`) calculan `effective_user_id = user_id or token_user_id`: si el atacante manda `?user_id=<víctima>` con **su** token, se usa el de la víctima. `GET /date/{date}` `:53-68` y `GET ""` `:75-99` devuelven los intentos de cualquier usuario.
- **Impacto:** fuga de datos personales de juego (palabras, puntajes, progreso).
- **Recomendación:** el token siempre prevalece; permitir `user_id` ajeno solo a admin (`tipo_usuario == 2`). Test de matriz de lectura.

#### H-04 — Alta: scoring client-trusted y puntos duplicables

- **Evidencia:** el request acepta `attempts/stars/score` sin validación (`app/features/user_attempts/schemas.py:15-17`); el servicio hace `$inc: {"puntos": req.score}` si `status == "completed"` y `req.score > 0` (`service.py:85-93`). La bandera `was_already_completed` se calcula con un `find_one` previo (`:71-72`) → dos requests concurrentes suman dos veces. La excepción al sumar puntos se traga con warning (`:94-95`).
- **Impacto:** manipulación directa del puntaje y corrupción de datos por concurrencia.
- **Recomendación:** recalcular score server-side a partir de `guesses/game_data` contra las reglas del juego; hacer la transición de estado atómica (`find_one_and_update` condicionado o transacción) y test con `asyncio.gather`.

#### H-05 — Alta: invitado narrativo compartido (`user_id=0`)

- **Evidencia:** `_get_current_user_id` devuelve 0 ante ausencia o invalidez de token (`app/features/narrative/game/router.py:64-76`); las runs se identifican y persisten con ese 0 (`setup_service.py:103,139,181` → `_id = f"run_{user_id}_{date}"`). El test V2 usa un `fake_token` que cae en 0 (`tests/test_narrative_v2_game.py:56`).
- **Impacto:** dos anónimos en el mismo día comparten partida: uno ve/continúa la del otro, y `reiniciar` borra la del otro (`setup_service.py:117-124`). También contamina la DB productiva con datos de prueba si los tests corren contra ella.
- **Recomendación:** identidad anónima por cookie/sesión con id propio, o exigir autenticación; test de aislamiento con dos clientes sin token.

#### H-06 — Alta: rate limit evadible + PIN numérico de 6 dígitos

- **Evidencia:** el limiter confía en `X-Forwarded-For` sin validar proxy (`app/core/rate_limit.py:49-53`), es in-memory por proceso (`:7-11,32`) y la clave es IP+fecha (`:55`). Los endpoints sensibles permiten 5 req/min (`auth/router.py:20,28,50,59,67,75`) y el PIN se genera numérico de 6 dígitos (`auth/service.py:238`, ver también `init_db.py:80` con `"999999"`).
- **Impacto:** fuerza bruta de códigos de acceso desde una sola IP rotando el header; en multi-proceso el límite se diluye.
- **Recomendación:** usar IP del socket o `X-Real-IP` seteado por Caddy; limiter compartido (Redis) si escala; evaluar códigos alfanuméricos o bloqueo por cuenta. Tests de abuso con IP spoofeada.

#### H-07 — Media: CORS universal con credenciales

- **Evidencia:** `allow_origin_regex=r"^https?://.*$"` + `allow_credentials=True` (`app/main.py:94-95`) conviviendo con whitelist (`:81-89`). Incluye una duplicación de import de `StarletteHTTPException` (`:102` y `:143`) — ver H-13.
- **Impacto:** cualquier origen web puede consumir la API desde navegadores de víctimas; unido a H-01/H-02 amplifica el daño.
- **Recomendación:** whitelist explícita por entorno; tests de preflight.

#### H-08 — Media: secretos y credenciales por defecto

- **Evidencia:** `JWT_SECRET` hardcodeado (`app/core/config.py:14`), admin `admin@sistemas.com` / `admin123` (`:27-28`), MySQL `root/root` (`:38`), SMTP user hardcodeado (`:21`), PIN admin `"999999"` en el seed (`app/scripts/init_db.py:80`).
- **Impacto:** si `.env` no sobreescribe (o falta), producción queda con secretos públicos en el repo; el JWT_SECRET permite forjar tokens.
- **Recomendación:** fallar en startup si valores por defecto en producción; `docker-compose` no debe depender de `.env` para secretos críticos (documentarlo en despliegue); test de "settings fail-fast".

#### H-09 — Media: concurrencia sin cobertura y sin manejo de colisiones

- **Evidencia:** patrón check-then-insert en registro (`auth/service.py:209-229,237-241`) e inicio de partida V2 (`setup_service.py:139-182`); índices únicos que mitigan a nivel DB (`database.py:62,79,90-93`) pero un choque simultáneo produciría `DuplicateKeyError` no manejado → 500; `init_indexes()` traga excepciones (`database.py:103-104`). Servicios de turno/transición hacen read-modify-write sin locking (`turn_service.py`, `transition_service.py`).
- **Recomendación:** manejar `DuplicateKeyError` como idempotencia (200/409 controlado); tests de doble ejecución concurrente con `asyncio.gather`.

#### H-10 — Media: sin infraestructura ni reproducibilidad de tests

- **Evidencia:** `requirements.txt:1-15` sin dependencias de test; `httpx` se importa en tests sin declararse (`tests/test_narrative_game.py:3`); sin `conftest.py`/config/CI (sección 2.4); `.pytest_cache` huérfano evidencia ejecuciones ad-hoc.
- **Impacto:** los tests no corren en un clon limpio; no hay puerta objetiva de calidad antes de desplegar.
- **Recomendación:** Fase 0 de la estrategia.

#### H-11 — Media: tests destructivos y dependientes del entorno

- **Evidencia:** conexión a la DB real (`tests/test_narrative_game.py:20-21`, `tests/test_narrative_v2_game.py:24-25`); borrado de runs (`:54` y `:42`); seeds automáticos si hay colecciones vacías (`:24-25` y `:28-29`); generación del mes de la fecha real (`:30-32` y `:34-37`); usuario 0 vía fake token (`test_narrative_v2_game.py:56`).
- **Impacto:** correrlos en un entorno compartido borra/crea datos; cualquier cambio de fecha produce resultados distintos; no son paralelizables ni deterministas.
- **Recomendación:** Fase 0 + reescritura de estos dos tests como E2E controlados.

#### H-12 — Baja: documentación desincronizada

- **Evidencia:** los diagramas usan `?fecha=` mientras la API real usa `?date` (`docs_interna/DIAGRAMAS_ARQUITECTURA_NARRATIVO.md:94,143,147,157` vs `tests/test_narrative_game.py:56,77,83,89` y `setup_service.py:77`); referencia a `router.py` con prefix `/api/narrative/partida` cuando hoy la fuente vive en `game/router.py` y coexiste `/api/narrative/v2/partida` (`ARQUITECTURA_JUEGOS_Y_NARRATIVO.md:172`); la guía de auth documenta `404` donde el servicio devuelve `401` (`GUIA_INTEGRACION_FRONTEND_AUTH.md:62` vs `auth/service.py:100-104`) y `201 Created` donde `register` responde 200 (`GUIA_INTEGRACION_FRONTEND_AUTH.md:154` vs `auth/router.py:48-55`).
- **Recomendación:** contract tests de OpenAPI + actualizar guías.

#### H-13 — Baja: higiene de repositorio

- **Evidencia:** `.pyc` huérfanos sin fuente en `app/features/narrative/__pycache__/` (`router.cpython-312/313.pyc`, `router_v2.*`, `service.*` — la fuente v1 ya no existe); import duplicado de `StarletteHTTPException` (`app/main.py:100-102` y `:143`); `Dockerfile:1` usa Python 3.12 mientras el `.venv` local generó pycache 3.13; endpoints de attempts con defaults temporales `year=2026/month=10` (`user_attempts/router.py:78-79`, `service.py:118-119`).
- **Recomendación:** limpieza; lint que detecte imports duplicados (`ruff F811`).

#### H-14 — Baja: excepciones tragadas

- **Evidencia:** 18 coincidencias de `except Exception` en `app/`. Ejemplos: seed de finalizaciones en startup solo loguea warning (`app/main.py:47-48`); fallo al sumar puntos solo warning (`app/features/user_attempts/service.py:94-95`); fallo al crear índices únicos solo warning (`app/core/database.py:103-104`).
- **Impacto:** pérdida silenciosa de invariantes (los índices únicos son la última defensa de H-09/H-04).
- **Recomendación:** distinguir recuperables de críticos; al menos un test que garantice que `init_indexes` propaga errores en entorno de test.

---

## 6. Riesgos, supuestos y preguntas abiertas

### 6.1 Riesgos

1. **Corregir los hallazgos críticos sin red de seguridad:** no hay tests de auth/admin; cualquier fix (H-01..H-06) puede introducir regresiones invisibles. Mitigar simultáneamente con Fases 0-2.
2. **Arranque no determinista:** `lifespan` ejecuta seeds y `ensure_current_and_next_month_generated()` (`app/main.py:36-48`) con llamadas RAE y `sleep(0.2)` (`daily_challenges/service.py:409`); en entornos sin red el arranque degrada y los E2E con lifespan fallarán.
3. **Datos mezclados:** el invitado `user_id=0` y los tests comparten espacio con datos de usuarios reales si se corre contra la DB de desarrollo (H-05/H-11).
4. **Multi-proceso futuro:** el rate limiter in-memory no sobrevive workers/reinicios (`core/rate_limit.py:32`).
5. **Drift documental creciente:** 5 guías en `docs_interna/` ya desincronizadas; sin contract tests el drift continuará.

### 6.2 Supuestos

- El proyecto se despliega con **un solo worker** de uvicorn (comando sin `--workers` en `Dockerfile:21`), lo que hace tolerable hoy el limiter in-memory.
- Caddy es el único ingreso (solo publica `8082`, `docker-compose.yml:10`) y sería quien puede sanear/proveer la IP real; **no se verificó** que setee `X-Forwarded-For` de forma confiable (fuera del alcance de esta lectura).
- La documentación (`docs_interna/`) se usa como referencia de frontend; se asume que las discrepancias citadas en H-12 no fueron intencionales.
- No existe CI en este repositorio; si existe en otra plataforma, el plan de Fase 5 debe adaptarse.

### 6.3 Preguntas abiertas

1. ¿Existe un pipeline de CI en otra plataforma? ¿Cuál es la cobertura mínima aceptable?
2. ¿El modo invitado del narrativo es un requisito de producto? Si sí, ¿cómo se identifica a cada anónimo (cookie/sesión)?
3. ¿El puntaje de los juegos debe ser server-authoritative? ¿El frontend ya envía `guesses/game_data` suficientes para recalcularlo?
4. ¿Se busca persistencia real de imágenes subidas (`app/static/narrative`)? Hoy no hay volumen en compose (`docker-compose.yml:99-100`), lo que condiciona los tests de upload.
5. ¿MongoDB en producción será gestionado (con auth/TLS) o el `mongo:7.0` del compose sin autenticación?
6. ¿Se puede eliminar definitivamente la v1 del narrativo (pyc huérfanos y referencias en docs) y el seed `seed_narrative.py` de 1.789 líneas, o se mantienen por retrocompatibilidad?

---

## Anexo A — Archivos consultados en la auditoría

`app/main.py`; `app/core/{config,database,dependencies,security,rate_limit,rae_client}.py`; `app/features/auth/{router,service,schemas}.py`; `app/features/usuario/router.py`; `app/features/progreso/{router,service,schemas}.py`; `app/features/user_attempts/{router,service,schemas}.py`; `app/features/daily_challenges/{router,service,schemas,wordle_generator,sudoku_generator,sopa_generator,crucigrama_generator}.py`; `app/features/narrative/{router→game/*,admin/*,engine/*,schemas/*,enums,constants}.py`; `app/features/narrative/docs/*`; `app/scripts/{init_db,seed_challenges,seed_sudoku,seed_sopa_letras,seed_narrative,migrate_from_mysql}.py`; `tests/test_narrative_game.py`; `tests/test_narrative_v2_game.py`; `requirements.txt`; `Dockerfile`; `docker-compose.yml`; `Caddyfile`; `.env.example`; `README.md`; `docs_interna/{ARQUITECTURA_JUEGOS_Y_NARRATIVO,DIAGRAMAS_ARQUITECTURA_NARRATIVO,GUIA_INTEGRACION_FRONTEND_AUTH,GUIA_PROGRESO_USUARIO,README_SEGURIDAD}.md`.

**Riesgo residual de esta auditoría:** el análisis fue estático (sin ejecución); los comportamientos de runtime (p. ej. evasión real del rate limit, carreras reproducibles) se infieren del código y quedan pendientes de confirmación con los tests propuestos.
