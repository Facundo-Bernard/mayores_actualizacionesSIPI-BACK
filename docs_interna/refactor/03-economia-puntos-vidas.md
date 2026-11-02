# Economía, puntos y vidas — contexto para la refactorización

> **Alcance:** saldo global de puntos, calificaciones S/A/B/C/F, pistas, desbloqueo histórico, suscripción, paquetes, vidas y ajustes admin.
> **Base analizada:** commit `d2a117b` (30/10/2026), con foco en el commit `9442693` (“puntos globales, calificaciones S/A/B/C/F y pistas por puntos”).
> **Método:** lectura completa de `app/features/economy/**`, `app/features/user_attempts/**`, `app/features/daily_challenges/**`, `app/features/narrative/game/endings_service.py`, `auth`, `usuario`, `progreso`, seeds y tests; búsqueda exhaustiva de términos (`vidas`, `puntos`, `lives`, `points`, `hints`, `pistas`, `coins`, `ledger`, etc.).
> **Estado:** análisis estático. No se ejecutó la app contra MongoDB ni se modificó código.

> **Errata (2/11/2026):** diferencias verificadas contra el código actual en [05-plan-solucion.md §2](05-plan-solucion.md). Este documento se conserva como foto original del relevamiento.
> **Audiencia:** desarrolladores que se incorporan al backend y van a refactorizar sin romper el frontend.

---

## 0. Cómo usar este documento

1. Las secciones 1 a 4 explican el modelo mental y el contrato HTTP.
2. Las secciones 5 y 6 son el modelo de datos y las reglas de negocio actuales.
3. La sección 7 muestra el único flujo que acredita puntos.
4. La sección 8 contrasta **comportamiento actual vs. esperado**.
5. La sección 9 lista defectos con archivo:línea.
6. Las secciones 10 a 13 fijan reglas, plan de refactor, migración y tests.

Documentos hermanos:

- [Juegos clásicos](01-juegos-clasicos.md)
- [Narrativo V1/V2](02-narrativo-v1-v2.md)
- [Testing](04-testing.md)

---

## 1. Resumen ejecutivo

- **La economía real es un único contador `usuarios.puntos`.** No hay ledger, historial de movimientos ni colección de transacciones.
- El saldo se incrementa en un solo lugar: `POST /api/games/attempts` → `save_user_attempt` ([app/features/user_attempts/service.py](../../app/features/user_attempts/service.py)). Se descuenta en compras, desbloqueos, pistas y ajustes admin (`app/features/economy/service.py:234-253,455-463,531-538`).
- **Los puntos se otorgan por calificación, no por juego.** El monto sale de `puntos_por_calificacion` (S=100, A=90, B=75, C=50, F=0 por defecto). `puntos_por_juego` quedó como configuración muerta: se publica y se edita, pero ningún camino de acreditación lo lee.
- **La acreditación es cliente-confianza.** El endpoint que otorga puntos no valida la solución, ni la fecha, ni el `game_id`, ni los intentos; acepta `grade`, `attempts`, `game_data` y `user_id` enviados por el cliente.
- **El replay es determinístico.** Un intento `completed` se puede volver a `in_progress`/`failed` y luego a `completed`; el guard `was_already_completed` se resetea y vuelve a acreditar. Además hay carrera entre el `find_one` y el `find_one_and_update`.
- **Las vidas por juego no existen en el backend.** Sigue existiendo un contador global `usuarios.vidas` con endpoints activos (`/consume-life`, `/buy-lives`, `/me`, admin adjust), pero ningún módulo de juego lo consulta.
- El único campo “por juego” es `remaining_attempts`, que envía el cliente, se sobrescribe en cada guardado y solo se usa para calcular la calificación.
- **Las pistas y los desbloqueos pagos son cosméticos.** Los GET de desafíos son públicos y devuelven la solución; ningún endpoint de desafío verifica `dias_desbloqueados`.
- `use_hint` cobra **antes** de resolver el contenido y no reembolsa si no encuentra la pista.
- El panel admin **no puede editar** `costo_pista_puntos` ni `puntos_por_calificacion`; el bundle solo expone el modelo viejo (`vidas_iniciales`, `vidas_maximas`, `puntos_por_juego`, paquetes).
- No hay tests de economía, puntos, vidas, pistas ni admin económico.
- No hay transacciones multi-documento en ningún flujo de `app/`.

---

## 2. Glosario

| Término | Significado |
|---|---|
| **Puntos** | Saldo entero global en `usuarios.puntos`. Única moneda real. |
| **Grado / calificación** | Letra `S/A/B/C/F` calculada por `calculate_grade_and_score`. |
| **Score** | Valor numérico asociado al grado; en juegos clásicos 0-100, en narrativo 250-1000. |
| **Puntos ganados** | Campo de respuesta (`puntos_ganados`) que indica cuánto se acreditó en esa request. No se persiste. |
| **Vida** | Contador global `usuarios.vidas`, consumible por endpoint manual. No gatea ningún juego. |
| **Pista** | Texto o celda revelada por `POST /api/economy/use-hint`, con costo en puntos. |
| **Desbloqueo** | Pago para acceder a una fecha histórica; se guarda en `usuarios.dias_desbloqueados`, pero no se enforce. |
| **Suscripción** | `basica` o `premium`; solo afecta `unlock-day`. Existe además el flag legado `black`, no sincronizado. |
| **Paquete** | Combinación de vidas por puntos en `paquetes_tienda`. |
| **Ledger** | Historial de movimientos. **No existe.** |
| **Ajuste admin** | Suma/set de puntos, vidas o suscripción desde la Torre. No es auditable. |

### Modelo mental

```text
Juego clásico o narrativo
        │
        │  (hoy) el cliente calcula el resultado y llama a /api/games/attempts
        ▼
save_user_attempt ──> $inc usuarios.puntos
        │
        └──> user_attempts (score, grade, stars)

Economía (satélite)
  ├─ GET /api/economy/me          → lee puntos/vidas
  ├─ POST /consume-life           → $inc vidas:-1
  ├─ POST /buy-lives              → $inc puntos:-costo, vidas:+n
  ├─ POST /unlock-day             → $inc puntos:-costo, $addToSet dias_desbloqueados
  └─ POST /use-hint               → $inc puntos:-costo
```

No hay reconciliación entre el saldo y los movimientos porque los movimientos no se registran.

---

## 3. Mapa del módulo y dependencias

### 3.1 Archivos

| Archivo | Responsabilidad |
|---|---|
| `app/features/economy/router.py` | Contratos HTTP y roles. No contiene reglas de negocio. |
| `app/features/economy/service.py` | Configuración, saldo, vidas, compras, desbloqueos, pistas, ajustes admin y suscripción. Acceso directo a Mongo. |
| `app/features/economy/schemas.py` | Modelos Pydantic de request/response. |
| `app/features/user_attempts/service.py` | Cálculo de grado/score y única acreditación de puntos. |
| `app/features/user_attempts/router.py` | Endpoints de intentos; identidad débil. |
| `app/features/narrative/game/endings_service.py` | Escribe `user_attempts` con escala narrativa, sin acreditar puntos. |
| `app/features/auth/service.py` | Crea usuarios con `puntos: 0`, sin vidas. |
| `app/features/usuario/schemas.py` | Devuelve `vidas=5`, `puntos=0`, `suscripcion="basica"` por defaults, no por DB. |

### 3.2 Dependencias salientes

`economy` depende de:

- `app.core.database.get_database`;
- `app.core.dependencies.get_current_user` / `get_current_admin`;
- sus propios schemas;
- tres colecciones Mongo sin capa de repositorio:
  - `configuracion_economia`;
  - `usuarios`;
  - `daily_challenges`.

No importa `auth`, `usuario`, `daily_challenges.service`, `user_attempts` ni `narrative`.

### 3.3 Dependencias entrantes

| Entrante | Evidencia | Uso |
|---|---|---|
| `app/main.py` | `main.py:26,139` | Monta `economy_router`. |
| `app/features/user_attempts/service.py` | `service.py:179-185` | Import diferido de `get_economy_config` para obtener `puntos_por_calificacion`. Es el **único** módulo que importa `economy`. |
| SPA admin | `app/static/admin/assets/index-BftnQgps.js:16,24` | Consume `/api/admin/economy/config`, `/user/search`, `/user/adjust`. |
| Frontend jugador | No está en este repo | Consume `/api/economy/*` y `/api/games/attempts`. No verificable acá. |

### 3.4 Acoplamiento por datos

`economy` es relativamente aislado a nivel imports, pero acoplado a nivel datos:

- lee `daily_challenges` para resolver pistas;
- `user_attempts` escribe `usuarios.puntos` sin pasar por `economy`;
- `narrative` escribe `user_attempts` sin pasar por `user_attempts.service`;
- `auth` crea usuarios con `puntos: 0` pero sin `vidas`;
- `usuario` devuelve vidas/puntos por default, no por DB.

---

## 4. Contratos HTTP congelados

> **Regla:** no cambiar paths, métodos, campos ni códigos de estado. Los campos marcados como “deprecados” se mantienen por compatibilidad hasta que el frontend migre.

### 4.1 Endpoints del módulo `economy`

| Método | Ruta | Auth | Request | Response | Efectos |
|---|---|---|---|---|---|
| `GET` | `/api/economy/config` | Público | — | `EconomyConfigResponse` | **Siembra** la config si no existe. Un GET escribe en DB. |
| `GET` | `/api/economy/me` | Usuario | — | `UserEconomyResponse`: `user_id`, `vidas`, `puntos`, `racha`, `suscripcion`, `dias_desbloqueados`, `costo_pista_puntos`, `updated_at` | Si falta `vidas`, asigna `vidas_iniciales`. |
| `POST` | `/api/economy/consume-life` | Usuario | `ConsumeLifeRequest {game_id?, motivo?}` | `ConsumeLifeResponse {success, vidas_restantes, consumidas, message}` | `$inc vidas:-1` con guarda `vidas > 0`. `game_id` solo se loguea; `motivo` se ignora. |
| `POST` | `/api/economy/buy-lives` | Usuario | `BuyLivesRequest {package_id?, vidas?}` | `BuyLivesResponse {success, vidas, puntos, compradas, costo, message}` | `$inc puntos:-costo, vidas:+n` con guarda `puntos >= costo`. No aplica `vidas_maximas`. |
| `POST` | `/api/economy/unlock-day` | Usuario | `UnlockDayRequest {game_id, date}` | `UnlockDayResponse {success, unlocked, puntos, costo, date, game_id, message}` | Premium gratis; si ya está desbloqueado, gratis; si no, `$inc puntos:-costo` + `$addToSet dias_desbloqueados`. |
| `POST` | `/api/economy/use-hint` | Usuario | `UseHintRequest {game_id, date?, hint_index?, row?, col?}` | `UseHintResponse {success, puntos_restantes, puntos_descontados, vidas_restantes, vidas_descontadas, pista, valor_revelado, message}` | Descuenta `costo_pista_puntos`; luego intenta resolver la pista. Si no encuentra contenido, **igual cobró**. |
| `GET` | `/api/admin/economy/config` | Admin | — | `EconomyConfigResponse` | Siembra config si falta. |
| `GET` | `/api/economy/admin/config` | Admin | — | `EconomyConfigResponse` | Alias oculto **bloqueado por el middleware** (`/admin/config`). |
| `PUT` | `/api/admin/economy/config` | Admin | `EconomyConfigUpdateRequest` | `EconomyConfigResponse` | `$set` de campos enviados + `updated_at`. No valida claves/valores. |
| `PUT` | `/api/economy/admin/config` | Admin | Igual | Igual | Alias oculto bloqueado. |
| `GET` | `/api/admin/economy/user/search` | Admin | `identificador` (email, PIN o ID) | `SearchUserEconomyResponse` | Solo lectura. |
| `POST` | `/api/admin/economy/user/adjust` | Admin | `AdjustUserEconomyRequest {identificador, vidas_sumar?, puntos_sumar?, vidas_set?, puntos_set?, suscripcion_set?}` | `AdjustUserEconomyResponse` | `$inc`/`$set`; si queda negativo, segundo update para clampear a 0. |
| `PUT` | `/api/admin/usuario/{usuario_id}/suscripcion` | Admin | `CambiarSuscripcionRequest {suscripcion}` | Dict sin `response_model` | `$set suscripcion`. |

### 4.2 Endpoints externos que afectan la economía

| Método | Ruta | Auth | Efecto económico |
|---|---|---|---|
| `POST` | `/api/games/attempts` | Token opcional; si no hay, `user_id` del body | **Único camino de acreditación**. Acepta `grade`, `attempts`, `game_data`, `user_id`, `date`, `game_id`. |
| `GET` | `/api/games/attempts/date/{date}` | Token opcional; `user_id` query pisa al token | Lectura de intentos de cualquier usuario. |
| `GET` | `/api/games/attempts` | Token opcional; `user_id` query pisa al token | Lectura mensual de cualquier usuario. |
| `GET` | `/api/challenges/*` | Público | Expone soluciones y fechas futuras. |
| `POST` | `/api/challenges` | **Público** | Sobrescribe desafíos y soluciones. |
| `POST/GET` | `/api/narrative/v2/partida/*` | Invitado o Bearer débil | Escribe `user_attempts` sin acreditar puntos. |

### 4.3 Autenticación y roles

- `get_current_user` valida JWT, permisos de servicio, usuario activo y existencia local (`app/core/dependencies.py:11-109`).
- `get_current_admin` exige `tipo_usuario == 2` (`dependencies.py:111-122`).
- `economy` usa correctamente esos dependencies.
- `user_attempts` **no** usa `get_current_user`: solo decodifica el token y no valida `servicios`, `activo` ni rol. Sin token, acepta `user_id` del body.
- `daily_challenges` GET/POST son públicos; solo los endpoints admin exigen admin.
- `narrative` devuelve `0` si no hay token y no valida activo ni permisos.

---

## 5. Modelo de datos

### 5.1 Colecciones relevantes

| Colección | Campos | Índices | Quién escribe | Quién lee |
|---|---|---|---|---|
| `usuarios` | `id`, `name`, `email`, `codigo_acceso`, `tipo_usuario`, `black`, `activo`, `estado_id`, `estado_codigo`, `date_start/end`, `progresos[]`, **`puntos`**, **`vidas`**, **`racha`**, **`suscripcion`**, **`dias_desbloqueados[]`**, `updated_at` | `email` unique, `codigo_acceso` **no unique**, `id` unique, `name`, `date_start` | `auth`, `economy`, `progreso` | `economy`, `dependencies.get_current_user`, `auth/usuario` |
| `configuracion_economia` | `_id="global_economy"`, `vidas_iniciales`, `costo_vida_puntos`, `costo_desbloqueo_dia_puntos`, `costo_pista_puntos`, `puntos_por_calificacion`, `paquetes_tienda[]`, `puntos_por_juego`, `vidas_maximas`, `updated_at` | Solo `_id` | `economy.get_economy_config` / `update_economy_config` | `economy` |
| `user_attempts` | `user_id`, `game_id`, `date`, `mode`, `status`, `word`, `attempts`, `stars`, `score`, `grade`, `guesses[]`, `game_data`, `remaining_attempts`, `created_at`, `updated_at` | único `(user_id, game_id, date)`; `(user_id, date)` | `user_attempts.service`, `narrative.endings_service` | `user_attempts.service`, frontend |
| `daily_challenges` | `game_id`, `date`, `difficulty`, `title`, `config`, `created_at`, `updated_at` | único `(game_id, date, difficulty)`; `(date)` | `daily_challenges.service`, admin de Crucigrama | `daily_challenges.service`, `economy.use_hint`, narrativo |

**No existe** colección `transactions`, `ledger`, `movimientos`, `economy_history`, `puntos_log` ni equivalente.

### 5.2 Configuración por defecto

| Clave | Default | Uso | Estado |
|---|---:|---|---|
| `vidas_iniciales` | 5 | `get_user_economy`, `consume_life` | Activo, marcado “deprecado/local”. |
| `costo_vida_puntos` | 50 | `buy_lives` | Activo. |
| `costo_desbloqueo_dia_puntos` | 100 | `unlock_historical_day` | Activo, pero el desbloqueo no se enforce. |
| `costo_pista_puntos` | 20 | `use_hint`, `/me` | Activo. |
| `puntos_por_calificacion` | S=100, A=90, B=75, C=50, F=0 | `user_attempts` | Activo; **no editable desde el panel admin**. |
| `paquetes_tienda` | pack_1 (1/50), pack_3 (3/120), pack_5 (5/180) | `buy_lives` | Activo; sin validación de IDs duplicados. |
| `puntos_por_juego` | wordle=50, sopa=50, sudoku=60, crucigrama=70, narrativo=80 | Solo `get_economy_config` | **Muerto para acreditación.** |
| `vidas_maximas` | `null` | Solo lectura/update | **Muerto**: no se aplica. |
| `updated_at` | ISO | Metadato | Activo. |

No hay settings de economía en `app/core/config.py` ni en `.env.example`; todo vive en `configuracion_economia`.

---

## 6. Reglas de negocio actuales

### 6.1 Puntos: acumulación y descuento

**Dónde se guarda:** un único entero `usuarios.puntos`.

**Cómo se acumula:**

- único camino: `save_user_attempt`, cuando `final_status == "completed"` y el intento no estaba completado;
- monto: `puntos_ganados = score`, donde `score = puntos_por_calificacion[grade]`;
- no hay multiplicador por juego, racha, estrellas, dificultad ni modo;
- no hay tope de puntos ni límite diario;
- no hay puntos por intentos, racha ni finalización más allá de `completed`;
- el narrativo **no** ejecuta este camino.

**Cómo se descuenta:**

| Operación | Evidencia | Guarda de saldo |
|---|---|---|
| Comprar vidas | `economy/service.py:234-241` | `puntos >= costo` |
| Desbloquear día | `economy/service.py:455-463` | `puntos >= costo` |
| Pedir pista | `economy/service.py:531-538` | `puntos >= costo` |
| Ajuste admin | `economy/service.py:341-344` | No; puede restar y luego clampear a 0 |

### 6.2 Calificaciones S/A/B/C/F

Algoritmo en `calculate_grade_and_score` (`user_attempts/service.py:17-129`):

1. Si `status` es `failed`/`lost`: `("F", 0, 0)`.
2. Si `status` no es `completed`/`won`: `(provided_grade or "C", 0, 0)`. Guardado intermedio, no acredita.
3. Si el cliente envía `grade` y la letra existe en `puntos_por_calificacion`: usa esa letra, el valor configurado como `score` y estrellas 3/2/1.
4. Si no, calcula por juego:
   - **Wordle:** `attempts <= 2` → S; `<= 4` → B; resto C. Nunca genera A.
   - **Sudoku:** `errors == 0` y (`remaining_attempts >= 3` o `== 0`) → S; `errors <= 1` o `remaining_attempts == 2` → B; resto C.
   - **Crucigrama:** `errors == 0` → S; `<= 2` → B; resto C.
   - **Sopa:** `errors == 0` → S; `<= 2` → B; resto C.
   - **Otro:** `remaining_attempts >= 3` o `attempts <= 2` → S; `remaining_attempts >= 1` o `attempts <= 4` → B; resto C.
5. `score = config_pts.get(grade, provided_score if > 0 else 50)`.
6. Estrellas: 3 para S/A, 2 para B, 1 para C/F; si el cliente manda `stars > 0`, se respeta clampeado a 1-3.

**Qué otorgan:** solo el `score` monetario. Las estrellas no otorgan puntos ni monedas. `F` otorga 0. No hay bonus por S, racha ni primer intento.

**Narrativo:** `calcular_finalizacion_victoria` usa promedio de recursos: `>=75` S, `>=55` A, `>=35` B, resto C. Derrota → F. Luego mapea a score 1000/850/700/500/250 y estrellas 3/3/2/1/1, pero **no acredita** `usuarios.puntos` y **no escribe `grade`**.

### 6.3 Pistas

- Costo: `costo_pista_puntos`, default 20.
- Descuento atómico con guarda `puntos >= costo`.
- **Se cobra antes de resolver el contenido.**
- Si no hay desafío, o `hint_index`/`row`/`col` no producen contenido, devuelve `success=true`, `pista=null`, `valor_revelado=null`, pero los puntos ya se descontaron.
- No hay idempotency key, registro de pistas consumidas ni límite por desafío. Cada llamada cobra de nuevo, incluso la misma pista o celda.
- `hint_index` fuera de rango cae a `hints[0]` en Wordle/Sopa, pero igual cobra.
- Sudoku revela cualquier celda 0-8 sin verificar que esté vacía ni que el tablero sea el correcto.
- Crucigrama busca la letra en `words[].coords`; si no hay match, cobra y devuelve null.
- **No filtra `difficulty`**: para Crucigrama hay dos documentos por fecha y `find_one` devuelve uno arbitrario.
- No hay trato especial para Premium, pese al summary del router.

### 6.4 Vidas

**Existe un contador global `usuarios.vidas`:**

- `get_user_economy` lo lee y, si falta, lo aprovisiona con `vidas_iniciales`.
- `consume_life` resta 1 con guarda `vidas > 0`.
- `buy_lives` suma vidas y resta puntos.
- `find_user_by_identifier` devuelve `vidas` con default 5.
- `adjust_user_economy` permite `vidas_sumar`/`vidas_set`.
- `/api/economy/me` devuelve `vidas`.
- `use_hint` devuelve `vidas_restantes` desde el mismo campo.

**Pero ningún juego lo consulta.** Búsqueda de `vidas` en `daily_challenges`, `narrative`, `progreso` y `user_attempts` no devuelve lecturas de `usuarios.vidas`; solo comentarios y textos. El único módulo que lee/escribe vidas es `economy` y el schema de `usuario`.

**No hay vidas por juego:** no existe `vidas_por_juego`, `vidas_juego`, `game_lives`, `lives_by`, ni un dict `{wordle: n, sudoku: n, ...}`. Lo más cercano es `user_attempts.remaining_attempts`:

- descrito como “Vidas/intentos restantes del juego”;
- se guarda en el documento;
- se serializa;
- se usa **solo** para calcular la calificación;
- no se descuenta en el servidor, no se compara contra un máximo, no se consulta antes de jugar y se **sobrescribe** con `req.remaining_attempts or 0` en cada guardado;
- no está en la clave única.

### 6.5 Suscripción, paquetes y desbloqueo

- `suscripcion` solo se usa en `unlock_historical_day`. Premium evita el cobro; básica paga 100 pts por defecto.
- No hay ninguna otra verificación de Premium en el backend.
- No hay enforcement de `dias_desbloqueados` en `daily_challenges`. Cualquier usuario puede leer cualquier fecha sin desbloquear.
- Los paquetes de la tienda son solo vidas por puntos; no hay pago real ni integración de moneda.
- `vidas_maximas` está en la config pero **nunca se aplica**.
- `paquetes_tienda` no valida IDs duplicados; `next(...)` toma el primero.
- Existen dos modelos de suscripción en paralelo: `black` (legado) y `suscripcion`, no sincronizados.

### 6.6 Otras divisas

- **No existen monedas, coins, créditos ni una segunda divisa global.**
- Los recursos del narrativo (`oro`, `pueblo`, `ejercito`, `fe`) son estado interno de la partida, no se convierten en `usuarios.puntos`.
- `examenPuntos` de cursos es un silo separado (0-1000) y no se suma a `usuarios.puntos`.

---

## 7. Flujo de acreditación paso a paso

```text
Cliente termina partida
  └─ POST /api/games/attempts
       ├─ router resuelve user_id (token o body)
       ├─ save_user_attempt carga economy config
       ├─ calculate_grade_and_score(...)
       ├─ upsert en user_attempts ($set + $setOnInsert)
       ├─ si es victoria nueva: $inc usuarios.puntos
       └─ responde puntos_ganados y puntos_totales_usuario
```

Detalle:

1. El router acepta token o `req.user_id`; 401 solo si faltan ambos (`user_attempts/router.py:39-46`).
2. `save_user_attempt` usa `authenticated_user_id or req.user_id or 1` (`service.py:169`).
3. Carga `get_economy_config()` y toma `puntos_por_calificacion`; si falla, usa fallback hardcodeado (`:179-185`).
4. Calcula `(grade, score, stars)` (`:188-198`).
5. Normaliza `status` a `completed`/`failed`/`in_progress` (`:200-206`).
6. Lee `existing` y decide `was_already_completed` / `is_new_victory` (`:225-227`).
7. Hace `find_one_and_update` con upsert (`:229-237`).
8. Si `is_new_victory`, `$inc usuarios.puntos` (`:243-257`).
9. Si el `$inc` falla, solo loguea un warning; la respuesta igual informa `puntos_ganados=score`.
10. Si no hubo acreditación nueva, consulta el saldo (`:262-268`).

### 7.1 Por qué esto es explotable

- `game_id` es string libre: cada par `(game_id, date)` inventado crea un slot nuevo.
- `date` solo valida regex `YYYY-MM-DD`: acepta fechas futuras, pasadas e imposibles.
- `grade` es aceptado si existe en config; un cliente puede mandar `S`.
- `attempts` no tiene mínimo; `attempts <= 2` da S.
- `game_data.errors` no numérico puede lanzar `ValueError` → 500.
- `user_id` del body permite escribir sobre la cuenta de otro si no hay token.
- El replay por cambio de estado permite cobrar múltiples veces el mismo slot.

---

## 8. Comportamiento actual vs. comportamiento esperado

> Las propuestas de “esperado” son recomendaciones. Las que dependen de producto están marcadas como **[decisión pendiente]**.

| Área | Actual | Esperado recomendado |
|---|---|---|
| **Fuente de verdad de puntos** | El cliente envía `grade`/`attempts`/`game_data`. | El servidor valida la submission y calcula grado/score. `grade` del cliente se ignora o se usa solo como fallback legacy. |
| **Idempotencia** | `find_one` + `$inc`; replay por estado; carrera. | Transición de estado atómica y acreditación única; clave de idempotencia o ledger. |
| **Ledger** | No existe. | Registrar cada movimiento: `user_id`, `delta`, `motivo`, `referencia`, `actor`, `timestamp`, `saldo_despues`. |
| **Puntos por juego** | `puntos_por_juego` muerto. | Eliminarlo o usarlo como base/multiplicador de forma explícita. **[decisión pendiente]** |
| **Puntos por calificación** | Activo, no editable desde el panel. | Editable desde la Torre o documentado como config de despliegue. |
| **Vidas** | Global ornamental; no gatea nada. | Modelo explícito: por juego o eliminadas. Si se mantienen, el servidor descuenta y bloquea. **[decisión pendiente]** |
| **Vidas máximas** | Config muerta. | Aplicar tope en `buy_lives` o eliminar la clave. |
| **Pistas** | Cobra antes de resolver; sin idempotencia; sin dificultad; sin reembolso. | Cobrar y entregar en una operación lógica; reembolsar si no hay contenido; idempotente por `(user, game, date, difficulty, pista/celda)`; distinguir dificultad. |
| **Desbloqueo histórico** | Cobra y guarda, pero no se enforce. | Verificar `dias_desbloqueados`/Premium en los GET de desafíos y en attempts. |
| **Suscripción** | Solo afecta unlock; `black` paralelo. | Un solo campo; aplicar donde corresponda; migrar `black`. |
| **Paquetes** | Sin validación de IDs duplicados. | Validar IDs únicos y valores positivos. |
| **Ajuste admin** | No atómico; clampeo en segundo update; sin auditoría. | Operación atómica con guarda; ledger; auditoría. |
| **Saldo inicial** | `puntos: 0` en auth, sin vidas. | Estado inicial uniforme y documentado; sin provisioning silencioso en GET. |
| **Errores** | Usuario inexistente devuelve 400 “puntos insuficientes”. | 404 para usuario inexistente; 400 solo para saldo insuficiente. |
| **Rate limiting** | Ausente en economía/attempts. | Límite por usuario/IP en compras, pistas, intentos y desbloqueos. |
| **Transacciones** | Ninguna multi-documento. | Sesión/transacción o patrón de compensación para intento + puntos; ledger como fuente de verdad. |

---

## 9. Hallazgos priorizados

### Alta

| ID | Hallazgo | Evidencia | Impacto |
|---|---|---|---|
| **A1** | Puntos ilimitados por `POST /api/games/attempts`: `user_id` sin auth, `game_id`/`date` arbitrarios, `grade`/`attempts`/`game_data` del cliente. | `user_attempts/router.py:39-46`; `schemas.py:8-21`; `service.py:17-129,163-257` | Cualquiera puede fabricar puntos; la economía y cualquier ranking futuro quedan inválidos. |
| **A2** | Replay determinístico: `completed` → `in_progress`/`failed` → `completed` vuelve a acreditar. | `user_attempts/service.py:200-207,225-244` | Doble/triple crédito sin carrera. |
| **A3** | Carrera de doble crédito entre `find_one` y `find_one_and_update`; crédito perdido si falla el `$inc`. | `user_attempts/service.py:225-259` | Saldos inconsistentes; no hay transacción ni reintento. |
| **A4** | Soluciones y desafíos futuros públicos; `POST /api/challenges` sin auth; pistas y desbloqueos sin enforcement. | `daily_challenges/router.py:25-84`; `economy/service.py:402-482` | Los juegos se resuelven mirando la API; los pagos son cosméticos. |
| **A5** | Narrativo no acredita puntos globales; `puntos_por_juego["narrativo"]=80` es letra muerta. | `narrative/game/endings_service.py:127-172`; `economy/service.py:42-48` | El juego principal no alimenta la economía; el catálogo miente. |
| **A6** | Vidas por juego inexistentes; sigue el contador global `usuarios.vidas` sin uso en gameplay. | `economy/service.py:136-146,164-266`; `user_attempts/schemas.py:21` | El modelo pedido no está implementado; se gastan puntos en vidas que no afectan nada. |

### Media

| ID | Hallazgo | Evidencia | Impacto |
|---|---|---|---|
| **M1** | `use-hint` cobra antes de validar contenido; si no hay desafío/pista, pierde puntos y devuelve `success=true`. | `economy/service.py:531-538,551-618` | Pérdida silenciosa de puntos; reclamos. |
| **M2** | `unlock-day` tiene carrera de doble cobro y no se enforce; Premium solo evita un cobro que no sirve. | `economy/service.py:417-463` | Cobros duplicados; suscripción sin valor real. |
| **M3** | `/usuario/{id}` y `POST /usuario` devuelven `vidas=5`, `puntos=0`, `suscripcion="basica"` por defaults, no por DB. | `usuario/schemas.py:47-50`; `auth/service.py:38-50` | Admins y jugadores ven saldos falsos. |
| **M4** | IDOR de lectura en attempts: `user_id` de query pisa al token y no requiere auth. | `user_attempts/router.py:59-68,82-99` | Exposición de progreso de cualquier alumno. |
| **M5** | `puntos_por_juego` contradice la acreditación real; helpers sin callers. | `economy/service.py:42-48,79,269-280`; `user_attempts/service.py:50-58,125` | El frontend muestra 50-80 pts; el backend paga 0-100 por nota. |
| **M6** | El panel admin no puede editar `costo_pista_puntos` ni `puntos_por_calificacion`. | `static/admin/assets/index-BftnQgps.js:16,24` | La economía nueva no es operable desde la Torre. |
| **M7** | Crucigrama fácil/difícil comparten intento/puntos; la pista tampoco filtra dificultad. | `database.py:108-111,116-119`; `user_attempts/service.py:172-176`; `economy/service.py:557-560` | Un solo pago por día para dos crucigramas; pistas del tablero equivocado. |
| **M8** | No hay ledger ni historial; ajustes admin y `$inc` solo quedan en logs. | `economy/service.py:234-253,384-387,455-463,531-538` | Imposible auditar o reconciliar saldos. |
| **M9** | `vidas_maximas` no se aplica; compra sin tope; usuario inexistente devuelve 400 engañoso. | `economy/service.py:80,106-107,216-249` | Vidas ilimitadas; mensajes incorrectos. |
| **M10** | `game_data.errors` no numérico produce 500; `attempts`/`remaining_attempts` negativos permiten S. | `user_attempts/service.py:63`; `schemas.py:15,21` | DoS trivial y notas manipulables. |
| **M11** | El alias `/api/economy/admin/config` está bloqueado por el middleware `/admin/config`. | `economy/router.py:123-127,137-141`; `core/security_middleware.py:21` | Endpoint muerto; si el frontend usa el alias, recibe 403. |
| **M12** | Sin rate limit ni idempotencia en economía/attempts. | `auth/router.py:16,25,39` (único uso) | Farming y doble click. |
| **M13** | `adjust_user_economy` no es atómico y `codigo_acceso` no es unique. | `economy/service.py:366-382`; `database.py:101` | Saldo negativo transitorio; búsqueda ambigua por PIN. |
| **M14** | `mode` no entra en la clave única; `daily` y `campaign` colisionan. | `database.py:116-119`; `user_attempts/service.py:172-176` | Un modo pisa el intento del otro. |

### Baja

- `racha` nunca se escribe; servicio devuelve 0, schema default 1.
- `vidas_maximas` no se puede volver a `null` por API.
- `UserEconomyResponse.updated_at` nunca se completa.
- GET con efectos de escritura (seed de config y provisioning de vidas).
- `consume-life` ignora `motivo` y solo usa `game_id` en el log.
- Zona horaria mixta: pistas/desafíos usan `datetime.now()` local; `updated_at` usa UTC.
- `puntos_por_calificacion`/`puntos_por_juego` aceptan dicts sin validar claves/valores.
- Dos modelos de suscripción (`black` y `suscripcion`).
- `score` significa puntos en quiz y 1000 en narrativo.
- `get_points_for_game`/`get_points_for_grade` y `vidas_maximas` son código/config muerto.

---

## 10. Reglas para tocar routers sin romper el frontend

1. **No cambiar paths, métodos ni nombres de campos.** El frontend consume `/api/economy/*`, `/api/games/attempts` y `/api/admin/economy/*` con los nombres actuales.
2. **Mantener los campos deprecados.** `vidas`, `vidas_restantes`, `vidas_descontadas`, `puntos_ganados` y `puntos_totales_usuario` se siguen devolviendo aunque dejen de tener sentido, hasta que el frontend migre.
3. **No cambiar el significado de `puntos_ganados`.** Si se agrega ledger, `puntos_ganados` debe seguir siendo el delta de esa request.
4. **La validación server-side entra por campos opcionales.** `POST /api/games/attempts` sigue aceptando el payload actual; si viene `submission`, el servidor manda. No romper clientes viejos.
5. **Los fixes de identidad son un cambio de comportamiento.** Ignorar `user_id` del body puede romper el modo invitado o clientes que no envían token; coordinar.
6. **La autenticación admin es un cambio de comportamiento.** Verificar que la SPA admin envíe Bearer antes de cerrar endpoints.
7. **No eliminar `usuarios.vidas` sin migración.** Si se decide eliminarlo, dejar de leerlo primero, marcarlo deprecado y después borrarlo.
8. **No cambiar el índice único de `user_attempts` sin migración.** Agregar `difficulty` requiere un índice nuevo y backfill.
9. **La lógica nueva va en services.** El router solo valida y delega.
10. **Tests de caracterización antes de tocar.** Congelar respuestas de `/me`, `/config`, `/consume-life`, `/buy-lives`, `/unlock-day`, `/use-hint`, admin y attempts.

---

## 11. Plan de refactor por fases

### Fase 0 — Red de seguridad

- Tests de caracterización de todos los endpoints de economía y attempts.
- Documentar el contrato real (este documento).
- Verificar qué consume el frontend.

### Fase 1 — Extraer sin cambiar comportamiento

- Separar `economy/service.py` en módulos:
  - `config_service`;
  - `points_service`;
  - `lives_service`;
  - `hints_service`;
  - `unlock_service`;
  - `admin_service`.
- Mantener routers y respuestas idénticas.
- Introducir un repositorio/DAO interno para `usuarios`, `configuracion_economia` y `daily_challenges`.

### Fase 2 — Hacer server-authoritative la acreditación

- Validar la submission en el servidor (ver documento de juegos clásicos y narrativo).
- Ignorar `grade`/`score` del cliente cuando haya submission.
- Transición de estado atómica:
  - solo `in_progress → completed/failed` acredita;
  - `completed` no vuelve a `in_progress` sin una operación explícita de reintento;
  - usar filtro condicional o `$setOnInsert` + `$inc` en una sola operación lógica.
- Agregar idempotency key o ledger.

### Fase 3 — Ledger y auditoría

- Colección `economy_ledger` (o `movimientos_puntos`) con:
  - `user_id`, `delta`, `motivo`, `referencia`, `actor`, `timestamp`, `saldo_despues`, `metadata`.
- Registrar créditos, compras, pistas, desbloqueos y ajustes admin.
- Reconciliar el saldo con la suma del ledger.
- Endpoint admin de historial (nuevo, no rompe nada).

### Fase 4 — Vidas y producto

- Definir el modelo:
  - **Opción A:** eliminar vidas globales y `consume-life`/`buy-lives`.
  - **Opción B:** vidas por juego, con contador por `(user_id, game_id)`, reglas de reposición y enforcement en el servidor.
- Si se mantiene el global, aplicarlo en algún juego o eliminarlo; no dejarlo ornamental.
- Definir si el narrativo otorga puntos y con qué escala.

### Fase 5 — Pistas, desbloqueo y admin

- Pista idempotente por `(user, game, date, difficulty, pista/celda)`.
- Reembolsar si no hay contenido.
- Incluir `difficulty` en la resolución.
- Enforce de `dias_desbloqueados`/Premium en los GET de desafíos y attempts.
- Exponer `costo_pista_puntos` y `puntos_por_calificacion` en la SPA admin.
- Validar claves/valores de configuración.

### Fase 6 — Operación

- Rate limiting en economía y attempts.
- Errores correctos (404 vs 400).
- Estado inicial uniforme.
- Migrar `black` a `suscripcion`.
- Documentación y tests.

---

## 12. Migración y compatibilidad

### 12.1 Saldos existentes

- No recalcular puntos históricos: el saldo actual es la única verdad.
- Si se agrega ledger, crear un asiento de apertura (`saldo_inicial`) por usuario.
- No borrar `puntos_por_juego` ni `vidas` de la config hasta que el frontend y la SPA admin migren.

### 12.2 `user_attempts`

- Agregar `difficulty` con default `standard` para filas viejas.
- Crear un índice nuevo `(user_id, game_id, date, difficulty)` y eliminar el viejo después del backfill.
- No reescribir `score` del narrativo sin una migración explícita; hoy convive 250-1000 con 0-100.

### 12.3 Vidas

- Si se eliminan: dejar de leer `usuarios.vidas`, mantener el campo un tiempo y luego borrarlo.
- Si se hacen por juego: crear `user_game_state` o `user_lives` con `(user_id, game_id)`, backfill desde el global solo si el producto lo define.

### 12.4 Configuración

- `configuracion_economia` se siembra en el primer GET. Si se agregan claves nuevas, usar defaults en código y persistir en la primera lectura/actualización.
- No eliminar `vidas_iniciales` hasta que no queden usuarios sin `vidas`.

---

## 13. Tests necesarios

La suite actual **no tiene tests de economía**. Mínimo:

### Puros / unitarios

- `calculate_grade_and_score` para todos los juegos, estados, grados y estrellas.
- `get_points_for_game`/`get_points_for_grade` si se conservan.
- Validación de configuración (claves, valores, paquetes).

### Integración con Mongo de test

- `consume_life`: éxito, sin vidas, concurrencia.
- `buy_lives`: paquete válido, inválido, saldo insuficiente, tope.
- `unlock_historical_day`: básico, premium, ya desbloqueado, saldo insuficiente, carrera.
- `use_hint`: éxito por juego, saldo insuficiente, pista inexistente, reembolso, idempotencia, dificultad.
- `adjust_user_economy`: suma, resta, clamp, usuario inexistente, auditoría.
- `save_user_attempt`: victoria nueva, repetida, replay, carrera, usuario inexistente, `$inc` fallido.
- `/me` y `/config`: defaults, provisioning, efectos de escritura.

La estrategia completa está en [04-testing.md](04-testing.md).

---

## 14. Preguntas abiertas para el dueño

1. **Vidas:** ¿el contador global debe desaparecer o quedar informativo? ¿Qué hacemos con los usuarios que ya lo tienen?
2. **Vidas por juego:** ¿qué juegos, cuántas, con qué reposición y dónde se persisten?
3. **Intentos vs vidas:** Wordle tiene 6 intentos y Sudoku sugiere “base 3”, pero el backend no lo enforce. ¿Son vidas, intentos o errores?
4. **Puntos por juego vs por calificación:** el catálogo dice 50/50/60/70/80, el código paga 100/90/75/50/0 por nota. ¿Cuál es la regla correcta? ¿Se combinan (base × multiplicador)?
5. **Narrativo:** ¿debe acreditar puntos globales? ¿Con qué monto/rango?
6. **Replay:** ¿se permite repetir un desafío completado? ¿Debe dar puntos? ¿Un solo intento por día/juego/dificultad?
7. **Dificultades:** ¿Crucigrama fácil y difícil son dos slots de puntos o uno?
8. **Pistas:** ¿idempotentes por desafío/celda? ¿Premium gratis o con descuento? ¿Reembolso si no hay pista?
9. **Desbloqueo histórico:** ¿el backend debe impedir leer desafíos no desbloqueados?
10. **Ledger:** ¿se necesita historial de movimientos para auditoría/ranking/soporte?
11. **Panel admin:** ¿el dueño debe poder editar `costo_pista_puntos` y `puntos_por_calificacion`?
12. **Invitados:** el narrativo escribe `user_attempts` con `user_id=0`. ¿Se acumulan? ¿Se limpian?
13. **Datos viejos:** ¿qué hacemos con los puntos otorgados por el modelo anterior y con `puntos_por_juego`/`vidas_maximas`?
14. **Soluciones públicas:** ¿los desafíos futuros y `config.solution` deben seguir siendo públicos?

---

## 15. Anexo: cobertura de búsqueda

Términos buscados en todo el repo (`app/`, `tests/`, `scripts/`, docs):

| Término | Resultado principal |
|---|---|
| `vidas`, `vida` | Solo `economy`, `usuario/schemas.py:47`, textos de desafíos/seeds y docs. No hay lógica per-game. |
| `lives`, `life`, `heart`, `corazon` | Solo nombres `ConsumeLife*`/`BuyLives*`, textos de seeds y un icono `heart` en docs. |
| `puntos`, `points` | `economy`, `user_attempts`, `auth` (`puntos:0`), `usuario/schemas.py:48`, `progreso.examenPuntos`, docs. |
| `coins`, `monedas`, `creditos`, `créditos` | Solo icono `coins` y textos narrativos; no hay divisa. |
| `hints`, `pistas` | `economy.use_hint`, generadores de desafíos y validador de Crucigrama. |
| `S/A/B/C/F`, `calificacion`, `grade` | `economy.puntos_por_calificacion`, `user_attempts.calculate_grade_and_score`, `narrative.rango`/`scores_map`. |
| `score` | `user_attempts`, `narrative.endings_service`. |
| `multiplicador`, `multiplier`, `bonus`, `bono` | Sin multiplicadores económicos; solo `CategoriaCartaEnum.BONUS` del narrativo. |
| `recompensa`, `reward` | Solo textos/docstrings; no hay tabla de recompensas. |
| `ledger`, `transaction`, `movimiento`, `historial_puntos` | Sin colección ni campo; solo palabras del diccionario español. |

**Limitación:** el frontend de jugador no está en este repositorio. No se puede verificar si muestra vidas por juego, si llama `consume-life` ni qué `grade`/`attempts` envía. Las conclusiones sobre vidas por juego son a nivel backend; si el frontend las simula localmente, no queda evidencia acá.
