# 03 — Auditoría de Seguridad — Plan de Soluciones (remediación planificada)

- **Basado en:** `auditorias/03-auditoria-de-seguridad.md` (informe 03, fecha 2026-10-19), con insumos de `00-informe-consolidado.md` y `02-persistencia-y-flujo-de-datos.md`.
- **Fecha del plan:** 19/10/2026.
- **Estado:** **PLANIFICACIÓN — nada de esto está implementado aún.** Este documento no modifica código, tests, configuración ni infraestructura; es el plan de trabajo para hacerlo. Ninguna aplicación ni base de datos fue ejecutada o atacada para producirlo.
- **Regla de confidencialidad:** no se reproducen valores reales del `.env` ni secretos. Donde el informe 03 indica "valor por defecto público" o "igualdad verificada", aquí se mantiene esa formulación.
- **Único artefacto escrito:** este archivo.

**Leyendas**

| Etiqueta | Esfuerzo | | Prioridad | |
|---|---|---|---|---|
| **S** | ≤ 1 día-persona | | **P0** | Contención / crítico |
| **M** | 2–5 días-persona | | **P1** | Alto |
| **L** | 1–2 semanas-persona | | **P2** | Medio |
| (Backend salvo aclaración; no incluye tiempos de terceros ni del frontend externo) | | | **P3** | Bajo / mejora |

| Riesgo de implementación | Significado |
|---|---|
| **Bajo** | Cambio acotado, sin consumidores externos. |
| **Medio** | Requiere coordinación (frontend, ops, datos existentes). |
| **Alto** | Rompe contratos o sesiones activas si no se hace en transición; requiere feature flag o ventana. |

---

## 1. Resumen ejecutivo y estrategia

El informe 03 describe un backend donde varias capas están bien resueltas (BCrypt, HS256 explícito, RLS en `/progreso`, anti-mass-assignment, hardening de compose), pero la autorización real tiene fallas estructurales explotables **sin credenciales**: toda la API admin del narrativo y de desafíos está abierta (CR-01/CR-02), el `JWT_SECRET` efectivo es un valor público (CR-03), conviven credenciales por defecto activas (CR-04), hay un account takeover sin prueba de posesión (CR-05) y un IDOR no autenticado con fraude de puntos (CR-06).

**La combinación CR-03 + CR-04 + CR-05 + CR-06 permite a un atacante externo llegar a control total.** La estrategia de remediación se ordena por esa realidad, no por la numeración:

1. **Contención primero (horas, sin código).** Rotar los secretos expuestos y bloquear/limitar en el borde (Caddy) los prefijos de administración. Esto reduce el riesgo de "control total" incluso antes de tocar el código. El *orden de rotación* importa (sección 5): terceros → base de datos → credenciales admin → **JWT_SECRET último** (invalida todas las sesiones; no debe hacerse como "previous" tolerante porque el secreto viejo está comprometido).
2. **Críticos de código (semana 1–2).** Cerrar CR-01/CR-02 con dependencia compartida `get_current_admin` y una transición que **no rompa la SPA admin** (hoy no envía Bearer; es un artefacto compilado en `app/static/admin` cuya fuente vive fuera de este repo). A la par: fail-fast de configuración (CR-03), desactivar el seed del admin por defecto y quitarle el login por PIN (CR-04), rediseñar `modificar-email-registro` con verificación de posesión (CR-05) y cerrar el IDOR de `user_attempts` (CR-06).
3. **Endurecimiento de autenticación (semanas 2–4).** Rate limiting confiable (AL-01), PIN como credencial de verdad (AL-02), sesiones cortas + refresh + revocación + magic links por código de un solo uso (AL-03), anti-enumeración (AL-04), logs sin secretos (AL-05), uploads saneados (AL-06), CORS explícito (ME-01), estado activo validado contra DB (ME-02), Mongo con auth (ME-04), cierre de `/docs`, `/redoc` y SPA admin según despliegue (ME-06).
4. **Cierre documental y verificación continua (semanas 4–6).** Actualizar `docs_interna/README_SEGURIDAD.md` (hoy miente por optimismo), `README.md` y la guía de integración; matriz de tests de autorización negativa por endpoint; SAST/DAST y pentest con la app corriendo.

**Por qué este orden.** (a) La superficie admin abierta es el vector más directo y el más barato de bloquear; su cierre seguro depende de una dependencia externa (SPA), por eso lleva feature flag y bloqueo de red mientras tanto. (b) Las rotaciones son irreversibles en la práctica (invalidan sesiones), así que se planifican con backups y con las consecuencias aceptadas: los alumnos vuelven a entrar con su PIN y los admins con su contraseña nueva. (c) La separación "código de activación" vs "PIN" (AL-02) es la reforma más profunda y toca registro, activación y email; conviene después de las rotaciones y coordinada con CR-04/CR-05. (d) Todo cambio de contraseña, PIN o secreto **debe** cortar las sesiones vigentes (claim `tv`), porque en un sistema con tokens de 180 días la rotación de credenciales sin corte es cosmética.

**Decisión troncal que condiciona todo:** ¿cómo autentica la SPA admin? Hoy la respuesta es "no lo hace". El plan (SOL-CR-01) documenta tres opciones y una secuencia de despliegue que empieza por bloquear por red, sigue con la SPA enviando Bearer (opción recomendada de corto plazo) y deja cookies httpOnly + CSRF como objetivo deseable de mediano plazo. Sin esta decisión, CR-01/CR-02 quedan mitigados pero no cerrados.

**Costo y riesgo de no hacer nada:** con los valores por defecto, cualquier persona con acceso al repositorio o a la imagen Docker puede firmar tokens de administrador, y con ellos operar la Torre de Control, emitir magic links y editar dados de baja. El fraude de puntos y el account takeover no son "teóricos": están en rutas alcanzables por Caddy (`/api*`), y la población objetivo (adultos mayores) es un colectivo especialmente sensible a phishing y a reutilizar credenciales.

---

## 2. Principios de remediación

1. **Defensa en profundidad:** cada hallazgo se cierra en la capa que le corresponde (borde, app, datos) y se agrega una capa adicional cuando es barata (p. ej., auth en router + bloqueo de red del prefijo admin).
2. **No romper frontend ni contratos:** primero aditivo (nuevos campos, nuevos endpoints, respuestas que no cambian de forma), luego feature flags, luego *shadow mode* (registrar lo que se rechazaría sin rechazarlo), y recién después `enforce`. La deprecación de endpoints es anunciada y con período de gracia.
3. **Compatibilidad de contratos:** se preservan rutas, métodos y campos que el frontend consume hoy (`user_id` en intentos se ignora, no se elimina del schema de entrada hasta que el cliente deje de enviarlo; `POST /api/challenges` conserva su path aunque cambie su autorización). Cualquier cambio de forma se documenta en la guía de integración.
4. **Seguro por defecto y *fail-fast*:** ningún default inseguro en `config.py` (sin `JWT_SECRET` no arranca; sin configuración SMTP válida en producción, el envío falla ruidosamente). Las flags de transición (`ADMIN_API_AUTH_MODE`, `SEED_DEFAULT_ADMIN`) tienen valor seguro por defecto y las combinaciones inseguras se prohíben en `APP_ENV=production`.
5. **Credencial cambiada ⇒ sesiones cortadas:** todo cambio de contraseña, PIN, email o desactivación incrementa una versión de token (`tv`) y revoca refresh tokens; se ofrece `logout` real. Los access tokens se acortan a 15–60 minutos.
6. **Mínimo privilegio y admin mínimo:** un solo tipo de admin (hoy `tipo_usuario == 2`), sin login por PIN para administradores, con cambio de contraseña forzado en el primer ingreso cuando la credencial provenga de configuración inicial.
7. **Trazabilidad:** las acciones sensibles (cambios de email, rotaciones de PIN, generación/borrado de catálogo, cambios de credenciales) emiten un registro de auditoría con `user_id`, acción, timestamp y origen; sin datos sensibles en el log.
8. **Cada fix con su test negativo:** no se da por cerrado un hallazgo sin una prueba automatizada que falle con el código viejo (401/403 sin token, XFF rotado, PIN débil, código reutilizado, etc.).
9. **Separar operación de código:** las rotaciones y bloqueos de borde son acciones operativas inmediatas (sección 5); los cambios de código van después con su revisión. No se "arregla" un secreto cambiándolo en la imagen: se reconstruye sin secretos.

---

## 3. Tabla resumen de soluciones

| ID plan | Hallazgos que cierra | Solución (resumen) | Prioridad | Esfuerzo | Riesgo impl. | Fase |
|---|---|---|---|---|---|---|
| SOL-CR-01 | CR-01, CR-02 (y AL-06 auth) | Dependencia `get_current_admin` compartida en routers admin del narrativo y desafíos + transición con flag y bloqueo de red + SPA admin autenticada | **P0** | M | Alto (rompe SPA/tests si se activa sin transición) | F1 (+F0 red) |
| SOL-CR-03 | CR-03 | `JWT_SECRET` obligatorio sin default + rotación de todos los secretos + `.env` fuera de la imagen (`.dockerignore`/Dockerfile/secrets) | **P0** | M (código S + ops M) | Medio | F0 (rotar) / F1 (código) |
| SOL-CR-04 | CR-04 | No sembrar admin en producción; quitar `admin123`/`999999`; sin login por PIN para admin; cambio obligatorio en primer ingreso | **P0** | M | Medio | F0 (ops) / F1 (código) |
| SOL-CR-05 | CR-05 | `modificar-email-registro` exige posesión del correo actual (código de un solo uso) y no reenvía el PIN; invalidación y auditoría | **P0** | L | Medio | F2 |
| SOL-CR-06 | CR-06 | `/api/games/attempts` con `get_current_user`; `user_id` del cliente ignorado; score/stars calculados o acotados en servidor; `$inc` de puntos atómico e idempotente | **P0** | M | Medio | F1 |
| SOL-AL-01 | AL-01, ME-07, ME-09, BA-06 | Rate limiting con IP confiable (sin XFF ciego), bloqueo por cuenta, límites por endpoint, purga de memoria y propagación de headers | **P1** | M/L | Medio | F2 |
| SOL-AL-02 | AL-02, ME-11, ME-10 | Separar código de activación (un solo uso, TTL) del PIN; PIN server-side, hasheado, comparación constante, bloqueo por cuenta, sin PIN para admin; regeneración | **P1** | L | Alto (cambia flujos de registro/activación) | F2 |
| SOL-AL-03 | AL-03 | Access 15–60 min + refresh rotativo con detección de reuso; `logout`; revocación por `tv`; magic links por código de un solo uso (sin JWT en URL) | **P1** | L | Alto (frontend + sesiones) | F3 |
| SOL-AL-04 | AL-04, BA-05 | Respuestas uniformes anti-enumeración en registro/activación/reenvío/modificar-email/login; 401 uniforme | **P1** | S | Bajo | F1/F2 |
| SOL-AL-05 | AL-05, ME-05 | Sin códigos/tokens/PII en logs; SMTP fail-fast en producción; asunto de email sin código; purga de logs históricos | **P0/P1** | S | Bajo | F1 |
| SOL-AL-06 | AL-06 | Upload autenticado, límite 5 MB en app, `MAX_IMAGE_PIXELS` + anti-bomba, magic bytes, EXIF fuera, rate limit y volumen | **P1** | S | Bajo | F2 |
| SOL-ME-01 | ME-01 | CORS por lista explícita por entorno; sin regex ni credenciales si el modelo es Bearer | **P0** | S | Bajo | F1 |
| SOL-ME-02 | ME-02 | Endpoints con token validan estado real en DB; token inválido presente ⇒ 401 (nunca degradar a invitado) | **P1** | S | Bajo | F2 |
| SOL-ME-04 | ME-04 | MongoDB con autenticación (root + usuario de app de mínimo privilegio), credenciales por secret/env | **P1** | M | Medio (ventana + volumen existente) | F2 |
| SOL-ME-06 | ME-06 | `/docs`, `/redoc`, `/openapi.json` apagados en producción; SPA admin fuera de internet (VPN/SSO) y no ruteada por Caddy | **P1** | S | Bajo | F2 |
| SOL-DOC-01 | Checklist falso de docs | `README_SEGURIDAD.md` corregido o marcado como roadmap; `README.md` sin credenciales por defecto; guía de frontend actualizada | **P2** | S | Bajo | F3 |
| SOL-COMP | ME-03, ME-08, ME-11*, BA-01…BA-10 | Complementarios acotados (invitado con identidad propia, soluciones de desafíos no públicas, pins/lockfile, no-root, TLS/CSP, catálogo de estados, etc.) | **P2/P3** | M | Bajo | F3/F4 |

\* ME-11 y ME-10 se detallan dentro de SOL-AL-02; ME-09 y BA-06 dentro de SOL-AL-01.

**Total estimado:** ≈ 35–45 días-persona de backend + ≈ 8–15 días-persona de frontend (SPA admin, flujo de acceso/refresh, juegos) + ventanas de ops para rotaciones y Mongo. Con 1 dev backend a tiempo completo y soporte parcial de frontend/ops: **8–10 semanas** hasta F3; el camino crítico para cerrar los 6 críticos es de **2–3 semanas** si las decisiones de la sección 7 se toman en la semana 1.

---

## 4. Soluciones detalladas

Cada solución incluye enfoque, archivos a tocar, pasos, criterios de aceptación/verificación (con las pruebas de seguridad a agregar), riesgos/mitigación, rollback, dependencias con otros planes y esfuerzo. Nada de esto está implementado.

### 4.1 SOL-CR-01 — CR-01/CR-02: autenticación de administración compartida y despliegue seguro sin romper la SPA admin

**Enfoque.** Aplicar `get_current_admin` (ya existente y correcto en `app/core/dependencies.py:63-74`) **a nivel de router** en toda la superficie administrativa, y además proteger el upsert de desafíos. Como la SPA admin compilada (`app/static/admin`, origen externo a este repo) **no envía `Authorization: Bearer`** (verificado: sus llamadas a `/api/narrative/admin/*` usan `fetch` con solo `Content-Type`), el cierre se hace en transición: primero se limita el alcance por red, después la SPA se actualiza, y recién entonces se fuerza el rechazo. El endpoint público de desafíos (`GET /api/challenges/*`) no cambia.

**Detalle de rutas a proteger (confirmado en informe 03, sección 3):**
- Todo `/api/narrative/admin/*` (catálogo de reglas, CRUD de 7 colecciones, `upload-imagen`, `sembrar-finalizaciones`, `generar-mes`).
- `POST /api/challenges` (upsert), `GET /api/challenges/admin/status`, `POST /api/challenges/admin/generate-month`.
- Recomendado además: `force` pasa de `True` a `False` por defecto en `generate-month` (alineado con 02-A6 y 05) y validación de `game_id` contra lista blanca para no aceptar `"narrativo"` o juegos inexistentes desde ese endpoint.

**Archivos a tocar.**
- `app/features/narrative/admin/router.py` (línea 64: agregar `dependencies=[Depends(get_current_admin)]` al `APIRouter`; importar `Depends`).
- `app/features/daily_challenges/router.py` (quitar auth implícita: crear `admin_router` con `dependencies=[Depends(get_current_admin)]` para `/admin/status` y `/admin/generate-month`; proteger `POST ""` con la misma dependencia; `force: bool = Query(False)`).
- `app/core/dependencies.py` (agregar helper de modo transitorio, p. ej. `require_admin_for_admin_api`, que respeta `ADMIN_API_AUTH_MODE`; reutilizar `get_current_admin` como dependencia final).
- `app/core/config.py` (nueva flag `ADMIN_API_AUTH_MODE: Literal["off","shadow","enforce"] = "enforce"` y `APP_ENV`; validación: en `APP_ENV=production` la combinación `off` es inválida al arrancar).
- `Caddyfile` (regla interina de acceso restringido a las rutas admin; ver pasos).
- `app/main.py` (si se opta por registrar los routers admin separados; opcional).
- `tests/test_narrative_game.py` y `tests/test_narrative_v2_game.py` (hoy consumen `/api/narrative/admin/catalogo-reglas` y `/api/narrative/admin/universos` sin credenciales — deben inyectar un token de admin de test o llamar a los servicios directamente).

**Pasos (orden seguro de despliegue, sin romper la SPA).**
1. **Fase 0 — Bloqueo por red (ops, sin código).** En el borde (Caddy, o el Nginx/firewall frontal), restringir `/api/narrative/admin*`, `/api/challenges/admin*` y `POST /api/challenges` a la red administrativa (VPN/IP allowlist). Concepto:
   ```
   @admin_api path /api/narrative/admin* /api/challenges/admin*
   handle @admin_api {
     @allowed remote_ip <red-admin-o-VPN>
     handle @allowed { reverse_proxy backend:8082 }
     respond 404
   }
   ```
   y análogo para `POST /api/challenges` (matcher por método + path). Si la red del operador no es fija, usar VPN o `basic_auth` como parche (documentar la limitación: la SPA compilada puede no mostrar el prompt en `fetch`). Esto ya reduce CR-01/CR-02 de "explotable por internet" a "explotable solo desde la red admin" aunque el backend siga sin auth.
2. **Fase 1a — Dependencia en backend con transición.** Implementar `ADMIN_API_AUTH_MODE`:
   - `enforce` (default): 401 sin token válido, 403 con token de alumno.
   - `shadow`: registra en log estructurado (`admin_api_auth_shadow`) cada request que *debería* ser rechazada, pero la deja pasar (para medir qué consumidores legítimos se romperían).
   - `off`: solo permitido si `APP_ENV != production`; el arranque falla en producción.
3. **Fase 1b — Adaptar la SPA admin (frontend externo).** La fuente de la SPA no está en este repo; solo los artefactos compilados en `app/static/admin`. Hay que actualizar el repositorio del frontend admin para que todas las llamadas a `/api/narrative/admin/*` y `/api/challenges/*` (incluido `POST /api/challenges`) envíen `Authorization: Bearer <token>` obtenido de `/api/auth/login-sistemas`, con manejo global de 401 (redirigir a login). Recompilar y reemplazar `app/static/admin`. Verificar en staging con el backend en `shadow`, mirando el log de shadow.
4. **Fase 1c — `enforce` en producción.** Cambiar la flag, verificar la SPA en caliente, mantener el bloqueo de red como defensa en profundidad (no quitarlo hasta F3). Confirmar que el único tráfico que llega a los prefijos admin es el esperado (logs de Caddy + telemetría de shadow).
5. **Fase 1d — Limpieza.** Actualizar tests, documentación (`docs_interna/README_SEGURIDAD.md` claim #1) y eliminar la flag en una fase posterior (cuando ya no haya duda del consumidor), dejando `get_current_admin` fijo.
6. **Paralelo:** mover conceptualmente el upsert a un router admin (mismo path `POST /api/challenges` protegido, o alias nuevo `/api/challenges/admin/upsert` manteniendo el viejo por una release); validación de `config` por juego con modelo Pydantic específico (coord. 02/06); `force=false` por defecto.

**Opciones para la autenticación de la SPA admin (decisión requerida, ver sección 7):**

| Opción | Cómo | Pros | Contras | Recomendación |
|---|---|---|---|---|
| A. Token en storage + header Bearer | La SPA guarda el JWT (localStorage/sessionStorage) y lo envía en `Authorization` | Consistente con el resto del frontend (guía actual), cambio acotado, no toca CORS/cookies | XSS en la SPA expone el token; hay que recompilar el artefacto | **Corto plazo (recomendada)** |
| B. Cookie httpOnly + CSRF | Backend emite cookie de sesión; SPA envía `X-CSRF-Token` | Token no accesible por JS; mejor contra XSS | Requiere CORS con `allow_credentials=True` y orígenes exactos, doble submit CSRF, cambios de backend y SPA; hoy el modelo es Bearer puro | Mediano plazo (objetivo) |
| C. Proxy que inyecta auth | Caddy/Nginx valida la sesión (forward_auth/OIDC) e inyecta un header/token de servicio al backend | No se toca la SPA; se puede combinar con VPN/SSO | Depende de infra fuera del repo; hay que proteger también el acceso directo al backend (hoy no publica puerto) | Si la SPA no puede modificarse pronto |

**Criterios de aceptación y verificación (pruebas de seguridad a agregar).**
- Sin token: `GET /api/narrative/admin/universos`, `DELETE /api/narrative/admin/universos/{id}`, `POST /api/narrative/admin/upload-imagen`, `POST /api/narrative/admin/generar-mes`, `POST /api/challenges`, `GET /api/challenges/admin/status`, `POST /api/challenges/admin/generate-month` → **401**.
- Con token de alumno (`tipo_usuario=1`) → **403** en todos los anteriores.
- Con token de admin → 2xx (flujo funcional completo en staging).
- `GET /api/challenges/today|month|range|date` sigue **público** y con el mismo contrato.
- `generate-month` con default `force=false` no pisa desafíos existentes salvo pedido explícito.
- SPA admin funciona end-to-end en producción con el bloqueo de red activo.
- Tests nuevos: `tests/security/test_admin_authz.py` (paramétrico por endpoint), y actualización de los dos tests existentes para no depender de rutas abiertas.
- En `APP_ENV=production` con `ADMIN_API_AUTH_MODE=off` la app **no arranca** (test de configuración).

**Riesgos y mitigación.** (a) *Romper la SPA admin y los tests existentes*: mitigado con `shadow` + staging + reemplazo coordinado del artefacto; riesgo residual: la fuente externa no esté disponible → opción C (proxy) o mantener VPN como cierre definitivo. (b) *Olvidar un endpoint admin*: mitigar con test paramétrico que recorra el router y exija dependencia en cada ruta admin (introspección de `app.routes` en test). (c) *Bloqueo de red mal configurado deja fuera a operadores legítimos*: probar la regla en staging, tener un plan B (VPN) y monitorear 404/403 en ese prefijo.

**Rollback.** Cambiar `ADMIN_API_AUTH_MODE` a `shadow` (o quitar la dependencia del router) y mantener el bloqueo de red, que es el que contiene el riesgo. El rollback del frontend es volver a desplegar el artefacto anterior (con el bloqueo de red activo).

**Dependencias.** Plan 04 (microservicios: contrato del gateway y de identidad; aquí se siembra el RBAC admin que luego migra a JWKS/introspección); plan 06 (estructura de tests y CI); decisión de la sección 7 sobre la SPA; ops para Caddy/VPN.

**Esfuerzo.** M global (backend S; frontend M; ops S). El cierre efectivo del hallazgo depende de que frontend + ops estén en la misma ventana.

### 4.2 SOL-CR-03 — CR-03: JWT_SECRET fail-fast, rotación de secretos y `.env` fuera de la imagen

**Enfoque.** Tres cambios inseparables: (1) eliminar el default público del secreto y validar en el arranque; (2) rotar **todos** los secretos que estuvieron expuestos (repository + imagen), en un orden operativo preciso (sección 5.1); (3) garantizar que la imagen Docker deje de "hornear" el `.env`. Se agrega soporte de `JWT_SECRET_PREVIOUS` **solo para rotaciones futuras planificadas**; en esta rotación de emergencia no se usa, porque el secreto viejo está comprometido y tolerarlo mantendría válidos los tokens forjados por un atacante.

**Archivos a tocar.**
- `app/core/config.py:14` — `JWT_SECRET: str` **sin default**; `field_validator` que rechace: vacío, longitud < 32, igual al valor default histórico, o igual a cualquiera del `.env.example`; opcional `JWT_SECRET_PREVIOUS: Optional[str] = None` para el futuro. Agregar `APP_ENV` (`development|staging|production`).
- `app/core/security.py:56-62` — `decode_access_token` intenta actual y, si falla firma, `JWT_SECRET_PREVIOUS` (solo si está definido y no en producción durante la rotación de emergencia). Mantener `algorithms=["HS256"]`.
- `app/core/database.py:21` — no loguear la `MONGODB_URL` completa (enmascarar credenciales/usuarios).
- `.dockerignore` — agregar `.env`, `.env.*`, `*.env` (hoy solo ignora `.env.example`), además de `tests/`, `auditorias/`, `docs_interna/` si no se quieren en la imagen.
- `Dockerfile:15` — reemplazar `COPY . .` por copias explícitas (`COPY app ./app`, `COPY requirements.txt .` ya existe); agregar usuario no-root (coord. BA-02); el `.env` **no** debe estar en ninguna capa.
- `docker-compose.yml` — mantener `env_file: .env` para desarrollo, pero para producción usar **Docker secrets** (`secrets:` + `*_FILE` soportado por pydantic-settings) o inyección de entorno desde el orquestador; documentar. El backend no debe recibir `JWT_SECRET` por defecto.
- `.env.example` — solo placeholders, nunca un valor "usable"; comentario de cómo generar (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- `README.md`, `docs_interna/*` — sacar cualquier mención de secretos utilizables.

**Pasos.**
1. Preparar el código fail-fast y validaciones (arriba) en una rama; **no** desplegar aún sin el secreto nuevo disponible.
2. Ejecutar la rotación operativa (sección 5.1) con los secretos nuevos cargados en el gestor correspondiente (env del orquestador, Docker secrets o vault).
3. Reconstruir imágenes `--no-cache`, verificar que la imagen no contiene `.env` (`docker history`, inspección de capas, `docker run ... ls /app/.env` → no existe) y purgar imágenes/tars/registry viejos (contenían los secretos rotados, ya inválidos, pero no deben quedar).
4. Desplegar; verificar que la app arranca con el secreto nuevo y que un token firmado con el default histórico es rechazado (401).
5. Documentar el procedimiento de rotación futura (con `JWT_SECRET_PREVIOUS` y ventana ≤ duración del access token una vez implementado AL-03).

**Criterios de aceptación y verificación.**
- Sin `JWT_SECRET` en el entorno, el proceso **falla al iniciar** con mensaje claro (test: instanciar `Settings` con env limpio → `ValidationError`).
- `JWT_SECRET` con el valor default histórico o longitud débil → falla al iniciar (test unitario parametrizado, sin imprimir valores).
- Token acuñado con el secreto viejo/default → `401` en cualquier endpoint protegido, incluidos `get_current_admin` y el rate limiter.
- La imagen Docker no contiene `.env` ni secretos (verificación estática documentada; el pipeline puede fallar si `docker history` o un escaneo de capas detecta `.env`).
- `.env.example` no contiene ningún valor utilizable (revisión manual + test que compare contra el default histórico, otra vez sin citar valores).
- Toda la app sigue funcionando: login alumno, login admin, emails, RAE (si aplica).

**Riesgos y mitigación.** (a) *Rotar el JWT_SECRET cierra todas las sesiones* → esperado y deseado; comunicar a operadores/alumnos que hay que volver a ingresar (los alumnos con su PIN, que no cambia en esta fase). (b) *Romper el envío de emails o la API RAE con credenciales nuevas* → probar envío y generación de crucigramas en staging antes de producción. (c) *Perder acceso al `.env` real* → copia segura temporal en el gestor de secretos, nunca en el repo. (d) *Imágenes viejas en registry de terceros* → asumir compromiso de todos los secretos que pasaron por la imagen (ya rotados) y purgar tags si el registry es propio.

**Rollback.** No se vuelve al secreto viejo (ya no es seguro). Si algo falla, se corrige hacia adelante con el secreto nuevo; el rollback posible es de código (volver a la versión anterior de la app) pero **manteniendo** los secretos nuevos por entorno, y restaurando el `.dockerignore` solo si la imagen se reconstruye sin `.env`.

**Dependencias.** Ops (rotaciones, registry); SOL-CR-04 (la contraseña del admin se rota en la misma ventana); SOL-AL-03 (acortar tokens hace menos traumáticas las rotaciones futuras); plan 04 (los secretos de JWT migran a claves de firma del micro de Auth/JWKS en el futuro).

**Esfuerzo.** M (código S, operación M).

### 4.3 SOL-CR-04 — CR-04: credenciales por defecto del admin y PIN `999999`

**Enfoque.** Que el sistema **no pueda** quedar con credenciales conocidas: (1) el seed del admin deja de ser automático en producción y no usa defaults; (2) el login por PIN rechaza a los administradores (el PIN es credencial de alumno); (3) si se sembró un admin con contraseña provista por configuración, se exige cambio en el primer ingreso; (4) operación: rotar/eliminar la cuenta existente. El flujo de alumnos no cambia en esta solución (su PIN se reforma en SOL-AL-02).

**Archivos a tocar.**
- `app/core/config.py:27-28` — quitar defaults de `ADMIN_DEFAULT_EMAIL`/`ADMIN_DEFAULT_PASSWORD` (o dejarlos solo en desarrollo detrás de `APP_ENV`); nueva flag `SEED_DEFAULT_ADMIN: bool = False`.
- `app/scripts/init_db.py:64-93` — `seed_default_admin()` solo corre si `SEED_DEFAULT_ADMIN=true`; si está activo, exigir email+password provistos (fallar si faltan) y marcar `must_change_password: True`; **eliminar `codigo_acceso: "999999"`** del documento sembrado (admin sin PIN).
- `app/main.py:38` — condicionar la llamada al seed; documentar el runbook de creación del primer admin (script CLI o seed explícito).
- `app/features/auth/service.py:90-125` — `login_codigo` filtra `tipo_usuario == 1` (además de estado), de modo que un PIN no puede emitir token de admin; si un admin tuviera PIN por datos históricos, se rechaza igualmente.
- `app/features/auth/service.py` + `router.py` + `schemas.py` — nuevo `POST /api/auth/cambiar-password` (actual + nueva, fortaleza mínima, `hmac`/bcrypt ya existente); `login_sistemas` devuelve `mustChangePassword` y aplica una restricción: `get_current_admin` rechaza (403 con código `PASSWORD_CHANGE_REQUIRED`) si `password_must_change=True`, salvo en el endpoint de cambio (que usa `get_current_user`).
- `README.md:76`, `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md:367-374` — eliminar credenciales publicadas.

**Pasos.**
1. Código: config + seed condicional + `login_codigo` por rol + flag `must_change_password` + endpoint de cambio.
2. Ops (ventana): rotar la cuenta admin existente — cambiar contraseña a una fuerte y única (no `admin123`), eliminar/regenerar su `codigo_acceso` (o dejarlo inutilizado por el filtro de rol), verificar que no existan otros usuarios `tipo_usuario=2` inesperados, y habilitar `must_change_password` para forzar el cambio en el siguiente ingreso.
3. Desplegar con `SEED_DEFAULT_ADMIN=false`; verificar en arranques posteriores que **no** se recrea nadie si se borra el admin (comportamiento actual: `init_db` lo repone).
4. Documentar alta de nuevos admins: vía `POST /usuario` con `tipoUsuario=2` autenticado, o script controlado; nunca por semilla pública.

**Criterios de aceptación y verificación (pruebas).**
- `POST /api/auth/ingresar-codigo` con cualquier PIN de un usuario admin → **401/403** y sin token (test con admin de fixture).
- Arranque con `SEED_DEFAULT_ADMIN=false` y base vacía → no se crea ningún usuario admin (test de integración).
- `SEED_DEFAULT_ADMIN=true` sin contraseña en env → el arranque falla (test de configuración).
- Admin sembrado con flag de cambio: cualquier endpoint admin (salvo cambio de contraseña) → 403 `PASSWORD_CHANGE_REQUIRED`; tras cambiar, opera normal y el flag queda en falso.
- `grep` del repo sin `admin123` ni `999999` como credenciales documentadas (test de higiene de documentación).
- Cuenta admin existente en producción ya no responde a las credenciales viejas (verificación operativa post-rotación).

**Riesgos y mitigación.** (a) *Perder acceso admin al rotar* → coordinar con SOL-CR-03 y tener acceso de break-glass a la base para re-flag de cambio; probar en staging. (b) *Romper clientes que usan `codigoAcceso` del admin* (p. ej. pantallas de soporte) → el filtro de rol es el comportamiento correcto; ajustar el consumo interno si existiera. (c) *Automatizaciones que dependen del seed* → reemplazar por alta explícita documentada.

**Rollback.** Re-activar el seed con una contraseña fuerte provista por entorno (no la default) es el único rollback parcial admisible; volver a `admin123`/`999999` no lo es. El rollback de código es restaurar el filtro de rol anterior solo si aparece un caso de uso legítimo documentado (no esperado).

**Dependencias.** SOL-CR-03 (misma ventana de rotación), SOL-AL-02 (el PIN del alumno se reforma allí; aquí solo se le quita a los admin), plan 04 (el alta de admin migra al micro de Auth).

**Esfuerzo.** M (código M, ops S).

### 4.4 SOL-CR-05 — CR-05: `modificar-email-registro` con verificación de posesión real

**Enfoque.** Reemplazar el cambio unilateral por un flujo de dos pruebas: (1) quien pide el cambio debe probar que controla el **correo actual** (código de un solo uso, 6 dígitos, TTL 15 minutos, almacenado hasheado, máximo de intentos), y (2) el nuevo correo recibe su propio código de activación (también de un solo uso, expirable). En ningún paso se reenvía el PIN de login como "código". Todo cambio de email: queda registrado en auditoría e invalida el código de activación previo y las sesiones del usuario (incremento de `tv`, coord. AL-03).

**Archivos a tocar.**
- `app/features/auth/service.py:365-408` — reescribir el flujo; eliminar el envío del `codigo_acceso` preexistente (línea 401-402).
- `app/features/auth/schemas.py` — nuevos requests: `SolicitarCambioEmailRequest {email_actual}`, `ConfirmarCambioEmailRequest {email_actual, codigo, email_nuevo}`; el endpoint viejo `ModificarEmailRegistroRequest` se depreca.
- `app/features/auth/router.py:73-79` — endpoints nuevos (`/api/auth/modificar-email-registro/solicitar` y `/confirmar`); el viejo responde 410/404 tras la transición (o se re-cablea internamente durante una release).
- `app/features/auth/email_service.py` — plantilla específica "Código para cambiar el correo" (no reutilizar la de activación con texto de PIN); asunto sin código (coord. AL-05).
- `app/core/database.py` — índice TTL para la colección de códigos (`auth_codes`) o campos con expiración en el usuario; si se usa colección nueva, agregarla a `init_indexes`.
- Frontend (registro): pantalla de "corregí mi correo" en dos pasos.

**Pasos.**
1. Definir almacenamiento de códigos: colección `auth_codes` (`user_id`, `tipo` (`cambio_email_actual` | `activacion`), `code_hash`, `expira`, `intentos`, `usado`) con índice TTL sobre `expira` y comparación `hmac.compare_digest`.
2. Implementar `solicitar`: si el email existe y está pendiente, generar y enviar código al correo actual; **respuesta uniforme** 200 exista o no (anti-enumeración, coord. AL-04). Rate limit ya existe; agregar cooldown por email.
3. Implementar `confirmar`: validar código (TTL, intentos, no usado) → validar que `email_nuevo` no pertenezca a otra cuenta → actualizar email → marcar código como usado → emitir **nuevo código de activación de un solo uso** al correo nuevo (no el PIN) → invalidar cualquier código anterior → registrar auditoría (`email_change`: user_id, viejo, nuevo, timestamp, IP) → requerir `verificar-codigo-registro` con ese código nuevo para activar (el usuario recién ahí obtiene su PIN/login).
4. Migración/transición: durante una release el endpoint viejo puede redirigir al nuevo flujo; luego 410 con mensaje que indique el flujo correcto. Documentar en la guía de frontend.
5. Auditoría operativa: listar cambios de email históricos si existieran (`grep`/consulta por `email_change` no aplica retroactivo; dejar constancia de que no es reconstruible).

**Criterios de aceptación y verificación (pruebas).**
- Escenario de ataque del informe: atacante conoce el email de una cuenta pendiente y llama al flujo sin acceso al correo actual → **no puede** cambiar el email ni recibir ningún código (test 1: `confirmar` sin código válido → 401/400; test 2: el código de posesión solo se envía al correo actual `to_email`).
- Código de posesión: un solo uso, expira a los 15 min, máximo de intentos, comparación constante, bloqueo tras N fallos (coord. AL-01/AL-02).
- Código reutilizado → rechazado; código de otro usuario → rechazado.
- `email_nuevo` ya registrado → error uniforme (sin filtrar si existe; decisión de UX documentada) y sin cambio de emails.
- Tras cambio exitoso: sesiones viejas invalidadas, PIN viejo no sirve para la cuenta hasta re-activar, y queda registro de auditoría.
- Respuestas uniformes en `solicitar` para email existente/no existente (test de igualdad de status y mensaje).
- Cliente viejo contra el endpoint deprecado → respuesta de error explícita y documentada (sin cambio de datos).

**Riesgos y mitigación.** (a) *Agregar fricción al soporte de personas mayores* (doble código) → mitigar con UX clara, textos grandes y opción de asistencia telefónica que **no** puede saltar el control (el operador puede reenviar el código al correo actual, nada más). (b) *Romper la pantalla actual de corrección* → transición con redirección y aviso; el flujo actual es el vulnerable, por lo que si el frontend no puede actualizarse, la alternativa segura es **deshabilitar** el endpoint hasta que pueda (documentado como mitigación temporal). (c) *Colisión con otros cambios de email* → operación de confirmación idempotente por `usado: true`.

**Rollback.** Volver al endpoint viejo es volver a la vulnerabilidad; el rollback seguro es hacia adelante o deshabilitar la función (410) con comunicación a soporte. El rollback de infraestructura estructural (colección `auth_codes`) es inocuo: se deja sin uso.

**Dependencias.** SOL-AL-02 (separación código de activación/PIN), SOL-AL-04 (respuestas uniformes), SOL-AL-03 (corte de sesiones por `tv`), plan 06 (tests), frontend (pantalla nueva).

**Esfuerzo.** L (backend M, frontend M).

### 4.5 SOL-CR-06 — CR-06: cerrar el IDOR de `user_attempts` y el fraude de puntos

**Enfoque.** El endpoint deja de confiar en el cliente para la identidad y el puntaje: (1) los tres endpoints usan `Depends(get_current_user)` (validación de firma + expiración + estado activo en DB); (2) todo `user_id` de query/body se **ignora** (se mantiene en el schema por compatibilidad de contrato, pero no tiene efecto; se registra si difiere del token); (3) `score`/`stars`/`attempts` no se toman del cliente como verdad: se acotan en Pydantic y, en la medida de lo posible, se calculan/validan server-side; (4) el `$inc` de puntos pasa a ser atómico e idempotente por intento (bandera `points_awarded`), coordinado con el plan 02. Se elimina el fallback mágico `or req.user_id or 1` de `service.py:46`.

**Archivos a tocar.**
- `app/features/user_attempts/router.py:17-99` — reemplazar `_extract_user_id_from_header` + `user_id or token` por dependencia `get_current_user`; los tres endpoints usan `current_user["id"]`.
- `app/features/user_attempts/service.py:40-97` — quitar fallback `or 1`; verificar ownership (no aplica si la identidad es la del token); cálculo/validación de puntaje; `$inc` condicionado a transición `points_awarded false→true` con `find_one_and_update` (retorno `BEFORE` para saber si correspondía acreditar).
- `app/features/user_attempts/schemas.py` — cotas: `score ge=0 le=<máximo por juego>`, `stars ge=1 le=3`, `attempts ge=0 le=<máximo>`, `date` con rango razonable (no futuro lejano, no pasado arbitrario; coord. plan 02-M1 con zona horaria de negocio); `remaining_attempts ge=0`.
- `app/core/database.py` — si se agrega `points_awarded` al índice/consultas, documentarlo; opcional índice `(user_id, game_id, date, points_awarded)`.
- Frontend de juegos — debe enviar `Authorization: Bearer` en guardado y lectura (si hoy no lo hace, el guardado en la nube de invitados se rompe: decisión de producto, ver sección 7).
- `tests/` — actualizar cualquier test que use `user_id` sin token.

**Pasos.**
1. Backend: dependencia en los 3 endpoints; ignorar `user_id` del cliente (log `attempts_user_id_mismatch` con `user_id` de token vs cliente, sin datos sensibles).
2. Definir tabla de máximos server-side por juego (`wordle`: score máx. X, stars 1-3, attempts ≤ 6; etc.) con el equipo de producto; mientras no exista cálculo completo, **clamp** de valores y no acreditar puntos si `score > máximo` (o acreditarlos con tope). El objetivo final (plan 02) es derivar puntos de la fuente de verdad.
3. Atomicidad: reemplazar el patrón "leer `was_already_completed` → upsert → `$inc`" por una actualización condicional del intento (`filter: {..., "points_awarded": {"$ne": True}}`, `update: {"$set": {"points_awarded": True, ...}}`, `return_document=BEFORE`) y acreditar solo si el documento previo existía sin la bandera (o era inserción). Un solo `$inc` por (user, game, date, mode) completado.
4. Fechas: validar `date` contra la fecha de negocio del servidor (coord. plan 02) y aplicar la misma lógica al mes consultado.
5. Rate limiting del POST (coord. SOL-AL-01) y test de concurrencia (dos POST simultáneos del mismo intento → un solo incremento).

**Criterios de aceptación y verificación (pruebas).**
- `GET /api/games/attempts`, `GET /date/{date}`, `POST /api/games/attempts` sin token → **401**.
- Con token de usuario A y `?user_id=B` → devuelve/escribe **solo datos de A** (test IDOR con dos usuarios).
- `POST` con `user_id` arbitrario en body → ignorado (test de que el documento queda con el ID del token).
- `score` negativo o absurdo → rechazado por Pydantic (400) o clampeado, y **nunca** incrementa puntos más allá del máximo permitido.
- Doble POST de "completed" del mismo día → puntos acreditados una sola vez (test secuencial y test concurrente con `asyncio.gather`).
- Usuario desactivado con token válido → 403 (validación contra DB, cubre ME-02 en este router).
- Cuenta sin token que antes guardaba en la nube → 401 explícito; decisión de producto documentada sobre invitados.
- Tests: `tests/security/test_attempts_idor.py`, `test_attempts_scoring.py`.

**Riesgos y mitigación.** (a) *Romper el guardado de invitados* si el frontend guardaba con `user_id` sin token → coordinar con frontend y decidir: guardado local para invitados (recomendado) o seguir permitiendo escritura solo con token de invitado firmado (más complejo). (b) *Puntos de usuarios históricos con doble conteo* → `points_awarded` no es retroactivo; decidir reconciliación (plan 02 A7) y no recalcular a la ligera. (c) *Clamps que rompan juegos legítimos* → definir máximos con producto y testear cada juego. (d) *Máximos por juego desactualizados* → centralizar en un módulo de reglas de puntaje.

**Rollback.** El IDOR y la identidad se revierten volviendo a la dependencia anterior (no recomendado, es el core del hallazgo). El clamp de puntaje es reversible por configuración; la bandera `points_awarded` es aditiva y no rompe datos existentes.

**Dependencias.** Plan 02 (puntaje como fuente de verdad, atomicidad/transacciones, `mode` y fechas), plan 05 (carga del endpoint), SOL-AL-01 (rate limit del POST), SOL-ME-02 (validación de estado — mismo cambio de dependencia).

**Esfuerzo.** M (backend M; frontend S/M).

### 4.6 SOL-AL-01 — AL-01 (+ME-07, ME-09, BA-06): rate limiting confiable, bloqueo por cuenta y limpieza

**Enfoque.** Que el límite dependa de datos que el cliente **no pueda falsificar** y que el abuso por cuenta también tenga costo: (1) IP de conexión (`request.client.host`) y `X-Forwarded-For` solo cuando la conexión venga de un proxy de confianza (`TRUSTED_PROXIES`); (2) contador por **cuenta objetivo** (email/PIN/USER) con bloqueo exponencial y persistencia que sobreviva reinicios; (3) límites específicos por endpoint; (4) sin bypass por claim de admin (o con verificación real contra DB y bucket generoso aparte); (5) purga de claves y cota de memoria en el limiter in-memory (coord. plan 05); (6) propagar headers (`Retry-After`, `WWW-Authenticate`) en el handler de excepciones (ME-09) y agregar límite a `verificar-token` (BA-06).

**Archivos a tocar.**
- `app/core/rate_limit.py` — `_client_ip()`: usar `request.client.host`; solo si es un proxy confiable (lista/CIDR en config), parsear XFF y tomar la IP **más a la derecha que no sea de confianza**; clave `ip:path` + clave por cuenta. `_history` con purga: al limpiar una clave vacía, `del` del dict; tope global de claves (p. ej. 50k) con desalojo. Docstring actualizado (hoy promete bypass admin).
- `app/core/config.py` — `TRUSTED_PROXIES: list[str] = []`, `RATE_LIMIT_ENABLED: bool = True`, límites por endpoint configurables.
- Nuevo `app/core/account_lockout.py` (o extender rate_limit) — contador por cuenta persistido en Mongo (`auth_lockouts`: `_id = tipo:identificador_hash`, `failures`, `lock_until`, `last_attempt`; índice TTL sobre `lock_until`), con backoff exponencial (p. ej. 5 fallos → 15 min; 10 → 1 h; 20 → 24 h) y desbloqueo automático/exitoso.
- `app/features/auth/router.py` — aplicar límites por endpoint (tabla abajo) y no solo por IP; `verificar-token` con límite.
- `app/features/auth/service.py` — alimentar el lockout en `login_sistemas`, `login_codigo`, `verificar-codigo-registro`, `modificar-email-registro` (éxito resetea, fallo incrementa); mensajes/headers de bloqueo.
- `app/main.py:104-114` — `JSONResponse(..., headers=exc.headers)` para conservar `Retry-After`/`WWW-Authenticate`.
- `Caddyfile` — configurar `trusted_proxies`/IP real en Caddy (para que la XFF que reenvía sea la correcta) y, si está disponible el módulo de rate limit del borde, límites complementarios.
- Tests: `tests/security/test_rate_limit.py`, `test_account_lockout.py`.

**Límites propuestos (punto de partida, ajustables):**

| Endpoint | Por IP | Por cuenta/target | Notas |
|---|---|---|---|
| `login-sistemas` | 5/min | + lockout 5 fallos/15 min | Mensaje uniforme 401 |
| `ingresar-codigo` | 5/min | + lockout por PIN/usuario | Con SOL-AL-02 comparte contador |
| `verificar-codigo-registro` | 10/min | + contador por cuenta | Código de un solo uso |
| `reenviar-codigo-registro` | 3/min | + cooldown por email (1/min) | Anti-spam de correos |
| `modificar-email-registro` | 5/min | + cooldown por email | Flujo de SOL-CR-05 |
| `verificar-token` (BA-06) | 30/min | — | Solo decodifica; igual conviene limitar |
| `POST /api/games/attempts` | 60/min | por usuario | Anti-farmeo (coord. plan 05) |
| `upload-imagen` | 10/hora | por admin | Con SOL-AL-06 |
| `generate-month` | 2/hora | por admin | Con SOL-CR-01; coord. plan 05 (CPU) |

**Pasos.**
1. Arreglar la IP (sin esto todo lo demás es evadible): config de proxies confiables + `request.client.host` por defecto.
2. Implementar el lockout por cuenta con persistencia y backoff; integrarlo en los servicios de auth.
3. Ajustar límites por endpoint (tabla) y quitar el bypass por claim; si se quiere trato especial para admins, verificar con `get_current_admin` real (DB) y aplicar un bucket generoso separado, nunca "sin límite".
4. Purga/cota de memoria del limiter in-memory (coord. plan 05; si se adopta Redis, migrar el limiter completo en una segunda etapa).
5. Propagar headers (ME-09) y tests.

**Criterios de aceptación y verificación (pruebas).**
- Rotar `X-Forwarded-For` aleatorio en cada request contra un endpoint limitado **sin** proxy delante → el bloqueo se sigue disparando (misma IP de conexión). Test explícito.
- Detrás del proxy de confianza, la XFF legítima sí se respeta (test con config de proxies).
- N fallos de PIN/contraseña de una cuenta → bloqueo con `429`/`423` + `Retry-After` correcto (header presente: prueba de ME-09); el éxito resetea; tras la ventana, se libera.
- Un atacante que rota IPs sigue topando con el lockout por cuenta.
- Token con claim `tipoUsuario=2` firmado (incluso válido) **no** saltea el límite de endpoints sensibles; el admin legítimo puede operar dentro de su bucket.
- La memoria del limiter no crece sin límite: test de purga/cota (coord. plan 05).
- `verificar-token` responde 429 al exceder.

**Riesgos y mitigación.** (a) *Bloquear usuarios legítimos* (adultos mayores que se equivocan) → backoff progresivo y no permanente, mensajes claros, desbloqueo asistido por admin; cooldowns por email en vez de solo por IP. (b) *Depender de XFF mal configurada* → si no hay proxy confiable configurado, ignorar XFF por completo (seguro por defecto). (c) *Multi-instancia resetea el limiter in-memory* → lockout en Mongo ya sobrevive; para el limiter de IP, coord. plan 05/04 (Redis) y documentar que hoy es por proceso. (d) *Exceso de escrituras de lockout* → upsert pequeño por intento fallido, aceptable; TTL libera espacio.

**Rollback.** Cada límite es configurable (bajarlos o desactivar el lockout por flag de emergencia documentado). El fix de IP no debería revertirse nunca (usar XFF a ciegas es el agujero).

**Dependencias.** Plan 05 (memoria/Redis/escalado), plan 02 (colección nueva y TTL), SOL-AL-02 (el contador por cuenta es el mismo mecanismo), SOL-CR-01 (límites de admin), SOL-AL-06 (upload).

**Esfuerzo.** M con lockout en Mongo; L si se migra todo a Redis en esta fase.

### 4.7 SOL-AL-02 — AL-02 (+ME-11, ME-10): PIN con política real, separado del código de activación

**Enfoque.** Dejar de usar un mismo valor para tres cosas (código de activación, credencial de login permanente y PIN de admin). Diseño objetivo:
- **Código de activación** (`auth_codes.tipo = activacion`): generado server-side, un solo uso, TTL 15–30 min, hasheado, con máximo de intentos; ligado al intento de registro y a cambios de email/regeneraciones.
- **PIN de acceso**: credencial de login **solo para alumnos** (`tipo_usuario=1`), generado server-side con CSPRNG, `^\d{6}$`, único (reintento ante colisión), almacenado de forma que un volcado de DB no lo exponga trivialmente (hash con pepper de servidor, que permite búsqueda por igualdad; se documenta el trade-off frente al PIN en claro actual), comparado con `hmac.compare_digest`.
- **Bloqueo por cuenta** (compartido con SOL-AL-01) y mensajes uniformes (SOL-AL-04).
- **Regeneración** de PIN (autoservicio con verificación por email o asistida por admin) con invalidación inmediata del anterior y corte de sesiones (`tv`).
- **ME-10:** el PIN no viaja en respuestas de login/verificar-token ni en el asunto del email; se muestra solo en la pantalla de activación del propio flujo y en acciones explícitas de soporte.
- **ME-11:** si se mantiene la posibilidad de PIN provisto por el usuario (accesibilidad), validar `^\d{4,10}$` **real** (el README lo promete y no se cumple), lista negra (repetidos, secuencias, `123456`, `999999`, etc.) y unicidad, capturando `DuplicateKeyError` con reintento acotado (hoy → 500).

**Archivos a tocar.**
- `app/features/auth/service.py:90-125` (login por PIN: filtro de rol ya en SOL-CR-04, comparación, lockout, mensajes uniformes), `:204-290` (registro: generación/validación de código y PIN por separado), `:292-338` (`verificar_codigo_registro` contra `auth_codes`), `:340-363` (reenvío: nuevo código, no el PIN).
- `app/features/auth/schemas.py:8-16,25-36` — `LoginCodigoRequest` (formato de PIN si aplica), `RegisterRequest.codigoAcceso` (validación estricta o eliminación).
- `app/features/auth/email_service.py` — plantilla de activación sin lenguaje de "tu PIN permanente" (o con el PIN solo si el producto lo exige y SOL-AL-05 lo permite: nunca en asunto); incluir aviso de que se puede regenerar.
- `app/features/auth/router.py` — `POST /api/auth/regenerar-pin` (público con verificación por email) y/o endpoint admin de reemisión.
- `app/scripts/init_db.py` — quitar `999999` (SOL-CR-04).
- `app/core/security.py` — helpers `generate_pin()`, `hash_pin()`/`verify_pin()` (HMAC con pepper o bcrypt según decisión), `generate_activation_code()`.
- `app/core/database.py` — colección `auth_codes` con índice TTL; índice único de `pin_hash` (o `codigo_acceso` hasta migrar).
- Migración: los usuarios existentes conservan su PIN actual en `codigo_acceso`; al primer uso post-deploy se puede migrar a `pin_hash` de forma perezosa (al loguear) o dejar la migración masiva con ventana (decisión). Sin migración forzosa de PIN salvo campaña de rotación.

**Pasos.**
1. Implementar `auth_codes` y separar físicamente los flujos: registro → se crea cuenta pendiente + código de activación (no PIN visible); activación → consume código → se genera el PIN definitivo (o se activa el ya generado) y se muestra en pantalla para que el alumno lo guarde.
2. Reforzar el login por PIN: unicidad, comparación constante, lockout, mensajes uniformes, sin rol admin.
3. Regeneración: endpoint + email de verificación + invalidación + `tv`.
4. ME-10/ME-11: dejar de devolver `codigoAcceso` en `format_user_response` salvo casos explícitos (`GET /usuario/{id}` de uno mismo/admin, `magic-link` admin), validar formato si se admite PIN provisto, blacklist y captura de `DuplicateKeyError`.
5. Coordinar con comunicación al alumno: "tu código de activación es de un solo uso; tu PIN de 6 dígitos es tu acceso del día a día" (si el producto decide mantener el PIN como credencial; alternativa futura: magic links asistidos).

**Criterios de aceptación y verificación (pruebas).**
- Registro con `codigoAcceso` provisto: según decisión, (a) se ignora y se genera server-side, o (b) se acepta solo si cumple `^\d{4,10}$`, no está en blacklist y es único; en colisión → reintento (nunca 500). Ambos casos test.
- Código de activación: un solo uso, expira (test con reloj congelado), intentos limitados, comparación constante; el reenvío emite uno **nuevo** e invalida el anterior.
- Login por PIN: PIN correcto → token; incorrecto ×N → lockout; usuario admin → rechazado; PIN de otro usuario → rechazado; `codigoAcceso` ya no aparece en la respuesta de login (`assert "codigoAcceso" not in resp` salvo casos explicitados).
- Regeneración: PIN viejo deja de funcionar, `tv` invalida tokens previos, el nuevo funciona.
- Asunto del email sin código (test de `subject`).
- Timing/comparación: unit test de que la verificación usa `compare_digest` (test estático/monkeypatch).

**Riesgos y mitigación.** (a) *La población objetivo olvidará su PIN* → fricción de soporte; mitigar con asistencia telefónica que reemite, textos grandes, y no forzar cambios masivos sin campaña. (b) *Migración de PINs existentes* → hacerla perezosa y tolerante; no romper login de nadie. (c) *El hash con pepper impide consultar `find_one({codigo_acceso})`* → se mantiene índice por hash determinista con pepper en env (el pepper se rota con cuidado; si se pierde, hay que reemitir todo). (d) *Cambios de contrato en documentos de email* → revisar plantillas con el equipo de contenidos.

**Rollback.** Los flujos nuevos pueden convivir con los viejos por una release (doble lectura: si no existe `pin_hash`, usar `codigo_acceso` actual). El rollback de la separación es volver a usar el mismo valor, lo que no se recomienda; el rollback admisible es desactivar la regeneración y mantener el resto.

**Dependencias.** SOL-CR-04 (rol admin), SOL-CR-05 (el cambio de email reutiliza `auth_codes`), SOL-AL-01 (lockout), SOL-AL-03 (`tv`), SOL-AL-04 (mensajes), SOL-AL-05 (emails/logs), plan 02 (`usuarios`, migración), plan 06.

**Esfuerzo.** L (núcleo del modelo de credenciales; toca registro, activación, login, email y datos históricos).

### 4.8 SOL-AL-03 — AL-03: sesiones con expiración razonable, revocación real y magic links sin JWT en URL

**Enfoque.**
- **Access tokens cortos** (15–60 min) con claims `jti`, `iss`, `aud`, `iat`, `exp` y `tv` (token version).
- **Refresh tokens** opacos (CSPRNG, 256 bits), almacenados **hasheados** en `refresh_tokens` (`user_id`, `token_hash`, `exp`, `revoked`, familia), con rotación en cada uso y **detección de reuso** (si se usa un refresh ya rotado, se revoca toda la familia).
- **`logout`** que revoca el refresh presentado; opcional denylist de `jti` con TTL para cortar el access vigente (el costo de un access de 30 min es acotado; el refresh es el que manda).
- **Revocación por `tv`:** `get_current_user` compara `payload.tv` con `usuarios.token_version` (0 por defecto). Se incrementa en: cambio de contraseña, regeneración de PIN, cambio de email, toggle de activo/black, cambio de rol. Con esto, "cambiar una credencial corta las sesiones" pasa a ser verdad.
- **Magic links:** no más `?token=<JWT>`. Se emite un **código de acceso de un solo uso** (aleatorio, TTL corto, hasheado) embebido en la URL; la página de acceso hace `POST /api/auth/canjear-acceso {code}` y recibe access+refresh. El JWT nunca viaja por email/historial/Referer. Afecta `enviar_acceso_correo` (`auth/service.py:181-184`) y `usuario/{id}/magic-link` (`usuario/router.py:132-140`).
- **Frontend:** interceptor que renueva access con refresh y hace `logout` en error de refresh; almacenamiento a revisar (idealmente memoria + refresh httpOnly, decisión de sección 7).

**Archivos a tocar.**
- `app/core/config.py` — `JWT_ACCESS_TOKEN_MINUTES=30`, `JWT_REFRESH_TOKEN_DAYS=30` (reemplazan `JWT_EXPIRATION_DAYS=180`; dejarlo como fallback deprecado una release), `ACCESS_CODE_TTL_MINUTES=10`.
- `app/core/security.py:29-54` — claims nuevos; `create_refresh_token()`/`hash_token()`; `decode_access_token` valida `iss`/`aud`.
- `app/core/dependencies.py:9-61` — check de `tv`; 401 uniforme también para usuario inexistente (BA-05); opcional check de denylist.
- `app/features/auth/service.py` — `login_sistemas`/`login_codigo`/`verificar_codigo_registro` devuelven access+refresh; `enviar_acceso_correo` emite código de un solo uso; nuevos `refresh_token()`, `logout()`, `canjear_acceso()`; incrementos de `tv` en los eventos sensibles; registros de auditoría.
- `app/features/auth/router.py` — `POST /api/auth/refresh`, `POST /api/auth/logout`, `POST /api/auth/canjear-acceso`.
- `app/features/usuario/router.py:119-143` — `magic-link` devuelve URL con código de un solo uso; mantener `codigoAcceso` solo si soporte lo necesita (decisión ME-10).
- `app/core/database.py` — colección `refresh_tokens` con TTL sobre `exp` e índice por `token_hash`; índice TTL para `access_codes`.
- Frontend (login, refresh, logout, `/acceso`): adaptación del contrato (nuevos campos `refreshToken`, `accessToken`/`token`).
- `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md` — ciclo de vida completo.

**Pasos.**
1. Introducir `tv` y claims con la expiración actual primero (compatible: tokens viejos sin `tv` se tratan como `tv=0`), desplegar, verificar que nadie se rompe.
2. Acortar access tokens y emitir refresh; el frontend aún puede ignorarlo en una primera release (si ignora el refresh, el usuario simplemente re-loguea más seguido → aceptable transitorio). Detectar esto con telemetría.
3. Implementar refresh+rotación+reuso+logout y adaptar el frontend.
4. Migrar los magic links a códigos de un solo uso (backend y frontend a la vez; el `?token=` viejo se deja de emitir y, tras una release, se documenta como no soportado).
5. Aumentar `tv` en todos los eventos de credencial (enlazado con SOL-AL-02/CR-04/CR-05).

**Criterios de aceptación y verificación (pruebas).**
- Access expirado → 401; refresh válido → nuevo par; refresh reutilizado → 401 y **toda la familia revocada** (test).
- `logout` → refresh inválido; access vigente sigue hasta expirar (documentado) o se corta si se implementó denylist.
- Cambio de contraseña/PIN/email/toggle → `tv` sube → tokens previos 401 (test por evento).
- Magic link: URL sin JWT (grep de la URL generada), código de un solo uso, TTL, `canjear-acceso` devuelve tokens y el segundo canje falla.
- `POST /api/auth/verificar-token` ya no devuelve `codigoAcceso` (ME-10/BA-06, enlazado).
- Usuario borrado con token válido → 401 (no 404, BA-05).
- Tests: `tests/security/test_tokens_lifecycle.py`, `test_magic_link_codes.py`.

**Riesgos y mitigación.** (a) *Romper la UX de una población que no maneja re-login* → mantener access razonable (30 min) y refresh largo (p. ej. 30 días) con rotación silenciosa; el objetivo es revocar, no molestar. (b) *Corte masivo de sesiones al subir `tv`* → no incrementar `tv` retroactivamente en el deploy; solo en eventos nuevos. (c) *Pérdida del refresh (storage limpiado)* → re-login por PIN/magic link (aceptable). (d) *Coordinar frontend en `/acceso`* → el canje por POST es un cambio real de contrato; mantener compatibilidad temporal aceptando `?token=` solo durante la ventana de transición con aviso en logs de auditoría (no emitirlo más). (e) *Sobrecomplicar con denylist* → dejar la denylist como opcional; `tv` + refresh ya cierran el caso.

**Rollback.** Volver a `JWT_EXPIRATION_DAYS=180` y aceptar tokens como antes (rollback de emergencia, mantiene el par `refresh` sin uso); el cambio de magic link puede convivir emitiendo ambos formatos durante la transición si hiciera falta (no recomendado prolongar por el riesgo del JWT en URL).

**Dependencias.** Plan 04 (JWKS/identidad futura; `tv` es la semilla del mecanismo de revocación), SOL-AL-02/CR-04/CR-05 (eventos que suben `tv`), plan 06, frontend (contrato de refresh/logout/acceso).

**Esfuerzo.** L (backend L; frontend M).

### 4.9 SOL-AL-04 — AL-04 (+BA-05): anti-enumeración de cuentas

**Enfoque.** Respuestas uniformes (mismo código, mismo mensaje y latencia comparable) para "existe" y "no existe" en todos los flujos públicos: registro, activación, reenvío, modificación de email y login de sistemas. El email se convierte en el canal de información ("si el correo existe, te enviamos un código"), nunca la API. En `login_sistemas`, no revelar rol antes de validar contraseña; para latencias, ejecutar un `bcrypt` *dummy* cuando el usuario no existe.

**Archivos a tocar.**
- `app/features/auth/service.py:54-88` (login_sistemas: verificar contraseña antes de revelar rol; 401 uniforme; dummy hash), `:204-229` (register con email activo: 200 genérico + email "ya tenés cuenta"), `:292-302` y `:340-349` (activación/reenvío: 200 genérico), `:365-408` (modificar email: 200 genérico — se reescribe igual por SOL-CR-05).
- `app/core/dependencies.py:49-53` — usuario inexistente → 401 uniforme (BA-05), no 404.
- `app/features/auth/email_service.py` — correos informativos acordes ("ya existe una cuenta", "si no pediste esto, ignorá").
- Tests: `tests/security/test_enumeration.py`.

**Criterios de aceptación y verificación (pruebas).**
- Suite que compara, para un email registrado y uno no registrado, el par (status, cuerpo) en: register, verificar-codigo, reenviar, solicitar cambio de email, login-sistemas → **idénticos**.
- Login-sistemas con contraseña incorrecta para email existente vs inexistente → mismo 401 y mensaje.
- Latencia: test de humo (no estricto) de que no hay diferencia grosera en login-sistemas (dummy bcrypt).
- El email correspondiente sí se envía para el existente (verificable en test con fake SMTP).

**Riesgos y mitigación.** (a) *UX de "reenvié el código" cuando el email no existe* → texto genérico con instrucciones; soporte capacitado. (b) *Romper el flujo de registro actual que informa "ya está registrado"* → es el comportamiento a cambiar; comunicar al frontend (mostrar el mensaje genérico del backend). (c) *Costos de bcrypt dummy* → acotado por rate limit.

**Rollback.** Trivial (revertir mensajes), pero no recomendado; el rollback aceptable es limitado a flujos internos si producto necesita mensajes específicos por accesibilidad (documentarlo como decisión consciente y compensar con rate limit/lockout).

**Dependencias.** SOL-CR-05 (flujo nuevo), SOL-AL-01 (límites), plan 06.

**Esfuerzo.** S.

### 4.10 SOL-AL-05 — AL-05 (+ME-05): logs sin códigos/tokens/PII y SMTP que falla ruidosamente

**Enfoque.** (1) Ningún log, asunto de email ni respuesta contiene códigos, PINs, magic links o tokens; (2) si falta configuración SMTP en producción, el envío **falla** (5xx y alerta) en vez de simular; (3) el fallback de desarrollo queda detrás de una flag explícita y nunca se activa en producción; (4) `MONGODB_URL` se loguea enmascarada; (5) purga/rotación de lo ya filtrado (operativo, sección 5); (6) filtro de redacción defensivo para evitar reintroducir fugas.

**Archivos a tocar.**
- `app/features/auth/email_service.py:16-23,42-45,98,101-107,126-128` — quitar código/enlace de los logs; error genérico con `user_id` (no email completo si no hace falta); asunto del email sin código; el fallback "simulado" solo con `APP_ENV=development` y `DEV_EMAIL_FALLBACK=true`, y sin imprimir el código completo (o directamente exigir SMTP local en desarrollo). En producción sin SMTP válido → levantar error 500 explícito (y healthcheck de configuración recomendado).
- `app/core/database.py:21` — enmascarar URL (`mongodb://***@host/db`).
- `app/main.py` — configurar un filtro de logging (`logging.Filter`) que redacte claves `codigo`, `pin`, `token`, `password`, `Authorization`, `access_url`; aplicarlo al root logger.
- `.env.example` — `DEV_EMAIL_FALLBACK=false`.
- Tests: `tests/security/test_logs_no_secrets.py` (usar `caplog` y capturar logs durante registro/activación/fallo SMTP forzado).

**Criterios de aceptación y verificación (pruebas).**
- Forzando fallo de SMTP: los logs capturados **no** contienen el código ni la URL con token; la respuesta al cliente es 5xx con mensaje genérico.
- `register` y `verificar-codigo` no loguean el PIN (grep sobre `caplog`).
- `connect_to_mongo` loguea la URL sin credenciales.
- Asunto del correo de activación sin dígitos del código (test del `subject`).
- En `APP_ENV=production` con `DEV_EMAIL_FALLBACK=true` → la app no arranca o el envío falla (test de configuración).
- Purga de logs históricos ejecutada y acceso restringido (verificación operativa, sección 5).

**Riesgos y mitigación.** (a) *Perder capacidad de debug en incidentes de email* → loguear `message_id`/resultado sin el secreto; en desarrollo usar SMTP local (MailHog/Papercut) o consola dedicada con la flag. (b) *Rotar retroactivamente todo lo que pudo filtrarse es imposible de determinar* → asumir el compromiso histórico: JWT rotado (CR-03) y campaña de regeneración de PIN evaluada (decisión, sección 7); mientras tanto, lockout (AL-01) y TTL corto de códigos (AL-02) limitan el daño de códigos ya expirados.

**Rollback.** Revertir el fail-fast de SMTP solo en entornos no productivos. En producción no se vuelve al fallback silencioso.

**Dependencias.** SOL-AL-02 (qué deja de loguearse), SOL-CR-03 (purga), ops (acceso a logs, purga).

**Esfuerzo.** S (código) + S operativo (purga).

### 4.11 SOL-AL-06 — AL-06: uploads con validación real y límites

**Enfoque.** El endpoint de imágenes queda detrás de admin (SOL-CR-01) y se endurece: límite de tamaño en la aplicación (5 MB), validación de **magic bytes** y formato real (JPEG/PNG/WebP) antes de decodificar, `Image.MAX_IMAGE_PIXELS` acotado y tratamiento de `DecompressionBombError`, verificación del archivo abierto (`verify()` + reapertura), descarte de EXIF (privacidad), rate limit y cuota de disco, y persistencia real (volumen o storage externo, coord. plan 02-A5).

**Archivos a tocar.**
- `app/features/narrative/admin/image_service.py:38-95` — `MAX_UPLOAD_BYTES` (5 MB) con lectura acotada (`await file.read(MAX+1)`), validación de firma binaria, `Image.MAX_IMAGE_PIXELS = 25_000_000` (ajustable) + `try/except Image.DecompressionBombError`, límite de dimensiones de entrada, `exif=img.getexif()` limpiado al guardar (o `img.info.pop('exif')`), cota de píxeles tras `thumbnail` (ya acotada), manejo de errores sin filtrar detalles internos.
- `app/features/narrative/admin/router.py:82-91` — auth (SOL-CR-01) + rate limit + parámetros de categoría ya validados.
- `app/core/config.py` — `MAX_UPLOAD_MB=5`, `MAX_IMAGE_PIXELS`.
- `docker-compose.yml` — volumen para `app/static/narrative` (coord. plan 02).
- `requirements.txt` — opcional: librería de detección (`filetype`/`python-magic`) si no se hace manualmente; si se agrega, fijar versión (BA-01).
- Tests: `tests/security/test_uploads.py`.

**Criterios de aceptación y verificación (pruebas).**
- Sin token/admin → 401/403; con admin → 200 con WebP.
- Archivo > 5 MB → 400/413 sin decodificar (test con bytes grandes).
- Archivo que no es imagen (texto con extensión `.jpg`) → 400.
- Imagen "bomba" (PNG pequeño con dimensiones enormes, generado en test) → 400 controlado, sin OOM del proceso de test (por diseño de test, límite bajo).
- EXIF GPS de la entrada no aparece en la salida (test con imagen con EXIF inyectado).
- Categoría inválida → 400 (ya existe); rate limit → 429.
- La imagen persiste tras un redeploy (verificación operativa con volumen).

**Riesgos y mitigación.** (a) *Rechazar imágenes legítimas de personas mayores* (fotos grandes de celular) → mensaje claro con límite y, si hace falta, redimensionado cliente-side; validar con fotos reales de prueba. (b) *Pillow sin cota por versión* → fijar versión (BA-01) y mantener actualizada con revisión. (c) *Almacenamiento local efímero* → coord. plan 02; si no hay volumen en esta fase, documentar la pérdida y priorizar.

**Rollback.** Los límites son configurables; el rollback de validación de formato no es aceptable en producción (reintroduce el vector). El rollback de la cota de píxeles puede subirse si rompe casos legítimos, con valor documentado.

**Dependencias.** SOL-CR-01 (auth), plan 02 (persistencia de imágenes y cuotas), plan 05 (offload a thread de Pillow), plan 06 (tests).

**Esfuerzo.** S.

### 4.12 SOL-ME-01 — ME-01: CORS con orígenes explícitos

**Enfoque.** Reemplazar `allow_origin_regex=r"^https?://.*$"` + `allow_credentials=True` por una lista explícita de orígenes por entorno desde configuración (`CORS_ALLOWED_ORIGINS`), sin regex (salvo localhost en `APP_ENV=development`), con `allow_credentials=False` mientras el modelo sea Bearer (el token viaja en header, no en cookies, según la guía actual). Acotar métodos y headers a los usados. Validar en el arranque que en producción los orígenes sean `https://` y no localhost.

**Archivos a tocar.**
- `app/main.py:80-98` — CORS desde config; eliminar la regex fija; mantener credenciales solo si algún día se adopta cookie httpOnly (entonces sí: orígenes exactos + CSRF).
- `app/core/config.py` — `CORS_ALLOWED_ORIGINS: list[str] = []`; validación en producción (falla si vacío o si contiene localhost/`*`).
- `.env.example` — ejemplo de lista; documentar que `allow_credentials` se activa únicamente con el patrón cookie+CSRF.

**Criterios de aceptación y verificación (pruebas).**
- Preflight/GET con `Origin: https://evil.example` → **sin** header `Access-Control-Allow-Origin`.
- Con el origen real de producción → header exacto (no `*`, no reflexión arbitraria).
- `allow_credentials` fuera del flujo cookie → `false` (test de configuración).
- En `APP_ENV=production` con orígenes vacíos/localhost → la app no arranca (test de configuración).
- Tests: `tests/security/test_cors.py`.

**Riesgos y mitigación.** *Romper el frontend real* si su origen no está en la lista → obtener los orígenes reales del despliegue antes del cambio (decisión, sección 7) y probar en staging; monitorear errores CORS en la consola del browser. *Confusión con desarrollo* → la flag de desarrollo conserva localhost.

**Rollback.** Re-agregar temporalmente el origen faltante (nunca la regex abierta). El rollback con regex solo se admite en desarrollo.

**Dependencias.** Decisión sobre el modelo de sesión de la SPA admin (opciones de SOL-CR-01), despliegue (dominios reales), plan 06.

**Esfuerzo.** S.

### 4.13 SOL-ME-02 — ME-02: tokens sin validación de estado activo

**Enfoque.** En los endpoints con efectos persistentes, la identidad se valida contra la base (estado, borrado, `tv`) y **un token inválido presente nunca degrada a invitado**. Regla: (a) sin header `Authorization` → comportamiento invitado donde el producto lo permita (narrativo demo); (b) con header presente e inválido/expirado → 401; (c) usuario desactivado → 403. Los endpoints de `user_attempts` pasan a exigir token (SOL-CR-06).

**Archivos a tocar.**
- `app/features/narrative/game/router.py:64-76` — reemplazar `_get_current_user_id` por una dependencia que distinga "sin token" (invitado explícito) de "token presente inválido" (401) y use `get_current_user` para tokens válidos (estado activo, `tv`).
- `app/features/user_attempts/router.py` — ya cubierto por SOL-CR-06.
- `app/core/dependencies.py` — helper `get_optional_current_user` (retorna `None` si no hay header; lanza 401 si hay header inválido).
- `app/core/rate_limit.py:40-46` — el bypass por claim ya se elimina en SOL-AL-01 (misma raíz: nunca confiar en el claim sin DB).

**Criterios de aceptación y verificación (pruebas).**
- Usuario desactivado con token vigente → 403 en narrativo (endpoints autenticables) y en attempts.
- Token corrupto/expirado con header → 401 (no invitado silencioso).
- Sin header → invitado donde esté diseñado (test de contrato).
- Usuario borrado → 401 uniforme (BA-05).
- Tests: `tests/security/test_token_state.py`.

**Riesgos y mitigación.** *Cambiar el comportamiento del invitado que traía un token vencido guardado en localStorage* → el frontend debe limpiar tokens inválidos al recibir 401 (coordinar; hoy el usuario seguiría como invitado). Es el comportamiento correcto: un token inválido no debe conceder acceso persistente.

**Rollback.** Revertir el helper a la degradación silenciosa reintroduce el bypass de desactivación; no recomendado. Rollback admisible: permitir invitado solo en lecturas de demo si el producto lo exige, documentado.

**Dependencias.** SOL-CR-06, ME-03 (identidad de invitado), plan 02-A3.

**Esfuerzo.** S.

### 4.14 SOL-ME-04 — ME-04: MongoDB con autenticación

**Enfoque.** Habilitar auth de MongoDB con credenciales por secret/env: usuario root solo para administración y un usuario de aplicación de mínimo privilegio (`readWrite` sobre la base de la app) para el backend; mantener la red interna y jamás publicar `27017`; healthcheck con credenciales; backups con credenciales. Documentar la migración sobre un volumen existente (crear usuarios antes de exigir auth).

**Archivos a tocar.**
- `docker-compose.yml:72-97` — `environment: MONGO_INITDB_ROOT_USERNAME/PASSWORD` (desde `secrets`/env), `command: ["--auth"]`, `MONGODB_URL` del backend con usuario de app (`...authSource=<db>`), healthcheck autenticado.
- Nuevo `mongo/init/01-app-user.js` (montado en `/docker-entrypoint-initdb.d`) — crea el usuario de app con `readWrite` en `mayores_actualizaciones` (y otro para ETL si aplica, mínimo privilegio).
- `.env.example` / secrets — placeholders de credenciales; nada real en el repo.
- `docs_interna/README_SEGURIDAD.md` — corregir el claim "no expuesto" agregando "con autenticación habilitada".

**Pasos (volumen existente).**
1. Con el Mongo actual (sin auth), crear root y usuario de app (`db.createUser(...)`) y probar conexión.
2. Actualizar backend a la URL con credenciales, redesplegar y verificar.
3. Reiniciar Mongo con `--auth`; verificar que sin credenciales falla y que el backend opera.
4. Verificar que el puerto no se publica y que los backups usan credenciales.
5. En un volumen nuevo (initdb) el script de init crea todo automáticamente: validar en un entorno de prueba.

**Criterios de aceptación y verificación.**
- `mongosh` sin credenciales desde otro contenedor de la red → **falla** de autenticación.
- Backend: healthcheck, lectura/escritura, seeds y generación funcionan con el usuario de app.
- `docker compose config`/revisión: `27017` no publicado; root no usado por el backend.
- Test de infraestructura documentado (no automatizable 100% aquí): verificación manual en staging + smoke de la app.

**Riesgos y mitigación.** (a) *Bloquear el acceso a datos existentes* → hacerlo con backup y en ventana; primero crear usuarios, después exigir auth. (b) *Olvidar un consumidor no autenticado* (ETL, scripts) → inventario previo: `migrate_from_mysql.py` y seeds usan `get_database()` con la URL de config → se actualizan solos, pero confirmar cada entrypoint. (c) *Rotación del root* → tratar como SOL-CR-03 (secret).

**Rollback.** Quitar `--auth` y volver a la URL sin credenciales (mantener los usuarios creados); es un rollback aceptable solo como emergencia y con registro del incidente.

**Dependencias.** SOL-CR-03 (gestión de secretos), plan 02 (backups/migración, ETL), plan 04 (bases lógicas separadas a futuro: aquí se prepara el camino).

**Esfuerzo.** M (operativo).

### 4.15 SOL-ME-06 — ME-06: `/docs`, `/redoc`, `/openapi.json` y SPA admin según despliegue

**Enfoque.** La documentación interactiva se apaga en producción vía configuración (`docs_url=None`, `redoc_url=None`, `openapi_url=None`), y la SPA admin (`/admin`) queda fuera de internet: hoy no está ruteada por Caddy (bien), pero el plan la asegura por diseño (VPN/SSO/bloqueo de red) además del cierre de la API (SOL-CR-01). Agregar `noindex` y considerar CSP (BA-03, infra).

**Archivos a tocar.**
- `app/main.py:70-78` — URLs de docs condicionadas a `ENABLE_DOCS`/`APP_ENV` (en producción, `None`).
- `app/main.py:139-165` — dejar el mount estático como está, pero documentar que su exposición depende del borde; si el producto mantiene la SPA en el backend, colocarla detrás de la misma red admin que la API; opción de eliminar el mount si la gestión migra al frontend principal (decisión).
- `Caddyfile` — confirmar/bloquear explícitamente `/admin`, `/docs`, `/redoc`, `/openapi.json`, `/assets` si no deben ser públicos (documentar cada decisión).
- `app/core/config.py` — `ENABLE_DOCS: bool = False` (con default `true` solo en `development`).

**Criterios de aceptación y verificación.**
- En producción: `GET /docs`, `/redoc`, `/openapi.json`, `/admin` → 404 (o inalcanzable por el borde).
- En desarrollo: siguen disponibles para trabajar (flag).
- Revisión cruzada con el informe 03, supuesto #3: si en el servidor real hay un proxy externo, la regla debe replicarse/fijarse.
- Test de app con `APP_ENV=production` → asserts de que las rutas de docs no existen.

**Riesgos y mitigación.** *Pérdida de acceso a OpenAPI en producción para diagnóstico* → servir el esquema como artefacto de build/CI (no por el servicio público) y mantener la doc en el repo. *Confusión del equipo de frontend* → documentar la URL de cada entorno.

**Rollback.** Reactivar `ENABLE_DOCS=true` (no recomendado en internet; si se necesita, exponerlo detrás del borde con auth).

**Dependencias.** SOL-CR-01 (admin API), ops/Caddy, BA-03 (TLS/CSP).

**Esfuerzo.** S.

### 4.16 SOL-DOC-01 — Documentación de seguridad veraz

**Enfoque.** `docs_interna/README_SEGURIDAD.md` hoy describe una realidad que no existe (claims #1, #4, #5, #6, #8 son falsos o engañosos según el informe 03, sección 5). Dos opciones: (a) corregir cada claim al estado real; (b) marcarlo explícitamente como **objetivo/roadmap** hasta que las soluciones se implementen, con un banner y una tabla "estado verificado". Se recomienda (b) ahora y (a) a medida que cada fase cierre. Además: `README.md` sin credenciales por defecto (CR-04) y `GUIA_INTEGRACION_FRONTEND_AUTH.md` actualizada con el ciclo de tokens nuevo (AL-03), el canje de acceso (CR-05/AL-03), el rechazo por enumeración (AL-04) y la autenticación de la SPA admin (CR-01).

**Archivos a tocar.**
- `docs_interna/README_SEGURIDAD.md` — banner "Documento aspiracional: ver `03-auditoria-de-seguridad-soluciones.md`"; tabla de claims con estado real (ver informe 03, sección 5) y fecha de última verificación; ir corrigiendo a medida que cada fase cierre.
- `README.md:76` — eliminar credenciales por defecto y runbook del admin.
- `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md` — flujos actualizados (registro/activación por código, PIN sin exponer, refresh/logout, código de acceso de un solo uso, CORS/headers).
- `docs_interna/ARQUITECTURA_JUEGOS_Y_NARRATIVO.md` — menciones de auth admin cuando se implemente (coord. plan 01/04).

**Criterios de aceptación y verificación.**
- `grep -i` sin credenciales por defecto (`admin123`, `999999`) en `README.md` y `docs_interna` (test de higiene documental).
- Checklist de `README_SEGURIDAD.md` con columna "Estado verificado (fecha)"; nada marcado ✅ que el informe 03 haya refutado sin corrección.
- La guía de frontend refleja el contrato real (validar con los endpoints implementados en F1–F3).

**Riesgos y mitigación.** *Documentación desactualizada otra vez* → incluir la revisión documental como criterio de cierre de cada fase (sección 6) y en el checklist de PR (plantilla).

**Rollback.** N/A (solo documentación).

**Dependencias.** Todas las soluciones de F1–F3 (se actualiza al ritmo de cada cierre).

**Esfuerzo.** S.

### 4.17 Soluciones complementarias (medios y bajos restantes)

Además de las soluciones detalladas, quedan hallazgos del informe 03 que no están en la lista obligatoria de la misión pero que conviene dejar planificados. Se agrupan aquí con el mismo formato abreviado (enfoque · archivos · criterio · esfuerzo):

| Hallazgo | Enfoque / solución | Archivos principales | Criterio de aceptación clave | Esf. |
|---|---|---|---|---|
| **ME-03** — invitado `user_id=0` compartido | Identidad de invitado por dispositivo (ID aleatorio en cookie firmada/header) o exigir login para escrituras narrativas; nunca usar `0` como usuario real. Decisión de producto (sección 7). | `app/features/narrative/game/router.py`, `setup_service.py`, `app/core/dependencies.py`; coord. plan 02-A3 | Dos invitados simultáneos no comparten run ni pueden reiniciarse entre sí; test de aislamiento | M |
| **ME-08** — soluciones de desafíos expuestas | Serialización pública sin campos sensibles (`config.solution` y análogos) y validación server-side de respuestas no iniciadas; mover upsert a admin (ya en SOL-CR-01). | `app/features/daily_challenges/service.py:26-48,351`, `schemas.py`, `router.py` | `GET /api/challenges/*` no incluye `solution`/soluciones; juego valida la respuesta en servidor; tests por juego | M |
| **ME-09** — headers no propagados | Propagar `exc.headers` en el handler de excepciones. | `app/main.py:104-114` (incluido en SOL-AL-01) | 429 conserva `Retry-After`; 401 conserva `WWW-Authenticate` (test) | S |
| **ME-10** — PIN en respuestas y asunto | Quitar `codigoAcceso` de `format_user_response` salvo casos explícitos (self/admin/magic-link de soporte); asunto sin código. Incluido en SOL-AL-02/AL-05. | `app/features/auth/service.py:44`, `email_service.py:98` | Login/verificar-token no devuelven `codigoAcceso`; tests de contrato | S |
| **ME-11** — PIN elegible y contraseña opcional | Validación/blacklist/unicidad del PIN provisto (o generación siempre server-side); `password` con `min_length` cuando exista (BA-07). Incluido en SOL-AL-02. | `app/features/auth/schemas.py:28-29`, `service.py:235-241` | Casos de colisión → reintento sin 500; PIN débil rechazado; tests | S |
| **BA-01** — dependencias sin pin | Fijar versiones o lockfile con hashes (`pip-compile`/`uv lock`), automatizar actualizaciones con revisión. | `requirements.txt` | Build reproducible; `pip-audit`/`trivy` sin críticos; lockfile en repo | S |
| **BA-02** — contenedor root y `COPY . .` | Usuario no-root, copias explícitas (incluido en SOL-CR-03), `read_only`/`tmpfs` donde se pueda. | `Dockerfile` | Proceso no corre como root (`id` ≠ 0); imagen sin `.env` | S |
| **BA-03** — Caddy sin TLS/HSTS/CSP | TLS en el borde real (o documentar el proxy TLS frontal), HSTS y CSP para la SPA; revisar timeouts. Mayormente infra fuera del repo. | `Caddyfile`, infra del servidor | Prueba TLS + headers HSTS/CSP presentes; documentado quién termina TLS | M |
| **BA-04** — `GET /usuario/estados` público | Requerir auth (admin o usuario) o mover a router admin; verificar si el frontend de alumnos lo usa. | `app/features/usuario/router.py:48-50` | Sin token → 401/403; flujo admin funciona | S |
| **BA-05** — 404 vs 401 en `get_current_user` | 401 uniforme (incluido en SOL-AL-04/SOL-AL-03). | `app/core/dependencies.py:49-53` | Usuario borrado → 401 | S |
| **BA-06** — `verificar-token` sin rate limit | Agregar límite (incluido en SOL-AL-01). | `app/features/auth/router.py:34-36` | 429 al exceder (test) | S |
| **BA-07** — `password` sin `min_length` | Fortaleza/longitud mínima en registro admin y cambio de contraseña; documentar que alumnos no usan contraseña. | `app/features/auth/schemas.py:28` | Password corta rechazada (400) | S |
| **BA-08** — `init_indexes` silencioso / seed en arranque | Try/except por índice con log y health-check de índices críticos; desacoplar seed (parcial en SOL-CR-04); coord. plan 02-M10. | `app/core/database.py:55-104`, `app/main.py:38` | Fallo de índice crítico → arranque falla/alerta; test de índices requeridos | S |
| **BA-09** — remitente personal y defaults MySQL | Casilla institucional para `MAIL_FROM`; credenciales ETL dedicadas sin defaults (raíz en SOL-CR-03). | `app/core/config.py:23,35-39` | Sin defaults utilizables; remitente institucional verificado | S |
| **BA-10** — `characters` vs `personajes` | Unificar carpeta/categoría y alias. | `image_service.py`, `app/static/narrative/*` | Una sola categoría canónica; sin 404 de assets | S |

---

## 5. Acciones operativas inmediatas (sin código)

Estas acciones se ejecutan **antes o en paralelo** a los cambios de código, porque reducen el riesgo hoy. Son procedimientos operativos: este plan no los ejecuta. Requieren ventana, backup y registro de evidencias.

### 5.1 Secuencia de rotación de secretos (qué rotar y en qué orden)

**Regla de oro:** primero lo que no rompe sesiones, al final lo que las invalida. Antes de empezar: backup/snapshot de MongoDB, copia segura del `.env` actual en el gestor de secretos, y registro de la ventana (fecha, responsable, evidencia).

| Orden | Secreto | Por qué en ese lugar | Verificación post-rotación |
|---|---|---|---|
| 0 | **Backup + inventario** | Poder revertir/forense; listar todos los consumidores de cada secreto | Snapshot restaurable; inventario escrito |
| 1 | `SMTP_PASSWORD` (Brevo) | Independiente; si falla, solo afecta emails (degradación controlada) | Envío de prueba a casilla interna; revisar que no haya errores SMTP |
| 2 | `RAE_API_KEY` | Independiente; se usa en generación de crucigramas | Generación de un crucigrama de prueba (o llamada directa controlada) |
| 3 | Credenciales MySQL del ETL | Independiente; se usan solo al ejecutar la migración | Prueba de conexión con usuario de mínimo privilegio (coordinado con plan 02; no ejecutar ETL completo) |
| 4 | Usuario/clave de MongoDB | Requiere ventana (SOL-ME-04); separar root vs app | Backend y healthchecks operativos con el usuario de app; acceso sin credenciales denegado |
| 5 | Cuenta admin (`admin@sistemas.com`) | Credenciales conocidas; rotar contraseña y eliminar/regenerar el PIN | Login con credenciales nuevas; las viejas fallan; `must_change_password` activado (SOL-CR-04) |
| 6 | **`JWT_SECRET` (último)** | Invalida **todas** las sesiones: alumnos vuelven a ingresar con su PIN, admins con su contraseña nueva. **Sin período de gracia**: el secreto viejo está comprometido; tolerarlo mantendría válidos tokens forjados | Token acuñado con el valor viejo → 401; logins nuevos OK. Comunicar a operadores que habrá re-login general |
| 7 | Purga de imágenes Docker | Las imágenes viejas contienen el `.env` "horneado" (con secretos ya rotados; igualmente no deben permanecer) | `docker image prune`/retención del registry documentada; inspección de capas de la imagen nueva |

Notas:
- `JWT_SECRET_PREVIOUS` **no** se usa en esta rotación (ver SOL-CR-03). Queda disponible para rotaciones futuras planificadas, cuando exista access corto + refresh (SOL-AL-03).
- Si algún secreto de terceros ya no puede rotarse (proveedor dado de baja), documentarlo y revocar el uso desde la app.
- Todo secreto que estuvo en el repositorio, en `.env.example` o dentro de una imagen se considera **comprometido**, aunque esté "solo en Git local".

### 5.2 Contención de superficie (borde, sin código)

1. **Bloquear o restringir por red** en Caddy (o el proxy frontal) `/api/narrative/admin*`, `/api/challenges/admin*` y `POST /api/challenges` a la red administrativa/VPN (detalle en SOL-CR-01, paso 1). Hacerlo **antes** de cualquier rotación, porque el admin sigue sin auth en el backend hasta F1.
2. **Confirmar** que el backend no publica puerto al host y que `/docs`, `/redoc`, `/admin`, `/assets` no se rutean por Caddy (hoy es así; verificar en el servidor real, no asumir).
3. **Revisar logs de acceso recientes** de esos prefijos (ventana sugerida: 30–90 días si existen) para detectar uso anómalo previo; conservar como evidencia (no purgar todavía).
4. **Rate limiting de borde**: si el proxy frontal lo soporta, aplicar límites básicos a `/api/auth/*` como capa extra (complementa SOL-AL-01).

### 5.3 Cuenta admin y credenciales por defecto

1. Rotar `admin@sistemas.com`: contraseña fuerte y única; eliminar su `codigo_acceso` (PIN) de la base o dejarlo inutilizado por el filtro de rol de SOL-CR-04; activar el flag de cambio obligatorio cuando el código lo soporte.
2. Enumerar `usuarios` con `tipo_usuario = 2`: confirmar que cada uno es legítimo; desactivar/eliminar los inesperados.
3. Buscar registros con `codigo_acceso = "999999"` (además del admin): tratarlos como comprometidos y regenerar.
4. Verificar si `SEED_DEFAULT_ADMIN` en el `.env` real puede recrear la cuenta: hasta que exista el código de SOL-CR-04, **documentar** que cada arranque la repone si fue borrada (comportamiento actual `init_db`), y planificarlo en la ventana de código.

### 5.4 Evidencia, backups y detección

1. Snapshot de Mongo antes de rotaciones (sección 5.1).
2. Conservar logs relevantes como evidencia y restringir su acceso (AL-05): quien pueda leer logs hoy pudo leer códigos y magic links.
3. Correlacionar: accesos a `/api/narrative/admin/*` desde IPs desconocidas, generaciones de `generate-month` repetidas, `$inc` de puntos atípicos, tokens forjados con el secreto default (no enumerables; asumir compromiso).
4. Considerar un aviso interno (no legal sin asesoramiento) sobre la posibilidad de acceso no autorizado a datos mientras no se complete el cierre.

### 5.5 Gestión de secretos y accesos

1. Definir el mecanismo definitivo (Docker secrets, env del orquestador, vault) **antes** de rotar, para no volver a dejar secretos en archivos versionados.
2. Restringir quién puede leer el `.env` del servidor y los logs de contenedores.
3. Rotar los accesos operativos (SSH/panel del servidor) si el acceso a la imagen o al `.env` pudo estar en manos de terceros.

### 5.6 Acciones admitidas vs prohibidas en esta etapa

- **Admitidas ya:** rotaciones, bloqueos de borde, cambios de credenciales de la cuenta admin, backups, revisión de logs, vaciado de tokens vía rotación de JWT.
- **Requieren código (fases 1–3):** fail-fast de secretos, quitar el seed, PIN admin, IDOR de intentos, flujo de email, rate limit confiable, sesiones/refresh, CORS, Mongo auth en compose, docs.
- **Prohibidas como "solución":** cambiar el secreto solo en el `.env` sin sacar el default del código; desactivar el email simulado sin SMTP real; borrar logs sin evidencia; publicar la SPA admin "arreglada" solo ocultándola en el menú; dar por cerrado un hallazgo sin test negativo.

---

## 6. Roadmap por fases y verificación

### 6.1 Fases

| Fase | Objetivo | Contenido | Criterio de salida |
|---|---|---|---|
| **F0 — Contención (0–48 h, ops)** | Reducir explotabilidad sin código | Bloqueo de prefijos admin en el borde (5.2); rotaciones en orden (5.1); rotar cuenta admin (5.3); backup/evidencia (5.4) | Prefijos admin inalcanzables por internet; secretos rotados y verificados; cuenta admin rotada; evidencia archivada |
| **F1 — Críticos de código (semana 1)** | Cerrar los CR de comportamiento y el fail-fast | SOL-CR-01 backend con `shadow` → `enforce`; SOL-CR-03 código; SOL-CR-04; SOL-CR-06; SOL-AL-05 (logs); SOL-ME-01 (CORS); sellos: BA-05, BA-06, BA-07, ME-09; tests de autorización negativa | Tests verdes de: admin 401/403, fail-fast de secretos, attempts 401/IDOR, CORS, logs; SPA admin adaptada y funcionando con `enforce` |
| **F2 — Autenticación y superficie (semanas 2–3)** | Endurecer credenciales y almacenamiento | SOL-CR-05 (email); SOL-AL-01 (rate limit/lockout); SOL-AL-02 (PIN separado); SOL-AL-06 (uploads); SOL-ME-02; SOL-ME-04 (Mongo auth); SOL-ME-06 (docs) | Tests de: posesión de email, XFF/lockout, PIN/lockout, uploads, token inválido→401, Mongo sin credenciales denegado, docs 404 en prod |
| **F3 — Sesiones y ecosistema (semanas 4–6)** | Revocación real y cierre documental | SOL-AL-03 (access/refresh/logout/magic links); ajustes frontend (SPA admin, acceso, refresh); SOL-DOC-01; SOL-COMP (ME-03, ME-08, BA-01/02/03/04/08/09/10); retirar flags de transición | Tests de ciclo de tokens, canje de acceso, no-secretos-en-URL; docs corregidas; flags retiradas |
| **F4 — Verificación continua** | Que no se reintroduzca | SAST/DAST en CI, pentest con app corriendo, revisión de dependencias, monitoreo de seguridad (429s, 401s admin, errores SMTP), revisión trimestral de secretos y matriz de roles | Informe de pentest sin críticos/altos abiertos; pipeline con gates de seguridad |

**Camino crítico:** F0 completa (bloqueo + rotación JWT) y F1 en `enforce`. Si el frontend admin no puede actualizarse en la ventana, el bloqueo de red de F0 pasa a ser el control principal y F1 se limita al backend en `shadow` (decisión registrada).

### 6.2 Suite de pruebas de seguridad a agregar (estrategia de tests)

Se integra a la estrategia del plan 06 (pytest + httpx `AsyncClient`, DB de test/contenedores, fechas congeladas, CI). Módulos sugeridos:

| Archivo de test | Casos | Aserciones clave | Fase |
|---|---|---|---|
| `tests/security/test_admin_authz.py` | Paramétrico sobre todas las rutas admin (introspección de `app.routes`); anon, alumno, admin; upload multipart; `generate-month` | 401 anon / 403 alumno / 2xx admin en **cada** ruta admin y upsert | F1 |
| `tests/security/test_config_fail_fast.py` | Settings sin `JWT_SECRET`; secret débil/default; `ADMIN_API_AUTH_MODE=off` + prod; `SEED_DEFAULT_ADMIN=true` sin password; CORS vacío en prod | El arranque/instanciación falla con mensaje claro | F1 |
| `tests/security/test_attempts_idor.py` | Anon → 401; token A con `user_id=B`; body con `user_id` ajeno; doble completed secuencial y concurrente | Solo datos propios; puntos una sola vez; 403 desactivado | F1 |
| `tests/security/test_logs_no_secrets.py` | `caplog` durante register/activación; fallo SMTP forzado; log de conexión Mongo | Sin código/PIN/URL/token; URL Mongo enmascarada; asunto sin código | F1 |
| `tests/security/test_cors.py` | Origen malicioso vs real; preflight; credenciales off | Sin ACAO para malicioso; ACAO exacto para real | F1 |
| `tests/security/test_email_change_takeover.py` | Escenario del informe; código expirado/reusado/ajeno; email nuevo ocupado; doble opt-in | No hay cambio sin posesión; códigos de un solo uso; auditoría registrada | F2 |
| `tests/security/test_rate_limit.py` | XFF rotado sin proxy; XFF con proxy confiable; headers `Retry-After`; purga de memoria | Sigue el bloqueo con XFF falso; headers presentes | F2 |
| `tests/security/test_account_lockout.py` | N fallos de PIN/password; éxito resetea; ventana libera; atacante multi-IP | Lockout por cuenta; persistente | F2 |
| `tests/security/test_pin_policy.py` | PIN provisto débil/colisión; comparación; rol admin; regeneración invalida; `codigoAcceso` ausente de respuestas | Rechazos y ausencias correctas | F2 |
| `tests/security/test_uploads.py` | Sin auth; >5 MB; no-imagen; bomba de descompresión; EXIF | Rechazos controlados; EXIF fuera | F2 |
| `tests/security/test_token_state.py` | Token inválido con header → 401; desactivado → 403; borrado → 401 | Nunca degradar a invitado con header presente | F2 |
| `tests/security/test_tokens_lifecycle.py` | Access expirado; refresh rotación/reuso; logout; `tv` por evento; canje de acceso | Familia revocada; `tv` corta sesiones; código de un solo uso | F3 |
| `tests/security/test_enumeration.py` | Registro/activación/reenvío/email/login con email existente vs no | Pares (status, body) idénticos | F2 (F1 en login) |
| `tests/security/test_docs_disabled.py` | App en prod: `/docs`/`/redoc`/`/openapi.json` | 404/inexistentes | F2 |
| `tests/security/test_no_default_creds.py` | Higiene: grep de repo/docs por credenciales default; `.env.example` sin valores usables | Sin coincidencias | F1/F3 |

Además (fuera de pytest): pipeline con `pip-audit`/`trivy` (dependencias e imagen), `bandit`/Semgrep (SAST), verificación `docker history`/capas sin `.env`, OWASP ZAP baseline contra staging (DAST) y un pentest externo en F4 sobre el entorno representativo.

### 6.3 Verificación por fase (puertas de salida)

- **F0:** capturas de la regla de borde probando desde internet (404/403) y desde la red admin (200); evidencia de rotaciones (sin valores); login admin con credenciales nuevas.
- **F1:** CI con los tests de F1 en verde; prueba manual de la SPA admin completa; token forjado con el default histórico rechazado; `APP_ENV=production` sin secretos → no arranca.
- **F2:** CI con F2 en verde; prueba de fuerza bruta simulada (XFF + multi-IP) bloqueada; cuenta desactivada sin acceso; Mongo rechaza accesos sin credenciales; docs no expuestas.
- **F3:** ciclo de sesión completo (login → refresh → logout → reuso rechazado); magic link canjeado una sola vez; `README_SEGURIDAD.md` reflejando el estado real; flags retiradas del código/config.
- **F4:** informe SAST/DAST/pentest; plan de seguimiento con hallazgos nuevos priorizados.

### 6.4 Métricas de cierre

- 0 endpoints admin alcanzables sin auth (medido por test paramétrico).
- 0 secretos con default público en código o imagen; 0 `.env` en imágenes.
- 0 credenciales por defecto documentadas o activas.
- 100% de los flujos sensibles (email, PIN, tokens) con test negativo automatizado.
- MTTR de credenciales: rotación completa ejecutable en < 2 h documentada y ensayada.
- `README_SEGURIDAD.md` con cada claim fechado y verificado.

---

## 7. Preguntas abiertas y decisiones necesarias

| # | Pregunta | Impacta a | Default propuesto si no se decide | Responsable |
|---|---|---|---|---|
| 1 | ¿Se puede modificar la SPA admin (fuente externa) para enviar Bearer en la ventana de F1? ¿Hay repo/equipo? | SOL-CR-01, ME-01, ME-06 | Si no: opción C (proxy que inyecta) + mantener bloqueo de red como cierre | Producto/Frontend/Ops |
| 2 | ¿La SPA admin se gestiona desde una red conocida (VPN/IP fija) o desde ubicaciones variables? | SOL-CR-01 F0 | VPN; si no, `basic_auth` de borde como parche documentado | Ops |
| 3 | ¿El guardado en la nube de juegos requiere soporte de invitados sin cuenta? | SOL-CR-06, ME-02/03 | Writes requieren login; invitados guardan local | Producto |
| 4 | ¿El puntaje (`puntos`) se expone/rankea y cuál es la fuente de verdad? | SOL-CR-06 (calc. server-side), plan 02-A7 | Derivar de `user_attempts` y recalcular; no confiar en `$inc` del cliente | Producto/Backend |
| 5 | ¿Se admite que el usuario elija su PIN (accesibilidad) o se genera siempre server-side? | SOL-AL-02 (ME-11) | Generar server-side; si se admite, validación estricta + blacklist | Producto |
| 6 | ¿Se acepta el re-login masivo de alumnos al rotar JWT (hoy) y al acortar sesiones (F3)? | SOL-CR-03, SOL-AL-03 | Sí para la rotación de emergencia; para F3 con refresh silencioso | Producto/Ops |
| 7 | ¿Bastan lockout en Mongo + limiter in-memory, o se adopta Redis ya? | SOL-AL-01, plan 05 | Mongo lockout + in-memory con purga; Redis cuando haya ≥2 réplicas | Backend/Infra |
| 8 | ¿Dónde vive el borde real (¿hay Nginx/firewall delante de Caddy?) y quién lo administra? | ME-06, BA-03, SOL-CR-01 F0 | Asumir Caddy como único borde y documentar límites | Ops |
| 9 | ¿Se purgan/rotan los PINs históricos que pudieron pasar por logs? | AL-05, AL-02 | Campaña de regeneración asistida para cuentas afectadas; postergar masivo | Producto/Soporte |
| 10 | ¿Los frontends consumen `codigoAcceso` de las respuestas de login? | ME-10/SOL-AL-02 | Quitarlo; si lo consumen, ajustar frontend en la misma release | Frontend |
| 11 | ¿El endpoint de upsert se mantiene en `POST /api/challenges` (protegido) o se muda a `/api/challenges/admin/upsert` con deprecación? | SOL-CR-01 (contrato) | Mantener path y proteger; alias nuevo opcional | Frontend/Backend |
| 12 | ¿Se dispone de gestor de secretos (Docker secrets/vault) para F0-F1? | SOL-CR-03, ME-04 | Docker secrets/env del orquestador; nunca archivo en repo | Ops |
| 13 | ¿Qué zona horaria de negocio se adopta (afecta validación de fechas de intentos)? | SOL-CR-06, plan 02-M1 | `America/Argentina/...` con helper único | Producto/Backend |
| 14 | ¿Se hace pentest externo en F4 con qué alcance y proveedor? | F4 | ZAP baseline + pentest externo sobre staging | Seguridad |

---

## Anexo A — Mapa completo hallazgo → solución

| Hallazgo | Solución de este plan |
|---|---|
| CR-01 | SOL-CR-01 (F0 red + F1 código) |
| CR-02 | SOL-CR-01 |
| CR-03 | SOL-CR-03 + sección 5.1 |
| CR-04 | SOL-CR-04 + sección 5.3 |
| CR-05 | SOL-CR-05 |
| CR-06 | SOL-CR-06 |
| AL-01 | SOL-AL-01 |
| AL-02 | SOL-AL-02 |
| AL-03 | SOL-AL-03 |
| AL-04 | SOL-AL-04 |
| AL-05 | SOL-AL-05 |
| AL-06 | SOL-AL-06 |
| ME-01 | SOL-ME-01 |
| ME-02 | SOL-ME-02 (+ SOL-CR-06) |
| ME-03 | SOL-COMP (ME-03) |
| ME-04 | SOL-ME-04 |
| ME-05 | SOL-AL-05 |
| ME-06 | SOL-ME-06 |
| ME-07 | SOL-AL-01 |
| ME-08 | SOL-COMP (ME-08) |
| ME-09 | SOL-AL-01 (+ SOL-COMP) |
| ME-10 | SOL-AL-02 (+ SOL-COMP) |
| ME-11 | SOL-AL-02 (+ SOL-COMP) |
| BA-01 | SOL-COMP (BA-01) |
| BA-02 | SOL-COMP (BA-02) + SOL-CR-03 (Dockerfile) |
| BA-03 | SOL-COMP (BA-03) |
| BA-04 | SOL-COMP (BA-04) |
| BA-05 | SOL-AL-04 + SOL-AL-03 |
| BA-06 | SOL-AL-01 (+ SOL-COMP) |
| BA-07 | SOL-COMP (BA-07) + SOL-CR-04 (cambio de contraseña) |
| BA-08 | SOL-COMP (BA-08) + SOL-CR-04 (seed) |
| BA-09 | SOL-COMP (BA-09) + SOL-CR-03 |
| BA-10 | SOL-COMP (BA-10) |
| Checklist falso de `README_SEGURIDAD.md` | SOL-DOC-01 |

---

*Fin del plan — 03-auditoria-de-seguridad-soluciones.md. Documento de planificación: nada de lo aquí descrito está implementado. Ningún valor de secreto real fue reproducido; ninguna app, test ni base de datos fue ejecutada o modificada.*
