# Testing y calidad — contexto para la refactorización

> **Alcance:** estado actual de la suite, cobertura real, problemas de aislamiento, estrategia de tests para refactorizar sin romper contratos y CI.
> **Base analizada:** commit `d2a117b` (30/10/2026).
> **Método:** lectura completa de `tests/` (15 archivos, ~2.594 líneas), `pytest.ini`, `requirements.txt`, `.github/workflows/`, scripts de diagnóstico; ejecución selectiva de tests puros y recolección completa.
> **Estado:** se ejecutaron tests puros y comandos de diagnóstico. No se levantaron Docker, MongoDB ni servidores. No se modificó código.
> **Audiencia:** desarrolladores que se incorporan al backend y van a refactorizar sin romper el frontend.

---

## 0. Cómo usar este documento

1. Las secciones 1 a 4 describen qué hay hoy y qué se ejecutó realmente.
2. La sección 5 explica por qué la suite actual no es una red de seguridad.
3. La sección 6 define la estrategia para el refactor: **tests de caracterización primero**.
4. Las secciones 7 y 8 proponen estructura, fixtures y prioridades.
5. La sección 9 propone CI.
6. La sección 10 fija reglas para no romper routers.

Documentos hermanos:

- [Juegos clásicos](01-juegos-clasicos.md)
- [Narrativo V1/V2](02-narrativo-v1-v2.md)
- [Economía, puntos y vidas](03-economia-puntos-vidas.md)

---

## 1. Resumen ejecutivo

- Hay **15 archivos** en `tests/`, **54 tests colectados** (44 funciones, algunas parametrizadas) y ~2.594 líneas.
- La única parte hermética y confiable es el núcleo puro de Crucigrama: **40 tests pasan en ~9,5 s** sin Mongo.
- Los tests de integración usan la base real `cognijuegos_db`, no una base de test, y borran datos por fechas/usuarios fijos.
- Los tests de auth/SSO son E2E contra servicios reales y están desactualizados: payloads que hoy devuelven 422/400, puertos que no coinciden con el backend actual.
- Los tests narrativos fallan sin Mongo o quedan en 401 porque no inyectan admin.
- **No hay un solo test de economía, puntos, vidas, pistas, Wordle, Sopa, Sudoku ni admin narrativo.**
- No hay `conftest.py`, fixtures compartidas, marcadores `unit`/`integration`, `testpaths` ni timeout global.
- `pytest` **no está en `requirements.txt`**.
- No hay job de tests en CI: el único workflow solo despliega en `main`.
- `scripts/test_growth_generator.py` y `scripts/test_hand_patterns.py` no tienen `assert`; siempre salen 0 y se ejecutan durante la recolección de pytest.
- La suite actual **no es una red de seguridad** para refactorizar. Antes de tocar routers hay que construir tests de caracterización y contrato.

---

## 2. Inventario actual

| Archivo | # | Área | Qué valida realmente | Estilo | Dependencias | ¿Corre sin servicios? |
|---|---:|---|---|---|---|---|
| `tests/test_auth_central_live.py` | 3 | Auth local/SSO | Health del autenticador, PIN, login admin, token, registro, `/usuario`, proxy Vite | E2E real | Auth central HTTPS, backend 8087, Vite 5174 | **No**; además está desactualizado |
| `tests/test_auth_microservice.py` | 1 | Auth | Health, usuarios semilla, token, suspendido, admin, `/usuario`, registro | E2E real | Servicio 8082 + auth + Mongo | **No**; puerto y contrato desactualizados |
| `tests/test_crucigrama_admin.py` | 1 | Crucigrama admin | 401 sin token, validate, anclas, vetos, CRUD, publish/apply, conflictos, generación mensual | Integración ASGI + Mongo | Mongo real | **No**; skip tras ~15 s |
| `tests/test_crucigrama_anclas.py` | 14 | Crucigrama solver | Normalización/validación de anclas, determinismo, cruces, errores | Unitario puro | Léxico/templates locales | **Sí** |
| `tests/test_crucigrama_bans.py` | 5 | Crucigrama bans | `clean_words`, exclusión de vetadas, cableado mensual | 4 unitarios + 1 integración | Mongo para el mensual | **Parcial** |
| `tests/test_crucigrama_bitset.py` | 7 | Crucigrama solver | Máscara densa, 11x11, determinismo, anclas, vetos | Unitario puro | Ninguna | **Sí** |
| `tests/test_crucigrama_recurrencia.py` | 1 | Crucigrama admin | Plantillas recurrentes, unicidad, día 31, prioridad, archivo | Integración ASGI + Mongo | Mongo real | **No** |
| `tests/test_crucigrama_validator.py` | 15 | Crucigrama validator | Estructura, solubilidad, simetría, léxico, pistas curadas | Unitario puro | JSON de léxico local | **Sí** |
| `tests/test_narrative_game.py` | 1 | Narrativo V1/V2 | Catálogo admin, universos, setup, inicio V2, modales, reinicio | Integración ASGI + Mongo | Mongo, seeds | **No**; falla sin Mongo y con Mongo quedaría en 401 |
| `tests/test_narrative_v2_admin.py` | 1 | Admin narrativo V2 | Listar/crear/obtener/borrar eventos y conversaciones V2 | Integración ASGI + Mongo | Mongo | **No**; siempre 401 |
| `tests/test_narrative_v2_desenlaces_tags.py` | 1 | Narrativo V2 engine | Anti-spoiler, desenlaces ponderados, tags permanentes | Integración engine + Mongo | Mongo, seeds | **No**; sin skip ni `finally` |
| `tests/test_narrative_v2_eventos_especiales.py` | 1 | Narrativo V2 engine | Umbrales de lealtad/traición, encadenamiento | Integración engine + Mongo | Mongo, seeds | **No**; sin skip ni `finally` |
| `tests/test_narrative_v2_game.py` | 1 | Narrativo V2 E2E | Ciclo de 12 meses: draft, evento, conversación, avance, finalización | E2E ASGI + Mongo | Mongo, seeds, fecha actual | **No**; muta configuración global |
| `tests/test_narrative_v2_graphs.py` | 1 | Narrativo V2 engine/API | Sanitización, arcos, navegación, persistencia, condiciones, endpoint | Integración engine/ASGI + Mongo | Mongo, seeds, `JWT_SECRET` | **No** |
| `tests/test_sso_ticket_flow.py` | 1 | SSO | Crear, canjear, reutilizar y retorno de tickets | E2E real | Auth 8000 + backend 8082 + Mongo | **No** |

**Fuera de `tests/`:**

| Archivo | Qué es | Problema |
|---|---|---|
| `scripts/test_growth_generator.py` | Validación del generador de crecimiento | No tiene `assert`; imprime y sale 0 aunque todo falle. |
| `scripts/test_hand_patterns.py` | Patrones 10x10 escritos a mano | No tiene `assert`; ningún patrón resultó utilizable pero “pasa”. |

---

## 3. Resultados verificados de ejecución

> Estos resultados se obtuvieron en la auditoría. No deben interpretarse como estado permanente del CI, porque hoy no hay CI de tests.

### 3.1 Colecta

```text
python -m pytest --collect-only -q
54 tests collected in 5.60s
```

- 0 errores de import/colección.
- 3 warnings por `class Config` deprecado en Pydantic v2 (`app/features/progreso/schemas.py:4,14,22`).
- Los tests `async` con `@pytest.mark.anyio` se colectan como `[asyncio]`.
- `pytest.ini` solo tiene `pythonpath = .`; no hay `testpaths`, marcadores, `filterwarnings` ni timeout global.

### 3.2 Tests puros

```text
python -m pytest tests/test_crucigrama_anclas.py tests/test_crucigrama_bitset.py \
  tests/test_crucigrama_validator.py tests/test_crucigrama_bans.py \
  -k "not test_generacion_mensual_recibe_vetos_globales" -q

40 passed, 1 deselected in 9.47s
```

Es la única parte de la suite que hoy funciona de forma hermética y rápida.

### 3.3 Tests que dependen de Mongo

```text
python -m pytest tests/test_crucigrama_bans.py::test_generacion_mensual_recibe_vetos_globales \
  tests/test_crucigrama_admin.py tests/test_crucigrama_recurrencia.py -q -rs

3 skipped in 48.23s
```

Cada skip tarda ~15 s porque `connect_to_mongo()` intenta conectar e inicializar índices antes de que el test haga `ping` y decida saltar.

### 3.4 Tests narrativos sin Mongo

```text
python -m pytest tests/test_narrative_game.py tests/test_narrative_v2_admin.py -q
2 failed in 29.11s
```

- `test_narrative_game` falla con `ServerSelectionTimeoutError`; no tiene skip.
- `test_narrative_v2_admin` falla con **401** porque el router admin exige `get_current_admin` y el test no inyecta token ni override.

```text
python -m pytest tests/test_narrative_v2_desenlaces_tags.py -q
1 failed in 17.32s
```

Falla con `ServerSelectionTimeoutError`; no tiene skip.

### 3.5 Diagnósticos puntuales

| Diagnóstico | Resultado |
|---|---|
| `POST /api/auth/ingresar-codigo` con `{"codigo":"123456"}` | **422**: falta `email`; el test usa ese payload y espera otro contrato. |
| `GET /usuario?limit=1` | **400**: endpoint deshabilitado; los tests esperan 200. |
| `create_access_token({"id": 1})` sin `.env` | `InvalidKeyError: HMAC key must not be empty`; `JWT_SECRET` default es `""`. |
| Puertos 27017, 8000, 8082, 8087, 5174 | Cerrados en la máquina de auditoría; por eso no se ejecutó la suite completa. |

### 3.6 Scripts

| Script | Resultado |
|---|---|
| `python scripts/test_growth_generator.py` | “20/20 tableros válidos”, exit 0. Sin asserts. |
| `python scripts/test_hand_patterns.py` | Ningún patrón `solved=True`, exit 0. Sin asserts. |

`pytest --collect-only -s scripts` **importa y ejecuta** ambos scripts durante la recolección.

---

## 4. Cobertura funcional por área

| Área | Cobertura real | Detalle |
|---|---|---|
| Crucigrama: solver/validator/anclas/vetos | **Buena** | 40 tests puros verdes. Máscaras densas, 11x11, determinismo, anclas, acentos, vetos y errores estructurales. |
| Crucigrama: admin/publicación/recurrencia | **Media** | 3 tests de integración grandes con Mongo real; cubren happy path, conflictos, archive, generación mensual y prioridad. |
| Narrativo V2: engine de grafos | **Parcial** | Anti-spoiler, desenlaces, tags, umbrales, arcos, condiciones y persistencia, todo con Mongo y seeds. |
| Narrativo V1 | **Nula efectiva** | El único test que lo roza falla sin Mongo y con Mongo quedaría en 401. No hay tests de `event_director`, `rule_engine` ni `transition_service`. |
| Admin narrativo V1/V2 | **Nula efectiva** | `test_narrative_v2_admin` siempre da 401. |
| Auth | **Nula hermética** | Solo E2E reales, uno desactualizado. Sin mocks de `login_sistemas`, `login_codigo`, `verificar_token`, `register_usuario`, JWT ni rate limiting. |
| SSO | **Nula efectiva** | Apunta a puertos que no son el backend actual. |
| Economía / vidas / puntos / pistas / suscripción | **Cero** | Sin referencias a `economy`, `use-hint`, `consume-life`, `buy-lives`, `unlock-day` en `tests/`. |
| Wordle | **Cero** | Sin referencias a `wordle`. |
| Sopa de letras | **Cero** | Sin referencias a `sopa`. |
| Sudoku | **Cero** | Sin referencias a `sudoku`. |
| API de desafíos diarios | **Cero directa** | `/today`, `/month`, `/range`, `/date`, `POST /api/challenges` y admin no tienen tests propios. |
| Intentos, calificaciones y puntos | **Cero** | `calculate_grade_and_score` es pura y no tiene tests. |
| Usuarios, progreso, seguridad | **Cero** | Sin tests de `usuario`, `progreso`, `get_current_user`, `get_current_admin`, `security_middleware` ni `/health`. |

### 4.1 Huecos con NINGÚN test

- Economía completa (`economy/router.py:42-189`, `economy/service.py:53-618`).
- Vidas por juego y `remaining_attempts`.
- Puntos: acreditación, idempotencia, replay, concurrencia.
- Pistas: descuento, saldo insuficiente, contenido por juego, reembolso.
- Desbloqueo histórico: premium, básico, doble cobro, fecha inválida.
- Wordle/Sopa/Sudoku: generadores y endpoints diarios.
- Auth/SSO hermético.
- Admin narrativo V1 completo y V2 real.
- Admin de desafíos: `POST /api/challenges` sin admin no tiene test que lo detecte.

---

## 5. Por qué la suite actual no es una red de seguridad

### 5.1 Aislamiento y limpieza

- **No hay `conftest.py` ni fixtures compartidas.** Cada test repite `connect_to_mongo`, seeds, `ASGITransport` y limpieza manual.
- **Los tests de integración usan la base real `cognijuegos_db`**, no una base de test.
- **Tests destructivos sobre datos reales:** borran `daily_challenges` de fechas fijas, runs de usuarios fijos (`777001`, `777002`, `999999`) y desafíos por fecha.
- **Limpieza no garantizada en narrativo:** varios tests limpian al final, pero no en `finally`. Una assertion fallida deja eventos/runs en la base.
- **Estado global mutado:** `test_narrative_v2_game.py:50` cambia `narrative_settings.motor` a `"v1"` y no lo restaura.
- **Seeds dentro de tests:** varios tests siembran datos si las colecciones están vacías; no es un fixture, es una escritura en la base configurada.
- **Overrides globales:** `app.dependency_overrides[get_current_admin]` no es paralelizable y puede contaminar si falla antes del `finally`.
- **Cliente Motor global + `asyncio.run` por test:** varios tests no cierran la conexión; pueden quedar clientes atados a event loops cerrados.

### 5.2 Hardcodeos y dependencia de estado

- Credenciales y datos reales hardcodeados: `admin@autenticador.com`, PIN `123456`, `654321`, `112233`, password `999999`, nombres y emails de personas.
- URLs y puertos fijos: auth de producción `https://autenticacion.asistodo.com.ar`, Vite 5174, backend 8087, servicios 8000/8082.
- Fechas fijas futuras: 2027-02-01, 2029-01-01, 2030-01-15/16/17, 2031-01-01..05. Evitan colisiones con “hoy”, pero pueden borrar plantillas/desafíos reales.
- IDs y contenidos exactos: `id == 2`, “Marta González”, `size == 7`, recursos 65/40/60/35.
- Dependencia implícita de `.env`: `test_narrative_v2_graphs` crea un JWT y sin `JWT_SECRET` falla.

### 5.3 Asserts débiles, duplicación y tests que prueban mocks

- **77 de 95 aserciones de status exigen `== 200`.** Varias solo comprueban status y un campo superficial.
- **Tests gigantes:** `test_crucigrama_admin` tiene 464 líneas y 96 asserts en una sola función; `test_narrative_v2_graphs` tiene 341 líneas y 5 “subtests”. El primer fallo oculta el resto.
- **Lógica pura enterrada en tests de integración:** la sanitización anti-spoiler se ejecuta después de conectar a Mongo; sin base, nunca corre.
- **Admin “testeado” con override:** `test_crucigrama_admin` inyecta un admin falso y no prueba JWT real ni 403.
- **`random` parcheado:** varios tests fuerzan `random.random` a 0.99; válido para determinismo, pero no prueba distribución.
- **Scripts que no fallan:** `scripts/test_*.py` no tienen asserts.

### 5.4 Timeouts, sleeps y duración

- No hay `sleep` en los tests.
- Timeouts HTTP de 10-12 s; no hay timeout global de pytest.
- Ticket SSO de 30 s con múltiples llamadas de 10 s: frágil en CI lento.
- Skips de Mongo de ~15 s cada uno.
- No hay medición de cobertura.

### 5.5 Configuración

- `pytest.ini` solo tiene `pythonpath = .`.
- No hay `conftest.py`.
- `requirements.txt` no incluye `pytest` ni plugins.
- No hay etapa de test en Dockerfile; `tests/` se copia a la imagen final.

---

## 6. Estrategia para el refactor

> El objetivo no es “agregar muchos tests”, sino **congelar contratos y comportamiento actual** antes de mover código.

### 6.1 Orden correcto

1. **Tests de contrato (OpenAPI + rutas).** Congelan paths, métodos, auth y schemas. Detectan cualquier cambio accidental en routers.
2. **Tests de caracterización.** Capturan el comportamiento actual de cada endpoint, incluidos los bugs conocidos. No corrigen nada; documentan.
3. **Tests unitarios de lógica pura.** Generadores, scoring, validadores, reglas, cálculo de grados.
4. **Tests de integración con base de test.** Servicios y flujos multi-documento.
5. **Tests E2E opt-in.** Solo contra entornos controlados; nunca producción.

### 6.2 Qué es un test de caracterización

Un test que describe lo que el sistema hace **hoy**, no lo que debería hacer. Ejemplo: si `POST /api/challenges` hoy es público, el test lo llama sin token y espera 200. Cuando se cierre la seguridad, ese test se actualiza deliberadamente y se documenta el cambio de contrato.

Sin esta red, cualquier refactor puede cambiar una respuesta y romper el frontend sin que nadie lo note.

### 6.3 Contratos que hay que congelar

- Respuestas de `/api/challenges/*`, incluida la solución (aunque sea un bug).
- Respuestas de `/api/games/attempts` (`puntos_ganados`, `puntos_totales_usuario`).
- Respuestas de `/api/economy/*` (incluidos `vidas`, `vidas_restantes`, `vidas_descontadas`).
- Respuestas del loop narrativo V1 y V2 (`iniciar`, `elegir-carta-mes`, `decidir-evento`, `responder-conversacion`, `avanzar-mes`, `avanzar-nodo`, `estado`, modales).
- Respuestas admin de Crucigrama y narrativo.
- Errores y códigos de estado del camino feliz y de los errores esperados.

### 6.4 Tests que NO hay que escribir todavía

- Tests que asumen el comportamiento “correcto” que todavía no existe (validación server-side, vidas por juego, ledger).
- Tests E2E contra producción.
- Tests que dependen de fechas relativas sin congelar el reloj.
- Tests que usan la base real.

---

## 7. Estructura propuesta

```text
tests/
├── conftest.py
├── contract/
│   ├── test_openapi_contract.py
│   └── snapshots/
│       └── openapi.json
├── unit/
│   ├── economy/
│   │   ├── test_scoring.py
│   │   └── test_grade_calculation.py
│   ├── challenges/
│   │   ├── test_wordle_generator.py
│   │   ├── test_sopa_generator.py
│   │   └── test_sudoku_generator.py
│   ├── crucigrama/
│   │   ├── test_anclas.py
│   │   ├── test_bitset.py
│   │   ├── test_validator.py
│   │   └── test_bans.py
│   └── narrative/
│       ├── test_rule_engine.py
│       ├── test_event_director.py
│       └── test_graph_validation.py
├── integration/
│   ├── test_challenges_api.py
│   ├── test_attempts_api.py
│   ├── test_economy_api.py
│   ├── test_crucigrama_admin.py
│   ├── test_narrative_v1.py
│   └── test_narrative_v2.py
└── live/
    ├── test_auth_live.py
    └── test_sso_live.py
```

### 7.1 `pytest.ini` propuesto

```ini
[pytest]
pythonpath = .
testpaths = tests
markers =
    unit: tests puros, sin IO ni base de datos
    integration: requieren MongoDB de test y app ASGI
    live: requieren servicios externos reales (opt-in)
    contract: congelan OpenAPI y rutas
addopts = -m "not integration and not live"
```

- `pytest -m unit` corre en cualquier máquina y en CI sin servicios.
- `pytest -m integration` requiere una base de test.
- `pytest -m live` solo se corre manualmente contra un entorno controlado.

### 7.2 `conftest.py` mínimo

Fixtures sugeridas:

| Fixture | Uso |
|---|---|
| `event_loop`/`anyio_backend` | Configuración async. |
| `app` | Instancia FastAPI con overrides de test. |
| `client` | `httpx.AsyncClient(transport=ASGITransport(app=app))`. |
| `test_db` | Base `cognijuegos_test`, limpieza por colección/prefijo. |
| `admin_override` | Inyecta un admin de test sin JWT real, pero con un test separado que valide el 401/403 real. |
| `freeze_today` | Congela la fecha para tests determinísticos. |
| `seeded_challenge` | Inserta un desafío de prueba sin ejecutar seeds completos. |
| `cleanup` | Limpieza garantizada en `finally`. |

Reglas de la base de test:

- Nombre distinto de producción (`cognijuegos_test`).
- Nunca usar la base real.
- Limpiar por `user_id`/`date` de test, no por fechas fijas globales.
- No ejecutar seeds completos; insertar solo lo necesario.
- Cerrar Motor al finalizar la sesión.

### 7.3 Dobles de servicios externos

- Auth/SSO: `httpx.MockTransport` o `unittest.mock.patch` sobre las llamadas salientes.
- RAE: fake local o fixture, no red.
- Imágenes: archivos temporales, no `app/static` real.
- JWT: `JWT_SECRET` de test explícito.
- Fechas: reloj congelado o fechas generadas por test.

---

## 8. Plan de tests por prioridad

### Prioridad 0 — Contrato y caracterización

1. **OpenAPI snapshot.** Comparar `app.openapi()` contra un JSON versionado. Detecta cambios de rutas, métodos, schemas y campos.
2. **Rutas y auth.** Test que recorre el router y verifica que cada endpoint admin sigue exigiendo admin, y cada endpoint público sigue público (documentando los que deberían cambiar).
3. **Desafíos.** `GET /today`, `/date`, `/month`, `/range` para cada juego; `POST /challenges`; admin status/generate.
4. **Attempts.** Victoria nueva, repetida, cambio de estado, `user_id` sin token, IDOR de lectura.
5. **Economía.** `/config`, `/me`, `consume-life`, `buy-lives`, `unlock-day`, `use-hint`, admin config/search/adjust.
6. **Narrativo.** Iniciar, draft, evento V1, conversación V1, avanzar mes, V2 `avanzar-nodo`, modales, admin.

### Prioridad 1 — Lógica pura

- `calculate_grade_and_score`: todos los juegos, estados, grados, estrellas, `game_data` inválido.
- Generadores Wordle/Sopa/Sudoku: determinismo por fecha, integridad de grilla, unicidad de Sudoku.
- `rule_engine`: condiciones, acciones, efectos, valores inválidos.
- `event_director`: selección ponderada, exclusión de jugados, reciclaje, opciones secretas.
- Validación de grafos: raíz, punteros, terminales, ciclos, pesos.
- `clean_words`, anclas, validador de Crucigrama (ya existen; mantener).

### Prioridad 2 — Integración

- `save_user_attempt` con Mongo de test: idempotencia, replay, concurrencia, `$inc` fallido.
- `use_hint`: éxito, sin saldo, sin desafío, reembolso, dificultad, idempotencia.
- `unlock-day`: básico, premium, ya desbloqueado, carrera.
- `buy_lives`: paquete, saldo, tope.
- Crucigrama admin: validar, publicar, aplicar, archivar, recurrencia.
- Narrativo V1: ciclo completo con seeds mínimos.
- Narrativo V2: grafo completo, eventos especiales, derrota, victoria, F5.

### Prioridad 3 — E2E opt-in

- Auth/SSO contra un entorno de staging, nunca producción.
- Flujo completo de un usuario: registro → desafío → intento → puntos → pista → desbloqueo.
- Marcados `live` y excluidos por defecto.

---

## 9. CI propuesto

### 9.1 Workflow mínimo

```yaml
name: tests
on:
  pull_request:
  push:
    branches: [main]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest -m "unit or contract" -q

  integration:
    runs-on: ubuntu-latest
    services:
      mongo:
        image: mongo:7
        ports: ["27017:27017"]
    env:
      MONGODB_DB_NAME: cognijuegos_test
      JWT_SECRET: test-secret
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest -m integration -q
```

### 9.2 Reglas

- `pytest` y plugins van en `requirements-dev.txt`; no en producción.
- El deploy debe depender de `unit`, `contract` e `integration` (`needs:`).
- No usar la base de producción ni el auth de producción.
- No correr `live` en CI.
- Publicar cobertura solo como artefacto, no como bloqueante al principio.
- Fijar `TZ=America/Argentina/Buenos_Aires` en CI para que los tests de fecha sean determinísticos.

### 9.3 Qué NO hacer

- No correr la suite actual completa en CI: intentaría pegarle a producción y a puertos locales.
- No usar `ci` como excusa para mantener tests destructivos.
- No agregar dependencias nuevas sin necesidad; `httpx` ya está en `requirements.txt`.

---

## 10. Reglas para no romper routers

1. **Los tests de contrato son obligatorios antes de tocar routers.** Si un test de OpenAPI falla, el cambio es visible y requiere decisión.
2. **No actualizar snapshots sin revisar el diff.** Un snapshot actualizado a ciegas puede ocultar un breaking change.
3. **Los tests de caracterización documentan bugs actuales.** No “arreglarlos” en el mismo commit que el refactor.
4. **Un cambio de comportamiento intencional va en un commit separado** con su test actualizado y su nota de migración.
5. **Los tests de integración no usan la base real.** Si un test necesita datos, los crea y los limpia.
6. **Los tests live no son la red de seguridad.** Son smoke tests manuales.
7. **Cada bug corregido debe tener un test de regresión.** Empezar por los P0 de los otros documentos.
8. **No testear mocks.** Si se mockea Mongo, el test no prueba la persistencia; usar base de test para integración.

---

## 11. Comandos de referencia

```bash
# Recolección completa
python -m pytest --collect-only -q

# Solo tests puros (hoy)
python -m pytest tests/test_crucigrama_anclas.py tests/test_crucigrama_bitset.py \
  tests/test_crucigrama_validator.py tests/test_crucigrama_bans.py \
  -k "not test_generacion_mensual_recibe_vetos_globales" -q

# Con la estructura propuesta
python -m pytest -m unit -q
python -m pytest -m contract -q
python -m pytest -m integration -q
python -m pytest -m live -q

# Scripts de diagnóstico (no son tests)
python scripts/test_growth_generator.py
python scripts/test_hand_patterns.py
```

---

## 12. Criterios de aceptación del refactor

- [ ] Existe `tests/conftest.py` con fixtures compartidas y base de test.
- [ ] `pytest.ini` tiene `testpaths`, marcadores y `addopts` por defecto.
- [ ] `pytest` y plugins están en `requirements-dev.txt`.
- [ ] Hay un snapshot de OpenAPI versionado y un test que lo compara.
- [ ] Hay tests de caracterización de desafíos, attempts, economía y narrativo.
- [ ] Hay tests unitarios de `calculate_grade_and_score`, generadores y `rule_engine`.
- [ ] Hay tests de integración de economía y narrativo con base de test.
- [ ] Ningún test usa la base `cognijuegos_db` ni producción.
- [ ] Ningún test borra datos por fechas/usuarios fijos.
- [ ] Toda limpieza está en `finally` o en un fixture.
- [ ] CI corre `unit` + `contract` en cada PR y `integration` en cada push.
- [ ] El deploy depende de los tests.
- [ ] Los tests live están marcados y excluidos por defecto.

---

## 13. Riesgos y preguntas abiertas

1. **¿El frontend está dispuesto a correr contract tests?** Idealmente, el mismo snapshot de OpenAPI se valida contra el cliente.
2. **¿Hay un Mongo de test disponible?** Si no, los tests de integración no pueden ser obligatorios al principio.
3. **¿Se puede congelar la fecha del servidor?** Necesario para tests determinísticos de desafíos diarios.
4. **¿Se van a mantener los tests live?** Hoy apuntan a producción y puertos viejos; hay que reescribirlos o eliminarlos.
5. **¿Se acepta agregar `requirements-dev.txt`?** Es el cambio mínimo para que CI funcione.
6. **¿Se va a medir cobertura?** Recomendado, pero no bloqueante al inicio.
7. **¿Quién es dueño de los tests de contrato?** Backend y frontend deben acordar el snapshot.
8. **¿Se migran los tests gigantes o se reescriben?** Recomendado: reescribir en casos pequeños con base de test.

---

## 14. Anexo: mapa de riesgos de la suite actual

| Riesgo | Test / archivo | Consecuencia |
|---|---|---|
| Test de admin siempre 401 | `tests/test_narrative_v2_admin.py:18` | Falsa cobertura del CRUD. |
| Test V1 sin skip de Mongo | `tests/test_narrative_game.py` | Falla en cualquier entorno sin base. |
| Test “V2” fuerza V1 | `tests/test_narrative_v2_game.py:50` | No prueba el motor de grafos. |
| Test live desactualizado | `tests/test_auth_central_live.py:61,88` | No puede pasar contra el código actual. |
| Test apunta a puerto viejo | `tests/test_auth_microservice.py:11`, `tests/test_sso_ticket_flow.py:7-8` | No prueba el backend actual. |
| Base real y datos destructivos | `tests/test_crucigrama_admin.py:30-33`, `tests/test_narrative_game.py:54` | Puede borrar datos reales. |
| Limpieza sin `finally` | `tests/test_narrative_v2_*.py` | Deja residuos si falla. |
| Estado global mutado | `tests/test_narrative_v2_game.py:50` | Contamina otros tests. |
| Sin `JWT_SECRET` | `tests/test_narrative_v2_graphs.py:200` | Falla al crear token. |
| Sin asserts | `scripts/test_*.py` | Siempre “pasa”. |
| Sin CI | `.github/workflows/deploy.yml` | Nada bloquea un merge roto. |
| Sin tests de negocio | `economy`, `wordle`, `sopa`, `sudoku`, `attempts` | Los bugs P0 no se detectan. |
