# Juegos clásicos — contexto para la refactorización

> **Alcance:** Wordle, Sopa de Letras, Sudoku y Crucigrama.
> **Base analizada:** commit `d2a117b` (30/10/2026).
> **Método:** lectura completa de `app/features/daily_challenges/**`, `app/features/daily_challenges/crucigrama_admin/**`, seeds, `user_attempts` y `economy`; verificación puntual del código.
> **Estado:** análisis estático. No se ejecutó la app contra MongoDB ni se modificó código.

> **Errata (2/11/2026):** diferencias verificadas contra el código actual en [05-plan-solucion.md §2](05-plan-solucion.md). Este documento se conserva como foto original del relevamiento.
> **Audiencia:** desarrolladores que se incorporan al backend y van a refactorizar sin romper el frontend.

---

## 0. Cómo usar este documento

1. Leer las secciones 1 a 4 para entender el dominio y el contrato HTTP.
2. Usar las secciones 5 y 6 como mapa de datos y de flujo.
3. La sección 7 explica cómo se genera cada juego.
4. La sección 8 contrasta **comportamiento actual vs. esperado**.
5. La sección 9 lista los defectos conocidos con archivo:línea.
6. La sección 10 fija las reglas para tocar routers.
7. La sección 11 propone un orden de refactor por fases.

Documentos hermanos:

- [Narrativo V1/V2](02-narrativo-v1-v2.md)
- [Economía, puntos y vidas](03-economia-puntos-vidas.md)
- [Testing](04-testing.md)

---

## 1. Resumen ejecutivo

- El backend de los juegos clásicos **no arbitra la partida**. Genera y sirve desafíos, pero la validación de la jugada ocurre en el cliente.
- Los `GET /api/challenges/*` son públicos y devuelven el `config` completo, incluida la solución (`solution`, `cells[].letter`, `words[].word`, `grid`).
- `POST /api/challenges` **no exige autenticación** y hace upsert sobre `daily_challenges`: cualquiera puede sobrescribir el desafío del día y su solución.
- El único camino que acredita puntos es `POST /api/games/attempts`, que acepta `user_id`, `game_id`, `date`, `grade`, `attempts` y `game_data` enviados por el cliente (`app/features/user_attempts/router.py:35-46`, `service.py:163-257`).
- No existe validación server-side de Wordle, Sopa, Sudoku ni Crucigrama.
- El intento (`user_attempts`) no tiene `difficulty`; fácil y difícil de Crucigrama comparten el mismo registro y solo pagan puntos una vez.
- Las vidas por juego no están implementadas en backend. Solo existe el contador global `usuarios.vidas` y el campo informativo `remaining_attempts` que envía el cliente.
- La generación mensual tiene `force=True` por defecto, los seeds de Wordle/Sopa pisan fechas en cada arranque y “hoy” depende de la zona horaria del servidor.
- El Crucigrama es el módulo más maduro: 31 plantillas 7x7, crecimiento 11x11, solver con backtracking, solver AC-3 con bitsets, validador, anclas, vetos globales, recurrencia y panel admin. También concentra la mayor parte del conocimiento técnico que hay que preservar.
- El núcleo puro de Crucigrama es la única parte con tests confiables (ver documento de testing).

---

## 2. Glosario y conceptos clave

| Término | Significado en este backend |
|---|---|
| **Desafío diario** | Documento en `daily_challenges` identificado por `(game_id, date, difficulty)`. Contiene el `config` que consume el cliente. |
| **Intento / partida** | Documento en `user_attempts` identificado por `(user_id, game_id, date)`. Guarda estado, grado, score, estrellas y datos del juego. |
| **Plantilla de Crucigrama** | Documento en `crucigrama_templates`: máscara, anclas, vetos, pistas, solución publicada y agenda. |
| **Ancla** | Palabra fija que se impone en un slot concreto de una plantilla. |
| **Veto global** | Palabra prohibida para todos los crucigramas, persistida en `crucigrama_settings`. |
| **Dificultad** | `standard` para Wordle/Sopa/Sudoku; `facil` o `dificil` para Crucigrama. Es parte de la clave del desafío, pero **no** del intento. |
| **Grado** | Calificación `S/A/B/C/F` calculada por `calculate_grade_and_score`. |
| **Puntos** | Único saldo global en `usuarios.puntos`. Se acreditan por grado, no por juego (ver documento de economía). |
| **Vidas** | Hoy: contador global ornamental en `usuarios.vidas`. No hay vidas por juego. |
| **Racha** | Campo `usuarios.racha` que se lee pero nunca se escribe. |

### Regla de negocio implícita

El backend asume este reparto de responsabilidades:

```text
Backend: genera desafío + guarda intento + acredita puntos
Frontend: muestra tablero, valida jugada, decide grado/errores y llama a /api/games/attempts
```

Ese reparto es la causa raíz de la mayoría de los hallazgos de seguridad y de integridad. Cualquier refactor tiene que decidir explícitamente si se mantiene o se invierte.

---

## 3. Mapa de archivos y dependencias

### 3.1 Archivos principales

| Archivo | Responsabilidad |
|---|---|
| `app/features/daily_challenges/router.py` | Endpoints públicos de desafíos y dos endpoints admin (estado y generación mensual). |
| `app/features/daily_challenges/service.py` | Orquestación: lectura/upsert, generación mensual y autogeneración de mes actual/siguiente. |
| `app/features/daily_challenges/schemas.py` | DTOs de desafío, mes y rango. |
| `app/features/daily_challenges/wordle_generator.py` | Pool de palabras, selección por frecuencia y pistas RAE. |
| `app/features/daily_challenges/sopa_generator.py` | Catálogo temático, grilla 8x8 y pistas RAE. |
| `app/features/daily_challenges/sudoku_generator.py` | Sudoku 9x9 determinista con solución única y 3 niveles internos. |
| `app/features/daily_challenges/crucigrama/generator.py` | Orquestador fácil/difícil: plantilla o crecimiento, celdas, palabras y pistas. |
| `app/features/daily_challenges/crucigrama/growth.py` | Generador por crecimiento para 11x11. |
| `app/features/daily_challenges/crucigrama/solver.py` | Léxico, slots, backtracking CSP y anclas. |
| `app/features/daily_challenges/crucigrama/solver_bitset.py` | Solver AC-3 con dominios como bitsets. |
| `app/features/daily_challenges/crucigrama/validator.py` | Validación estructural y de solubilidad de máscaras. |
| `app/features/daily_challenges/crucigrama/bans.py` | Vetos globales en MongoDB. |
| `app/features/daily_challenges/crucigrama/clues.py` | Pistas curadas. |
| `app/features/daily_challenges/crucigrama/templates_facil.py` | 31 plantillas 7x7 con `pattern` y `fallback_grid`. |
| `app/features/daily_challenges/crucigrama_admin/router.py` | Endpoints del diseñador de máscaras (todos admin). |
| `app/features/daily_challenges/crucigrama_admin/service.py` | Ciclo de vida de plantillas, publicación, agenda, recurrencia y bans. |
| `app/features/daily_challenges/crucigrama_admin/schemas.py` | DTOs del panel admin. |
| `app/features/user_attempts/router.py` | Endpoints de intentos. |
| `app/features/user_attempts/service.py` | Persistencia, cálculo de grado y acreditación de puntos. |
| `app/features/economy/service.py` | Pistas y consumo de puntos relacionados con desafíos. |
| `app/scripts/seed_challenges.py` | Wordle estático Ago–Oct 2026. |
| `app/scripts/seed_sopa_letras.py` | Sopa estática Ago–Oct 2026 + copia local del generador. |
| `app/scripts/seed_sudoku.py` | Dispara generación Sudoku Ago–Dic 2026. |

### 3.2 Grafo de dependencias

```text
app/main.py
 ├─ daily_challenges.router
 │   └─ daily_challenges.service
 │       ├─ wordle_generator ──> core.rae_client
 │       ├─ sopa_generator ────> core.rae_client
 │       ├─ sudoku_generator
 │       ├─ crucigrama.generator
 │       │   ├─ growth ──> solver
 │       │   ├─ solver ──> clues, rae_client
 │       │   ├─ templates_facil
 │       │   └─ clues
 │       ├─ crucigrama.bans
 │       └─ crucigrama_admin.service
 │           ├─ crucigrama.generator
 │           ├─ crucigrama.solver
 │           ├─ crucigrama.validator ──> solver, solver_bitset
 │           ├─ crucigrama.bans
 │           └─ core.rae_client
 ├─ crucigrama_admin.router ──> crucigrama_admin.service
 ├─ user_attempts.router ──> user_attempts.service ──> economy.service (import diferido)
 ├─ economy.router ──> economy.service
 └─ scripts.seed_* ──> service/generadores
```

Punto de acoplamiento a corregir: `daily_challenges.service` importa `crucigrama_admin.service` para resolver plantillas agendadas/recurrentes (`service.py:24-27`). La generación pública depende del módulo admin. No hay ciclo de imports, pero sí un acoplamiento evitable.

`app/features/progreso` no participa de los juegos: solo maneja cursos y no se vincula con `daily_challenges` ni con `user_attempts`.

---

## 4. Contratos HTTP congelados

> **Regla:** estas rutas, métodos, nombres de campos, tipos y códigos de estado son consumidos por el frontend. No cambiar sin coordinar y sin una estrategia de compatibilidad. La columna “Consumidor” debe verificarse contra el frontend real, que no está en este repositorio.

### 4.1 Desafíos diarios — `/api/challenges`

| Método | Ruta | Auth | Request | Response | Servicio |
|---|---|---|---|---|---|
| `GET` | `/api/challenges/today` | Público | `game_id` (default `wordle`), `difficulty` (default `standard`) | `DailyChallengeResponse` con `config` completo | `get_today_challenge` |
| `GET` | `/api/challenges/month` | Público | `year` 2020-2050, `month` 1-12, `game_id`, `difficulty`, `until_today` | `MonthChallengesResponse` | `get_month_challenges` |
| `GET` | `/api/challenges/range` | Público | `game_id` | `ChallengeRangeResponse` | `get_challenge_date_range` |
| `GET` | `/api/challenges/date/{date}` | Público | Path `YYYY-MM-DD`; query `game_id`, `difficulty` | `DailyChallengeResponse` | `get_challenge_by_date` |
| `POST` | `/api/challenges` | **Sin auth** | `DailyChallengeCreateRequest` | `DailyChallengeResponse` | `upsert_challenge` |
| `GET` | `/api/challenges/admin/status` y `/admin/status-year` | Admin | `year`, `game_id` | Estado mensual | `get_challenges_monthly_status` |
| `POST` | `/api/challenges/admin/generate-month` | Admin | `year`, `month`, `game_id`, `force` (default **True**) | Resultado de generación | `generate_and_save_*_month` |

Códigos: 404 si no hay desafío; 400 por mes/año inválido; 422 por Pydantic; 401/403 en admin.

### 4.2 Admin de Crucigrama — `/api/challenges/admin/crucigrama/templates`

Router con `dependencies=[Depends(get_current_admin)]` a nivel de router (`crucigrama_admin/router.py:23-27`).

| Método | Ruta | Request | Response |
|---|---|---|---|
| `POST` | `/validate` | `CrucigramaMaskValidateRequest` | Reporte de validación/solución |
| `GET` | `/global-bans` | — | `{banned_words, updated_by, updated_at}` |
| `PUT` | `/global-bans` | `CrucigramaGlobalBansRequest` | Igual al GET |
| `GET` | `/dictionary/{word}` | Path `word` | `{word, definition, found}` |
| `POST` | `/dictionary` | `CrucigramaDictionaryRequest` | `{definitions, missing}` |
| `GET` | `""` | `status`, `difficulty`, `size`, `limit`, `skip` | `CrucigramaTemplateListResponse` |
| `POST` | `""` | `CrucigramaTemplateCreate` | `CrucigramaTemplateDetail` |
| `GET` | `/{template_id}` | — | `CrucigramaTemplateDetail` |
| `PUT` | `/{template_id}` | `CrucigramaTemplateUpdate` | `CrucigramaTemplateDetail` |
| `DELETE` | `/{template_id}` | — | `{success, deleted_id}` |
| `POST` | `/{template_id}/publish` | `CrucigramaPublishRequest` | `{template, applied_to}` |
| `POST` | `/{template_id}/archive` | — | `CrucigramaTemplateDetail` |
| `POST` | `/{template_id}/apply` | `CrucigramaApplyRequest` | Resultado de aplicación |

Errores: 400 máscara inválida; 404 plantilla inexistente; 409 edición/borrado de publicada o conflicto de agenda; 422 Pydantic.

### 4.3 Intentos — `/api/games/attempts`

| Método | Ruta | Auth | Request | Response |
|---|---|---|---|---|
| `POST` | `/api/games/attempts` | Token **opcional**; si no hay token usa `req.user_id`; 401 solo si faltan ambos | `UserAttemptCreateRequest` | `UserAttemptResponse` con `puntos_ganados`, `puntos_totales_usuario` |
| `GET` | `/api/games/attempts/date/{date}` | Token opcional; `user_id` query pisa al token | `game_id`, `user_id?` | `UserAttemptResponse` o `null` |
| `GET` | `/api/games/attempts` | Token opcional; `user_id` query pisa al token | `user_id?`, `game_id`, `year`, `month` | `UserAttemptsListResponse` |

`UserAttemptCreateRequest` acepta: `user_id?`, `game_id`, `date`, `mode`, `status`, `word?`, `attempts`, `stars?`, `score?`, `grade?`, `guesses`, `game_data?`, `remaining_attempts?` (`app/features/user_attempts/schemas.py:8-21`).

### 4.4 Economía usada por los juegos

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/api/economy/me` | Saldo, vidas, suscripción y costo de pista. |
| `POST` | `/api/economy/use-hint` | Pista para Wordle/Sopa/Sudoku/Crucigrama. |
| `POST` | `/api/economy/unlock-day` | Desbloqueo de fecha histórica. |
| `GET/PUT` | `/api/admin/economy/config` | Configuración económica. |

El detalle completo está en [03-economia-puntos-vidas.md](03-economia-puntos-vidas.md).

---

## 5. Modelo de datos MongoDB

### 5.1 `daily_challenges`

| Campo | Tipo | Notas |
|---|---|---|
| `_id` | ObjectId | Los upserts no definen `_id`; la documentación que dice `"{game_id}_{date}_{difficulty}"` está desactualizada. |
| `game_id` | str | `wordle`, `sopa_letras`, `sudoku`, `crucigrama`, `narrativo`. Se guarda en minúsculas. |
| `date` | str | `YYYY-MM-DD`. |
| `difficulty` | str | `standard` para Wordle/Sopa/Sudoku; `facil`/`dificil` para Crucigrama; `normal` para narrativo. |
| `title` | str | Generado por cada seed/servicio. |
| `config` | dict | Formato dependiente del juego. |
| `created_at` | datetime UTC | `$setOnInsert`. |
| `updated_at` | datetime UTC | `$set` en cada upsert. |
| `source` | str? | Solo `"admin_template"` cuando lo aplica el admin. |
| `updated_by` | str? | Solo en aplicación admin. |

Índices (`app/core/database.py:106-112`):

- único `(game_id, date, difficulty)`;
- `(date)`.

### 5.2 Formatos de `config` por juego

**Wordle** (`wordle_generator.py:83-88`):

```json
{
  "solution": "PERRO",
  "word_length": 5,
  "max_attempts": 6,
  "hints": ["...", "..."]
}
```

**Sudoku** (`sudoku_generator.py:134-146`):

```json
{
  "solution": [[...9x9...]],
  "boards": {"1": [[...]], "2": [[...]], "3": [[...]]},
  "clues": {"1": 40, "2": 34, "3": 28}
}
```

`0` representa celda vacía.

**Sopa de letras** (`sopa_generator.py:202-209`):

```json
{
  "theme": "...",
  "words": ["..."],
  "hints": ["..."],
  "grid_size": 8,
  "grid": [["...8x8..."]],
  "placed_words": [
    {"word": "...", "start": [0, 0], "end": [0, 5], "direction": "H"}
  ]
}
```

**Crucigrama** (`crucigrama/generator.py:168-174`):

```json
{
  "theme": "...",
  "grid_size": 7,
  "cells": [[{"row": 0, "col": 0, "is_block": false, "letter": "A", "number": 1, "across_num": 1, "down_num": null}]],
  "words": [{"id": 1, "number": 1, "direction": "H", "word": "CASA", "length": 4, "row": 0, "col": 0, "coords": [[0,0]], "clue": "..."}],
  "total_words": 10,
  "date": "2026-10-30"
}
```

`cells[].letter` y `words[].word` contienen la solución completa.

### 5.3 `user_attempts`

| Campo | Tipo |
|---|---|
| `user_id` | int |
| `game_id` | str |
| `date` | str |
| `mode` | str (`daily` por defecto, sin enum) |
| `status` | `in_progress`, `completed`, `failed` |
| `word` | str/null |
| `attempts` | int |
| `stars` | int 1-3 |
| `score` | int |
| `grade` | `S/A/B/C/F`/null |
| `guesses` | lista arbitraria |
| `game_data` | dict arbitrario |
| `remaining_attempts` | int |
| `created_at`, `updated_at` | datetime UTC |

Índices (`app/core/database.py:114-120`):

- único `(user_id, game_id, date)`;
- `(user_id, date DESC)`.

**No existe `difficulty`** ni en el documento ni en el índice. Para Crucigrama, fácil y difícil comparten el mismo intento.

### 5.4 `crucigrama_templates`

Campos principales: `id` (uuid hex), `name`, `theme`, `pattern`, `size`, `difficulty`, `anchors`, `banned_words`, `clue_overrides`, `status` (`draft`/`published`/`archived`), `scheduled_date`, `monthly_day`, `total_words`, `solution_grid`, `clues`, `published_config`, `last_seed`, `notes`, `created_by`, `created_at`, `updated_at`, `published_at`, `published_by`, `archived_at`, `archived_by`.

Índices (`app/core/database.py:141-164`):

- único `id`;
- `(status, scheduled_date, difficulty)`;
- único parcial `(scheduled_date, difficulty)` para publicadas;
- único parcial `(monthly_day, difficulty)` para publicadas.

### 5.5 `crucigrama_settings`

Documento `_id="global_bans"` con `banned_words: [str]`, `updated_by`, `updated_at` (ISO string). Sin índice adicional.

---

## 6. Flujo actual end-to-end

### 6.1 Pipeline común

```text
Arranque (main.lifespan)
  └─ seeds Wordle/Sopa/Sudoku + ensure_current_and_next_month_generated
      └─ cada 12 h vuelve a asegurar mes actual y siguiente

Cliente
  ├─ GET /api/challenges/today|date|month  → recibe config con solución
  ├─ valida la jugada localmente
  └─ POST /api/games/attempts             → guarda intento y acredita puntos
```

1. **Arranque:** `main.lifespan` conecta Mongo, siembra estados y lanza una tarea de fondo con los seeds y `ensure_current_and_next_month_generated` (`app/main.py:40-76`). Luego repite la generación cada 12 horas (`app/main.py:69-74`).
2. **Autogeneración:** verifica mes actual y siguiente para `sudoku`, `wordle`, `sopa_letras`, `crucigrama` y `narrativo`; si faltan días, llama al generador (`daily_challenges/service.py:618-678`).
3. **Lectura del desafío:** el cliente llama `GET /api/challenges/today` o `/date/{date}`. El backend devuelve el documento completo, incluida la solución.
4. **Validación de la jugada:** no existe endpoint backend que reciba y valide jugadas de ninguno de los cuatro juegos. La comparación contra `config` ocurre en el cliente.
5. **Registro del intento:** el cliente llama `POST /api/games/attempts` con `status`, `attempts`, `grade`/`game_data`, etc.
6. **Cálculo y puntos:** `save_user_attempt` calcula `grade/score/stars`, hace upsert y, si es una victoria nueva, incrementa `usuarios.puntos` (`user_attempts/service.py:163-274`).
7. **Vidas:** no hay consumo automático. Solo existe el endpoint manual `POST /api/economy/consume-life`, que descuenta una vida global.

### 6.2 Matriz por juego

| Juego | Generación/selección | Validación backend | Grado si el cliente no envía `grade` | Puntos | Vidas específicas |
|---|---|---|---|---|---|
| Wordle | Seed estático Ago–Oct + generación mensual; primera palabra no usada del pool por frecuencia | No | Según `attempts`: ≤2 S, ≤4 B, resto C | `puntos_por_calificacion` | No |
| Sopa | Seed estático Ago–Oct + generación mensual; tema y grilla determinísticos por fecha | No | Según `game_data.errors`: 0 S, ≤2 B, resto C | `puntos_por_calificacion` | No |
| Sudoku | Generación mensual determinística por fecha | No | Según `errors` y `remaining_attempts` | `puntos_por_calificacion` | No |
| Crucigrama | Plantilla agendada > plantilla recurrente > generador; dos dificultades | No | Según `game_data.errors`: 0 S, ≤2 B, resto C | `puntos_por_calificacion` | No |

---

## 7. Cómo se genera cada juego

### 7.1 Wordle

1. **Siembra:** `seed_wordle_challenges` carga listas estáticas de agosto, septiembre y octubre 2026 y hace upsert con `$set` (`seed_challenges.py:109-146`). Se ejecuta en cada arranque.
2. **Generación mensual:** `generate_and_save_wordle_month` recupera soluciones ya usadas, recorre los días y:
   - si el día existe y no es `force`, lo salta;
   - si existe y es `force`, conserva la solución y regenera pistas (`service.py:380-389`);
   - si no existe, llama `generate_wordle_challenge(date_str, used_words, index=day)`.
3. **Selección:** `pick_wordle_word` devuelve la primera palabra del archivo `app/data/palabras_wordle_5_letras.txt` (4.933 palabras ordenadas por frecuencia) que no esté usada; si el pool se agota, usa `pool[fallback_index % len(pool)]` (`wordle_generator.py:64-76`).
4. **Pistas:** RAE o, si falla, vocales/última letra + primera letra (`wordle_generator.py:46-62`).
5. **Lectura:** `GET /api/challenges/today?game_id=wordle&difficulty=standard` devuelve `config.solution`.
6. **Validación:** inexistente en backend. `guesses` se guarda sin verificar (`user_attempts/service.py:219`).

### 7.2 Sopa de letras

1. **Siembra estática:** `seed_sopa_letras_challenges` usa `SOPA_LETRAS_RAW_DATA` y una copia local de `generate_word_search` (`seed_sopa_letras.py:8-166`). Hace `$set` en cada arranque.
2. **Generación mensual:** `generate_and_save_sopa_month` llama `generate_sopa_challenge_for_date(date_str)` para cada día faltante (`service.py:429-511`).
3. **Selección:** `seed_val = int(date.replace("-", ""))`; tema por `seed_val % len(SOPA_THEMES_CATALOG)`; 4 palabras; grilla 8x8 solo horizontal/vertical (`sopa_generator.py:186-209,111-169`).
4. **Pistas:** enriquecidas con RAE (`sopa_generator.py:171-184`).
5. **Lectura:** `config` incluye `words`, `grid` y `placed_words`.
6. **Validación:** inexistente; el cliente compara selecciones. El grado usa `game_data.errors`.
7. **Riesgo:** el seed duplica el generador y su propio catálogo; pueden divergir.

### 7.3 Sudoku

1. **Generación:** `generate_sudoku_for_date` usa `random.Random(f"sudoku_{date_str}")`, llena una solución 9x9 con backtracking, remueve celdas preservando unicidad y deriva tres tableros (`sudoku_generator.py:82-146`).
2. **Siembra:** `seed_sudoku_challenges` dispara la generación Ago–Dic 2026; `ensure_current_and_next_month_generated` cubre mes actual/siguiente.
3. **Lectura:** `config` incluye `solution` y `boards`.
4. **Validación:** inexistente; el cliente elige nivel y valida. No se registra qué nivel usó.
5. **Grado:** `calculate_grade_and_score` (`user_attempts/service.py:77-87`):
   - S si `errors == 0` y (`remaining_attempts >= 3` **o `remaining_attempts == 0`**);
   - B si `errors <= 1` o `remaining_attempts == 2`;
   - C en el resto.
   El `== 0` hace que “sin vidas” se califique como perfecto.

### 7.4 Crucigrama

#### Prioridad de resolución

`generate_and_save_crucigrama_month` recorre cada día y cada dificultad (`facil`, `dificil`) y aplica (`daily_challenges/service.py:513-616`):

1. `get_scheduled_published_config(date, diff)`: plantilla publicada con `scheduled_date` exacta.
2. `get_recurring_published_config(date, diff, global_bans)`: plantilla publicada con `monthly_day` igual al día del mes, re-resuelta con semilla de la fecha.
3. `generate_crucigrama_challenge_for_date(date, diff, banned_words=global_bans)`: generador.

#### Generador fácil (7x7)

- 31 plantillas en `templates_facil.py:7-690`, cada una con `theme`, `pattern` y `fallback_grid`.
- Selección: `CRUCIGRAMA_TEMPLATES[int(date) % 31]` (`generator.py:198-200`). Determinística por fecha, pero se repite cada 31 días.
- Resolución: `_parse_template_slots` + `_solve_crucigrama_backtracking(prefer_curated=True, banned_words=banned)` (`generator.py:202-206`).
- Si no hay solución: usa `fallback_grid` **sin filtrar vetos ni validar léxico** (`generator.py:218-220`); solo se registra un warning si hay palabras vetadas.
- Construcción final: numera celdas, arma `cells`, `words`, `coords` y enriquece pistas con `CURATED_CLUES`, overrides y RAE en un `ThreadPoolExecutor(max_workers=8)` (`generator.py:38-174`).

#### Generador difícil (11x11)

- No usa plantillas: crecimiento puro (`generator.py:224-235`).
- Tema fijo `"Palabras Cruzadas"`.
- Objetivo 15-28 palabras; si no alcanza 15 solo se emite un warning.
- No se valida el patrón generado con `validate_pattern`.
- `growth.py` garantiza el invariante de no-contacto y crece desde una palabra semilla; hasta 40 intentos (`growth.py:35-363`).

#### Solver y validador

- `solver.py`: léxico de `app/data/acentos_todas_palabras.json` (48.623 claves, longitudes 3-10), índices por longitud/posición/letra, backtracking con MRV/Degree, forward checking, tope de 150 candidatos por rama y soporte de anclas/vetos.
- `solver_bitset.py`: AC-3 con dominios como bitsets para máscaras densas; MRV + backtracking con presupuesto de nodos/segundos.
- `validator.py`: tamaños 7 y 11; mínimos de 5 y 12 palabras; validación de estructura, cobertura, simetría (solo warning) y solubilidad con presupuestos crecientes.
- Detalle de rendimiento: la propagación AC-3 reencola vecinos excepto el que originó el recorte (`solver_bitset.py:136-138`). Es una propagación incompleta que puede explorar de más, pero no produce soluciones inválidas.

#### Anclas, vetos, recurrencia y admin

- **Anclas:** `anchors: {slot_id: palabra}`; se validan con `normalize_preassigned` (slot, alfabética, longitud, léxico, no repetida, cruces compatibles) y se aplican en validación, publicación y recurrencia. No hay tope duro.
- **Vetos globales:** `crucigrama_settings._id="global_bans"`; se aplican al generador, al validador admin y a la publicación, pero **no retroactivamente** a desafíos ya generados y **no se revalidan** en plantillas agendadas exactas.
- **Recurrencia:** `scheduled_date` (fecha exacta) y `monthly_day` (día del mes). Prioridad exacta > recurrente > generador. El día 31 no existe en febrero.
- **Ciclo de vida admin:** crear (draft), editar (prohibido si publicada), publicar (valida estructura/solución/léxico/vetos/anclas/conflictos), archivar, eliminar (solo no publicadas), aplicar a fecha.
- **Publicación:** si tiene `scheduled_date`, aplica inmediatamente a `daily_challenges` con `force=True`.
- **Bans globales:** reemplaza la lista completa, con límite de 300.

---

## 8. Comportamiento actual vs. comportamiento esperado

> Las propuestas de “esperado” son recomendaciones de refactor. Las que dependen de producto están marcadas como **[decisión pendiente]**.

| Área | Actual | Esperado recomendado |
|---|---|---|
| **Autorización de desafíos** | `POST /api/challenges` público; cualquiera sobrescribe el desafío. | Exigir admin o eliminar el endpoint público. Si la SPA admin no envía Bearer, coordinar primero. **[decisión pendiente: mantener por compatibilidad o cerrar]** |
| **Exposición de soluciones** | Los GET devuelven `solution`, letras y palabras. | El contrato de jugador no debe incluir la solución. Estrategia compatible: nuevo endpoint/DTO sanitizado y mantener el actual hasta migrar el frontend. No borrar campos de golpe. |
| **Validación de jugadas** | El cliente valida y manda `grade`/`errors`. | El servidor debe validar la submission contra el desafío y calcular el grado. Mantener `POST /api/games/attempts` aceptando el payload actual, pero ignorar los campos de confianza y agregar `submission` opcional. |
| **Identidad** | `user_id` del body si no hay token; query pisa al token en GET. | Ignorar `user_id` del cliente; usar siempre el del token. Si se necesita compatibilidad, aceptar el body solo cuando no haya token y mientras se migra. |
| **Idempotencia de puntos** | `find_one` + `$inc`; replay por cambio de estado; carrera. | Transición de estado atómica y acreditación única. Registrar `puntos_ganados` o un ledger. Ver documento de economía. |
| **Dificultad** | El intento no guarda `difficulty`; fácil/difícil colisionan. | Agregar `difficulty` opcional al intento y al índice único; migrar datos existentes con default. **[decisión pendiente: ¿un intento por dificultad o uno por día?]** |
| **Vidas por juego** | No existen; solo global y `remaining_attempts` del cliente. | Modelo explícito por juego si el producto lo requiere; el servidor debe descontar y bloquear. Si no se requieren, eliminar el global y los endpoints. **[decisión pendiente]** |
| **Generación mensual** | `force=True` por defecto; puede reescribir días con intentos. | Default `force=False`; bloquear regeneración de fechas con intentos o versionar soluciones. |
| **Seeds de arranque** | Wordle/Sopa pisan Ago–Oct 2026 en cada boot. | `$setOnInsert` o seed opt-in por entorno; nunca pisar datos editados. |
| **Zona horaria** | `datetime.now()` del servidor; Docker sin `TZ`. | Fijar `America/Argentina/Buenos_Aires` o recibir la fecha del cliente con validación. |
| **Generación pesada** | CPU-bound dentro del event loop. | `asyncio.to_thread` o worker/background task; no bloquear requests. |
| **Fallback de Crucigrama** | Usa `fallback_grid` sin vetos/léxico; contiene `ALBANIL`. | Validar el fallback o corregirlo (`ALBAÑIL`); nunca publicar palabras vetadas. |
| **Estado mensual de Crucigrama** | Cuenta documentos sin `difficulty`; un mes con solo fácil puede figurar completo. | Contar por `(game_id, difficulty)` y validar `config` mínima, no solo existencia. |
| **Pistas de Crucigrama** | `use_hint` busca sin `difficulty`; puede revelar el tablero equivocado. | Incluir `difficulty` en la pista (query o body opcional). |
| **Rangos de fecha** | `/range` ignora `difficulty`. | Incluir `difficulty` o documentar que el rango es combinado. |
| **Mayúsculas** | GET compara `game_id`/`difficulty` sin normalizar; el upsert guarda minúsculas. | Normalizar en lectura o documentar el contrato en minúsculas. |

---

## 9. Hallazgos priorizados

### Alta

1. **`POST /api/challenges` sin autenticación.** `daily_challenges/router.py:78-84`; el schema acepta `game_id`, `date`, `difficulty` y `config` arbitrarios; `upsert_challenge` hace upsert directo (`service.py:143-172`). Cualquiera puede sobrescribir el desafío y su solución.
2. **Todos los GET filtran la solución.** `DailyChallengeResponse.config` es `Dict[str, Any]`; Wordle expone `solution`, Sudoku `solution/boards`, Sopa `words/grid/placed_words`, Crucigrama `cells[].letter/words[].word`.
3. **Intento y puntos controlados por el cliente.** `UserAttemptCreateRequest` acepta `user_id`, `game_id`, `date`, `grade`, `score`, `attempts`, `guesses`, `game_data`, `remaining_attempts`; `save_user_attempt` no verifica que el desafío exista ni que la solución sea correcta.
4. **Doble conteo por regresión de estado y por carrera.** `existing` se lee antes del upsert; volver de `completed` a `in_progress`/`failed` y luego a `completed` vuelve a acreditar; dos POST concurrentes también.
5. **IDOR en lectura de intentos.** `effective_user_id = user_id or token_user_id`; cualquier usuario autenticado puede leer los intentos de otro pasando `user_id`. El token se decodifica sin validar `activo` ni permisos de servicio.
6. **No hay validación server-side de ninguna jugada clásica.** `guesses` se guarda sin comparar; `game_data` se usa para calcular grado sin validación.
7. **Vidas por juego no implementadas.** Solo `usuarios.vidas` global y `remaining_attempts` informativo. El grado de Sudoku con `remaining_attempts == 0` da S.
8. **`force=True` por defecto y `apply` pueden destruir historial.** `generate-month` fuerza regeneración; `apply_template` usa `force=True`; no se consulta si hay intentos.
9. **`puntos_por_juego` está muerto.** La acreditación usa `puntos_por_calificacion`; cambiar puntos por juego no tiene efecto.
10. **Desbloqueo histórico y Premium no se aplican.** Se cobran puntos y se guarda `dias_desbloqueados`, pero ningún endpoint de desafíos lo consulta.
11. **`use_hint` no distingue dificultad y cobra antes de validar.** Puede revelar el tablero equivocado y no reembolsa si no hay contenido.
12. **`user_attempts` no tiene `difficulty`.** Fácil y difícil comparten intento y solo pagan una vez.

### Media

13. **Estado mensual de Crucigrama cuenta mal.** Cuenta documentos sin `difficulty`; un mes con solo fácil puede figurar completo.
14. **Zona horaria del servidor.** El día cambia a las 21:00 ART si el contenedor corre en UTC.
15. **Fallback del fácil ignora vetos y léxico.** `ALBANIL` no está en el léxico (`ALBAÑIL` sí).
16. **Plantillas agendadas no revalidan vetos ni forma del config.** Un `config` sin `theme` lanza `KeyError` y aborta la generación.
17. **Seeds pisan cambios manuales.** Wordle/Sopa reescriben Ago–Oct 2026 en cada arranque.
18. **Chequeos de “mes completo” aceptan documentos corruptos.** Cuentan documentos, no configs válidas. Un `RuntimeError` del difícil aborta el mes completo.
19. **Generación mensual bloquea el event loop.** Generadores CPU-bound y RAE sincrónico (`urlopen`, `time.sleep`) sin `asyncio.to_thread`.
20. **No hay transacción entre intento y puntos.** Crash o carrera dejan intento sin puntos o puntos duplicados.
21. **Narrativo escribe intentos por fuera de la economía.** Ver documento de narrativo.
22. **`buy_lives` ignora `vidas_maximas`.**
23. **`unlock_historical_day` tiene carrera y no valida existencia.**
24. **Contrato de dificultad inconsistente.** El default `standard` no existe para Crucigrama; omitirlo devuelve 404.
25. **Plantilla: dificultad y tamaño no se validan entre sí.** Un 11x11 puede marcarse `facil` y publicarse en la franja fácil.
26. **`get_today_challenge` no genera bajo demanda.** Si falta el día, 404 hasta el próximo ciclo.
27. **El generador difícil puede producir tableros pobres.** Devuelve la mejor tentativa aunque tenga menos de 15 palabras.
28. **Seeds de Sopa duplican el generador y el catálogo.**
29. **Sin rate limiting en endpoints de juego.**
30. **`init_indexes` se traga errores.** Si el índice único no se crea, la app sigue sin la garantía de unicidad.

### Baja

31. Las 31 plantillas “simétricas” no son simétricas según `_is_symmetric`; el validador solo avisa.
32. `/range` ignora dificultad.
33. Los GET son sensibles a mayúsculas.
34. `POST /api/challenges` acepta fechas imposibles (`2026-99-99`).
35. `racha` no se actualiza.
36. Usuarios nuevos sin vidas iniciales.
37. El alias `/api/economy/admin/config` está bloqueado por el middleware.
38. El pool de Wordle incluye 49 palabras con `Ñ`; el seed usa “OTOÑO”.
39. Código muerto: `get_points_for_game`, `get_points_for_grade`, imports sin uso, `attempt_budgets` ignorado, duplicación de Sopa.
40. Documentación interna desactualizada.
41. `_apply_config_to_date` no limpia `source`/`updated_by`.
42. No se puede limpiar `monthly_day`/`scheduled_date` de una plantilla publicada.

---

## 10. Reglas para tocar routers sin romper el frontend

1. **No cambiar paths, métodos ni nombres de campos.** El frontend consume snake_case (`game_id`, `date`, `remaining_attempts`, etc.).
2. **No eliminar campos de respuesta.** Si un campo deja de tener sentido (`solution`), mantenerlo hasta que el frontend migre y agregar un DTO/endpoint nuevo.
3. **No cambiar códigos de estado en el camino feliz.** Agregar errores nuevos solo para casos que hoy no existen.
4. **Los cambios de autenticación son comportamiento nuevo.** Agregar `Depends(get_current_admin)` a `POST /api/challenges` puede romper la SPA admin si no envía Bearer. Verificar el frontend antes.
5. **La lógica nueva va en services.** Los routers deben quedar delgados: validar request, llamar service, serializar response.
6. **Los fixes de seguridad que cambian contrato se hacen con feature flag o endpoint nuevo.** Ejemplo: `POST /api/games/attempts` sigue aceptando el payload actual, pero el servidor ignora `grade` y valida `submission` si viene.
7. **Mantener compatibilidad de datos.** Agregar `difficulty` al intento con default; no romper el índice único existente sin migración.
8. **Tests de caracterización antes de tocar.** Congelar request/response actuales de cada endpoint antes de refactorizar.
9. **No tocar `app/static/admin` ni contratos de la SPA sin coordinación.**
10. **La fecha y la zona horaria son parte del contrato.** Un cambio de “hoy” puede duplicar o perder intentos.

---

## 11. Plan de refactor por fases

### Fase 0 — Red de seguridad

- Crear tests de caracterización de los endpoints de desafíos, intentos y admin de Crucigrama.
- Congelar respuestas actuales (incluida la solución) para detectar cambios accidentales.
- Documentar qué consume el frontend (no está en este repo).

**Criterio de aceptación:** los tests pasan contra el código actual sin cambios.

### Fase 1 — Extraer lógica sin cambiar comportamiento

- Mover la orquestación de `daily_challenges/service.py` a módulos por juego (`wordle/`, `sopa/`, `sudoku/`, `crucigrama/`).
- Separar generación, persistencia y serialización.
- Eliminar imports cruzados `daily_challenges -> crucigrama_admin` mediante una interfaz de plantillas.
- Mantener routers y respuestas idénticas.

**Criterio:** mismos bytes de respuesta en los tests de caracterización.

### Fase 2 — Cerrar agujeros graves

- `POST /api/challenges`: exigir admin (o deshabilitar en producción).
- Intentos: ignorar `user_id` del cliente; usar el del token.
- Acreditación: transición atómica + idempotencia (ver documento de economía).
- `init_indexes`: fallar ruidosamente si no puede crear un índice único.

**Criterio:** tests de seguridad; ningún endpoint admin accesible sin token; replay imposible.

### Fase 3 — Validación server-side (compatible)

- Agregar un validador por juego que reciba la submission y calcule `errors`, `grade` y `score`.
- Mantener `POST /api/games/attempts` aceptando el payload actual; si viene `submission`, el servidor manda.
- Agregar un endpoint nuevo de verificación si el frontend necesita feedback inmediato.

**Criterio:** un cliente que manda `grade: "S"` sin submission no recibe puntos; el frontend actual sigue funcionando para el camino feliz.

### Fase 4 — Modelo de datos

- Agregar `difficulty` al intento y al índice único (migración con default).
- Definir vidas por juego si el producto lo requiere.
- Agregar ledger de puntos (documento de economía).

### Fase 5 — Operación

- `force=False` por defecto; bloquear regeneración con intentos.
- Seeds idempotentes/opt-in.
- Zona horaria fija.
- Generación en threadpool/worker.
- Limpiar código muerto y documentación.

---

## 12. Tests de caracterización recomendados

Mínimo antes de tocar routers:

1. `GET /api/challenges/today` para cada juego: status, shape y campos de `config`.
2. `GET /api/challenges/date/{date}` con fecha existente e inexistente.
3. `GET /api/challenges/month` con y sin `until_today`.
4. `POST /api/challenges` con payload válido (documentar que hoy es público).
5. `POST /api/games/attempts`: victoria nueva, intento repetido, cambio de estado, `user_id` sin token.
6. Admin de Crucigrama: `validate`, `publish`, `apply`, `archive`, `global-bans`.
7. Generadores puros: determinismo por fecha, integridad de grilla Sopa, unicidad Sudoku, Wordle del pool.

La estrategia completa está en [04-testing.md](04-testing.md).

---

## 13. Preguntas abiertas para el dueño

1. ¿El cliente debe seguir recibiendo la solución? Si no, ¿cómo migramos el frontend sin romperlo?
2. ¿Se implementa validación server-side? ¿Qué juegos primero?
3. ¿Las vidas son por juego o se eliminan? ¿Qué juegos, cuántas y cómo se reponen?
4. ¿Los puntos se pagan por calificación, por juego, o base × multiplicador?
5. ¿Fácil y difícil de Crucigrama son dos intentos o uno?
6. ¿Se permite registrar intentos de fechas pasadas/futuras? ¿Se valida suscripción/desbloqueo?
7. ¿Se puede regenerar un mes con intentos? ¿Se versionan soluciones?
8. ¿Los vetos globales aplican retroactivamente a plantillas agendadas y al fallback?
9. ¿La dificultad debe derivarse del tamaño (7→fácil, 11→difícil)?
10. ¿Cuál es la zona horaria oficial de “hoy”?
11. ¿Se mantiene `POST /api/challenges` por compatibilidad o se restringe?
12. ¿Los seeds deben pisar datos existentes?

---

## 14. Anexo: archivos y comandos útiles

- `app/features/daily_challenges/router.py`
- `app/features/daily_challenges/service.py`
- `app/features/daily_challenges/crucigrama/generator.py`
- `app/features/daily_challenges/crucigrama/growth.py`
- `app/features/daily_challenges/crucigrama/solver.py`
- `app/features/daily_challenges/crucigrama/solver_bitset.py`
- `app/features/daily_challenges/crucigrama/validator.py`
- `app/features/daily_challenges/crucigrama_admin/service.py`
- `app/features/user_attempts/service.py`
- `app/core/database.py`
- `app/scripts/seed_challenges.py`
- `app/scripts/seed_sopa_letras.py`

Comandos de referencia:

```bash
# Tests puros de Crucigrama (no requieren Mongo)
python -m pytest tests/test_crucigrama_anclas.py tests/test_crucigrama_bitset.py \
  tests/test_crucigrama_validator.py tests/test_crucigrama_bans.py \
  -k "not test_generacion_mensual_recibe_vetos_globales" -q

# Recolección completa
python -m pytest --collect-only -q

# Generador de crecimiento (script de diagnóstico, no test)
python scripts/test_growth_generator.py
```
