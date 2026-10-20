# Auditoría 06 — Plan de soluciones: Testing y Calidad

| Campo | Valor |
|---|---|
| **Proyecto** | `mayores_actualizacionesSIPI-BACK` — Backend "Mayores Actualizaciones" (FastAPI + MongoDB/Motor) |
| **Ruta** | `C:\Users\nmonti\Desktop\proyectos\backend\mayores_actualizacionesSIPI-BACK` |
| **Fecha** | 19/10/2026 |
| **Insumo principal** | `auditorias/06-testing-y-calidad.md` (inventario, mapa de riesgo, estrategia por fases, hallazgos H-01…H-14) |
| **Insumos secundarios** | `auditorias/00-informe-consolidado.md`; referencias cruzadas a `01-arquitectura-y-modularidad.md`, `02-persistencia-y-flujo-de-datos.md`, `03-auditoria-de-seguridad.md` y `05-eficiencia-y-rendimiento.md` |
| **Etapa** | **Planificación**. Este documento es un plan; **nada de lo aquí propuesto está implementado**. |
| **Nota de ejecución** | **No se ejecutó pytest, ni ningún test, ni la aplicación; no se tocó ninguna base de datos; no se modificó código, tests ni configuración.** Todo el diseño se basa en el análisis estático de los informes previos y en lectura (solo lectura) del código. |
| **Único archivo creado** | Este documento (`auditorias/06-testing-y-calidad-soluciones.md`). |

**Escala de esfuerzo usada en todo el documento:** `S` ≤ 0,5 día-persona · `M` 0,5–2 días-persona · `L` > 2 días-persona (por fase, tester con contexto).

---

## 1. Resumen ejecutivo y estrategia de adopción

### 1.1 Punto de partida (según informe 06)

- Solo existen **2 tests** (`tests/test_narrative_game.py`, `tests/test_narrative_v2_game.py`): integración E2E contra la **Mongo real del `.env`**, dependientes del reloj y destructivos (borran la run del usuario 0 del día: `test_narrative_game.py:54`, `test_narrative_v2_game.py:42`).
- **Sin infraestructura**: `pytest`/`pytest-asyncio`/`httpx` no declarados (`requirements.txt:1-15`), sin `conftest.py`, sin config, sin CI (`.github/` no existe).
- **Sin red de seguridad para los hallazgos críticos**: auth, user_attempts (IDOR/puntos), progreso (RLS), daily_challenges (admin sin auth, soluciones filtradas), narrativo (admin sin auth, invitado compartido `user_id=0`, carreras) y seeds no tienen ni un test.
- Riesgo central: **corregir H-01…H-06 (planes 02/03) sin tests de regresión** hace invisible cualquier ruptura nueva.

### 1.2 Estrategia de adopción ("sin frenar el desarrollo")

1. **Fase 0 primero y corta** (1–2 días): dependencias de test, `conftest.py`, DB efímera, fechas congeladas, mocks de red (RAE/SMTP) y configuración de markers. Habilita todo lo demás.
2. **Tests por riesgo, no por cobertura ciega**: el orden de las fases sigue el mapa de riesgo del informe 06 (auth → user_attempts/puntos → progreso → daily_challenges → narrativo → seeds/ETL → seguridad transversal → CI).
3. **Regla "un fix P0 = un test de regresión en el mismo PR"**: cada corrección de los planes 02/03 aterriza con el test que la fija. Los tests que documentan un bug aún no corregido se escriben en modo **`xfail` estricto** (`xfail_strict = true`): cuando el fix llega, el test pasa de rojo-documentado a **fallo por XPASS**, lo que obliga a quitar el marker en el mismo PR del fix. Así los tests se pueden adelantar sin bloquear el desarrollo, y no quedan `xfail` zombis.
4. **Verde honesto**: prohibido debilitar un assert para "hacer pasar" un bug conocido; el mecanismo es `xfail(reason="H-xx: pendiente fix plan 03")`.
5. **Los 2 tests existentes se reescriben, no se borran**: se portan a DB efímera + fecha congelada + usuario autenticado (dejan de ser destructivos y toman valor como smoke E2E).
6. **CI como única puerta objetiva** (Fase 7): lint → unit → integración con `mongo:7.0` → seguridad; cobertura con ratchet incremental y reglas por área (no 100% ciego).

### 1.3 Fases macro

| Fase | Nombre | Contenido | Esfuerzo |
|---|---|---|---|
| **0** | Habilitadores | dependencias dev, conftest, DB efímera, mocks, markers, estructura `tests/`, port de los 2 tests | M |
| **1** | Auth y sesión | unit + integración de `auth` y `core/security` (PIN, bloqueo, enumeración, roles) | M |
| **2** | Intentos, puntos y RLS | `user_attempts` (IDOR, scoring, puntos), `progreso` (RLS), `usuario` (admin) | M–L |
| **3** | Desafíos diarios | generadores (determinismo/correctitud), service (meses/fechas/TZ), API (admin, solución no filtrada) | M |
| **4** | Narrativo | engine unit, partida V2 (happy path, errores, doble submit, invitados), admin (authz + CRUD) | L |
| **5** | Datos y arranque | seeds idempotentes, lifespan sin red, `init_indexes` fail-fast, ETL dry-run | S–M |
| **6** | Seguridad y contratos | matriz authz parametrizada, JWT forjado/vencido, rate limit/XFF, CORS, OpenAPI/docs | M |
| **7** | CI/CD y calidad | pipeline lint→unit→integración, cobertura por área, ruff, pre-commit, typing gradual, docs | S–M |

### 1.4 Definición de éxito (criterios medibles)

1. `python -m pytest` corre en un clon limpio **sin Mongo real ni acceso a red** y pasa (los casos `docker`/`slow` quedan marcados y skipeados por defecto).
2. Ningún test abre la DB configurada en `.env`: guardia dura `MONGODB_DB_NAME` con sufijo `_test` + `network_guard`.
3. Existe una matriz authz parametrizada que cubre **todos** los endpoints de escritura/admin, con expectativas 401/403/200, y hace fallar CI si aparece un endpoint nuevo sin clasificar.
4. Los dos tests narrativos viejos ya no tocan datos de desarrollo y corren dos veces seguidas con el mismo resultado (idempotencia del entorno).
5. Rueda el pipeline en cada PR con lint + unit + integración y umbrales de cobertura incrementales (ratchet).

### 1.5 Esfuerzo total estimado

**~18–26 días-persona** repartidos en ~4–5 semanas calendario a media dedicación (o ~2,5–3 semanas full-time con dos personas en paralelo). El detalle por fase está en la sección 5 y el roadmap en la sección 7.

---

## 2. Principios del plan

1. **Riesgo primero (trazabilidad hallazgo → test).** Cada bloque de tests referencia el hallazgo que mitiga (H-xx del informe 06, CR-xx/AL-xx del informe 03). El Anexo A es la matriz de trazabilidad. Ningún hallazgo Crítico/Alto queda sin al menos un test de regresión.
2. **DB efímera por test.** Por defecto `mongomock-motor` en memoria, recreada por test; cuando se necesita semántica real (índices únicos, carreras, `DuplicateKeyError`), Mongo de test real vía testcontainers local o *service container* de CI, siempre con nombre de base terminado en `_test` y guardia que aborta si no lo está.
3. **No depender de datos productivos.** Seeds programáticos mínimos por fixture (`seed_catalog`, `seed_challenge_day`); prohibido leer/clampear colecciones reales o imágenes subidas. Cero llamadas a RAE/SMTP reales: `mock_rae` y `mock_smtp` autouse.
4. **Determinismo total.** Fechas congeladas (`freezegun`), sin `datetime.now()` real en setup de tests, sin depender de `random` global no sembrado (semillas explícitas). Un test que falla un día sí y otro no es un bug del test.
5. **Pirámide pragmática.** Mucho unit de servicios/puros (rápidos, sin I/O), integración ASGI con DB efímera para contratos y authz, y pocos E2E (ciclo narrativo, arranque). Los E2E usan el mismo seed determinista que unit.
6. **Verde honesto y `xfail` estricto.** Los tests se pueden escribir antes del fix, marcados `xfail(reason="H-xx")`; `xfail_strict = true` convierte el "XPASS" en fallo cuando el fix aterriza, forzando limpieza del marker. Nada de tests comentados ni asserts castrados.
7. **Tests de comportamiento, no de implementación.** Se assertea el contrato HTTP (status, shape JSON, efecto en DB) y las reglas de negocio; se evita acoplarse a nombres de campos internos no contratados.
8. **Aislamiento y paralelismo.** Fixture autouse que limpia el rate limiter in-memory (`rate_limiter._history`) y contadores entre tests; tests docker/slow marcados para no correr en el gate rápido; sin compartir el invitado `user_id=0` entre tests (cada test crea sus usuarios).
9. **Rápido por defecto.** Objetivo: suite `unit` < 30 s, suite con integración mongomock < 3 min en CI. Lo que supere eso va a `slow` o `docker`.
10. **CI como puerta de calidad.** El gate de PR (lint + unit + integración) es lo que evita la regresión futura; sin CI, todo este plan se degrada en semanas.

---

## 3. Tabla resumen: área | casos | prioridad | esfuerzo | fase

Conteos de diseño (aproximados; la matriz de seguridad es parametrizada y multiplica ejecuciones). Prioridad según informe 06 (P0 bloqueante, P1 alta, P2 media).

| Área | Casos (aprox.) | Prioridad | Esfuerzo | Fase |
|---|---:|---|---|---|
| Infra de testing (self-tests de conftest/guardias) | ~6 | P0 | M | 0 |
| `auth` (login sistemas/PIN, registro, verificación, roles, enumeración, bloqueo) | ~25 | P0 | M | 1 |
| `user_attempts` (ownership/IDOR, scoring server-side, no duplicar puntos, concurrencia) | ~22 | P0 | M | 2 |
| `progreso` (RLS self/admin/tercero) | ~9 | P1 | S | 2 |
| `usuario` (torre de control: permisos, paginación, filtros, toggles) | ~11 | P1 | S–M | 2 |
| `daily_challenges` — generadores (determinismo, correctitud, RAE mockeado) | ~9 | P1 | M | 3 |
| `daily_challenges` — service + API (meses, fechas/TZ, idempotencia, solución no filtrada, admin sin auth) | ~19 | P0 (escritura) / P1 | M | 3 |
| `narrative` — engine (condiciones, efectos, sorteos, finales) | ~10 | P1 | M | 4 |
| `narrative` — partida V2 (happy path, errores, doble submit, invitados, modales) | ~18 | P0 | L | 4 |
| `narrative` — admin (32 endpoints: authz + smoke CRUD) | ~10 | P0 | M | 4 |
| Seeds idempotentes + arranque (`lifespan`, `init_indexes`) | ~13 | P1 | S–M | 5 |
| ETL MySQL→Mongo (dry-run, upsert por email, colisiones) | ~5 | P2 | S–M | 5 |
| Seguridad transversal (matriz authz, JWT forjado/vencido, rate limit/XFF, CORS) | ~21 + parametrizadas | P0 | M | 6 |
| Contratos/OpenAPI + sincronía `docs_interna` | ~5 | P1 | S | 6 |
| CI/CD, cobertura, lint, pre-commit, typing, política de errores | n/a (pipeline + configs) | P0–P1 | M | 7 |
| **Total** | **~180 casos** (más matriz parametrizada) | | **M–L** | |

---

## 4. Fase 0 — Habilitadores (detallada)

### 4.0 Ficha de la fase

- **Objetivo:** construir la infraestructura mínima para que cualquier persona pueda escribir y correr tests aislados, deterministas y sin red ni DB productiva, y portar los 2 tests existentes a esa base.
- **Alcance:** `requirements-dev.txt`, `pyproject.toml` (pytest + ruff), `tests/conftest.py` + `tests/unit|integration|security|e2e/fixtures/`, mocks de RAE/SMTP, guardias de seguridad; sin tocar código de `app/` (salvo que un fix de otro plan lo requiera; los monkeypatches viven en tests).
- **Herramientas:** pytest, pytest-asyncio, httpx, mongomock-motor, testcontainers[mongodb], freezegun, respx, pytest-cov, pytest-timeout, ruff, pre-commit.
- **Pasos:** 4.1 → 4.8.
- **Criterios de aceptación:** 4.9.
- **Riesgos:** 4.10.
- **Esfuerzo:** **M (1–2 días)**.
- **Dependencias:** ninguna. **Bloquea a todas las fases 1–7.** Recomendación: ejecutarla en paralelo con los primeros fixes P0 del plan 03 (los tests de esos fixes dependen de esta fase).

### 4.1 Dependencias de desarrollo

Crear **`requirements-dev.txt`** (o extras `[dev]` en `pyproject.toml`; se recomienda `requirements-dev.txt` por consistencia con `requirements.txt` ya existente). Propuesta:

| Paquete | Rol | Obligatorio |
|---|---|---|
| `pytest` | runner | Sí |
| `pytest-asyncio` | tests async (`asyncio_mode=auto`) | Sí |
| `httpx` | cliente ASGI (`ASGITransport`); ya lo usan los tests sin estar declarado | Sí |
| `pytest-cov` + `coverage[toml]` | cobertura y umbrales | Sí |
| `mongomock-motor` | Mongo en memoria para unit/la mayoría de la integración | Sí |
| `testcontainers[mongodb]` | Mongo real efímero local para tests `docker` | Sí (con Docker); alternativa: solo `TEST_MONGODB_URL` |
| `pytest-timeout` | evitar cuelgues por `sleep(0.2)`/RAE (`daily_challenges/service.py:409`) | Sí |
| `freezegun` | fechas congeladas (o `time-machine` como alternativa; se elige freezegun por familiaridad y `tz_offset`) | Sí |
| `respx` | mock HTTP para futuros clientes httpx; hoy el RAE usa `urllib` y se mockea por monkeypatch (ver 4.6) | Sí (por si el plan 05 migra RAE a httpx) |
| `asgi-lifespan` | ejecutar `lifespan` real en el smoke de arranque | Sí |
| `ruff` | linter + formatter | Sí |
| `pre-commit` | hooks locales | Sí |
| `pyright` (o `mypy`) | type checking gradual (decisión en 8.x) | Opcional fase 7 |
| `faker` | datos de fábrica para usuarios/tests | Opcional |

**Notas:**

- **Versión de Python:** fijar **3.12** (alineada con `Dockerfile:1 python:3.12-slim`) y documentarla; hoy el `.venv` generó pycache 3.13 (H-13). Decisión pendiente en 8.x, pero la suite debe correr en una única versión declarada (idealmente también en CI).
- **Pines:** `requirements.txt` usa `>=` (H-13). En Fase 0, **no** pinchar lo productivo (riesgo de romper), pero sí **generar un lock/`pip freeze` del entorno dev** para que CI sea reproducible (ver 6.8). Compatibilidad a verificar antes de fijar: `motor>=3.6` + `pymongo>=4.9` con `mongomock-motor` (si hay incompatibilidad, plan B: bajar a `testcontainers` para toda la integración o aislar los tests sin DB detrás de funciones puras; queda como pregunta 8.x).
- **Regla de oro:** `requirements-dev.txt` nunca se copia al `Dockerfile` de producción (la imagen no lleva pytest ni testcontainers).

### 4.2 Estructura de carpetas propuesta

```text
tests/
├── conftest.py                  # fixtures globales y guardias
├── fixtures/
│   ├── factories.py             # user_factory, challenge_factory, narrative_seed
│   ├── data/
│   │   ├── narrative_min.json   # universo/personajes/cartas/eventos mínimos
│   │   └── challenges_min.json
│   └── __init__.py
├── unit/
│   ├── conftest.py
│   ├── test_core_security.py
│   ├── auth/                    # test_auth_service.py, ...
│   ├── user_attempts/
│   ├── daily_challenges/        # generadores y service (sin HTTP)
│   └── narrative/               # engine, endings, transition (sin HTTP)
├── integration/
│   ├── conftest.py
│   ├── test_auth_api.py
│   ├── test_usuario_api.py
│   ├── test_progreso_api.py
│   ├── test_user_attempts_api.py
│   ├── test_daily_challenges_api.py
│   ├── test_narrative_api.py
│   └── test_narrative_admin_api.py
├── security/
│   ├── conftest.py
│   ├── authz_matrix.yaml        # clasificación endpoint → rol esperado (fuente de la matriz)
│   ├── test_authz_matrix.py
│   ├── test_jwt.py
│   ├── test_rate_limit.py
│   └── test_cors.py
├── e2e/
│   ├── test_narrative_v2_cycle.py      # port de test_narrative_v2_game.py
│   ├── test_narrative_setup_modals.py  # port de test_narrative_game.py
│   ├── test_seeds_idempotent.py
│   ├── test_lifespan_smoke.py
│   └── test_etl_dry_run.py
└── docker/                      # solo semántica real (índices, carreras)  [opcional, o dentro de integration con marker]
```

- No hace falta `tests/__init__.py` (pytest con rootdir); sí evitar nombres de archivo duplicados.
- Los 2 archivos actuales se **mueven** a `tests/e2e/` con los nombres de arriba y se reescriben (4.8). Decisión de compatibilidad: dejar de soportar la ejecución manual `python tests/test_x.py` (pregunta 8.x).

### 4.3 Configuración de pytest (`pyproject.toml`)

Propuesta (reemplaza la necesidad de `pytest.ini`/`setup.cfg`):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
xfail_strict = true                     # XPASS = fallo: obliga a limpiar markers al corregir
addopts = "-ra --strict-markers --strict-config -m 'not slow'"
markers = [
  "unit: tests puros sin I/O (rápidos)",
  "integration: ASGI + DB efímera (mongomock)",
  "docker: requiere Mongo real (testcontainers o TEST_MONGODB_URL)",
  "security: autorización, abuso, hardening",
  "e2e: ciclos completos o arranque",
  "slow: no corre por defecto",
]
timeout = 120                           # pytest-timeout; el smoke de lifespan no debe colgarse
filterwarnings = ["error::DeprecationWarning:app.*"]
```

- **Markers solicitados:** `unit`, `integration`, `security`, `slow` (+ `docker` y `e2e` como adicionales necesarios).
- **Convención de ejecución:** `pytest -m unit`, `pytest -m "integration and not docker"`, `pytest -m docker`, `pytest -m security`, `pytest -m e2e --slow`. Los `docker` se skipean con mensaje claro si no hay `TEST_MONGODB_URL` ni Docker.
- **freezegun + asyncio:** con `asyncio_mode=auto` no se necesitan decoradores; el freeze se aplica por fixture.

### 4.4 `tests/conftest.py` — inventario de fixtures

| Fixture | Scope | Qué hace | Rol de aislamiento |
|---|---|---|---|
| `testing_env` | session, autouse | Exporta `TESTING=1` **antes** de importar `app.main` (import perezoso dentro de fixtures); fuerza `settings.FRONTEND_URL`, etc. a valores de test | Evita que un import tardío dispare configuración real |
| `db` | function | Crea `AsyncMongoMockClient`, monkeypatchea `app.core.database.db_instance.client/.db` y por lo tanto `get_database()`; recrea store por test | DB efímera por test; destruye el estado entre tests |
| `real_db` | function | Si `TEST_MONGODB_URL` está set o hay Docker: cliente Motor real (testcontainers `mongo:7.0`); si no, `pytest.skip("docker no disponible")`. **Guardia:** aborta si el nombre de DB no termina en `_test` | Paridad real solo donde importa (índices/carreras) |
| `client` | function | `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`. **Sin lifespan** (ASGITransport no ejecuta eventos de lifespan), por lo que **no corren seeds ni `ensure_current_and_next_month_generated()`** (`app/main.py:36-48`) | Sin red, sin seeds, sin arranque |
| `client_lifespan` | function | `asgi-lifespan.LifespanManager` + mocks de red; solo smoke de arranque (Fase 5) | Prueba el arranque real de forma controlada |
| `frozen_today` | function | `freeze_time("2026-10-19 12:00:00", tz_offset=0)` + helper `today_str` | Determinismo de fechas; los tests de TZ eligen offsets explícitos |
| `user_factory` | function | Función que inserta usuario alumno (id desde `counters`, BCrypt barato configurable, `estado_id=2`, `activo=True`) y devuelve el doc | Cada test crea sus usuarios; nadie depende de datos previos |
| `admin_user` / `alumno_user` | function | Atajos sobre `user_factory` | Idem |
| `auth_headers(user)` / `admin_headers` | function | `create_access_token` con el usuario dado (`app/core/security.py:29`) | Identidad controlada; tokens emitidos en test |
| `expired_headers` / `forged_headers` | function | Token con `exp` pasado / firmado con otro secreto | Base de Fase 6 |
| `seed_estados` | function | Inserta los 3 estados de `ESTADOS_INICIALES` (`app/scripts/init_db.py:9-34`) sin correr el seed completo | Seed mínimo |
| `seed_challenge_day` | function | Inserta un `daily_challenges` wordle (o del juego pedido) para la fecha pedida | Seed mínimo |
| `seed_narrative_min` | function | Inserta universo `test_uni` (con `recursos`), 5 personajes, 5 cartas, evento + resultados y challenge narrativo del día con config mínima; devuelve ids | Seed mínimo determinista para narrativo |
| `mock_rae` | autouse | Monkeypatch de `app.core.rae_client.fetch_rae_definition/get_masked_definition/get_definition` **y** de los imports directos en `wordle_generator`/`sopa_generator` con un diccionario fijo; espía de llamadas | Cero red; cero `time.sleep(1.2)` (`rae_client.py:183`) |
| `mock_smtp` | autouse | Monkeypatch de `email_service.enviar_magic_link`/`enviar_codigo_activacion` (o de `aiosmtplib.send`) devolviendo `True`; registra destinatario/código para asserts | Cero SMTP real; permite capturar el PIN en flujos registro→verificación |
| `network_guard` | autouse | Parchea `socket.socket.connect` para fallar en hosts/puertos no permitidos (permite localhost del Mongo de test) | Cualquier test que intente red real falla con mensaje claro |
| `reset_rate_limiter` | autouse | Limpia `rate_limiter._history` de `app/core/rate_limit.py:32` | Evita 429 fantasma entre tests |
| `deterministic_random` | function (opt-in) | Semilla fija (`random.seed(42)`) o `random.Random(42)` inyectado | Tests de sorteos/generadores deterministas |

**Detalles de implementación a respetar (evitan falsos imposibles):**

- `get_database()` es perezoso: si `db_instance.db is None`, crea cliente real (`app/core/database.py:14-18`). El fixture debe parchear **antes** de que cualquier servicio lo llame; parchear `db_instance` completo es lo más robusto.
- `ASGITransport(app)` **no** dispara `startup/lifespan`; esto es una ventaja (no corren seeds) y hay que documentarlo para que nadie "arregle" tests activando lifespan por default.
- Para tests de `lifespan` usar `asgi-lifespan` + `mock_rae` + `mock_smtp` + `db` (mongomock) o `real_db`.

### 4.5 Política de base de datos: mongomock vs Mongo real

| Capacidad | mongomock-motor | Mongo real (`mongo:7.0`) | Consecuencia |
|---|---|---|---|
| CRUD, filtros, `upsert`, `$set/$inc` | Sí | Sí | Unit + mayoría de integración |
| `find_one_and_update(return_document=AFTER)` | Sí (verificar versión) | Sí | Idempotencia básica |
| **Índices únicos se aplican** | **No** | Sí | Todo test de `DuplicateKeyError`/idempotencia-concurrente va a `docker` |
| Semántica de carrera real (`$inc` concurrente, doble submit) | Limitada (serial) | Real | Tests de concurrencia (H-04/H-09) van a `docker` |
| Transacciones multi-documento | No | Requieren replica set; **el compose actual es standalone** (`docker-compose.yml:72-97`) | No se testean transacciones hasta que el plan 02 decida; se testea el upsert condicionado |
| Velocidad | Muy rápida | Lenta (segundos de arranque) | Default mongomock; `docker` solo lo necesario |

Regla operativa: si un test valida un **invariante de base** (unicidad, atomicidad, carrera), es `docker` y corre en CI con service container y local con testcontainers/TEST_MONGODB_URL.

### 4.6 Mocks externos (RAE y SMTP)

- **RAE:** `app/core/rae_client.py` usa `urllib.request.urlopen` + `time.sleep` (síncrono). `respx` no aplica a `urllib`; por eso el mock es **monkeypatch de funciones** (`fetch_rae_definition`, `get_definition`, `get_masked_definition`) en el módulo de origen **y** en los módulos que hacen `from ... import fetch_rae_definition` (`wordle_generator.py:12-13,51`; `sopa_generator.py`). Si el plan 05 migra RAE a httpx/async, `respx` queda listo.
- **SMTP:** monkeypatch de `app/features/auth/email_service.py` (`enviar_magic_link`, `enviar_codigo_activacion`). El espía guarda `(destinatario, codigo)` para poder completar flujos de verificación sin SMTP.
- **Pillow/upload:** los tests de upload usan una imagen mínima generada en memoria (no fixtures binarios grandes).

### 4.7 Guardias de seguridad de la suite

1. **Guardia de DB productiva:** fixture session que falla si `settings.MONGODB_DB_NAME` no termina en `_test` **o** si `TEST_MONGODB_URL` apunta a una base sin sufijo. También falla si algún test intenta usar el cliente real sin `real_db`.
2. **Guardia de red:** `network_guard` autouse; cualquier `connect` externo levanta excepción con traceback identificable.
3. **Guardia de seeds:** test que verifica que `client` no ejecutó seeds (colecciones de catálogo vacías tras crear el cliente).
4. **Auto-test de la infraestructura** (para que la Fase 0 tenga su propio verde): `test_guardia_db_real_falla_en_produccion`, `test_guardia_red_bloquea_host_externo`, `test_reset_rate_limiter_limpia_estado`, `test_frozen_today_es_estable`, `test_mongomock_no_aplica_indices_unicos` (documenta la limitación y justifica los `docker`), `test_client_no_ejecuta_lifespan`.

### 4.8 Port de los 2 tests existentes (mismos flujos, nueva base)

- `tests/e2e/test_narrative_setup_modals.py` (port de `test_narrative_game.py`): fecha congelada, `seed_narrative_min`, **usuario autenticado** para el ciclo (y un test aparte para el invitado), sin `delete_one` sobre datos reales, y asserts más profundos (ids ofrecidos ⊂ catálogo, corte tiene 3, inventario 3, historial mes 1, tras reiniciar `tiene_partida_activa == False`).
- `tests/e2e/test_narrative_v2_cycle.py` (port de `test_narrative_v2_game.py`): ciclo completo con seed determinista, DB efímera, fecha congelada, usuario autenticado; se conservan los asserts de `fase_actual`/`finalizacion` y se agregan invariantes (un evento por mes, fases válidas, recursos dentro de límites).
- Se elimina el `fake_token` que caía en `user_id=0` (`test_narrative_v2_game.py:56`); el comportamiento de invitado se prueba en un test dedicado (Fase 4).
- Decisión: estos archivos dejan de ser ejecutables con `python tests/...`; pasan a serlo con `pytest -m e2e`.

### 4.9 Criterios de aceptación (Fase 0)

1. `pip install -r requirements.txt -r requirements-dev.txt` en un venv limpio y `python -m pytest -m "unit or (integration and not docker)"` pasa **sin Mongo externo ni red**.
2. Los 4 self-tests de guardias (4.7) pasan; el test de "DB con nombre sin `_test`" **falla a propósito** cuando se simula, demostrando la guardia.
3. Los 2 tests portados pasan 2 veces seguidas con el mismo resultado y no dejan documentos en la DB de desarrollo (verificado por diseño: DB efímera).
4. `pyproject.toml` con `[tool.pytest.ini_options]` es la única config de pytest (sin `pytest.ini`).
5. `python -m pytest --collect-only -q` lista los markers `unit/integration/docker/security/e2e/slow` sin warnings de markers desconocidos.

### 4.10 Riesgos y mitigaciones (Fase 0)

| Riesgo | Impacto | Mitigación |
|---|---|---|
| `mongomock-motor` incompatible con `motor`/`pymongo` vigentes | Alto (bloquea integración) | Verificar **antes** de comprometerse; plan B: `testcontainers` como default de integración y unit sin DB (funciones puras) |
| Tests que "pasan" por accidente contra `get_database()` real | Crítico | `network_guard` + guardia de nombre `_test` + revisión de fixtures |
| freezegun no congela `datetime.now()` de dependencias en C | Bajo | Los módulos usan `datetime` de stdlib; auto-test `test_frozen_today_es_estable` |
| Seeds mínimos divergen del seed real (`seed_narrative.py` 1.789 líneas) | Medio | `narrative_min.json` versionado + test de compatibilidad de schemas (Fase 4); decidir suerte del seed real (H-13/8.x) |
| Importar `app.main` antes de setear `TESTING` | Medio | Imports perezosos dentro de fixtures y `testing_env` session autouse |

---

## 5. Plan por fases con casos de test enumerados

**Nota metodológica.** Las fases 1–6 reorganizan el contenido de las Fases 1–4 del informe 06 agrupándolo por riesgo/feature (mismo orden de prioridad: auth → user_attempts/progreso → challenges → narrativo → datos → seguridad). La Fase 7 corresponde a la Fase 5 del informe (calidad continua). Convenciones de las tablas de casos:

- **Estado inicial**: `PASA` = debe pasar hoy (regresión pura); `XFAIL H-xx` = el test documenta el bug y queda `xfail` estricto hasta que aterrice el fix del hallazgo (ver 1.2.3); `DOCKER` = requiere Mongo real (testcontainers/CI) y va con marker `docker`.
- Los nombres son propuestas concretas de archivo/test; la implementación es parte de cada fase (aquí no se escriben archivos de test).
- Cada test lleva en su docstring el `Hallazgo: H-xx / CR-xx` que cubre (trazabilidad, Anexo A).

---

### Fase 1 — Auth y sesión (P0)

- **Objetivo:** fijar con tests el portón del sistema (login sistemas, login PIN, registro/verificación, tokens) y documentar con `xfail` los agujeros P0/P1 del informe 03 (CR-04, CR-05, AL-02, AL-04, H-08) para que cada fix llegue con su regresión.
- **Alcance:** `app/features/auth/{router,service,schemas}.py`, `app/core/{security,dependencies}.py`, `app/core/rate_limit.py` (solo lo tocado por auth).
- **Herramientas:** fixture `db`, `user_factory`, `mock_smtp`, `frozen_today`, `client`, `reset_rate_limiter`.
- **Pasos:** (1) unit de servicio sobre DB efímera; (2) integración API con `ASGITransport`; (3) revisar con el equipo las decisiones de contrato (enumeración uniforme, PIN vs activación) antes de fijar los `xfail` definitivos.

#### 1A. Unit — `tests/unit/auth/test_auth_service.py` (+ `test_core_security.py`)

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_login_sistemas_ok_admin_activo` | admin activo + password correcto → `success=True` y token decodificable con `id/tipoUsuario` | PASA |
| `test_login_sistemas_password_incorrecta_401` | 401 genérico, sin distinguir email | PASA |
| `test_login_sistemas_email_inexistente_401` | mismo 401 que password mala (no enumeración por este canal) | PASA |
| `test_login_sistemas_alumno_403` | rol alumno no entra por login-sistemas (`service.py:70-74`) | PASA |
| `test_login_sistemas_inactivo_403` | cuenta `activo=False` → 403 | PASA |
| `test_login_codigo_ok_activo` | PIN correcto de alumno activo → token | PASA |
| `test_login_codigo_inexistente_401` / `test_login_codigo_pendiente_403` / `test_login_codigo_inactivo_403` | matriz de estados de `login_codigo` (`service.py:98-117`) | PASA |
| `test_login_codigo_admin_pin_no_emite_token` | CR-04/ME-02: hoy el PIN fijo del admin (`init_db.py:80`) loguea como usuario; fix: restringir rol admin a login-sistemas | XFAIL CR-04 |
| `test_register_publico_fuerza_tipo_usuario_1` | mass assignment: `tipoUsuario=2` en registro público se ignora (`service.py:246`) | PASA |
| `test_register_email_duplicado_activo_400` | duplicado activo → 400 | PASA |
| `test_register_email_duplicado_pendiente_reenvia_codigo` | pendiente → 200 + reenvío (spy SMTP) | PASA |
| `test_register_codigo_provisto_cliente_sin_validar` | ME-11: hoy acepta PIN elegido por el cliente sin validar formato/unicidad (`schemas.py:29`, `service.py:235-241`); fix: `^\d{6}$` + unicidad | XFAIL AL-02 |
| `test_register_genera_pin_6_digitos_unico` | generación cuando no se provee: rango numérico y no colisiona con existentes | PASA |
| `test_register_carrera_de_duplicados_no_500` | H-09: dos registros concurrentes → `DuplicateKeyError` controlado (200/409), no 500 | DOCKER + XFAIL H-09 |
| `test_verificar_codigo_registro_activa_y_emite_token` | flujo feliz de activación | PASA |
| `test_verificar_codigo_registro_incorrecto_400` | código erróneo → 400 | PASA |
| `test_verificar_codigo_no_es_pin_permanente` | AL-02: hoy el código de activación **es** el PIN de login (`service.py:310`); fix: separar ambos | XFAIL AL-02 |
| `test_reenviar_codigo_ok_activo_400_inexistente_404` | contratos de reenvío (`service.py:340-363`) | PASA |
| `test_modificar_email_registro_ok_pendiente` / `_conflicto_400` | cambio de email en pendiente y colisión con otra cuenta | PASA |
| `test_modificar_email_no_permite_takeover` | CR-05: hoy cambia el email de un pendiente sin verificar posesión y reenvía el PIN (`service.py:365-408`); fix: exigir código al email actual o deshabilitar | XFAIL CR-05 |
| `test_token_firmado_con_otro_secreto_invalido` / `test_token_expirado_invalido` | `core/security.py:56-62` | PASA |
| `test_settings_fail_fast_sin_secretos_default` | H-08/CR-03: en modo producción, `JWT_SECRET` sin default debe impedir arranque; hoy el default embebido es efectivo (`config.py:14`) | XFAIL CR-03 |

#### 1B. Integración API — `tests/integration/test_auth_api.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_api_login_sistemas_ok_devuelve_token` | contrato JSON del login | PASA |
| `test_api_login_sistemas_rate_limit_429` | 5 req/min → 6.º = 429 con `Retry-After` (`auth/router.py:20`) | PASA |
| `test_api_login_codigo_rate_limit_429` | idem PIN (`router.py:28`) | PASA |
| `test_api_flujo_registro_completo` | register → (código capturado del spy) → verificar-codigo → login-codigo | PASA |
| `test_api_verificar_token_ok_y_forjado_401_y_vencido_401` | `verificar-token` con token válido, firmado con otro secreto y expirado | PASA |
| `test_api_verificar_token_usuario_inactivo_403` | token válido pero cuenta inactiva | PASA |
| `test_api_register_publico_no_acepta_campos_admin` | campos admin en registro público no escalan rol | PASA |
| `test_api_enviar_acceso_correo_sin_token_401` / `_con_alumno_403` | único endpoint auth ya protegido (`router.py:38-46`) | PASA |
| `test_api_enumeracion_respuestas_uniformes` | AL-04: hoy 401 (código inexistente) vs 403 (pendiente) vs 404 (reenviar/modificar) revelan existencia; fix: respuestas uniformes | XFAIL AL-04 |
| `test_api_modificar_email_takeover_rechazado` | CR-05 por API | XFAIL CR-05 |
| `test_api_login_codigo_admin_pin_rechazado` | CR-04 por API | XFAIL CR-04 |
| `test_api_no_loguea_codigos_ni_tokens` | AL-05: el flujo no debe dejar PIN/tokens en logs (`caplog`) | XFAIL AL-05 |

- **Criterios de aceptación:** los casos `PASA` verdes; los `XFAIL` listados y estrictos (con `reason` conteniendo el id de hallazgo); cobertura de `auth/service.py` ≥ 70% al cierre de la fase; ningún test depende de reloj real ni de SMTP.
- **Riesgos:** decidir contrato anti-enumeración afecta asserts de varios tests (resolver en 8.x antes de "congelar" los mensajes); el test de carrera exige Mongo real (marcar `docker` para no romper CI rápido).
- **Esfuerzo:** **M (2–3 días)**.
- **Dependencias:** Fase 0; fixes del plan 03 (CR-03/CR-04/CR-05, AL-02/AL-04/AL-05) para desmarcar `xfail` (los tests ya se pueden escribir antes).

---

### Fase 2 — Intentos, puntos y RLS (P0/P1)

- **Objetivo:** blindar el flujo de intentos (ownership/IDOR, scoring server-side, puntos no duplicables) y fijar por regresión las RLS que hoy funcionan (progreso, perfil de usuario), más la matriz de permisos de la torre de control.
- **Alcance:** `app/features/user_attempts/{router,service,schemas}.py`, `app/features/progreso/*`, `app/features/usuario/*`, colección `usuarios.puntos` y `usuarios.progresos`.
- **Herramientas:** `db`/`real_db` (concurrencia), `user_factory`, `auth_headers`/`admin_headers`, `client`, `frozen_today`.
- **Pasos:** (1) unit de `user_attempts/service` incluida la carrera de puntos; (2) integración API de attempts (IDOR y scoring); (3) integración de progreso (RLS); (4) integración de usuario (admin).

#### 2A. Unit — `tests/unit/user_attempts/test_service.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_save_attempt_crea_doc_y_suma_puntos` | upsert + `$inc` de puntos en `usuarios` (`service.py:74-93`) | PASA |
| `test_save_attempt_upsert_mismo_user_game_date_actualiza` | mismo día/juego ⇒ 1 documento | PASA |
| `test_save_attempt_completed_repetido_no_vuelve_a_sumar` | `was_already_completed` (`service.py:71-72`) | PASA |
| `test_save_attempt_in_progress_luego_completed_suma_una_vez` | transición de estado suma una sola vez | PASA |
| `test_save_attempt_score_cero_o_negativo_no_suma` | guarda `req.score > 0` | PASA |
| `test_save_attempt_status_failed_no_suma` | `status != completed` no toca puntos | PASA |
| `test_save_attempt_concurrencia_no_duplica_puntos` | H-04: dos requests concurrentes (`asyncio.gather`) ⇒ un solo `$inc`; hoy el check-then-update duplica | DOCKER + XFAIL H-04 |
| `test_save_attempt_fallo_al_sumar_no_se_traga` | H-14: hoy warning silencioso (`service.py:94-95`); fix: propagar/compensar con test | XFAIL H-14 |
| `test_save_attempt_sin_identidad_no_cae_en_user_1` | eliminar el fallback `or 1` (`service.py:46`, pedido por plan 01-A-04) | XFAIL H-03 |
| `test_get_by_month_febrero_28_y_29` | `calendar.monthrange` (`service.py:125-127`): 2026=28, 2024=29 | PASA |
| `test_get_by_month_mes_invalido_400` | validación 1–12 | PASA |
| `test_get_by_month_solo_devuelve_el_mes` | límites `start_date`/`end_date` inclusivos | PASA |

#### 2B. Integración API — `tests/integration/test_user_attempts_api.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_post_attempt_sin_token_y_sin_user_id_401` | 401 sin identidad (`router.py:41-45`) | PASA |
| `test_post_attempt_sin_token_con_user_id_ajeno_no_permitido` | CR-06: hoy un anónimo escribe intentos a nombre de cualquiera (`router.py:39-46`) | XFAIL CR-06 |
| `test_post_attempt_token_prevalece_sobre_user_id_del_body` | con token de A y body B ⇒ se guarda en A | PASA |
| `test_post_attempt_score_cliente_no_confiable` | H-04: hoy `score/stars` del cliente se persisten y suman (`schemas.py:15-17`); fix: recálculo server-side | XFAIL H-04 |
| `test_post_attempt_defaults_year_month_eliminados` | H-13: defaults temporales `year=2026/month=10` (`router.py:78-79`) | XFAIL H-13 |
| `test_post_attempt_token_usuario_inexistente_rechazado` | ME-02: hoy `_extract_user_id_from_header` solo decodifica, no valida contra DB (`router.py:17-28`); fix: `get_current_user` | XFAIL ME-02 |
| `test_get_attempt_date_propio_ok` | lectura propia por fecha | PASA |
| `test_get_attempt_date_user_id_ajeno_403` | H-03: hoy `?user_id=víctima` con token propio devuelve datos ajenos (`router.py:56-68`) | XFAIL H-03 |
| `test_get_attempts_mes_propio_ok` | listado mensual propio | PASA |
| `test_get_attempts_mes_user_id_ajeno_403` | IDOR de listado (`router.py:76-99`) | XFAIL H-03 |
| `test_get_attempts_admin_puede_consultar_ajeno` | contrato destino: `user_id` ajeno solo admin (`tipo_usuario == 2`) | XFAIL H-03 |
| `test_get_attempts_sin_identidad_contrato_definido` | hoy devuelve lista vacía; fix propuesto: 401 explícito | XFAIL (decisión 8.x) |
| `test_puntos_acumulados_exactos_por_flujo` | integración completa: 3 intentos completos ⇒ `puntos` = suma exacta | PASA (mongomock; variante DOCKER para carrera) |

#### 2C. Integración — `tests/integration/test_progreso_api.py` (regresión de RLS que ya funciona)

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_crear_progreso_propio_201` | dueño crea su progreso | PASA |
| `test_crear_progreso_ajeno_403` | RLS `router.py:19-23` | PASA |
| `test_crear_progreso_admin_para_alumno_ok` | admin puede crear para alumno | PASA |
| `test_crear_progreso_sin_token_401` | `get_current_user` | PASA |
| `test_actualizar_progreso_propio_upsert` / `_ajeno_403` | PUT `router.py:34-38` | PASA |
| `test_obtener_progreso_propio_ok` / `_ajeno_403` / `_admin_ok` | GET `router.py:47-51` | PASA |
| `test_progreso_concurrencia_array_embebido` | P1 del plan 02: read-modify-write del array `progresos` en `usuarios`; test de carrera real | DOCKER + XFAIL (plan 02) |

#### 2D. Integración — `tests/integration/test_usuario_api.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_listar_usuarios_sin_token_401` / `_alumno_403` | `get_current_admin` (`router.py:34`) | PASA |
| `test_listar_usuarios_paginacion_limit_skip` | contrato `PaginatedUsuariosResponse` | PASA |
| `test_listar_usuarios_filtros` | parametrizado: `nombre`, `fechaDesde/Hasta`, `tipoUsuario`, `black`, `activo` | PASA |
| `test_listar_usuarios_orden_asc_desc` | patrón `^(asc\|desc)$` y orden real | PASA |
| `test_crear_usuario_admin_ok_y_activo` | creación pre-activada (`is_admin_creation=True`) | PASA |
| `test_crear_usuario_admin_no_permite_rol_invalido` | `tipoUsuario` fuera de {1,2} según schema | PASA |
| `test_toggle_activo_admin_ok_y_alumno_403` | `router.py:93-98` | PASA |
| `test_toggle_black_y_alias_suscribirse` | dos rutas al mismo handler (`router.py:100-106`) | PASA |
| `test_magic_link_admin_ok_incluye_token_valido` | devuelve `token` + `accessUrl` (`router.py:119-143`) | PASA |
| `test_obtener_usuario_ajeno_403` / `_propio_ok` / `_admin_ok` | ownership `router.py:85-91` | PASA |
| `test_cambiar_estado_y_toggle_estado_admin` | endpoints de catálogo de estados | PASA |
| `test_estados_catalogo_lectura_publica` | BA-04: `/usuario/estados` es público por diseño; test documenta decisión (¿mover a admin?) | XFAIL (decisión 8.x) |

- **Criterios de aceptación:** unit ≥ 85% de `user_attempts/service.py`; los 5 casos `XFAIL` de IDOR/scoring con `reason` CR-06/H-03/H-04; RLS de progreso/usuario cubierta con casos negativos (403) y positivos por cada rol; cero falsos verdes por rate limiter compartido.
- **Riesgos:** el contrato de lectura de attempts (¿401 vs lista vacía?) y el recálculo server-side dependen del frontend (preguntas 8.x); mongomock no reproduce carreras → los 2 tests de concurrencia quedan `docker` y pueden ser inestables: usar `asyncio.gather` con reintentos documentados y timeout.
- **Esfuerzo:** **M–L (3–4 días)**.
- **Dependencias:** Fase 0; fixes del plan 03 (CR-06, ME-02) y plan 02 (atomicidad de `$inc`, array `progresos`) para desmarcar `xfail`.

---

### Fase 3 — Desafíos diarios: generadores, fechas y API (P0/P1)

- **Objetivo:** verificar determinismo y correctitud de los 4 generadores, fijar el comportamiento de meses/fechas (topes de días, `until_today`, zona horaria) e idempotencia de la generación mensual; y dejar documentados con `xfail` los agujeros P0 de la API admin/upsert y la fuga de soluciones.
- **Alcance:** `app/features/daily_challenges/{wordle,sudoku,sopa,crucigrama}_generator.py`, `service.py`, `router.py`, `app/scripts/seed_challenges.py`, `seed_sudoku.py`, `seed_sopa_letras.py`, `app/core/rae_client.py` (mockeado).
- **Herramientas:** `mock_rae` (autouse), `frozen_today`, `db`, `client`, `seed_challenge_day`, `deterministic_random`.
- **Pasos:** (1) unit de generadores con fecha fija; (2) unit de service para meses/TZ/idempotencia; (3) integración API (lectura pública + admin/upsert).

#### 3A. Unit — `tests/unit/daily_challenges/test_generators.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_wordle_determinista_misma_fecha` | misma fecha ⇒ misma palabra/hints (seed por fecha) | PASA |
| `test_wordle_hints_con_rae_mockeado_sin_sleep` | `generate_wordle_hints` usa el mock; no cuelga ni pega a red (`wordle_generator.py:51`) | PASA |
| `test_wordle_no_repite_palabras_en_el_mes` | unicidad contra `used_words` | PASA |
| `test_sudoku_solucion_valida_y_unica` | filas/columnas/cajas 1–9 sin repetidos y solución única | PASA |
| `test_sudoku_determinista_por_fecha_y_dificultad` | mismo día+dificultad ⇒ mismo puzzle | PASA |
| `test_sopa_palabras_presentes_en_grilla` | cada palabra está en la grilla (direcciones válidas) | PASA |
| `test_sopa_no_contamina_random_global` | A-07: hoy `random.seed(seed)` global (`sopa_generator.py:118`); fix: `random.Random` local; test compara `random.getstate()` antes/después | XFAIL A-07 |
| `test_crucigrama_intersecciones_y_longitudes` | grilla sin choques inválidos; longitudes de pistas/huecos | PASA |
| `test_crucigrama_determinista_por_fecha` | idem sudoku | PASA |

#### 3B. Unit/service — `tests/unit/daily_challenges/test_service.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_get_month_challenges_dias_exactos` | topes `calendar.monthrange`: 31/30/28 y 29 en bisiesto (`service.py:99-124`) | PASA |
| `test_get_month_challenges_until_today` | con fecha congelada, corta en el día (no futuro) | PASA |
| `test_get_today_challenge_con_fecha_congelada` | `/today` usa la fecha del clock inyectado/frozen | PASA |
| `test_today_respeta_zona_horaria_negocio` | P1 del informe 02: contenedor UTC hace que el "día" cambie a las 21:00 ART; hoy `datetime.now()` naive (`service.py:104`, `:140`); fix: helper `today_str` con TZ de negocio | XFAIL (decisión TZ) |
| `test_generate_and_save_sudoku_month_idempotente` | `force=False` no pisa existentes; `force=True` regenera | PASA |
| `test_generate_and_save_wordle_month_cuenta_y_no_toca_otros_generos` | N documentos del mes, sin efectos cruzados | PASA |
| `test_ensure_current_and_next_month_no_regenera_si_completo` | conteo == días del mes ⇒ no llama generadores | PASA |
| `test_ensure_rollover_diciembre` | freeze 2026-12-15 ⇒ targets (2026-12, 2027-01) (`service.py:602-608`) | PASA |
| `test_upsert_challenge_idempotente` | mismo `game_id/date/difficulty` ⇒ 1 documento, `updated_at` avanza | PASA |
| `test_upsert_challenge_normaliza_game_id` | `game_id` lower/strip | PASA |

#### 3C. Integración API — `tests/integration/test_daily_challenges_api.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_get_today_200_shape_y_sin_solucion` | ME-08: la respuesta pública no debe incluir la solución del puzzle (`service.py:37-48`); fix: `config_publica` filtrada | XFAIL ME-08 |
| `test_get_month_respeta_topes_y_dificultad` | contrato `MonthChallengesResponse` | PASA |
| `test_get_range_ok_y_game_invalido` | rango disponible por juego | PASA |
| `test_get_date_formato_invalido_422` | patrón `^\d{4}-\d{2}-\d{2}$` (`router.py:71`) | PASA |
| `test_get_date_sin_desafio_404` | 404 de `get_challenge_by_date` | PASA |
| `test_post_challenges_sin_token_401` | H-02/CR-02: hoy cualquiera sobrescribe desafíos (`router.py:77-83`) | XFAIL CR-02 |
| `test_post_challenges_admin_ok` | contrato destino con admin | XFAIL CR-02 |
| `test_admin_status_sin_token_401` | H-02 (`router.py:85-93`) | XFAIL H-02 |
| `test_admin_status_admin_ok` | contrato de cobertura mensual | XFAIL H-02 |
| `test_admin_generate_month_sin_token_401` | H-02 (`router.py:95-113`) | XFAIL H-02 |
| `test_admin_generate_month_admin_ok_y_force_default_false` | fix: `force=True` por defecto es peligroso (`router.py:103`); destino `force=False` | XFAIL H-02 |
| `test_admin_generate_month_game_no_soportado_400` | hoy responde 200 con `success:false`; definir contrato | XFAIL (decisión 8.x) |

- **Criterios de aceptación:** generadores deterministas verificados (2 corridas ⇒ mismo output); casos de topes de mes/bisiesto verdes; los 6 `XFAIL` de auth/solución con `reason` CR-02/H-02/ME-08; suite de esta fase < 60 s sin `docker`.
- **Riesgos:** los generadores son CPU-bound y algunos usan datos grandes (`crucigrama_generator.py` 1.085 líneas) ⇒ acotar tamaños en tests y marcar `slow` lo pesado; la TZ queda bloqueada por decisión de negocio (preguntas 8.x); el mock de RAE debe cubrir también imports directos.
- **Esfuerzo:** **M (2–3 días)**.
- **Dependencias:** Fase 0 (mocks RAE); fix H-02 del plan 03; helper TZ y refactor `random` del plan 01 (A-07/M-04) para desmarcar sus `xfail`.

---

### Fase 4 — Narrativo: engine, partida V2 y admin (P0/P1)

- **Objetivo:** dar cobertura al corazón lógico del juego (reglas, sorteos, finales), al ciclo completo V2 (happy path y errores, concurrencia, aislamiento entre usuarios e invitados) y a la superficie admin (authz + smoke de CRUD).
- **Alcance:** `app/features/narrative/engine/{rule_engine,event_director}.py`, `game/{setup,turn,transition,endings,modals}_service.py` + `game/router.py`, `admin/{router,challenge_service,crud_service}.py`, `constants.py`/`enums.py`.
- **Herramientas:** `seed_narrative_min`, `mock_rae` (no aplica casi), `frozen_today`, `client`, `auth_headers`/`admin_headers`, `real_db` para concurrencia.
- **Pasos:** (1) unit de engine/finales; (2) integración de partida con usuarios autenticados (y un test dedicado de invitados); (3) concurrencia `docker`; (4) admin: barrido de authz parametrizado + smoke CRUD/upload.

#### 4A. Unit — `tests/unit/narrative/test_engine.py` (+ `test_endings.py`, `test_transition.py`)

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_rule_engine_evaluar_condicion_por_operador` | parametrizado sobre `rule_engine.py:15-71` (==, !=, <, <=, >, >=, entre, etc.) | PASA |
| `test_rule_engine_evaluar_condiciones_anidadas_y_or` | listas/`AND`-`OR` de condiciones | PASA |
| `test_rule_engine_despachar_efectos_modifica_recursos_y_tags` | `despachar_efectos` (`rule_engine.py:144`) aplica deltas y respeta límites del universo | PASA |
| `test_rule_engine_amortiguar_danio_documentado` | A-05: `AMORTIGUAR_DANIO` anunciado y no implementado; test documenta no-op hasta que se implemente o se retire del catálogo | XFAIL A-05 |
| `test_event_director_seleccion_determinista_con_seed` | `seleccionar_evento_mes` con semilla fija ⇒ mismo evento | PASA |
| `test_event_director_respeta_bloqueos_y_pesos` | eventos bloqueados no salen; pesos se respetan | PASA |
| `test_event_director_distribucion_probabilidades` | `sortear_resultado_opcion`: N=1000 con semilla fija; tolerancia estadística documentada | PASA (`slow` si excede 2 s) |
| `test_endings_rangos_s_a_b_c_umbrales` | `calcular_finalizacion_victoria` (`endings_service.py:86-127`): umbrales exactos por rango | PASA |
| `test_endings_colapso_por_recurso_en_minimo` | `verificar_colapso_recursos` (`:24`): cada recurso en su min ⇒ finalización `F` | PASA |
| `test_transition_costos_pasivos_cada_mes_y_colapso` | `transition_service.py`: pasivos por mes y colapso resultante | PASA |

#### 4B. Integración — partida V2 + invitados + concurrencia (`tests/integration/test_narrative_api.py`)

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_setup_fecha_congelada_5_y_5_ofrecidos` | setup con `seed_narrative_min`; ids ofrecidos ⊂ catálogo | PASA |
| `test_iniciar_usuario_autenticado_usa_id_del_token` | la run pertenece al usuario del token (no a 0) | PASA |
| `test_iniciar_sin_token_queda_invitado_0` | documenta H-05 (`game/router.py:64-76`) | PASA (documental) |
| `test_dos_usuarios_autenticados_misma_fecha_aislados` | runs separadas; modales de cada uno solo ven lo propio | PASA |
| `test_dos_invitados_misma_fecha_no_comparten_partida` | H-05: hoy ambos caen en `user_id=0` y uno ve/resetea la del otro (`setup_service.py:103,139,181`); fix: cookie/sesión anónima o auth obligatoria | XFAIL H-05 |
| `test_doble_submit_iniciar_genera_una_sola_run` | H-09: `asyncio.gather` de 2 `/iniciar` ⇒ 1 run, sin 500 por `DuplicateKeyError` | DOCKER + XFAIL H-09 |
| `test_doble_submit_decidir_evento_un_solo_efecto` | idempotencia de turno: segundo submit no duplica efectos ni avanza dos veces | DOCKER + XFAIL H-09 |
| `test_ciclo_v2_completo_12_meses` | port del E2E: fase final `FINALIZADA` + `finalizacion` + rango coherente con `status` | PASA (fecha congelada, seed mínimo) |
| `test_ciclo_invariantes_por_mes` | invariantes: un evento por mes, secuencia de fases válida, recursos dentro de `min/max` del universo en cada respuesta | PASA |
| `test_elegir_carta_fase_incorrecta_400` | máquina de fases (`turn_service.py:65`) | PASA |
| `test_decidir_evento_opcion_inexistente_400` | validación de opción | PASA |
| `test_responder_conversacion_sin_conversacion_400` | validación de fase | PASA |
| `test_avanzar_mes_fase_incorrecta_400` | `transition_service.py:49` | PASA |
| `test_reiniciar_idempotente_y_solo_run_propia` | segundo reinicio ⇒ `eliminada=false`; nunca borra run ajena (`setup_service.py:117-124`) | PASA |
| `test_modales_shape_completo` | parametrizado: setup/corte/inventario/historial/finalizacion/draft/evento/conversacion/resultado/estado | PASA |
| `test_modales_usuario_autenticado_no_filtra_ajeno` | usuario B consulta fecha de A ⇒ vacío/404, sin fuga | PASA |
| `test_estado_turno_restaura_tras_recarga` | `/v2/partida/estado` devuelve fase/evento actual (contrato F5) | PASA |
| `test_finalizar_sincroniza_intento_narrativo` | `sincronizar_intento_usuario` (`endings_service.py:127-136`) escribe/actualiza `user_attempts` del mismo usuario | PASA (contrato a confirmar con plan 02) |

#### 4C. Integración — admin narrativo (`tests/integration/test_narrative_admin_api.py`)

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_admin_narrative_sin_token_401` | H-01: barrido parametrizado de los ~32 endpoints (`admin/router.py:70-311`); hoy todos son públicos | XFAIL H-01 |
| `test_admin_narrative_con_alumno_403` | ídem con token de alumno | XFAIL H-01 |
| `test_admin_narrative_con_admin_ok` | contrato destino feliz | XFAIL H-01 |
| `test_admin_upload_requiere_auth_y_limita_peso` | AL-06: upload sin auth y sin límite en app (`image_service.py:38`); fix: 401 + 413 | XFAIL AL-06 |
| `test_admin_crud_universo_roundtrip` | POST → GET lista → GET id → DELETE `test_uni` | PASA (mongomock) |
| `test_admin_generar_mes_narrativo_idempotente` | 2 corridas ⇒ mismo set de challenges del mes, sin pisar configs esperadas | PASA |
| `test_admin_sembrar_finalizaciones_idempotente` | `sembrar_finalizaciones_para_universo` 2 corridas ⇒ sin duplicados | PASA |
| `test_cache_recursos_se_invalida_al_editar_universo` | A-06: caché en memoria (`setup_service.py:51-71`) sirve datos viejos tras editar; fix: invalidar en CRUD | XFAIL A-06 |
| `test_admin_catalogo_reglas_contrato` | shape de `catalogo-reglas` (disparadores/operadores/tipos) | PASA |
| `test_admin_404s_uniformes` | `universo/personaje/carta` inexistente ⇒ 404 con mensaje del handler global | PASA |

- **Criterios de aceptación:** engine unit ≥ 80% de `rule_engine`/`endings`; ciclo V2 verde sin datos productivos y repetible 2 veces; barrido admin parametrizado cubre el 100% de los endpoints del router (definido en `authz_matrix.yaml`); ningún test usa `user_id=0` compartido salvo los dedicados a documentar H-05.
- **Riesgos:** los servicios narrativos hacen read-modify-write (`setup_service.py:139-182`, `turn_service.py`, `transition_service.py`) ⇒ los tests de concurrencia pueden ser flaky; usar `docker`, timeout y aserciones de efecto final (no de timing). El seed mínimo debe cubrir las reglas que disparan el ciclo (si no, el E2E "no llega" a FINALIZADA): mantener `narrative_min.json` versionado y un test que valide su coherencia con los schemas.
- **Esfuerzo:** **L (4–5 días)**.
- **Dependencias:** Fase 0; plan 01 (A-03 helper identidad, A-06 caché) y plan 02 (locking/atomicidad de runs) para desmarcar concurrencia; plan 03 (CR-01 + ME-03) para los 401/403; plan 04 (la SPA admin debe enviar Bearer para que el fix no rompa el panel).

---

### Fase 5 — Datos y arranque: seeds, lifespan, índices y ETL (P1/P2)

- **Objetivo:** garantizar que los seeds son idempotentes y no pisan datos, que el arranque no depende de red, que `init_indexes` no traga errores críticos y que el ETL puede ensayarse sin escribir (dry-run).
- **Alcance:** `app/scripts/{init_db,seed_challenges,seed_sudoku,seed_sopa_letras,seed_narrative}.py`, `app/main.py` (lifespan), `app/core/database.py:55-104`, `app/scripts/migrate_from_mysql.py`.
- **Herramientas:** `db` + `real_db` (índices), `client_lifespan` + `mock_rae`/`mock_smtp`, fake de cursor MySQL, `frozen_today`.
- **Pasos:** (1) idempotencia de seeds con DB efímera; (2) smoke de lifespan sin red; (3) índices en Mongo real + propagación de error; (4) ETL con doble fake (MySQL/Mongo) y propuesta de flag `--dry-run`.

#### 5A. Seeds idempotentes — `tests/e2e/test_seeds_idempotent.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_seed_estados_idempotente` | 2 corridas ⇒ mismos 3 documentos, sin duplicados (`init_db.py:36-62`) | PASA |
| `test_seed_default_admin_no_duplica_ni_rehashea` | 2 corridas ⇒ 1 admin; no reescribe password/PIN si ya existe (`init_db.py:64-93`) | PASA |
| `test_seed_wordle_challenges_idempotente` | 2 corridas ⇒ mismo estado (conteos e ids) | PASA/condicional (si `$set` no pisa `updated_at`; si lo pisa, marcar `xfail` "check-first") |
| `test_seed_sudoku_idempotente` / `test_seed_sopa_idempotente` | ídem | PASA/condicional |
| `test_seed_narrative_idempotente` | catálogo (universos/personajes/cartas/eventos/finalizaciones) estable tras 2 corridas | PASA |
| `test_seed_narrative_no_pisa_imagenes_subidas` | preservar `imagen_url` custom (motivo del check-first actual) | PASA |

#### 5B. Arranque (`lifespan`) — `tests/e2e/test_lifespan_smoke.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_lifespan_arranca_sin_red` | con `client_lifespan` + mocks: arranque completo (seeds + `ensure_current_and_next_month_generated`) sin RAE/SMTP reales (`main.py:32-68`) | PASA tras Fase 0 (hoy requeriría red) |
| `test_lifespan_no_bloquea_mas_de_1s_con_mocks` | el `sleep(0.2)` × N palabras (`service.py:409`) no se ejecuta con RAE mockeado; guard de tiempo generoso (no timing frágil) | PASA |
| `test_lifespan_loop_12h_se_cancela_en_shutdown` | la task `_auto_check_loop` no queda colgada ni lanza en cancel (`main.py:50-66`) | PASA |
| `test_lifespan_seeds_solo_si_falta` | 2 arranques ⇒ no se duplican documentos | PASA |

#### 5C. Índices — `tests/e2e/test_indexes.py` (marker `docker`)

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_init_indexes_crea_unicos_esperados` | existen los índices únicos de `usuarios.email/id`, `daily_challenges(game_id,date,difficulty)`, `user_attempts(user_id,game_id,date)`, `narrative_runs(user_id,date,game_id)` (`database.py:61-94`) | DOCKER PASA |
| `test_init_indexes_propaga_error` | H-14: hoy traga excepciones (`database.py:103-104`); fix: propagar en arranque (fail-fast) — test monkeypatchea `create_index` para lanzar y espera excepción | DOCKER + XFAIL H-14 |
| `test_arranque_falla_si_hay_duplicados_previos` | fail-fast ante datos inconsistentes que impiden crear el único | DOCKER + XFAIL H-14 |

#### 5D. ETL dry-run — `tests/e2e/test_etl_dry_run.py`

> Requiere un cambio mínimo de producción (fuera de esta fase; coordinado con plan 02): refactorizar `run_migration()` (`migrate_from_mysql.py:11`) a `run_migration(dry_run: bool = False)` + flag CLI `--dry-run`, y pasar el cursor MySQL o un fake inyectable.

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_etl_dry_run_no_escribe_mongo` | con `--dry-run` y fakes: cero escrituras en Mongo y reporte de conteos | XFAIL (a implementar; plan 02) |
| `test_etl_upsert_por_email_no_pisa_otro_id` | riesgo del informe 02: hoy el upsert es por `{"id": ...}` (`migrate_from_mysql.py:105-110`) pese al comentario "por email" ⇒ puede pisar usuarios | XFAIL (bug 02) |
| `test_etl_colision_email_reportada_sin_abortar` | emails duplicados en MySQL se reportan y no rompen la corrida | XFAIL (plan 02) |
| `test_etl_actualiza_counters_y_secuencia` | `set_sequence_value` con `max_user_id`/`max_progreso_id` (`:113-120`) | PASA (con fakes) |
| `test_etl_error_de_mysql_no_crashea` | conexión fallida ⇒ log de error y retorno controlado (`:26-28`) | PASA |

- **Criterios de aceptación:** 2 corridas de cada seed ⇒ mismo estado (comparación de `find().to_list()` ordenado); arranque completo en test sin red ni > 120 s; ETL cubierto con fakes y dry-run documentado como contrato destino; los `XFAIL` con `reason` H-14/bug-02.
- **Riesgos:** `seed_narrative.py` (1.789 líneas) es lento; decidir si se testea como herramienta o se saca del repo productivo (H-13, decisión 8.x) — si se saca, los casos 5A de narrativo se mueven a "herramienta de desarrollo". El dry-run del ETL exige tocar `migrate_from_mysql.py` (coordinación explícita con plan 02 para no duplicar cambios).
- **Esfuerzo:** **S–M (1,5–2 días)**.
- **Dependencias:** Fase 0; plan 02 (seeds check-first, ETL, índices fail-fast) para desmarcar `xfail`.

---

### Fase 6 — Seguridad transversal y contratos (P0)

- **Objetivo:** convertir la matriz de autorización del informe 03 en un artefacto ejecutable que clasifique **todos** los endpoints y falle ante cualquier endpoint nuevo sin clasificar; fijar JWT, rate limit, CORS y contratos/OpenAPI.
- **Alcance:** `app.routes` completo (auth, usuario, progreso, challenges, attempts, narrative game/admin), `core/{security,dependencies,rate_limit}.py`, CORS (`main.py:80-98`), `openapi.json`, `docs_interna/`.
- **Herramientas:** `tests/security/authz_matrix.yaml`, `client`, `auth_headers`/`admin_headers`/`expired_headers`/`forged_headers`, `reset_rate_limiter`, snapshot de OpenAPI.
- **Pasos:** (1) redactar la matriz (tabla informe 03:85-108) como YAML; (2) test parametrizado que recorre `app.routes` y assertea por rol; (3) tests de JWT/rate/CORS; (4) snapshot OpenAPI + validación de docs.

#### 6A. Matriz de autorización — `tests/security/test_authz_matrix.py`

Estructura propuesta de `authz_matrix.yaml` (una entrada por endpoint×método con `rol_esperado`: `publico | autenticado | owner | admin` y `estado_sin_token`/`estado_alumno`):

| Grupo | Endpoints | Expectativa destino | Estado inicial |
|---|---|---|---|
| `narrative/admin/*` (CRUD, upload, generar-mes, sembrar) | ~32 | sin token 401 · alumno 403 · admin 2xx | **XFAIL H-01/CR-01** (hoy todo 200) |
| `challenges`: `POST /api/challenges`, `/admin/status`, `/admin/generate-month` | 3 | sin token 401 · alumno 403 · admin 2xx | **XFAIL CR-02/H-02** |
| `auth`: `/api/admin/enviar-acceso-correo` | 1 | sin token 401 · alumno 403 | PASA |
| `usuario`: listar/crear/toggles/magic-link/cambiar-estado | ~10 | admin | PASA |
| `usuario/{id}` GET | 1 | owner o admin (ajeno 403) | PASA |
| `progreso/*` | 3 | owner o admin (ajeno 403) | PASA |
| `games/attempts` | 3 | escritura autenticado; lectura owner/admin | **XFAIL CR-06/H-03** |
| `narrative game/*` (v2 + modales) | ~19 | autenticado o invitado-por-decisión; nunca ver run ajena | PASA parcial (H-05 XFAIL invitados) |
| `challenges` GET, `/`, `/health` | 5 | públicos por diseño | PASA |

Casos ejecutables:

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_matriz_authz_endpoint_x_rol` | parametrizado (endpoint, rol) contra `app.routes`; assertea status codes 401/403/2xx según matriz | mixto (ver tabla) |
| `test_matriz_cubre_todos_los_endpoints` | **guardián**: si aparece un endpoint nuevo sin entrada en el YAML ⇒ falla (fail-closed) | PASA tras Fase 0 |
| `test_endpoints_admin_documentan_security` | los endpoints admin declaran `Depends(get_current_admin)` en OpenAPI (`security` presente) | XFAIL H-01/H-02 |
| `test_endpoints_escritura_sin_auth_no_pueden_entrar` | regla general: POST/PUT/DELETE con efecto debe estar clasificado como admin/owner/autenticado | PASA (guardián) + XFAIL lo hoy suelto |

#### 6B. JWT y sesión — `tests/security/test_jwt.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_jwt_firma_invalida_401` | token firmado con otro secreto | PASA |
| `test_jwt_expirado_401` | `exp` pasado (`create_access_token(expires_delta=-1h)`) | PASA |
| `test_jwt_alg_none_rechazado` | rechazo de `alg: none` | PASA |
| `test_jwt_sin_id_ni_email_401` | payload sin identidad (`dependencies.py:42-46`) | PASA |
| `test_jwt_usuario_borrado_respuesta_uniforme_401` | BA-05: hoy `get_current_user` responde 404 `usuario no existe` (`dependencies.py:49-53`); destino: 401 uniforme | XFAIL BA-05 |
| `test_jwt_forjado_con_secreto_default_rechazado` | CR-03: con el secreto default público (`config.py:14`), un token forjado hoy es válido; el test "exige" el fail-fast/config rotada | XFAIL CR-03 |
| `test_token_solo_identifica_rol_desde_db` | H-07 informe 03: el rol efectivo sale de `usuarios`, no del claim (evita bypass del rate limit con claim manipulado en tokens legítimos de otra instancia) | PASA (con `get_current_user`; documentar excepción de `rate_limit.py:44-46`) |

#### 6C. Rate limiting — `tests/security/test_rate_limit.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_rate_limit_5_por_minuto_429` | límite base con `Retry-After` (`rate_limit.py:21-28`) | PASA |
| `test_rate_limit_xff_spoof_no_evade` | H-06/AL-01: hoy rotar `X-Forwarded-For` reinicia el límite (`rate_limit.py:49-53`); fix: IP del socket/`X-Real-IP` de proxy confiable | XFAIL AL-01 |
| `test_rate_limit_key_por_endpoint` | endpoints distintos no comparten balde (`:55`) | PASA |
| `test_rate_limit_bypass_solo_con_admin_valido` | bypass `tipoUsuario==2` (`:41-46`) exige token válido; alumno no evade | PASA |
| `test_rate_limit_sin_crecimiento_infinito` | P2 del plan 05: la estructura `_history` no debe crecer sin límite (TTL/limpieza); test de limpieza por ventana | XFAIL plan 05 |

#### 6D. CORS — `tests/security/test_cors.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_cors_preflight_origen_permitido` | origen de la whitelist ⇒ `Access-Control-Allow-Origin` correcto (`main.py:81-89`) | PASA |
| `test_cors_origen_arbitrario_rechazado` | H-07: hoy `allow_origin_regex=r"^https?://.*$"` + `allow_credentials=True` acepta cualquier origen (`main.py:94-95`); fix: allowlist por entorno | XFAIL H-07 |
| `test_cors_credentials_no_combinan_con_wildcard` | tras fix: sin `*` con credenciales; preflight de origen no listado sin headers CORS | XFAIL H-07 |

#### 6E. Contratos y `docs_interna` — `tests/security/test_contracts.py`

| Caso propuesto | Qué valida | Estado inicial |
|---|---|---|
| `test_openapi_snapshot_estable` | snapshot versionado de `openapi.json`; cualquier cambio de contrato exige actualizarlo a propósito | PASA (crear snapshot en esta fase) |
| `test_contrato_registro_responde_200_no_201` | H-12: docs dicen 201, router responde 200 (`auth/router.py:48-55`) | PASA + nota docs |
| `test_contrato_auth_codigo_incorrecto_401_no_404` | H-12: guía dice 404, servicio devuelve 401 (`GUIA_INTEGRACION_FRONTEND_AUTH.md:62`) | PASA + nota docs |
| `test_docs_contratos_param_fecha_vs_date` | H-12: docs usan `?fecha=` y la API `?date` (`DIAGRAMAS_ARQUITECTURA_NARRATIVO.md:94,143,147,157`) | XFAIL H-12 (fix en plan 01/M-03) |
| `test_error_handler_formato_uniforme` | todas las respuestas de error tienen `success/detail/message` (handler `main.py:104-114`) | PASA |

- **Criterios de aceptación:** la matriz cubre el 100% de endpoints de `app.routes`; el guardián falla si se agrega un endpoint sin clasificar; los `XFAIL` de seguridad referencian CR-01/CR-02/CR-03/CR-06, AL-01, H-05/H-06/H-07/BA-05; snapshot OpenAPI commiteado.
- **Riesgos:** la matriz depende de decisiones de contrato (invitado, attempts sin token, `/usuario/estados` público) → cerrar en 8.x antes de marcar "definitivo"; el escape de CORS con `allow_origin_regex` y credenciales debe probarse con `Origin` real (no solo OPTIONS).
- **Esfuerzo:** **M (2–3 días)**.
- **Dependencias:** Fase 0; fixes del plan 03 (CR-01/CR-02/CR-03/CR-06, AL-01, H-07, BA-05) para desmarcar `xfail`; plan 04 (Bearer del panel admin); plan 01 (docs).

---

## 6. CI/CD, cobertura y calidad (Fase 7)

### 6.0 Ficha de la fase

- **Objetivo:** que el verde sea automático y obligatorio antes de mergear, con umbrales de cobertura razonables por área y herramientas de estilo/typing que no frenen al equipo.
- **Alcance:** `.github/workflows/ci.yml`, `pyproject.toml` (ruff/coverage), `.pre-commit-config.yaml`, `pyrightconfig.json` o `mypy.ini` (decisión), `docs_interna` + snapshot OpenAPI, pins/lock de `requirements-dev.txt`.
- **Pasos:** 6.1 → 6.8.
- **Criterios de aceptación:** 6.9.
- **Riesgos:** 6.10.
- **Esfuerzo:** **S–M (1–2 días)**.
- **Dependencias:** Fase 0 (y se puede montar en paralelo desde el día 2; el job de integración con `mongo:7.0` no necesita más).

### 6.1 Pipeline propuesto (GitHub Actions)

No existe `.github/` hoy (H-10). Propuesta de 3 jobs required en PR + 1 extendido:

```yaml
name: CI
on:
  pull_request:
  push: { branches: [main] }

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .

  unit:                      # rápido, sin servicios externos
    needs: lint
    steps:
      - ... setup + install ...
      - run: python -m pytest -m "unit" --cov=app --cov-report=xml --cov-report=term
      - run: python -m pytest -m "integration and not docker"

  integration:               # Mongo real de test
    needs: lint
    services:
      mongo: { image: "mongo:7.0", ports: ["27017:27017"] }
    env:
      TEST_MONGODB_URL: mongodb://127.0.0.1:27017/sipi_test
    steps:
      - ... setup + install ...
      - run: python -m pytest -m "docker or (integration and docker)" --cov=app --cov-append
      - run: python -m pytest -m "security and not docker"
      - run: python -m pytest -m e2e --ignore-glob="*slow*"   # smoke E2E
```

- **Gating de PR:** activar branch protection en `main` con `lint`, `unit`, `integration` como checks requeridos. Los `slow` corren en un job nocturno (`schedule: cron`) y no bloquean PRs.
- **DB de test en CI:** *service container* `mongo:7.0` (más estable que testcontainers en runners) + `TEST_MONGODB_URL` con base `sipi_test` (la guardia de 4.7 exige el sufijo).
- **Cache:** pip con `actions/setup-python` (`cache: pip`); no cachear la DB.
- **Secretos:** ninguno real en CI; `JWT_SECRET=tests-only-secret`, SMTP/RAE mockeados por fixtures. Nunca usar el `.env` del repo.
- **Alternativa:** si el equipo usa otra plataforma (GitLab CI, Jenkins), el mismo esquema (lint → unit → integration → security) portado; queda como pregunta 8.x.

### 6.2 Cobertura: objetivos razonables por área (ratchet, no 100% ciego)

Política: **la cobertura no puede bajar** del umbral alcanzado en cada fase (ratchet). `pytest-cov` con `--cov-fail-under` global incremental:

| Hito | Global | Áreas críticas (umbral específico) |
|---|---|---|
| Al terminar Fase 1–2 | 35% | `core/security` ≥ 90% · `user_attempts` ≥ 85% |
| Al terminar Fase 3–4 | 50% | `auth/service` ≥ 70% · `progreso` ≥ 90% · `narrative/engine` ≥ 80% |
| Al terminar Fase 6 | 60% | matriz authz = 100% de endpoints admin/escritura (medida como casos, no líneas) |
| Mantenimiento | 60% y subiendo si sale gratis | generadores grandes (`crucigrama_generator.py`) exentos hasta nueva orden |

- Los módulos con `XFAIL` **cuentan** su cobertura: lo importante es que la lógica esté ejecutada por tests, incluso si el assert es "bug documentado".
- Exenciones explícitas y justificadas por archivo (`[tool.coverage.report] exclude_lines` y `omit` para `app/static/`, `seed_narrative.py` si se decide), nunca exclusiones globales silenciosas.
- Sin exigir 100%: el criterio de calidad es el mapa de riesgo cubierto (Anexo A), no el número.

### 6.3 Linter/formatter — configuración propuesta de `ruff` (`pyproject.toml`)

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
exclude = [".venv", "app/static"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "C4", "SIM", "ASYNC", "S", "RUF"]
# E722 = bare except (política 6.6); ASYNC = bloqueos en async (plan 05); S = bandit básico
ignore = ["S101"]  # asserts: permitidos (proyecto de app, no librería)

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S311", "S105", "S106"]   # seeds de test y passwords dummy
"app/scripts/**" = ["S311"]                      # random no criptográfico en generación de puzzles (documentado)
"app/features/**/generators/**" = ["S311"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", "fastapi.Path", "fastapi.Header", "fastapi.File", "fastapi.Body"]
# sin esto, B008 marca todos los defaults de FastAPI
```

- Arranque pragmático: el repo actual tiene deuda (H-13/H-14); aplicar `ruff check --statistics` en la primera pasada y decidir entre (a) arreglar lo automático (`--fix`: imports duplicados como `main.py:100-102/143`, `__future__`), o (b) `per-file-ignores` temporales con fecha de vencimiento. Recomendado (a) para F/I y dejar B/SIM en observación la primera semana.
- **Formatter:** `ruff format` (reemplaza Black). Si el equipo prefiere mantener diffs mínimos, correrlo una vez sobre `tests/` y `app/` nuevos, y dejar el resto para cuando se toque el archivo (estrategia "format-on-touch" documentada).

### 6.4 Pre-commit

`.pre-commit-config.yaml` propuesto:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.x          # fijar la misma minor que CI
    hooks: [{ id: ruff, args: [--fix] }, { id: ruff-format }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - end-of-file-fixer
      - trailing-whitespace
      - check-yaml
      - check-added-large-files   # evita imágenes/binarios accidentales
      - detect-private-key        # higiene de secretos (CR-03)
```

- No incluir pytest en pre-commit (lento); el gate rápido lo da CI. Opcional: hook `pytest -m unit --lf -x` solo si el repo local lo decide.
- Documentar `pre-commit install` en el README de desarrollo (nuevo `CONTRIBUTING.md` o sección).

### 6.5 Type checking gradual (opción mypy o pyright)

- **Propuesta:** `pyright` en modo `basic` (menos fricción con Pydantic v2/Motor que mypy+stubs; decisión en 8.x).
- **Adopción gradual por allowlist** (no bloquear todo el repo): empezar por `app/core/*` y los módulos nuevos/tocados por fases 1–6; `pyright` corre en CI con `continue-on-error: true` durante 2–3 semanas y luego pasa a required para los archivos de la allowlist.
- **Criterio de éxito:** cero errores de tipo en `app/core/` y en los archivos de test nuevos (los tests son código de primera clase: `pyright tests/` opcional).

### 6.6 Política de manejo de errores (H-14)

Reglas que se proponen como estándar del repo (y que los tests de Fases 2/5/6 fijan):

1. **Prohibido `except:` / `except Exception` sin acción:** `ruff E722` + revisión. Cada `except Exception` debe: (a) usar `logger.exception` (no `warning`) y (b) o re-lanzar, o degradar con una acción explícita y testeada.
2. **`init_indexes` fail-fast:** no tragarse errores al crear índices únicos (`database.py:103-104`) — son la última defensa de H-04/H-09. Cambio propuesto: propagar la excepción (al menos en `TESTING`/no-producción) y test `test_init_indexes_propaga_error`.
3. **No silenciar caminos críticos:** suma de puntos (`user_attempts/service.py:94-95`) y sembrado de finalizaciones (`main.py:47-48`) no pueden morir en un warning; definir compensación/reintento con test.
4. **Respuestas de error uniformes:** mantener el handler global (`main.py:104-114`) como único formato `{success, detail, message}`; los tests de contrato (6E) lo fijan.
5. **Logs sin secretos:** PIN/tokens/códigos nunca en logs (AL-05), con test de `caplog` en Fase 1.

### 6.7 Proceso para mantener `docs_interna` sincronizadas (H-12)

Cuatro mecanismos combinados:

1. **Snapshot OpenAPI versionado** (`tests/security/test_contracts.py::test_openapi_snapshot_estable`): cualquier cambio de contrato (rutas, parámetros, status codes, schemas) rompe el test hasta actualizar el snapshot **y** revisar las guías.
2. **Checklist en PR** (`.github/pull_request_template.md` propuesto): casillas "¿cambió una ruta/param/status? → actualicé `docs_interna/` y el snapshot". El checklist es barato y visible; el gate real es el punto 1.
3. **Job `docs-contract` (opcional, no bloqueante al inicio):** script propuesto `scripts/check_docs_contract.py` que compara nombres de rutas/params citados en `docs_interna/*.md` contra `app.routes`/OpenAPI y lista discrepancias (detectaría hoy `?fecha` vs `?date`, 404 vs 401, 201 vs 200 de H-12). Pasa a bloqueante al cierre de Fase 6.
4. **Punto único de verdad:** `docs_interna/` se corrige en las fases 11/14 del plan 01 (M-03); este plan agrega la red que evita la reincidencia. Frecuencia de revisión trimestral sugerida de las 5 guías.

### 6.8 Pins y dependencias

- **Lock del entorno dev:** congelar `requirements-dev.txt` con versiones exactas (`pip freeze` filtrado o `pip-tools`/`uv`) para reproducibilidad de CI; los pins productivos (`requirements.txt`) se abordan en la fase 15/16 del plan 01 (B-01). Decisión unificada en 8.x para no duplicar trabajo.
- **Alineación Python:** CI en 3.12 = `Dockerfile:1`; eliminar la divergencia con 3.13 del venv local (H-13).
- **Dependabot/Renovate:** propuesta de PR mensual de bumps (con CI verde obligatorio) una vez que el pipeline exista.

### 6.9 Criterios de aceptación (Fase 7)

1. Pipeline verde en un PR de prueba vacío; los 3 checks son required en `main`.
2. `ruff check .` y `ruff format --check .` pasan (con la estrategia de arranque elegida documentada).
3. `pytest --cov` cumple el umbral global del momento y los umbrales de áreas críticas de 6.2.
4. El job de integración usa `mongo:7.0` de servicio y los tests `docker` pasan.
5. Pre-commit instalado y corriendo en el repo; `OPENAPI` snapshot commiteado; `docs-contract` listo (bloqueante al cierre).

### 6.10 Riesgos (Fase 7)

| Riesgo | Mitigación |
|---|---|
| El pipeline tarda > 10 min y el equipo empieza a ignorarlo | jobs paralelos, marker `slow` fuera del gate, cache pip, timeout 120 s por test |
| Falsos negativos por tests flaky (concurrencia/timing) | reintentos solo en `docker`, aserciones de efecto final, cuarentena explícita (mover a `slow` con issue) |
| El ratchet de cobertura bloquea PRs legítimos | excluir `XFAIL` de la culpa (ya cuentan), permitir override documentado del umbral con justificación en el PR |
| `ruff` con reglas S/B genera ruido masivo al inicio | arranque por subconjunto (E,F,W,I), activar B/SIM/S/ASYNC por etapas con PRs dedicados |

---

## 7. Roadmap y dependencias con otros planes

### 7.1 Secuencia propuesta (sin frenar el desarrollo)

Semana tipo de un tester/trabajando en paralelo con los fixes P0 de los planes 01/02/03/05:

| Semana | Fases | En paralelo con |
|---|---|---|
| 1 | **Fase 0** (habilitadores) + arranque de **Fase 1** (auth) | Fixes P0 del plan 03 (CR-01…CR-06) — sus tests se escriben ya, en `xfail` |
| 2 | Cierre **Fase 1** + **Fase 2** (attempts/progreso/usuario) + montar **Fase 7 parcial** (lint + unit en CI) | Plan 03 (CR-06) y plan 02 (atomicidad de puntos) |
| 3 | **Fase 3** (challenges) + **Fase 4A/4B** (engine + partida) | Plan 01 (A-03/A-06/A-07, TZ M-04) y plan 02 (locking de runs) |
| 4 | **Fase 4C** (admin narrativo) + **Fase 5** (seeds/arranque/ETL) | Plan 04 (Bearer en la SPA admin) y plan 02 (seeds/ETL/índices) |
| 5 | **Fase 6** (seguridad/contratos) + cierre **Fase 7** (integración en CI, ratchet, docs-contract) | Plan 03 (AL-01, H-07) y plan 01 (docs H-12) |

- Los tests `xfail` permiten empezar antes del fix: **el test forma parte del PR del fix** (regla 1.2.3).
- Si el equipo es una sola persona: estirar a ~8 semanas a media dedicación; las fases son secuenciales solo por dependencia de la Fase 0; Fases 1–6 se pueden solapar por bloques.

### 7.2 Dependencias cruzadas con otros planes de solución

| Fase de este plan | Depende de (otro plan) | Tipo | Nota |
|---|---|---|---|
| 0 | ninguno | — | habilita todo |
| 1 (auth) | plan 03 CR-03/CR-04/CR-05, AL-02/AL-04/AL-05 | desmarca `xfail` | los tests se escriben antes |
| 2 (attempts/progreso) | plan 03 CR-06/ME-02; plan 02 atomicidad `$inc`/array `progresos` | desmarca `xfail` | incluye contrato de lectura con front |
| 3 (challenges) | plan 03 H-02/CR-02; plan 01 A-07/M-04 (random/TZ) | desmarca `xfail` | decisión de TZ bloqueante (8.x) |
| 4 (narrativo) | plan 03 CR-01/ME-03; plan 02 locking runs; plan 01 A-03/A-06; plan 04 Bearer admin | desmarca `xfail` + evita romper SPA | el barrido admin es el que "caza" regresiones del fix |
| 5 (seeds/ETL) | plan 02 seeds check-first, índices fail-fast, ETL | co-desarrollo | el flag `--dry-run` es cambio de producción acordado |
| 6 (seguridad) | plan 03 AL-01/H-07/BA-05/CR-03; plan 01 docs | desmarca `xfail` | matriz debe reflejar decisiones de contrato |
| 7 (CI) | ninguno adicional | — | puede empezar en semana 1–2 en versión mínima |

### 7.3 Reglas de convivencia (para que el plan no frene nada)

1. **Ningún fix P0 se mergea sin su test de regresión** (el test puede ser `xfail` en el commit previo y desmarcarse en el mismo PR del fix).
2. **Los PRs de fixes existentes se anotan con el H-xx/CR-xx** y referencian el caso de test que lo fija; la matriz del Anexo A se actualiza cuando se cierra un hallazgo.
3. **Los cambios de contrato** (status codes, params, shapes) requieren: snapshot OpenAPI actualizado + mención en el PR + ajuste de `docs_interna` (6.7). Eso evita el drift de H-12.
4. **Ventana de estabilización de CI:** la primera semana del pipeline puede tener flakies; se resuelven moviendo a `slow`/`docker` con issue, nunca deshabilitando el gate completo.
5. **Revisión quincenal de `xfail`s:** listar los `xfail` restantes; si el fix ya está mergeado y el test no se desmarcó, `xfail_strict` lo convierte en fallo (el mecanismo fuerza la limpieza).

### 7.4 Esfuerzo total (resumen)

| Fase | Esfuerzo | Días-persona (aprox.) |
|---|---|---|
| 0 | M | 1–2 |
| 1 | M | 2–3 |
| 2 | M–L | 3–4 |
| 3 | M | 2–3 |
| 4 | L | 4–5 |
| 5 | S–M | 1,5–2 |
| 6 | M | 2–3 |
| 7 | S–M | 1–2 |
| **Total** | | **~17–24 días-persona** (diseño + tests + CI) |

No incluye el tiempo de los fixes de los planes 01/02/03/05, con los que este plan comparte PRs.

### 7.5 Riesgos del roadmap

- **Si los fixes P0 se demoran**, los `xfail` se acumulan: mitigación → los `xfail` estrictos + revisión quincenal mantienen visibilidad, y ninguna fase se bloquea.
- **Si no hay CI**, el plan se degrada: mitigación → Fase 7 mínima (lint+unit) en la semana 2, aunque todavía no haya integración.
- **Si se migra a microservicios (plan 04)** antes de terminar: la matriz authz y los tests de contrato son portables; los tests de integración por feature también (misma API).

---

## 8. Preguntas abiertas y decisiones necesarias

Cada una con propuesta por defecto para no bloquear:

1. **CI:** ¿GitHub Actions es la plataforma? (no existe `.github/`). *Propuesta:* sí; si no, portar el mismo esquema (6.1).
2. **Versión de Python:** ¿3.12 fija (alineada con Docker) o salto a 3.13? *Propuesta:* 3.12; CI y `Dockerfile` idénticos.
3. **Mongomock vs testcontainers:** ¿el equipo tiene Docker en todas las máquinas? *Propuesta:* mongomock default; `docker`/CI con `mongo:7.0` para índices y carreras.
4. **Contrato de lectura de `user_attempts`:** ¿sin identidad 401 o lista vacía? ¿admin puede leer ajenos? *Propuesta:* 401 sin token; owner + admin (`tipo_usuario==2`), ajeno 403.
5. **Scoring server-side:** ¿el frontend envía `guesses/game_data` completos para recalcular `score/stars` de cada juego? Sin eso, el recálculo server-side no es viable y H-04 se mitiga de otra forma. *Propuesta:* definir por juego; empezar por wordle/sudoku.
6. **Invitados del narrativo:** ¿el modo invitado es requisito de producto? Si sí, ¿cookie/sesión anónima o auth obligatoria? *Propuesta:* identidad anónima efímera (cookie firmada) — habilita el test de aislamiento H-05.
7. **Cuenta vulnerada y enumeración:** ¿aceptar respuestas uniformes en login/registro/reenvío? Afecta asserts de Fase 1. *Propuesta:* uniformar con mensaje genérico y código de seguimiento.
8. **`seed_narrative.py` (1.789 líneas) y v1 del narrativo:** ¿se eliminan del repo productivo o se conservan como herramienta? *Propuesta:* mover a `tools/` con tests propios mínimos.
9. **Zona horaria de negocio:** ¿fijar ART (UTC-3) con helper común (plan 01 M-04)? *Propuesta:* sí, configurable por setting.
10. **Cobertura y gating:** ¿umbral mínimo aceptado y política de bloqueo? *Propuesta:* la de 6.2 (ratchet 35→50→60%).
11. **Type checker:** ¿`pyright` o `mypy`? *Propuesta:* pyright basic con allowlist.
12. **SPA admin y Bearer:** ¿el panel admin enviará token para los 32 endpoints? Bloquea el cierre verde de H-01 (plan 04). *Propuesta:* sí, antes de aplicar `get_current_admin`.
13. **Plataforma de servicio de Mongo en prod (auth/TLS) y ETL:** ¿habrá réplica/con transacciones? Cambia qué se puede testear de atomicidad (hoy standalone). *Propuesta:* decidir con plan 02.
14. **Umbral de revisión de `xfail`:** ¿quién y cada cuánto? *Propuesta:* quincenal, dueño rotativo, lista en el PR semanal.

---

## Anexo A — Trazabilidad hallazgo → fase/casos de test

| Hallazgo (informe 06 / 03) | Fase | Casos principales |
|---|---|---|
| H-01 — narrativa admin sin auth | 4 (4C), 6 | `test_admin_narrative_sin_token_401`, matriz authz |
| H-02 — challenges upsert/admin sin auth | 3 (3C), 6 | `test_post_challenges_sin_token_401`, `test_admin_status_*`, matriz |
| H-03 — IDOR lectura attempts | 2 (2B), 6 | `test_get_attempt_date_user_id_ajeno_403`, `test_get_attempts_mes_user_id_ajeno_403` |
| H-04 — scoring client-trusted / puntos duplicables | 2 (2A/2B) | `test_save_attempt_concurrencia_no_duplica_puntos`, `test_post_attempt_score_cliente_no_confiable` |
| H-05 — invitado `user_id=0` compartido | 4 (4B) | `test_dos_invitados_misma_fecha_no_comparten_partida` |
| H-06 — rate limit evadible / PIN | 1, 6 (6C) | `test_rate_limit_xff_spoof_no_evade`, `test_login_codigo_admin_pin_no_emite_token` |
| H-07 — CORS universal | 6 (6D) | `test_cors_origen_arbitrario_rechazado` |
| H-08 — secretos por defecto | 1, 6 (6B) | `test_settings_fail_fast_sin_secretos_default`, `test_jwt_forjado_con_secreto_default_rechazado` |
| H-09 — carreras sin manejo | 2 (2A), 4 (4B), 5 (5C) | dobles submit, `test_register_carrera_de_duplicados_no_500` |
| H-10 — sin infraestructura | 0, 7 | conftest/CI |
| H-11 — tests destructivos/dependientes | 0 (4.8), 4 | port de los 2 tests |
| H-12 — docs desincronizadas | 6 (6E) | `test_docs_contratos_param_fecha_vs_date`, snapshot OpenAPI |
| H-13 — higiene repo | 0, 7 | `ruff` (F811/F401), `test_post_attempt_defaults_year_month_eliminados` |
| H-14 — excepciones tragadas | 2, 5, 7 | `test_init_indexes_propaga_error`, `test_save_attempt_fallo_al_sumar_no_se_traga` |
| CR-01/CR-02 (admin/challenges) | 4, 6 | matriz authz |
| CR-03/CR-04/CR-05/CR-06 | 1, 2, 6 | casos `xfail` de Fase 1/2/6 |
| AL-01/AL-02/AL-04/AL-05/AL-06 | 1, 4C, 6 | rate limit, PIN, enumeración, logs, upload |
| A-03/A-06/A-07 (plan 01) | 4, 3 | identidad, caché, random local |
| Atomicidad/seeds/ETL (plan 02) | 2, 4, 5 | concurrencia, idempotencia, dry-run |

---

*Fin del documento — `06-testing-y-calidad-soluciones.md`. Plan de planificación: nada implementado, nada ejecutado; sin cambios de código, tests, configuración ni base de datos.*
