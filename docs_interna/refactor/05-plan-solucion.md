# Plan de solución — backend de juegos

> **Estado:** Fases 0, 0.5, 1, 2, 3 y 4 implementadas, y Fase 5 en su parte de separación/truncado (Opción A), en `feature/refactor-backend` (3/11/2026). V2 sigue sin declararse oficial: falta contenido/readiness y la migración del frontend por universo.
> **Base:** commit `d2a117b` + relevamiento de solo lectura del frontend (`Desktop/proyectos/frontend`, 2/11/2026).
> **Restricciones acordadas:**
> - Los routers son contrato sagrado: no se cambian paths, métodos, campos ni códigos del camino feliz.
> - El frontend se lee, no se modifica en esta etapa.
> - V1 sigue siendo el motor operativo; V2 es el objetivo, pero solo se declara oficial cuando pase una prueba de readiness.
> - Replay no permitido: el backend también lo bloquea, aunque el frontend ya lo bloquee.
> - Vidas locales por partida (4 por juego/fecha), con recarga pagada en puntos.
> - El narrativo acredita puntos, también a invitados (para invitados, en `localStorage`).
> - Crucigrama fácil y difícil son dos slots y dos acreditaciones.
> - No se implementa código hasta aprobación explícita.
> **Documentos base:** [01-juegos-clasicos.md](01-juegos-clasicos.md), [02-narrativo-v1-v2.md](02-narrativo-v1-v2.md), [03-economia-puntos-vidas.md](03-economia-puntos-vidas.md), [04-testing.md](04-testing.md).

---

## 0. Resumen para decidir

El problema no es uno, son tres capas que conviene separar:

1. **Integridad de datos:** el servidor acepta como verdad lo que manda el cliente (`grade`, `score`, `attempts`, `time_taken_seconds`, `errors`). Los puntos se acreditan con un `find_one` + `$inc` no atómico, replayable.
2. **Anti-cheat:** los GET de desafíos entregan la solución completa y el cliente valida localmente. Aunque se valide la submission en el servidor, mientras la solución siga siendo pública el jugador puede copiarla.
3. **Operación y estado:** el narrativo V2 no está sembrado, el seed V1 pisa el motor en cada arranque, los endpoints manuales de grafos no validan fase, y no hay tests que sostengan un refactor. El pipeline de despliegue queda fuera de alcance por ahora.

**Orden recomendado:** red de seguridad → integridad de economía/intentos → validación server-side con el payload actual → narrativo operativo y readiness V2 → estructura/operación. No hacer un big-bang.

**Lo que ya se puede hacer sin tocar el frontend:**
- Acreditar puntos de forma idempotente (ledger con clave única).
- Validar Wordle/Sopa/Sudoku/Crucigrama usando los campos que el frontend **ya envía** al finalizar (`word`, `guesses`, `game_data.userGrid`, `game_data.cells`, `game_data.difficulty`).
- Separar la acreditación de Crucigrama fácil/difícil usando `game_data.difficulty`.
- Cobrar pistas solo si hay contenido y hacerlas idempotentes.
- Poner guardas de fase en los endpoints manuales de grafos.
- Dejar de pisar el catálogo y el `motor` en cada arranque.
- Agregar tests de contrato, caracterización e integración local.

**Lo que necesita cambio de frontend (se documenta, no se implementa ahora):**
- Usar `puntos_totales_usuario` en vez de sumar `score` local.
- Apuntar la recarga de vidas a un endpoint de jugador (hoy llama a uno de admin y recibe 403).
- Migrar a GET de desafío sanitizado y a feedback server-side por jugada.
- Enviar `difficulty` explícita en intentos/pistas (o seguir usando `game_data.difficulty`).
- Economía de invitado en `localStorage`, con volcado único al crear la cuenta y sobrescritura al iniciar sesión con otra cuenta.

**Decisiones confirmadas (2/11/2026):** D1 vidas locales + recarga por endpoint de jugador; D2 sin replay y una acreditación por slot; D3 dos slots para Crucigrama; D4 el narrativo acredita puntos (para invitados, en `localStorage`); D6 puntos de invitado en `localStorage`, volcado al crear cuenta y el saldo del servidor pisa al cambiar de cuenta.

**Aclaraciones de alcance:**
- `POST /api/challenges` no es el camino de juego de invitado. Es un **upsert** público que permite crear/pisar el desafío del día y su solución. El juego de invitado usa `GET /api/challenges/today` y `GET /api/challenges/date/{date}`, que siguen públicos. Cerrar el POST no quita el modo invitado. El frontend no llama al POST; el admin usa `/api/challenges/admin/*`.
- **Pipeline fuera de alcance:** no se modifica `.github/workflows/deploy.yml` ni se agrega CI en esta etapa. El riesgo que sí abordamos es la base local: los tests actuales no tienen `conftest.py` y usan la DB configurada (`mayores_actualizaciones`). Ver §8.5.

---

## 1. Diagnóstico en una página

### 1.1 Causa raíz

```text
GET /api/challenges/*  → entrega config con solución
Cliente                → valida, calcula grade/score/stars/errors
POST /api/games/attempts → acepta esos valores y acredita puntos
```

El backend genera y persiste, pero no arbitra. Todo lo demás deriva de ahí.

### 1.2 Estado real de los puntos

La acreditación vive en un solo lugar: `save_user_attempt` ([app/features/user_attempts/service.py:188](../../app/features/user_attempts/service.py#L188)).

```text
existing = find_one(...)                    # lectura
find_one_and_update(..., $set=doc, upsert)  # escritura
if is_new_victory: $inc usuarios.puntos     # segunda escritura
```

Problemas concretos:

- `effective_user_id = authenticated_user_id or req.user_id or 1` ([service.py:194](../../app/features/user_attempts/service.py#L194)): sin token se confía en el body.
- `was_already_completed` se lee antes del upsert: `completed → failed/in_progress → completed` vuelve a acreditar.
- Dos POST concurrentes pueden acreditar dos veces.
- Si el `$inc` falla, solo se loguea un warning y la respuesta igual informa `puntos_ganados`.
- No se valida que el desafío exista, ni que la submission sea correcta, ni que la fecha sea jugable.
- `game_id` es string libre.

### 1.3 Estado real de la calificación

`calculate_grade_and_score` ([service.py:17](../../app/features/user_attempts/service.py#L17)) **sí** tiene calificación por tiempo para `sudoku`, `crucigrama` y `sopa_letras` ([service.py:51-71](../../app/features/user_attempts/service.py#L51)), aunque el tiempo lo manda el cliente.

Precedencia actual:

1. `failed/lost` → `F`.
2. Estado intermedio → `C` o el `grade` provisto, sin puntos.
3. Juego cronometrado + tiempo + escalas → grado por tiempo.
4. `grade` del cliente si existe en `puntos_por_calificacion`.
5. Cálculo por juego con `attempts`, `errors` y `remaining_attempts`.

Deudas:
- El cliente puede mandar `time_taken_seconds: 1` o `grade: "S"`.
- `remaining_attempts == 0` da `S` en Sudoku ([service.py:103](../../app/features/user_attempts/service.py#L103)).
- `game_data.errors` no numérico puede lanzar `ValueError` → 500.
- El frontend manda `remaining_attempts: 0` en el guardado final ([attemptsService.ts:400](../../../../frontend/src/VISTAS/JUEGOS/attemptsService.ts#L400)).
- `mode` y `difficulty` no están en la clave única: fácil y difícil de Crucigrama comparten intento y acreditación.

### 1.4 Estado real de vidas

Hay **dos sistemas**:

| Sistema | Dónde vive | Quién lo usa |
|---|---|---|
| Vidas globales `usuarios.vidas` | `/api/economy/me`, `consume-life`, `buy-lives`, admin adjust | `LivesBadge` cuando no recibe prop; tienda; endpoints |
| Vidas por partida (4) | `useGameLives` en el cliente | Todos los juegos; se recargan con 50 puntos |

La recarga de las vidas de partida llama a `POST /api/admin/economy/user/adjust` ([PlayerEconomyContext.tsx:270](../../../../frontend/src/context/PlayerEconomyContext.tsx#L270)), que exige admin ([economy/router.py:162-177](../../app/features/economy/router.py#L162)). Un jugador normal recibe 403; el propio código tiene un mensaje para ese caso ([PlayerEconomyContext.tsx:276](../../../../frontend/src/context/PlayerEconomyContext.tsx#L276)). **La recarga de las 4 vidas de partida está rota en producción.**

No es el único camino de compra: la mini-tienda usa `POST /api/economy/buy-lives` con `{ package_id }` ([PlayerEconomyContext.tsx:286](../../../../frontend/src/context/PlayerEconomyContext.tsx#L286)) y **sí funciona** para usuarios con sesión. La distinción importa para la seguridad: el paquete define vidas y precio en el servidor, así que el cliente no elige la cantidad.

El endpoint `buy-lives` además acepta la vía legacy `{ vidas: N }` ([economy/service.py:241-245](../../app/features/economy/service.py#L241)), donde el servidor calcula el costo pero el cliente elige la cantidad y no se aplica `vidas_maximas`. Hoy el frontend no la usa; conviene depreciarla o ignorarla.

### 1.5 Estado real del narrativo

- El frontend **ya ejecuta el loop V2**: `iniciar`, `elegir-carta-mes`, `avanzar-nodo` cuando hay `nodo_id`, `decidir-evento`, `responder-conversacion`, `avanzar-mes`, `estado` ([narrativeService.ts:313-402](../../../../frontend/src/VISTAS/JUEGOS/NARRATIVO/narrativeService.ts#L313), [KingsCourt.tsx:281-363](../../../../frontend/src/VISTAS/JUEGOS/NARRATIVO/KingsCourt.tsx#L281)).
- También entiende `grafo_actual`, `nodo_actual`, `es_final` y `opciones` ([narrativeService.ts:130-193](../../../../frontend/src/VISTAS/JUEGOS/NARRATIVO/narrativeService.ts#L130)).
- Lo que **no** usa: `GET /grafo-actual`, `iniciar-evento-grafo`, `iniciar-conversacion-grafo`.
- El bloqueo real de V2 no es el renderizado: es **contenido, seed, validación de grafos, guardas de fase e historial**.
- El seed V1 se ejecuta en cada arranque y reescribe el universo sin `motor`, dejando `"v1"` ([app/main.py:57-60](../../app/main.py#L57), `app/scripts/seed_narrative.py:60-72`).
- Con 7 eventos V2 y sin reciclaje, una partida de 12 meses no cierra.
- Los endpoints manuales no validan fase, estado ni `grafo_activo`; permiten farmear recursos, reroll y revivir partidas.

---

## 2. Hallazgos del relevamiento que corrigen la auditoría

Estas son diferencias entre lo documentado y lo que hace el código/frontend hoy. Hay que corregir los documentos antes de planificar sobre ellos.

| # | Documento decía | Realidad verificada | Impacto en el plan |
|---|---|---|---|
| 1 | El panel admin no puede editar `puntos_por_calificacion` ni `costo_pista_puntos` (03, M6) | `EconomyConfigUpdateRequest` **sí** los acepta ([economy/schemas.py:91-104](../../app/features/economy/schemas.py#L91)); el admin los envía | No hay que agregar esa capacidad; sí validar claves/valores |
| 2 | No hay calificación por tiempo (03, §6.2) | Está implementada para sudoku, crucigrama y sopa ([user_attempts/service.py:51-71](../../app/features/user_attempts/service.py#L51)) | El problema no es que falte, sino que el tiempo es del cliente |
| 3 | Wordle y Sudoku consumen `/api/challenges` | No lo hacen: reciben el challenge por `location.state` desde el calendario; el calendario usa `/today` y `/month` | Los cambios de payload afectan al calendario, no a la pantalla del juego |
| 4 | `puntos_por_juego` contradice a la acreditación y el frontend muestra 50-80 | El frontend lo carga en el store, pero `getPuntosParaJuego` no tiene llamadores | Se puede deprecar sin cambiar UI; mantener la clave en la respuesta por compatibilidad |
| 5 | V2 no es operable y el frontend no está preparado | El frontend ejecuta grafos (`avanzar-nodo`, `es_final`, `opciones`) | La brecha es backend/contenido; conviene un spike de readiness antes de decidir |
| 6 | Las vidas globales son ornamentales | Hay además 4 vidas locales por partida; la recarga paga 50 pts vía endpoint admin y falla con 403 | Bug P0 de producto, no solo de seguridad |
| 7 | Los puntos del cliente y del servidor pueden divergir | El frontend suma `score` local y **no lee** `puntos_ganados`/`puntos_totales_usuario` ([attemptsService.ts:371-401](../../../../frontend/src/VISTAS/JUEGOS/attemptsService.ts#L371)) | El saldo mostrado puede diferir del de la DB; el servidor debe devolver el saldo autoritativo y el frontend migrar |
| 8 | Crucigrama fácil/difícil comparten intento | El frontend **sí** manda `game_data.difficulty` en el final ([CrucigramaGame.tsx:405-414](../../../../frontend/src/VISTAS/JUEGOS/CRUCIGRAMA/CrucigramaGame.tsx#L405)) | Se puede separar la acreditación sin tocar el contrato de attempts |
| 9 | El frontend manda `user_id` y usa el token | En clásicos manda `user_id` y Bearer, y **no llama** al backend si no hay cuenta ([attemptsService.ts:255-258](../../../../frontend/src/VISTAS/JUEGOS/attemptsService.ts#L255)); en narrativo manda solo Bearer y cae en invitado 0 | Se puede exigir token en attempts sin romper invitados; el narrativo necesita `guest_id` aparte |
| 10 | `use-hint` no distingue dificultad | El frontend no manda `difficulty`, pero hay un intento con `game_data.difficulty` en curso | Se puede inferir en el servidor antes de exigir el campo |

---

## 3. Principios de diseño

1. **Aditivo primero.** Todo lo nuevo entra como campo opcional, endpoint nuevo o flag. No se renombra ni se borra nada existente.
2. **Dos velocidades.** Un cambio que solo afecta caminos de exploit puede ir directo; un cambio que afecta el camino feliz va detrás de flag y se activa por juego.
3. **El servidor es la verdad de los puntos, no de la UI.** El cliente puede seguir calculando para feedback inmediato; el servidor recalcula y devuelve el saldo autoritativo.
4. **Idempotencia por clave de negocio.** Una acreditación por `(user_id, game_id, date, difficulty)`; reintentos y carreras no duplican.
5. **Ledger antes que saldo.** El saldo es una caché; el ledger es la fuente de verdad auditable.
6. **Validar con el payload actual.** El frontend ya manda suficiente información para validar el estado final; no hace falta esperar una migración para empezar.
7. **Sanitizar después de validar.** Quitar la solución de los GET es el último paso del anti-cheat, no el primero, porque hoy el cliente la necesita.
8. **V1 sigue operativo.** V2 se enciende por flag cuando pase la prueba de 12 meses; V1 no se apaga.
9. **Tests de contrato antes de tocar routers.** Si el snapshot de OpenAPI cambia, es una decisión, no un accidente.
10. **No big-bang.** Primero integridad y guardas; después estructura.

---

## 4. Decisiones necesarias

| # | Decisión | Recomendación | Alternativa | Bloquea |
|---|---|---|---|---|
| D1 | **Vidas** | **Confirmado:** mantener las 4 vidas por partida en el cliente y agregar `POST /api/economy/refill-lives` para que la recarga funcione. El servidor fija precio (50 pts) y beneficio; el cliente **no** manda cantidad ni costo. `buy-lives` conserva solo `package_id`; la vía directa `vidas` se deprecia/ignora y se aplica `vidas_maximas`. Con vidas locales, el backend protege los puntos, no el contador local. | Mover las vidas al servidor por `(user, game, date)` si se necesita integridad del contador. | Fase 1 (recarga) y Fase 3 (estado) |
| D2 | **Replay y acreditación** | **Confirmado:** no se permite replay. Una acreditación por slot `(user, game, date, difficulty)`. Si el intento ya está `completed/won`, rechazar o ignorar la transición a `in_progress/failed` (respuesta idempotente, `puntos_ganados: 0`) y auditar el intento. | Acreditar solo la diferencia hasta el mejor resultado (requiere `best_score` y ledger por delta). | Fase 1 (ledger) |
| D3 | **Crucigrama fácil/difícil** | **Confirmado:** dos slots y dos acreditaciones. Mantener un documento diario como resumen y guardar `by_difficulty`; el ledger usa la dificultad. | Dos documentos separados y cambiar el GET/índice único. | Fase 1 (modelo de intento) |
| D4 | **Narrativo y puntos** | **Confirmado:** acredita al finalizar, mapeando rango S/A/B/C/F a `puntos_por_calificacion`, con el mismo ledger idempotente. **Incluye invitados**: para una cuenta se acredita en el servidor; para un invitado, el servidor calcula y devuelve `puntos_ganados` y el cliente lo suma en `localStorage` (sin saldo server-side). Una sola acreditación por partida; `reiniciar` no vuelve a acreditar la misma. | Dejarlo fuera de la economía y documentarlo (descartado). | Fase 3 |
| D5 | **Validación server-side** | Empezar por Wordle con el payload actual; seguir Sopa, Sudoku y Crucigrama. Flags `GRADING_ENFORCE_<JUEGO>`. | Exigir un endpoint de submission nuevo desde el día uno. | Fase 2 |
| D6 | **Puntos de invitado e identidad** | **Confirmado:** los puntos de invitado viven **solo en `localStorage`**. Al **crear** la cuenta se vuelcan una vez al servidor; si el usuario **inicia sesión con otra cuenta**, el saldo del servidor pisa el local. El invitado no necesita `guest_id` para los puntos, pero sí para aislar la run narrativa (`run_0_<fecha>` compartida hoy). | Perfil server-side por `guest_id` (descartado por ahora). | Fase 3 |
| D7 | **Desbloqueo histórico** | No enforce en los GET públicos (rompería el contrato). Agregar endpoint autenticado de jugador que valide Premium/desbloqueo y migrar el calendario después. | Enforce ya en los GET. | Fase 2/3 |
| D8 | **Seeds** | `$setOnInsert` + opt-in por entorno. El seed V1 no toca `motor`. | Mantener seeds destructivos. | Fase 3 |
| D9 | **Zona horaria** | Fijar `America/Argentina/Buenos_Aires` para el día de juego; `updated_at` sigue en UTC. | Recibir la fecha del cliente con validación. | Fase 0/4 |
| D10 | **Tiempo de juego** | Medir el tiempo en el servidor: `started_at` en el primer `in_progress`, elapsed al final. Ignorar el tiempo del cliente o usarlo solo como sanidad. | Seguir confiando en `time_taken_seconds`. | Fase 2 |

> D1-D4 y D6 están confirmadas. D5 y D7-D10 se resuelven durante Fase 0/2.

> **Nota D6 (riesgo asumido):** si el frontend sube el saldo de `localStorage` al crear la cuenta, el cliente puede inflarlo. Mitigación mínima: tope de migración y asiento de auditoría con `motivo: guest_migration`. **Tope propuesto: 1.000 pts**, configurable (`guest_migration_max_points`); el asiento guarda `solicitado`, `aplicado` y `tope`. Si se quiere integridad real, el invitado necesitaría identidad y economía server-side, que es justo lo que se descartó.

---

## 5. Fases

### Fase 0 — Verdad y red de seguridad (1-2 semanas)

Objetivo: que el refactor no sea a ciegas y que la documentación no mienta.

0. **Aislar el entorno de trabajo.** Crear la rama de trabajo y el worktree estable antes de tocar código (Anexo E). No trabajar ni pushear directo a `main`.
1. **Mapa de contrato del frontend.** Anexo A de este documento + script de verificación que busque llamadas a `/api/` en `src/` y `admin_src/`.
2. **Snapshot de OpenAPI.** `tests/contract/snapshots/openapi.json` + test que compare `app.openapi()`.
3. **Matriz de auth por ruta.** Test que recorra el router y verifique qué endpoints son públicos, de usuario y de admin; documenta las excepciones actuales.
4. **`tests/conftest.py` + `pytest.ini`.**
   - Marcadores `unit`, `contract`, `integration`, `live`.
   - `testpaths = tests`.
   - `addopts = -m "not integration and not live"`.
   - Base `mayores_actualizaciones_test`, nunca `mayores_actualizaciones`.
   - Fixtures: `app`, `client`, `test_db`, `admin_override`, `freeze_today`, `seeded_challenge`, `cleanup`.
5. **Tests de caracterización** de desafíos, attempts, economía, narrativo y admin. Congelan los bugs actuales (POST público, solución expuesta, replay, IDOR) para que los fixes sean deliberados.
6. **`requirements-dev.txt`** con pytest y plugins; ejecución local (`pytest -m "not integration and not live"`). Sin cambios de CI/pipeline en esta etapa.
7. **Corregir los documentos 01-04** con los hallazgos de la sección 2.
8. **TZ de test** fija en ART.

**Criterio de aceptación:** los tests pasan contra el código actual sin modificarlo; el snapshot de OpenAPI refleja los routers reales; ningún test toca la base real.

### Fase 0.5 — Arquitectura objetivo y orden estructural (1 semana)

Objetivo: que el backend deje de ser una caja negra y que las fases siguientes muevan lógica a un lugar predecible, sin big-bang.

**Estructura objetivo (strangler, no reescritura):**

```text
app/
  core/                 # config, db, auth, errores, reloj
  shared/               # ledger, idempotencia, paginación, resultados
  features/
    <feature>/
      router.py         # HTTP: valida y delega; sin reglas de negocio
      schemas.py        # Pydantic
      service.py        # casos de uso
      repository.py     # acceso a Mongo (solo donde aporte)
      validation/       # reglas puras, testeables sin DB
```

**Reglas de dependencia:**

1. `router → service → repository`. El router no toca Mongo ni calcula grados.
2. Nada de imports directos entre features; lo compartido va a `app/shared/` o a una interfaz explícita.
3. Los validadores son funciones puras `(submission, config) → resultado`; no leen DB.
4. Un solo módulo decide “hoy” (`app/shared/clock.py`, TZ `America/Argentina/Buenos_Aires`); el resto lo recibe.
5. Los errores de dominio se definen en `app/shared/errors.py` y se traducen a HTTP en el router.
6. Cada extracción conserva el contrato y se hace con los tests de Fase 0 ya verdes.

**Mapa de destino inicial (solo lo que tocan las fases 1-3):**

| Hoy | Destino | Fase |
|---|---|---|
| `user_attempts/service.py` (grade + persistencia + acreditación) | `service.py` (caso de uso) + `validation/` (grados) + ledger en `shared/` | 1-2 |
| `economy/service.py` (config, vidas, pistas, unlock, admin) | `economy/points.py`, `economy/lives.py`, `economy/hints.py`, `economy/admin.py` | 1 |
| `narrative/game/*` (V1 y V2 mezclados) | `narrative/motor_v1/`, `narrative/motor_v2/`, `narrative/validation/` | 3 |
| `daily_challenges/service.py` (generación + persistencia + serialización) | separar por juego y por responsabilidad | 4 |

**Entregables:**

1. ADR corto con la estructura, las reglas de dependencia y el criterio de extracción.
2. `app/shared/clock.py`, `app/shared/errors.py` y la interfaz de ledger (sin implementación todavía).
3. Test o regla de lint que detecte imports `feature → feature`.
4. Tabla de módulos actuales → destino, actualizada a medida que se extrae.

**Estado al 2/11/2026:** ADR en [adr/0001-arquitectura-objetivo.md](adr/0001-arquitectura-objetivo.md); `app/shared/clock.py`, `app/shared/errors.py` y `app/shared/ledger.py` creados (ledger sin implementación); ratchet de imports en `tests/unit/test_architecture_imports.py` con las 6 violaciones actuales en baseline. `tzdata` agregado a `requirements.txt` para que `zoneinfo` funcione en Windows.

**Criterio de aceptación:** el diseño permite implementar ledger, idempotencia y validadores sin duplicar lógica ni tocar routers; ninguna extracción se hace sin tests de contrato verdes; no se mueve un módulo que la fase no necesita.

### Fase 1 — Integridad de economía e intentos (2-3 semanas)

Objetivo: que el servidor no pueda ser convencido de acreditar puntos falsos por replay, carrera o `user_id` ajeno. Sin cambiar el contrato del camino feliz.

1. **Identidad.**
   - **Verificado:** el frontend **no llama** a `POST /api/games/attempts` si no hay cuenta: `getCurrentUserId()` devuelve `null` y la función retorna antes ([attemptsService.ts:255-258](../../../../frontend/src/VISTAS/JUEGOS/attemptsService.ts#L255)). Cerrar el camino sin token no rompe invitados.
   - `POST /api/games/attempts`: con token, el `user_id` del body se ignora y gana el del token. Sin token, responder 401/403 y no escribir nada; eliminar el fallback `req.user_id or 1`.
   - `GET /api/games/attempts*`: con token, ignorar `user_id` de query. Sin token, 401/403.
   - Esto elimina el IDOR de lectura/escritura y la acreditación a un usuario arbitrario sin autenticación.
   - Tests de IDOR, invitado sin token y token válido.

2. **Modelo de intento con dificultad (D3).**
   - Derivar `difficulty = req.difficulty or game_data.difficulty or "standard"`.
   - Mantener la clave única `(user_id, game_id, date)` para no romper GET ni calendario.
   - Agregar `by_difficulty: {facil: {...}, dificil: {...}}` al documento; el nivel superior refleja el último/mejor.
   - El ledger usa `(user_id, game_id, date, difficulty)` para la acreditación.
   - Backfill: `game_data.difficulty` donde exista; `standard` en el resto. Las colisiones históricas de Crucigrama no son recuperables; documentarlo.

3. **Sin replay (D2).**
   - Si el intento existente está `completed/won`, un POST posterior con `in_progress`, `failed` o `completed` **no** cambia el estado, no recalcula grado y no acredita.
   - Respuesta idempotente con el documento vigente y `puntos_ganados: 0`; registrar el evento en el ledger/auditoría como `replay_rejected`.
   - Esto cubre el replay que hoy permite `completed → failed/in_progress → completed`; no depende de que el frontend lo bloquee.
   - Para el narrativo, `reiniciar` no vuelve a acreditar la misma partida; si se permite una nueva partida, define una clave de acreditación distinta (a confirmar en Fase 3).

4. **Ledger e idempotencia (D2).**
   - Colección `economy_ledger` con `idempotency_key` único.
   - Clave por acreditación: `attempt:{user_id}:{game_id}:{date}:{difficulty}`.
   - Flujo: insertar asiento `pending` → `$inc usuarios.puntos` → marcar `applied` con `saldo_despues`.
   - Si el asiento ya existe, no se acredita; `puntos_ganados = 0` y `puntos_totales_usuario` se lee de la DB.
   - Reconciliador de asientos `pending` al arrancar y periódico.
   - `puntos_ganados` mantiene su significado: delta de esa request.

5. **Bugs de calificación.**
   - Quitar `remaining_attempts == 0` como condición de `S`.
   - Validar `game_data.errors` numérico; devolver 422/400 en vez de 500.
   - Acotar `attempts`, `remaining_attempts`, `score`, `stars` (`ge=0`, topes).
   - No confiar en `stars`/`score` del cliente cuando el flag de validación del juego esté activo.

6. **Pistas.**
   - Resolver contenido **antes** de cobrar.
   - Si no hay contenido: 200 con `success: true`, `puntos_descontados: 0`, `pista: null` (mantiene la forma).
   - Idempotencia por `(user_id, game_id, date, difficulty, hint_key)`; segunda llamada devuelve lo mismo sin cobrar.
   - `difficulty` opcional en el request; si falta, inferirla del intento del usuario para esa fecha.
   - Tests: éxito, sin saldo, sin contenido, repetida, dificultad.

7. **Recarga de vidas (D1).**
   - Nuevo `POST /api/economy/refill-lives`: sin body de cantidad. El servidor fija precio (50 pts) y beneficio (señal de recarga); descuenta con guarda atómica `puntos >= 50` y devuelve `{success, puntos, message}`. Como las vidas son locales, no devuelve un contador de vidas de partida que el servidor no posee; el cliente resetea sus 4 vidas al confirmar.
   - Si el cliente manda `cantidad`, `vidas` o `costo`, se ignoran. El precio y el beneficio son del servidor.
   - Mantener `/api/admin/economy/user/adjust` intacto.
   - `buy_lives`: mantener `package_id` (el servidor define vidas y precio). Depreciar/ignorar la vía directa `req.vidas` y aplicar `vidas_maximas` al resultado (hoy no se aplica).
   - Límite explícito: con vidas locales, el backend protege los puntos, no el contador local. Si se necesita integridad del contador, hay que mover las vidas al servidor (decisión posterior).
   - El frontend queda pendiente de apuntar a este endpoint; hasta entonces la recarga de partida sigue fallando con 403, aunque la compra por paquete en la mini-tienda sí funciona.

8. **Admin adjust atómico + auditoría.**
   - Un solo `find_one_and_update` con guarda; evitar el segundo update de clampeo.
   - Registrar el ajuste en el ledger con `actor=admin`.

9. **Guardas narrativas P0** (se pueden adelantar si la prioridad es narrativo):
   - `iniciar-evento-grafo` / `iniciar-conversacion-grafo`: exigir `run.motor == "v2"`, `status == "in_progress"`, fase permitida y sin `grafo_activo`; si no, 409.
   - `avanzar-nodo`: exigir `run.motor == "v2"`, `grafo_activo` existente y nodo actual correcto.
   - Endpoints V1: exigir `run.motor == "v1"`.
   - Limpiar `grafo_activo` y punteros al terminar; persistir opción/resultado.
   - Tests de salto de fase, reroll, partida finalizada y doble avance.

**Criterio de aceptación:** replay y doble POST concurrente producen una sola acreditación; un intento `completed` no vuelve a `in_progress/failed`; fácil y difícil acreditan una vez cada uno; una pista sin contenido no cobra; la recarga no acepta cantidades del cliente; un jugador no puede leer ni escribir intentos de otro; los endpoints manuales rechazan fases inválidas con 409.

**Estado al 2/11/2026:** Fase 1 completa. Ledger idempotente con reconciliador, identidad por token en intentos, dificultad con `by_difficulty`, rechazo de replay con auditoría, pistas idempotentes y cobro posterior a la resolución, `refill-lives` de precio fijo del servidor, admin adjust atómico con actor, backfill de dificultad en dev y guardas narrativas P0 (409 por motor/fase/grafo inválido, persistencia de opción y resultado). Suite: 78 passed, 18 integration/live deseleccionados.

### Fase 2 — Validación server-side con el payload actual (2-3 semanas)

Objetivo: que el servidor recalcule grado/score a partir de la submission, sin exigir un contrato nuevo.

1. **Validadores por juego** (`app/features/user_attempts/validation/`):
   - **Wordle:** `word` debe ser la solución; `guesses` define `attempts` y la victoria; recalcular estado.
   - **Sopa:** `guesses` debe ser subconjunto de `config.words`; `completed` solo si están todas; `errors` se acepta como métrica secundaria.
   - **Sudoku:** `game_data.cells` debe coincidir con `config.solution`; `completed` solo si no hay ceros.
   - **Crucigrama:** `game_data.userGrid` contra `config.cells[].letter`; `guesses` contra `config.words`; dificultad desde `game_data.difficulty`.
   - Cada validador devuelve `{valid, reason, attempts, errors, completed}`.

2. **Integración en `save_user_attempt`.**
   - Si `status == completed` y el flag del juego está activo, validar; si no valida, guardar `validation_status: "rejected"` y acreditar 0, con respuesta 200 y `puntos_ganados: 0` (no romper el cliente).
   - Si valida, el servidor manda sobre `grade/score/stars/attempts`; el cliente solo aporta la submission.
   - Flags por juego: `GRADING_ENFORCE_WORDLE`, `..._SOPA`, `..._SUDOKU`, `..._CRUCIGRAMA`, default `false` hasta pasar tests y una ventana de observación.

3. **Tiempo server-side (D10).**
   - En el primer guardado `in_progress`, setear `started_at` si no existe.
   - En el final, calcular elapsed = `now - started_at`; si el cliente manda un tiempo mucho menor, usar el del servidor o marcar `time_suspect`.
   - No rompe la respuesta; cambia el grado solo cuando el flag esté activo.

4. **Feedback inmediato (opcional, nueva ruta).**
   - `POST /api/games/validate` con `{game_id, date, difficulty, submission}` → feedback sanitizado (colores de Wordle, conflictos de Sudoku, palabras encontradas, letras correctas).
   - Es aditivo; el frontend puede migrar juego por juego.

5. **Desafío sanitizado (después del feedback).**
   - Nueva ruta o query param `GET /api/challenges/.../jugador` que omite `solution`, `cells[].letter`, `words[].word`, `boards` y `grid` según el juego.
   - El default actual se mantiene hasta que el frontend migre. Recién ahí se puede cerrar la fuga.
   - Hasta ese momento, documentar que el anti-cheat no está cerrado aunque la forgery de grados sí.

6. **Migración del frontend (backlog, no se implementa acá).**
   - Usar `puntos_totales_usuario`.
   - Llamar `validate` para feedback.
   - Consumir el desafío sanitizado.
   - Enviar `difficulty` explícita.

**Criterio de aceptación:** un cliente que manda `grade: "S"` sin submission válida recibe 0 puntos con el flag activo; un cliente legítimo sigue jugando igual; el OpenAPI solo cambia por campos opcionales y rutas nuevas.

**Estado al 2/11/2026:** Fase 2 completa en su núcleo. Validadores por juego en `app/features/user_attempts/validation/` (Wordle, Sopa, Sudoku y Crucigrama), con lookup de desafío exacto por dificultad para Crucigrama y fallback histórico para el resto; un desafío inexistente se rechaza con flag activo (`desafio_no_encontrado`) para no abrir una vía de forgery. Flags `GRADING_ENFORCE_*` en `app/core/config.py`, default `false`. `save_user_attempt` valida solo finales completados con flag activo: el rechazo se persiste como `validation_status: "rejected"` con F/0/0, HTTP 200 y `puntos_ganados: 0`, sin asiento en el ledger y habilitando un reintento legítimo; una submission válida deja grade/score/stars/attempts en manos del servidor. D10: `started_at` en el primer `in_progress`, `server_elapsed_seconds` y `time_suspect` en el final; el grado usa el tiempo del servidor solo con flag activo. Sin cambios de schema ni de OpenAPI (snapshot intacto). Pendiente explícito para una pasada posterior: ruta opcional de feedback (`POST /api/games/validate`) y desafío sanitizado (ítems 4 y 5). Suite: 101 passed, 18 integration/live deseleccionados.

### Fase 3 — Narrativo operativo y readiness V2 (2-3 semanas)

Objetivo: que V1 sea seguro y que V2 tenga una prueba objetiva de que puede ser oficial.

1. **Seed y motor (D8).**
   - V1: `$setOnInsert` para el universo; no reescribir `motor`.
   - V2: seed idempotente (`$setOnInsert` por `_id`) y opt-in (`SEED_NARRATIVE_V2=true`).
   - No sembrar V2 por defecto hasta que pase el dry-run.

2. **Índices V2** para `universo_id` en eventos, conversaciones y especiales.

3. **Validador de grafos** (`app/features/narrative/validation/graph_validator.py`):
   - `nodo_raiz` existe; `nodos` claves coinciden con `id`.
   - Todos los `siguiente_nodo` y `desenlaces[].nodo` existen.
   - Nodos no finales con opciones; finales sin opciones.
   - Al menos un terminal alcanzable; sin ciclos; pesos > 0 y suma > 0.
   - Raíz no final (o impactos de raíz manejados).
   - Nuevo endpoint admin `POST /api/narrative/admin/v2/validar` (ruta nueva, no rompe nada).
   - Etapa posterior: rechazar create/update inválidos con 409, coordinado con la SPA admin.

4. **Historial V2.** Persistir `opcion_elegida_id`, `resultado_obtenido_id` y desenlace; agregarlos como campos opcionales en los DTO de modales.

5. **Readiness V2 (dry-run).**
   - Script `scripts/v2_readiness.py` (no test): crea una run en `mayores_actualizaciones_test`, juega 12 meses eligiendo opciones válidas, registra eventos usados, errores 500, soft-locks y nodos sin salida.
   - Criterio: 12 meses completos, 0 errores, sin repetir eventos (o con reciclaje explícito), y el frontend actual puede renderizar cada estado.
   - Si falla por contenido: autorar eventos faltantes o implementar reciclaje controlado (decisión de producto).
   - Si pasa: V2 puede activarse por flag (`NARRATIVE_MOTOR_DEFAULT=v2` o por universo).

6. **Concurrencia.** Bloqueo optimista con `version` en `narrative_runs`: `find_one_and_update` con filtro de versión; si no coincide, 409 y reintento del cliente. Los documentos viejos sin `version` se tratan como versión 0.

7. **Economía narrativa (D4).** Al finalizar, mapear rango → grado → puntos y acreditar por el ledger. `reiniciar` no borra el intento ni vuelve a acreditar la misma partida; la clave es `(identidad, narrativo, date, normal)`. **Los invitados también acreditan**: la acreditación no depende de tener cuenta. Para el invitado, la identidad es `guest_id`, no `user_id = 0`.

8. **Invitados y puntos (D6).**
   - **Puntos:** solo en `localStorage`. Para una partida de invitado, el servidor calcula y devuelve `puntos_ganados`; el cliente lo suma localmente. No se acredita a `user_id = 0`.
   - **Crear cuenta:** volcado único del saldo local al servidor mediante un endpoint de reclamo (ruta nueva, p. ej. `POST /api/economy/guest-migration`), con tope configurable (`guest_migration_max_points`, propuesto 1.000) y asiento de auditoría (`guest_migration`) que registre `solicitado`, `aplicado` y `tope`; luego se limpia la clave local. Idempotente por cuenta.
   - **Iniciar sesión con otra cuenta:** el saldo del servidor pisa el local. No hay fusión bidireccional.
   - **Run narrativa:** hoy todos los invitados comparten `run_0_<fecha>` ([identity.py:67](../../app/features/narrative/game/identity.py#L67)). Agregar `guest_id` por dispositivo (header o body opcional) para aislar la partida; si no llega, fallback al comportamiento actual.
   - **Riesgo asumido:** el saldo de `localStorage` es manipulable por el cliente; el tope de migración es la única defensa. Documentarlo.

**Criterio de aceptación:** el dry-run de 12 meses pasa; los endpoints manuales no permiten saltar fases; el seed no pisa ediciones; V2 se puede activar y desactivar sin migración de datos; una partida narrativa acredita puntos una sola vez, también para invitados con `guest_id`.

**Estado al 2/11/2026:** Fase 3 implementada. El seed es idempotente (`$setOnInsert` por `_id`) y no pisa ediciones del admin ni el flag `motor`; V2 se siembra solo con `SEED_NARRATIVE_V2=true`. Índices V2 por `universo_id` y compuesto `(universo_id, personaje_id, direccion)` para eventos especiales. Validador de grafos en `app/features/narrative/validation/graph_validator.py` (raíz, referencias, terminales alcanzables, ciclos, pesos) expuesto por `POST /api/narrative/admin/v2/validar`, con validación inline y de grafos almacenados; el rechazo 409 en create/update queda para cuando la SPA admin consuma el validador. Historial V2 persistido (`opcion_elegida_id`, `resultado_obtenido_id`, desenlace) y concurrencia optimista por `version` con 409 en escritura obsoleta (documentos sin `version` se tratan como 0). Economía narrativa D4/D6: los cuatro DTO de V2 devuelven `puntos_ganados`; la cuenta acredita una sola vez por ledger y el invitado recibe sus puntos sin escribir `usuarios`/`user_attempts`; la identidad de invitado es un `user_id` interno negativo estable derivado de `X-Guest-Id`, lo que aísla partidas sin romper los índices únicos existentes; `POST /api/economy/guest-migration` vuelca el saldo local una sola vez por cuenta, con tope configurable (`guest_migration_max_points`, default 1.000) y asiento de auditoría `guest_migration`. Readiness: `scripts/v2_readiness.py` juega 12 meses contra `mayores_actualizaciones_test`; con los 7 eventos sembrados el dry-run falla por soft-lock en el mes 8, y con reciclaje explícito (`--reciclar`, o `reciclaje_eventos_v2` por universo, default `false`) completa 12/12 meses con 0 errores, 0 soft-locks, 1 reciclaje y 5 eventos repetidos. Por eso V2 no puede declararse oficial todavía: requiere autorar más eventos o habilitar el reciclaje por universo (Fase 5). Snapshot OpenAPI regenerado por rutas y campos opcionales nuevos; la migración del frontend a esos campos sigue en backlog (Anexo F). Suite: 156 passed, 18 integration/live deseleccionados.

### Fase 4 — Estructura y operación (continuo)

1. Extraer `daily_challenges/service.py` por juego; separar generación, persistencia y serialización.
2. Extraer `economy/service.py` en `config`, `points`, `lives`, `hints`, `unlock`, `admin`.
3. Separar narrativo V1/V2 en módulos internos (`motor_v1`, `motor_v2`).
4. Eliminar el acoplamiento `daily_challenges → crucigrama_admin` con una interfaz de plantillas.
5. Generación pesada en `asyncio.to_thread`.
6. `force=False` por defecto; bloquear regeneración con intentos.
7. Seeds opt-in; nunca pisar datos editados.
8. Rate limiting en economía, attempts, pistas y narrativo.
9. Limpiar código muerto: `puntos_por_juego`, `get_points_for_game`, `get_points_for_grade`, `vidas_maximas` sin uso, `attempt_budgets`, duplicación de Sopa.
10. Actualizar documentación y borrar docs obsoletas.

**Estado al 3/11/2026:** Fase 4 implementada en su núcleo estructural y operativo. `daily_challenges/service.py` queda como fachada de serialización/persistencia y los generadores viven en `games/` (`wordle`, `sopa`, `sudoku`, `crucigrama`, `coverage`, `common`), con la generación CPU-bound y la resolución de plantillas en `asyncio.to_thread`; el acoplamiento con `crucigrama_admin` se cortó mediante `crucigrama/published_templates.py`. `economy/service.py` se dividió en `config`, `lives`, `points`, `hints`, `unlock` y `admin`, conservando la fachada de imports. El narrativo se separó en `game/motor_v1/` (setup legacy y modales) y `game/motor_v2/` (setup, ciclo mensual, transiciones, desenlaces, estado reactivo y motor de grafos), con `identity`, `run_repository` y `universe_resources` como piezas compartidas; los routers y sus paths no cambiaron. Operación: `force=false` por defecto y regeneración bloqueada con 409 si el mes tiene intentos; seeds no destructivos y seeds estáticos opt-in (`SEED_STATIC_CHALLENGES=false`); rate limiting en economía, intentos y narrativo (ventana deslizante en memoria, límites configurables por minuto) y se conservó el límite anti-fuerza bruta del login con bypass de admin. El único cambio de contrato OpenAPI es el default/descripción de `force` en `POST /api/challenges/admin/generate-month`; snapshot regenerado. Suite: 169 passed, 18 integration/live deseleccionados. Queda como deuda menor revisar las referencias históricas de los documentos de relevamiento (01–04) que describen el layout previo.

### Fase 5 — V2 oficial (gated)

Solo después de Fase 3 y con el dry-run verde:

1. Activar V2 por universo o globalmente por flag.
2. Mantener V1 disponible para rollback.
3. Monitorear: errores 500, soft-locks, runs atascadas, eventos agotados.
4. Recién entonces actualizar la documentación que declara V2 oficial.

**Estado al 3/11/2026 (preparación de truncado, Opción A).** Se separaron los motores sin mover URLs ni cambiar el contrato del camino feliz. El ciclo común (`iniciar`, `elegir-carta-mes`, `avanzar-mes`, `estado`) y las lecturas compartidas (`setup`, `historial`, `inventario`, `corte`, `finalizacion`) viven en `game/` (`setup_service`, `turn_service`, `transition_service`, `modals_service`, `turn_state`, `endings_service`); los grafos quedan en `game/motor_v2/` (`graph_engine`, `v2_graph_service`, rama V2 de `elegir-carta-mes`) y la resolución plana en `game/motor_v1/turn_service.py`, con sus consultas atómicas en `game/motor_v1/modals.py`. Se agregó el discriminador aditivo `motor` a `elegir-carta-mes` y `estado` (además del ya existente en `iniciar`), y se marcaron `deprecated` en OpenAPI `decidir-evento`, `responder-conversacion`, `evento-actual`, `conversacion-actual`, `resultado-actual` y `draft-actual`, con aviso de log en runtime. La matriz motor×endpoint queda cubierta por `tests/contract/test_narrative_motor_matrix.py`: V1 resuelve todo el ciclo plano; V2 arranca grafos, resuelve con `avanzar-nodo` y recibe 409 en las rutas planas. **El frontend no necesita cambiar URLs**: migra por universo cuando el autor decida `motor="v2"`; recién entonces se pueden retirar los endpoints planos y el código de `motor_v1`. Snapshot OpenAPI regenerado (campo `motor` + `deprecated`). Suite: 172 passed, 18 integration/live deseleccionados.

**Panel de administración (3/11/2026).** El panel vuelve a servirse desde el backend en `/admin`: `SPAStaticFiles` monta `app/static/admin` (build de `frontend/admin_src`, base `/admin/`) y cae a `index.html` solo para rutas del cliente; un asset faltante responde 404 en lugar de devolver HTML. La entrada `/admin` sirve el index directamente para que el `?ticket=` del SSO llegue intacto al canje por el BFF (`/api/auth/sso/canjear-ticket`). Sin build disponible se conserva el redirect al Autenticador. Tests: `tests/test_admin_static_serving.py` (entrada con query, deep link, assets, 404 de asset faltante y `test-narrativo.html`). Suite: 177 passed, 18 integration/live deseleccionados.

**Pendiente de la línea panel admin.** Reestructurar el shell (`PanelAltasSistemas`, navegación y capa común de API/auth) y partirlo en rutas; el visor narrativo de grafos (`NarrativeAdminModal`, `GrafosV2Tab`, `DiagramaNodosV2`) se preserva y solo recibe fixes verificados. `PanelJuegosAdmin`, `ModalNarrativoV2` y `ModalDesafios` no están importados (código muerto) a la espera de decisión. El build se emite en `app/static/admin` (versionado): correr `npm run build:admin` antes de desplegar y preservar `test-narrativo.html`, que `--emptyOutDir` elimina.

---

## 6. Primer sprint recomendado (Fase 0 + arranque de Fase 1)

| # | Tarea | Entregable | Criterio |
|---|---|---|---|
| 1 | Congelar contrato | Snapshot OpenAPI + matriz de auth | Pasa contra el código actual |
| 2 | Infra de tests | `conftest.py`, `pytest.ini`, `mayores_actualizaciones_test`, `requirements-dev.txt` | `pytest -m unit` corre sin servicios |
| 3 | Caracterización | Tests de desafíos, attempts, economía, narrativo | Documentan los bugs actuales |
| 4 | Aislamiento de tests | `conftest.py` fuerza `mayores_actualizaciones_test` | Los tests no tocan la base compartida |
| 5 | Ledger + sin replay | `economy_ledger` + clave idempotente + rechazo de `completed → in_progress/failed` | Una sola acreditación por slot; el replay no vuelve a acreditar |
| 6 | Dificultad | `by_difficulty` + derivación desde `game_data.difficulty` | Fácil y difícil acreditan una vez cada uno |
| 7 | Identidad | Token manda en attempts; sin token, 401/403 | Tests de IDOR, invitado sin token y token válido |
| 8 | Grade bugs | Sin `remaining_attempts == 0`; errores numéricos | Sin 500 por `game_data` inválido |
| 9 | Pistas | Cobro después de resolver + idempotencia | Pista inexistente no cobra |
| 10 | Recarga | `POST /api/economy/refill-lives` sin cantidad del cliente | Un jugador normal puede recargar; el precio/beneficio es del servidor |
| 11 | Guardas narrativas | 409 en fases inválidas y cross-engine | Reroll/revivir imposibles |
| 12 | Docs | Correcciones de la sección 2 | Los 4 documentos reflejan el código |

No incluye V2 oficial ni sanitización de desafíos: eso es Fase 2/3.

---

## 7. Reglas para tocar el contrato

1. **No cambiar paths, métodos, nombres de campos ni códigos del camino feliz.**
2. **Agregar campos opcionales** es aceptable; quitarlos o cambiar su significado, no.
3. **Los flags de comportamiento** (`GRADING_ENFORCE_*`, `NARRATIVE_MOTOR_DEFAULT`, `SEED_*`) permiten activar sin romper.
4. **Las rutas nuevas** son la vía para sanitizar, validar o simular; no se reemplazan las existentes de golpe.
5. **Los tests de caracterización se actualizan en un commit separado** del fix, con nota de cambio de contrato.
6. **La lógica nueva va en services**; el router valida y delega.
7. **La fecha y la zona horaria son parte del contrato:** no cambiar “hoy” sin tests de fechas y coordinación.

---

## 8. Tests locales

### 8.1 Unitarios puros
- `calculate_grade_and_score`: todos los juegos, estados, tiempo, `grade` del cliente, `game_data` inválido, `remaining_attempts`.
- Validadores de submission por juego.
- Derivación de dificultad.
- Ledger: clave única, replay, delta 0.
- Validador de grafos V2.
- `rule_engine` y `event_director`.

### 8.2 Integración con Mongo de test
- `save_user_attempt`: victoria nueva, repetida, replay, `completed → in_progress/failed`, dos concurrentes, `$inc` fallido, usuario inexistente.
- `use_hint`: éxito, sin saldo, sin contenido, repetida, dificultad.
- `unlock-day`: básico, premium, ya desbloqueado, carrera.
- `buy-lives`: paquete, saldo, tope.
- `refill-lives`: éxito, sin saldo, tope.
- `adjust_user_economy`: suma, resta, clamp, auditoría.
- Narrativo: guardas de fase, seed idempotente, dry-run corto, acreditación única al finalizar y acreditación de invitado con `guest_id`.

### 8.3 Contrato y caracterización
- OpenAPI snapshot.
- Matriz de auth.
- Respuestas de `/api/challenges/*`, `/api/games/attempts*`, `/api/economy/*`, narrativo y admin.
- Bugs actuales congelados antes de corregirlos.

### 8.4 Reglas
- Nunca usar `mayores_actualizaciones` (base estable) desde tests.
- Limpiar por prefijos/IDs de test, no por fechas globales.
- Limpieza en `finally` o fixture.
- Reloj congelado para fechas.
- `TZ=America/Argentina/Buenos_Aires` en la sesión de tests.
- `live` excluido por defecto; nunca contra producción.

### 8.5 Base local y pipeline

**Pipeline: fuera de alcance.** No se modifica `.github/workflows/deploy.yml` ni se agrega CI en esta etapa; el equipo no se ocupa del despliegue por ahora. Consecuencia asumida: un push a `main` sigue desplegando sin barrera de tests. Por eso no se trabaja directo sobre `main` (ver Anexo E).

**Base de tests.** No existe `tests/conftest.py`; los tests usan la DB configurada, que por defecto es `cognijuegos_db` ([app/core/config.py:21](../../app/core/config.py#L21)), aunque el `.env` local hoy apunta a `mayores_actualizaciones`. Varios tests borran datos con filtros fijos. Aun en local, eso puede pisar datos que otro agente o el usuario están usando. La Fase 0 crea `conftest.py` y fuerza `mayores_actualizaciones_test`; los tests se corren localmente antes de cada merge.

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Romper el frontend por cambiar un campo | Aditivo + snapshot + flags + relevamiento del Anexo A |
| Cambiar el puntaje que ve el usuario | Activar flags por juego después de tests; comunicar el cambio |
| Perder crédito si falla el `$inc` | Ledger `pending` + reconciliador |
| Migración de `difficulty` con datos viejos | `by_difficulty` sin cambiar la clave única; backfill documentado |
| V2 sin contenido suficiente | Dry-run de 12 meses como gate; reciclaje o más eventos |
| V2 rompe partidas existentes | Flag por universo; V1 sigue disponible; rollback |
| Cliente miente el tiempo | Elapsed server-side desde `started_at` |
| Puntos de invitado sin identidad | `guest_id` por dispositivo; si no llega, no acreditar a un `user_id = 0` compartido |
| Seeds pisan datos | `$setOnInsert` + opt-in |
| Sin transacciones multi-documento | Ledger/outbox; no prometer atomicidad que Mongo standalone no da |
| Docs desactualizadas | Fase 0 las corrige; una sola fuente de verdad |

---

## 10. Preguntas abiertas

**Confirmadas:** D1 (vidas locales + recarga por endpoint), D2 (sin replay, una acreditación por slot), D3 (fácil y difícil son dos slots), D4 (el narrativo acredita puntos, incluidos invitados), D6 (invitado en `localStorage`, volcado al crear cuenta, el saldo del servidor pisa al cambiar de cuenta).

**Abiertas:**

1. ¿La validación server-side empieza por Wordle o por el juego con más usuarios?
2. ¿El desbloqueo histórico se enforcea en el backend o alcanza con el calendario?
3. ¿V2 se activa por universo o globalmente cuando pase el dry-run?
4. ¿Quién autoría los eventos V2 faltantes si el dry-run falla por contenido?
5. ¿Te sirve un tope de 1.000 pts para el volcado de invitado, o preferís otro valor?

---

## Anexo A — Mapa de consumo del frontend

### Clásicos y economía

| Endpoint | Consumidor | Campos usados |
|---|---|---|
| `GET /api/challenges/today` | `calendarService.ts:48` | challenge completo, `config` |
| `GET /api/challenges/month` | `calendarService.ts:88` | challenge completo, `config` |
| `GET /api/challenges/range` | `calendarService.ts:77` | rango de fechas |
| `GET /api/challenges/date/{date}` | Sopa (`:147`, sin difficulty), Crucigrama (`:124`, con difficulty) | `config.theme`, `words`, `hints`, `grid`, `cells`, `words`, `grid_size` |
| `POST /api/games/attempts` | `attemptsService.ts:264-277` y `:386-401` | `user_id`, `game_id`, `date`, `mode`, `status`, `word`, `attempts`, `stars`, `score`, `grade`, `time_taken_seconds`, `guesses`, `game_data`, `remaining_attempts` |
| `GET /api/games/attempts/date/{date}` | `attemptsService.ts:193` | intento del día |
| `GET /api/games/attempts?year&month` | `calendarService.ts:105` | intentos del mes |
| `GET /api/economy/config` | `PlayerEconomyContext.tsx:111-122` | costos, paquetes, `puntos_por_juego`, `vidas_maximas` |
| `GET /api/economy/me` | `PlayerEconomyContext.tsx:132-140` | `vidas`, `puntos`, `suscripcion`, `dias_desbloqueados` |
| `POST /api/economy/buy-lives` | `PlayerEconomyContext.tsx:286` | `vidas`, `puntos`, `message` |
| `POST /api/economy/unlock-day` | `PlayerEconomyContext.tsx:358` | `puntos`, `message` |
| `POST /api/economy/use-hint` | `pistasService.ts:30` | `puntos_restantes`, `puntos_descontados`, `pista`, `valor_revelado` |
| `POST /api/admin/economy/user/adjust` | `PlayerEconomyContext.tsx:270` (recarga de vidas) | `puntos`; **hoy da 403 a jugadores** |

Validación local: Wordle contra `config.solution`; Sopa contra `grid`; Sudoku contra `config.solution`/`boards`; Crucigrama contra `cells[].letter`. El cliente calcula `score` y suma puntos localmente; no lee `puntos_ganados` ni `puntos_totales_usuario`.

El frontend **no** consume `POST /api/challenges` (el upsert público): los juegos reciben el desafío por `location.state` o por `GET /today`/`GET /date/{date}`. La SPA admin usa `/api/challenges/admin/*`.

Sin cuenta, el frontend **no llama** a `POST /api/games/attempts` ni a `GET /api/games/attempts*`: guarda el progreso en `localStorage`. Eso habilita exigir token en esas rutas sin romper el modo invitado.

### Narrativo

| Endpoint | Consumidor | Uso |
|---|---|---|
| `GET /api/narrative/partida/setup` | `narrativeService.ts:310` | setup y `tiene_partida_activa` |
| `POST /api/narrative/v2/partida/iniciar` | `:362` | 3 personajes + 3 cartas |
| `POST /api/narrative/v2/partida/elegir-carta-mes` | `:367` | draft |
| `POST /api/narrative/v2/partida/avanzar-nodo` | `:372` | grafo V2 |
| `POST /api/narrative/v2/partida/decidir-evento` | `:384` | V1 |
| `POST /api/narrative/v2/partida/responder-conversacion` | `:395` | V1 |
| `POST /api/narrative/v2/partida/avanzar-mes` | `:400` | transición |
| `GET /api/narrative/v2/partida/estado` | `:313,378` | F5 y estado |
| `GET /api/narrative/partida/historial` | `:316` | crónica |
| `GET /api/narrative/partida/corte` | `:351` | corte |
| `POST /api/narrative/partida/reiniciar` | `:357` | reset |
| `GET /api/narrative/admin/eventos` | `:57` | condiciones secretas; requiere admin y hoy falla para jugadores (se ignora) |

No usa `grafo-actual`, `iniciar-evento-grafo` ni `iniciar-conversacion-grafo`.

---

## Anexo B — Correcciones a los documentos 01-04

| Documento | Corrección |
|---|---|
| 01 | Wordle y Sudoku no llaman `/api/challenges` directamente; reciben el challenge por el calendario. |
| 01 | El frontend lee `config.solution` en Wordle y Sudoku, y `cells[].letter`/`words[].word` en Crucigrama: quitar esos campos hoy rompe los juegos. |
| 01 | El intento no tiene `difficulty`, pero el frontend manda `game_data.difficulty` en Crucigrama: hay una vía de compatibilidad. |
| 02 | El frontend ya consume el loop V2 (`avanzar-nodo`, `es_final`, `opciones`); la brecha es backend/contenido, no renderizado. |
| 02 | El frontend no usa los endpoints manuales de grafos; las guardas no rompen el camino feliz. |
| 03 | El admin sí puede editar `puntos_por_calificacion` y `costo_pista_puntos`. |
| 03 | Existe calificación por tiempo (`escalas_tiempo_por_juego`); el problema es que el tiempo es del cliente. |
| 03 | `puntos_por_juego` se carga en el store, pero no tiene consumidores: se puede deprecar sin cambiar UI. |
| 03 | La recarga de vidas de partida usa un endpoint admin y falla con 403; es un bug de producto. |
| 04 | Hay que agregar tests de economía, attempts, Wordle/Sopa/Sudoku y contrato; la suite actual no cubre nada de eso. |

---

## Anexo C — Diseño de idempotencia (pseudocódigo)

```python
async def credit_attempt_points(user_id, game_id, date, difficulty, grade, score):
    key = f"attempt:{user_id}:{game_id}:{date}:{difficulty}"
    now = datetime.now(timezone.utc)

    try:
        await ledger.insert_one({
            "_id": key,
            "user_id": user_id,
            "delta": score,
            "motivo": "attempt_credit",
            "referencia": key,
            "status": "pending",
            "created_at": now,
        })
    except DuplicateKeyError:
        return CreditResult(puntos_ganados=0, duplicate=True)

    user = await usuarios.find_one_and_update(
        {"id": user_id},
        {"$inc": {"puntos": score}, "$set": {"updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not user:
        await ledger.update_one({"_id": key}, {"$set": {"status": "orphan"}})
        return CreditResult(puntos_ganados=0, error="user_not_found")

    await ledger.update_one(
        {"_id": key},
        {"$set": {"status": "applied", "saldo_despues": user["puntos"], "applied_at": now}},
    )
    return CreditResult(puntos_ganados=score, puntos_totales=user["puntos"])
```

Propiedades:
- La clave única del ledger impide la doble acreditación por replay o carrera.
- El saldo se puede reconstruir sumando el ledger.
- Un asiento `pending` indica un `$inc` que no se confirmó; el reconciliador lo reintenta.
- `puntos_ganados` sigue siendo el delta de la request; en un replay es 0.

---

## Anexo D — Orden sugerido de implementación

```text
Fase 0    Tests/contrato/docs
   │
Fase 0.5  Arquitectura objetivo, reglas de dependencia y shared/ mínimo
   │
Fase 1    Identidad → dificultad → sin replay → ledger → grade bugs → pistas → recarga → guardas narrativas
   │
Fase 2  Validadores (Wordle primero) → flags → tiempo server-side → feedback → sanitización
   │
Fase 3  Seeds/motor → índices V2 → validador de grafos → dry-run 12 meses → economía narrativa
   │
Fase 4  Extracción de servicios, TZ, threadpool, rate limiting, limpieza
   │
Fase 5  V2 oficial por flag, con rollback a V1
```

Ninguna fase posterior requiere haber hecho la anterior completa, pero la Fase 1 no debería empezar sin la red de seguridad de la Fase 0.

---

## Anexo E — Entorno compartido con el frontend

El backend actual se levanta a veces para que el desarrollador frontend testee contra él. La regla es **no compartir proceso ni base entre “estable” y “en refactor”**. Un branch solo no alcanza: si se reinicia el mismo puerto con código a medio hacer, el frontend se rompe igual.

**Estrategia recomendada: dos runtimes aislados desde el mismo repo.**

| Rol | Código | Puerto | Base | Quién lo usa |
|---|---|---|---|---|
| Estable | `feature/juego-narrativo` @ `9a7ffd2` en el worktree `../sipi-estable` | 8080 (el que ya usa el frontend) | `mayores_actualizaciones` | Desarrollador frontend |
| Refactor | `feature/refactor-backend` @ `9a7ffd2` en el worktree principal | 8090 (vía `PORT`) | `mayores_actualizaciones_dev` | Nosotros |
| Tests | rama de trabajo | sin servidor | `mayores_actualizaciones_test` | pytest |

Estado al 2/11/2026 (ya ejecutado):

1. Worktree estable creado: `git worktree add ../sipi-estable feature/juego-narrativo`. Es `feature/juego-narrativo` y no `main` porque el frontend necesita las escalas de calificación por tiempo (commit `9a7ffd2`), que todavía no están en `main`.
2. `.env` del worktree estable copiado tal cual del repo principal: `PORT=8080`, `MONGODB_DB_NAME=mayores_actualizaciones`.
3. `.env` del worktree de refactor ajustado: `PORT=8090`, `MONGODB_DB_NAME=mayores_actualizaciones_dev`.
4. Base duplicada una vez con `pymongo` (no hay `mongodump`/`mongosh` en el PATH): 19 colecciones, 1064 documentos, índices incluidos. De acá en adelante las bases divergen a propósito.
5. Base `mayores_actualizaciones_test` creada vacía (solo una colección `_meta` de marcador). Los tests de Fase 0 la van a poblar y limpiar por prefijos.

Comandos de arranque (cada uno en su carpeta):

```bash
# Estable para el frontend (dejar corriendo durante sus ventanas de prueba)
cd ../sipi-estable
../mayores_actualizacionesSIPI-BACK/.venv/Scripts/python.exe -m app.main   # usa PORT del .env = 8080

# Refactor
cd ../mayores_actualizacionesSIPI-BACK
.venv/Scripts/python.exe -m app.main                                       # usa PORT del .env = 8090
```

El worktree estable comparte el intérprete del repo principal para no duplicar dependencias. Si `requirements.txt` cambia en refactor y el estable necesita quedarse con las versiones viejas, crear un `.venv` propio en `../sipi-estable`.

**Lanzadores (fuera de ambos repos).** Carpeta `C:\Users\nmonti\Desktop\proyectos\servicios`. Se ejecutan con doble clic; cada uno abre su ventana, hace `cd` a la carpeta correcta y muestra la URL.

| Script | Levanta | Puertos |
|---|---|---|
| `backend-estable.cmd` | Backend del worktree estable | 8080 |
| `backend-refactor.cmd` | Backend del worktree de refactor | 8090 |
| `frontend.cmd` | Vite; el proxy `/api` sale del `.env.local` (8080) | 5174 |
| `frontend.cmd http://localhost:8090` | Vite con proxy forzado al refactor, sin editar archivos | 5174 → 8090 |
| `estable-y-frontend.cmd` | Estable + frontend (flujo del desarrollador frontend) | 8080 / 5174 |
| `refactor-y-frontend.cmd` | Refactor + frontend apuntando al refactor | 8090 / 5174 |

El frontend no se toca: `VITE_BACKEND_URL` pasado por entorno gana sobre `.env.local` porque `vite.config.ts` usa `loadEnv` y luego el proxy toma ese valor. Verificado con 8080 apagado: la request por 5174 llegó al 8090.

**Reglas de convivencia:**

- Cambios de esquema/índices solo en `mayores_actualizaciones_dev`; nunca correr migraciones destructivas sobre `mayores_actualizaciones`.
- Campos nuevos aditivos y flags apagados por defecto para que el contrato no cambie hasta validar.
- Tests siempre en `mayores_actualizaciones_test`, con limpieza por prefijos.
- Anunciar cuando el runtime de trabajo está inestable; el estable no se toca en esa ventana.
- No copiar la carpeta del backend a mano: se desincroniza. El aislamiento se logra con worktrees + puertos + bases, no con una copia.

**Por qué no una copia del backend:** una copia manual duplica código, dependencias y configuración, y a los pocos días divergen. Git ya da dos árboles de trabajo con `git worktree`; lo que falta es separar runtime y datos.

**Qué no hacer:** trabajar en `main`, reiniciar el proceso que usa el frontend, o cambiar índices/colecciones en la base compartida. Eso rompe la relación aunque el código compile.

**Qué es (y qué no es) un worktree:**

- Es **solo local**. Crea otra carpeta de trabajo sobre el mismo repositorio; no crea ramas nuevas en GitHub, no pushea nada y no se ve en el remoto.
- `git worktree add ../sipi-estable feature/juego-narrativo` no modifica GitHub: la rama ya existe. Solo la checkoutea en otra carpeta.
- Se administra con `git worktree list` y se elimina con `git worktree remove ../sipi-estable` (o borrando la carpeta y `git worktree prune`).
- Cada worktree tiene su propia copia de archivos no versionados: `.env`, `.venv`, logs y `dist/` **no** se comparten. El `.env` del estable se copió a mano.
- Si querés que algo sea visible en GitHub, tiene que ser un branch pusheado; el worktree en sí no se publica.

---

## Anexo F — Migración del frontend (workstream separado)

El backend puede quedar correcto sin tocar el frontend, porque los cambios son aditivos. Pero la experiencia del usuario no cambia hasta que el frontend consuma los campos nuevos. Nada de esto se implementa en esta etapa; queda como backlog coordinado.

| # | Cambio en el frontend | Motivo | Sin esto... |
|---|---|---|---|
| F1 | Leer `puntos_totales_usuario` de `POST /api/games/attempts` en vez de sumar `score` local ([attemptsService.ts:371-401](../../../../frontend/src/VISTAS/JUEGOS/attemptsService.ts#L371)) | El servidor es la fuente de verdad del saldo | La UI puede mostrar un saldo distinto al de la DB |
| F2 | Usar `puntos_ganados` de la respuesta; en invitado, sumarlo a `localStorage` | Evitar doble conteo y reflejar la acreditación real | El invitado no ve los puntos del narrativo |
| F3 | Leer `by_difficulty` para mostrar progreso de Crucigrama fácil/difícil | Hoy fácil y difícil comparten intento en la UI | El calendario puede mostrar un estado incorrecto |
| F4 | Apuntar la recarga de vidas a `POST /api/economy/refill-lives` en vez de `POST /api/admin/economy/user/adjust` ([useGameLives.tsx:68](../../../../frontend/src/VISTAS/JUEGOS/useGameLives.tsx#L68)) | Hoy recibe 403 para jugadores | La recarga de las 4 vidas sigue rota |
| F5 | Enviar `guest_id` por dispositivo en el narrativo (header o body opcional) | Aislar `run_0_<fecha>` entre invitados | Dos invitados comparten la misma partida |
| F6 | Al crear cuenta, llamar una vez a `POST /api/economy/guest-migration` con el saldo local y limpiar la clave | Volcar puntos de invitado con tope y auditoría | Los puntos de invitado se pierden al registrarse |
| F7 | Al iniciar sesión, reemplazar el saldo local por el del servidor | Evitar mezclar cuentas | Un saldo local viejo pisa el de la cuenta |
| F8 | Fase 2: consumir desafío sanitizado y feedback server-side | Cerrar la fuga de soluciones | El anti-cheat queda incompleto aunque el grado se valide |

Regla de compatibilidad: el backend mantiene los campos y rutas actuales; el frontend puede migrar de a un ítem, con flags cuando aplique. Si un ítem no se hace, el sistema sigue funcionando como hoy, pero sin la mejora correspondiente.
