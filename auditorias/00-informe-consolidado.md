# 00 — Informe consolidado de auditorías

**Proyecto:** Backend "Mayores Actualizaciones" (SIPI Back) — FastAPI + MongoDB
**Ruta:** `C:\Users\nmonti\Desktop\proyectos\backend\mayores_actualizacionesSIPI-BACK`
**Fecha:** 19/10/2026
**Método:** 6 auditorías ejecutadas en paralelo por subagentes independientes. 100% análisis estático: no se ejecutó la app ni pytest, no se modificó ninguna línea de código y no se tocó la base de datos. El `.env` se leyó únicamente para evaluar higiene de secretos (sus valores no aparecen en ningún informe).

---

## Índice de informes

| # | Informe | Área | Tamaño |
|---|---------|------|--------|
| 01 | [Arquitectura y modularidad](01-arquitectura-y-modularidad.md) | Caja negra, dependencias, duplicación, refactor | 21 hallazgos |
| 02 | [Persistencia y flujo de datos](02-persistencia-y-flujo-de-datos.md) | Colecciones, índices, IDs, concurrencia, journey | 20 hallazgos |
| 03 | [Auditoría de seguridad](03-auditoria-de-seguridad.md) | AuthN/AuthZ, secretos, infra, superficie | 6 críticos / 6 altos / 11 medios / 10 bajos |
| 04 | [Desacoplamiento microservicios](04-desacoplamiento-microservicios.md) | Cursos / Juegos / Auth, plan strangler | 82 endpoints inventariados |
| 05 | [Eficiencia y rendimiento](05-eficiencia-y-rendimiento.md) | Event loop, Mongo, cachés, escalabilidad | 29 hallazgos |
| 06 | [Testing y calidad](06-testing-y-calidad.md) | Cobertura, riesgos, estrategia de tests | 2 tests existentes |

---

## 1. Hallazgos transversales (los que hay que mirar primero)

Estos aparecieron corroborados por varios informes a la vez, lo que les da alta confianza.

### P0 — Contención inmediata

| # | Hallazgo | Evidencia | Corroboran |
|---|----------|-----------|------------|
| 1 | **Endpoints de administración SIN autenticación**: panel admin del narrativo (CRUD, uploads, seeds, `generar-mes`) y upsert/operaciones admin de desafíos diarios. Cualquiera puede sobrescribir el desafío del día (incluida la solución) o el contenido narrativo. | `app/features/narrative/admin/router.py:64-320`, `app/features/daily_challenges/router.py:77-113` | 01, 02, 03, 04, 06 |
| 2 | **Identidad forjable y secretos por defecto**: `JWT_SECRET` con default embebido y efectivo en la práctica; `.env` real queda dentro de la imagen Docker; credenciales default (`admin123`) y PIN fijo (`999999`) sembrados en el arranque. | `app/core/config.py:14,27-28`, `Dockerfile:15` + `.dockerignore`, `app/scripts/init_db.py:64-93` | 01, 03, 04, 06 |
| 3 | **Fraude de puntos + IDOR en intentos**: el `user_id` de body/query pisa al del token y los puntos se incrementan con el `score` que envía el cliente (duplicable por carrera). | `app/features/user_attempts/router.py:39-99`, `service.py:46,85-95` | 01, 02, 03, 06 |
| 4 | **Account takeover en `modificar-email-registro`**: cambia el email de cuentas pendientes sin verificar posesión y reenvía el código (que es el PIN permanente). | `app/features/auth/service.py:365-408` | 03 |
| 5 | **CORS universal con credenciales**: regex `^https?://.*$` + `allow_credentials=True`. | `app/main.py:91-98` | 01, 03, 06 |
| 6 | **Rate limiting evadible**: confía en `X-Forwarded-For`; además PIN permanente sin bloqueo ni comparación en tiempo constante. | `app/core/rate_limit.py:40-53`, `app/features/auth/service.py:90-125` | 03, 06 |

### P1 — Integridad y operación

| # | Hallazgo | Evidencia | Corroboran |
|---|----------|-----------|------------|
| 7 | **Sin transacciones ni control de concurrencia**: MongoDB standalone + flujos multi-documento (intento+puntos, array embebido `progresos` con read-modify-write, `narrative_runs` con `replace_one` completo). | `docker-compose.yml:72-97`, `progreso/service.py:37-46,85-88`, `narrative/game/transition_service.py:122` | 02, 05, 06 |
| 8 | **Datos duplicados/desincronizados**: `usuarios.progresos` vs `user_attempts` sin sincronización; `usuarios.puntos` se escribe y nunca se lee; invitados anónimos comparten `user_id=0` (partidas cruzadas y borrados entre sí). | `user_attempts/service.py:85-95`, `narrative/game/router.py:64-76`, `endings_service.py:136` | 02, 06 |
| 9 | **Arranque costoso y frágil**: seeds reescriben ~185 documentos en cada arranque; generación mensual pesada dentro del lifespan; cliente RAE sincrónico (`urlopen` + `time.sleep`) bloqueando el event loop; `generate-month` con `force=true` por defecto en request path. | `app/main.py:36-42`, `seed_challenges.py:109-146`, `rae_client.py:115-190`, `daily_challenges/router.py:99-113` | 05 (y 01, 02) |
| 10 | **ETL MySQL→Mongo riesgoso**: hace upsert por `{"id": ...}` cuando el comentario dice "por email" → puede pisar usuarios existentes o abortar por colisión de email. Imágenes subidas no persisten (sin volumen). Con BD fresca el narrativo da 500. | `scripts/migrate_from_mysql.py:105-110`, `docker-compose.yml:37-69`, `setup_service.py:80,87` | 02 |

### P2 — Calidad y deuda estructural

| # | Hallazgo | Evidencia | Corroboran |
|---|----------|-----------|------------|
| 11 | **Testing casi inexistente**: solo 2 tests del narrativo (happy path, DB real, destructivos); sin pytest/httpx en requirements, sin conftest ni CI. | `tests/test_narrative_game.py`, `tests/test_narrative_v2_game.py` | 06 |
| 12 | **Duplicación y caja negra**: `narrative/rule_engine.py` y `event_director.py` duplican a los de `engine/`; god files (`seed_narrative.py` 1789 líneas, `crucigrama_generator.py` 1085); helpers duplicados de sopa; caché de recursos sin invalidación; ECA anunciado sin implementar (`AMORTIGUAR_DANIO`) y triggers `EN_EVENTO_*`/`AL_FINAL_PARTIDA` nunca despachados. | `app/features/narrative/**`, `app/scripts/seed_narrative.py`, `daily_challenges/service.py` | 01 |
| 13 | **Docs internas desactualizadas**: contradicen el código en varios puntos (auth forzada en admin, RLS anti-IDOR "completo", `?fecha` vs `?date`, 404 vs 401, endpoint que devuelve cosas distintas). | `docs_interna/*`, `README.md` | 01, 03, 04, 06 |

---

## 2. Panorama por área

### 01 — Arquitectura y modularidad
21 hallazgos con severidad, grafos de dependencias (mermaid) y mapa de capas actual vs. propuesta. Conclusión: el sistema **no es del todo una caja negra** (hay features y services), pero el módulo narrativo y los generadores son difíciles de seguir: lógica de negocio en routers, duplicación v1/v2, estado global (`random.seed`) y efectos secundarios en import/arranque. Incluye **plan de modularización en 16 fases no rompiente** (compatible con el contrato 100% del frontend).

### 02 — Persistencia y flujo de datos
Inventario de **13 colecciones** con dueños e índices, journey end-to-end (registro/login → desafíos → intentos → progreso → narrativo), análisis de intersecciones y riesgos del ETL. Conclusiones clave: el flujo funciona en el camino feliz pero se rompe con BD fresca; hay carreras y datos huérfanos posibles en casi todos los flujos multi-documento; fechas naive con contenedor UTC (el "día" cambia a las 21:00 ART); PIN en claro expuesto en respuestas; admin con PIN fijo.

### 03 — Auditoría de seguridad
Matriz de autenticación endpoint por endpoint + contraste con `README_SEGURIDAD.md` (varios ✅ documentados **no se cumplen** en el código). Lo que sí está bien: BCrypt, HS256 fijo, RLS real en `/progreso`, anti-mass-assignment público, `re.escape` anti-ReDoS y hardening básico de compose/Caddy. Incluye plan de remediación priorizado.

### 04 — Desacoplamiento microservicios
Corte propuesto: **Auth = auth + usuario**, **Cursos = progreso**, **Juegos = daily_challenges + user_attempts + narrative** (+ `rae_client` y assets). El bloqueante real no son los routers sino **los datos**: `progresos` embebido en `usuarios`, `user_attempts` escribe `usuarios.puntos` y `get_current_user` consulta `usuarios` en cada request. Plan **Strangler Fig en 6 fases** con gateway estable desde el día 1 (los 82 endpoints + 4 de sistema + 2 mounts mantienen sus rutas), identidad por **JWT/JWKS** + introspección selectiva, bases lógicas separadas. Incluye **20 preguntas abiertas** para el contrato del micro de Auth. Advertencia: cerrar la auth del admin requiere actualizar la SPA admin (hoy no envía Bearer).

### 05 — Eficiencia y rendimiento
Top hotspots: cliente RAE sincrónico (bloquea el loop hasta ~3.5s × 2 intentos × N palabras), generación mensual pesada en el lifespan y en request path, CPU-bound en el event loop (sudoku, crucigrama, bcrypt, Pillow), `get_current_user` sin proyección (trae password + array de progresos en cada request), caché RAE reescrita completa por palabra (O(n²)), rate limiter sin límite de crecimiento. Con 2+ workers/instancias se rompen cachés, límites y el loop de 12h. Incluye quick wins ordenados por esfuerzo/impacto.

### 06 — Testing y calidad
Mapa de riesgo/cobertura por feature y estrategia por fases (mongomock / testcontainers / httpx AsyncClient / fechas congeladas / CI). Gaps prioritarios: auth, IDOR, concurrencia (registro check-then-insert sin manejo de `DuplicateKeyError`), scoring client-trusted, índices que tragan errores en `database.py:103-104`.

---

## 3. Plan de acción sugerido

### P0 — Contención (antes de seguir sumando features)
1. Exigir auth (o deshabilitar) en `narrative/admin/*` y `daily_challenges` admin/upsert.
2. Rotar secretos reales y eliminar defaults: `JWT_SECRET` obligatorio (fail-fast sin default), sacar `.env` de la imagen Docker, rotar credenciales del admin sembrado y quitar PIN fijo.
3. Cerrar el fraude/IDOR de `user_attempts`: ignorar `user_id` del cliente, calcular score en servidor, puntos con operación atómica.
4. Restringir CORS a orígenes reales.
5. Corregir `modificar-email-registro` (verificación de posesión; no reenviar el PIN).

### P1 — Integridad y endurecimiento (semanas siguientes)
6. Atomicidad/transacciones en flujos críticos y arreglo de races (`progresos` array, `narrative_runs`).
7. Seeds check-first idempotentes; volumen para imágenes; manejo de zona horaria; identidad propia para invitados (no `user_id=0`).
8. Rate limiting confiable; JWT con expiración razonable + revocación; PIN con bloqueo.
9. MongoDB con credenciales en compose; limpieza de `.dockerignore`; headers de Caddy.

### P2 — Modularización, eficiencia y tests
10. Quick wins de eficiencia: `asyncio.to_thread` para RAE/sudoku/crucigrama/bcrypt/Pillow; proyección en `get_current_user`; generación mensual a background task; caché RAE con escritura atómica e invalidación.
11. Refactor modular por fases del informe 01 (sin romper contratos del frontend).
12. Estrategia de tests por fases del informe 06 + CI.

### P3 — Microservicios
13. Ejecutar la migración Strangler del informe 04 (fases 0–5) con gateway y JWKS; resolver las 20 preguntas del contrato de Auth.

---

## 4. Decisiones pendientes (para vos / equipo)
- ¿`narrative` es parte de Juegos o servicio aparte?
- ¿`usuario` va con Auth o con Cursos?
- ¿Una base Mongo compartida con owners lógicos o bases separadas por servicio?
- ¿Se actualizará la SPA admin para enviar Bearer? (requisito para cerrar la auth del admin sin romperlo)
- Contrato del micro de Auth: ver sección 8 del informe 04.

## 5. Limitaciones del análisis
- 100% estático: los hallazgos están confirmados por lectura de código, pero no se explotaron ni se ejecutó nada; puede haber falsos positivos/negativos.
- No se ejecutó pytest ni la app; no se tocó la base de datos.
- El `.env` se revisó solo para higiene; sus valores no fueron expuestos en los informes. **Recomendación: rotar cualquier secreto que haya estado en texto plano.**
- Único cambio en el repo: la creación de `auditorias/` con estos 7 informes.
