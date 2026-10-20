# 03 — Auditoría de Seguridad (estática) — Backend "Mayores Actualizaciones" (SIPI)

- **Fecha:** 2026-10-19
- **Alcance:** repositorio completo `mayores_actualizacionesSIPI-BACK` (app/, tests/, Dockerfile, docker-compose.yml, Caddyfile, requirements.txt, docs_interna/, `.env.example` y `.env` real solo para evaluar higiene).
- **Método:** análisis estático de solo lectura (lectura de código, grep/glob, comparaciones de igualdad de secretos ejecutadas localmente —sin imprimir valores— y revisión de documentación). **No** se ejecutó la aplicación, **no** se corrieron tests, **no** se modificó ningún archivo, **no** se atacó ningún servicio.
- **Regla de confidencialidad aplicada:** no se reproducen valores reales de secretos (JWT actual, contraseña SMTP, RAE_API_KEY, contraseñas MySQL). Donde se menciona igualdad con valores por defecto, se indica el hecho sin citar el valor.
- **Producto de este informe:** único artefacto escrito: este archivo.

---

## 1. Resumen ejecutivo

El backend está construido sobre FastAPI + MongoDB (Motor) con JWT HS256, BCrypt, RBAC por `tipo_usuario`, rate limiting propio y un supuesto esquema de "defensa en profundidad" (Docker hardening, Caddy con headers, RLS anti-IDOR, anti-mass-assignment). El código de algunas capas **sí** está bien implementado (hash BCrypt, RLS de `/progreso`, escape anti-ReDoS, `algorithms=["HS256"]` explícito, compose con límites y red interna). Sin embargo, el modelo real de autorización tiene **falencias estructurales y explotables sin autenticación**:

1. **Toda la API de administración del juego narrativo (`/api/narrative/admin/*`) está sin autenticación** (CRUD de catálogos, subida de imágenes, generación de meses). Es alcanzable desde internet a través de Caddy (`/api*`).
2. **Los endpoints "admin" de desafíos diarios y el upsert de desafíos también están sin autenticación** (`/api/challenges/admin/*`, `POST /api/challenges`): cualquiera puede sobrescribir el desafío del día (soluciones incluidas).
3. **El `JWT_SECRET` efectivo es exactamente el valor por defecto público** impreso en `config.py` y `.env.example` (verificado por comparación contra `.env`, sin citar el valor). Cualquiera que vea el repositorio puede **forjar tokens de administrador**. Además, el `.env` con secretos reales **queda dentro de la imagen Docker** porque `.dockerignore` no excluye `.env`.
4. **Las credenciales de administrador por defecto siguen activas**: `admin@sistemas.com` / `admin123` (valor público documentado en `config.py:28` y `README.md:76`) y el **PIN fijo `999999`** del admin es usable en `POST /api/auth/ingresar-codigo`, que no distingue roles → sesión de administrador trivial.
5. **Account takeover de registros pendientes**: `POST /api/auth/modificar-email-registro` cambia el email de una cuenta pendiente **sin ninguna prueba de posesión del correo original** y envía el código de activación (que además es el PIN de login permanente) al nuevo correo elegido por el atacante.
6. **IDOR no autenticado en `/api/games/attempts`**: el `user_id` se toma de un query param que pisa al del token y puede usarse sin token alguno → lectura/escritura del progreso de cualquier alumno y `$inc` de puntos arbitrario.
7. **PIN de 6 dígitos = contraseña permanente**, sin bloqueo por cuenta, sin expiración, comparación no constante y con rate limiting **evadible inyectando `X-Forwarded-For`** (y también evadible con un token con claim admin falso si el secreto es el default — ver punto 3). Fuerza bruta acotada solo por la red.

La combinación CR-03 + CR-04 + CR-05 + CR-06 implica que, con el despliegue tal como está documentado, **un atacante externo puede llegar a control total de la plataforma y de los datos de todos los alumnos**. El informe detalla 6 hallazgos críticos, 6 altos, 11 medios y 10 bajos, más la sección de contraste con `docs_interna/README_SEGURIDAD.md`.

### Tabla resumen de hallazgos por severidad

| ID | Severidad | Hallazgo | Ubicación principal | Estado |
|---|---|---|---|---|
| CR-01 | Crítico | API de administración narrativa completa sin autenticación (CRUD, upload, generación mensual) | `app/features/narrative/admin/router.py:64` (sin `Depends`), `:82-91`, `:108-320` | Confirmado |
| CR-02 | Crítico | Endpoints admin/upsert de desafíos sin autenticación | `app/features/daily_challenges/router.py:77-113` | Confirmado |
| CR-03 | Crítico | `JWT_SECRET` efectivo = default público + `.env` embebido en imagen Docker | `app/core/config.py:14`, `.env.example:10`, `.dockerignore:1-13`, `Dockerfile:15` | Confirmado (comparación local; "baked" confirmado estáticamente) |
| CR-04 | Crítico | Credenciales admin por defecto activas + PIN admin `999999` usable en login de alumnos | `app/scripts/init_db.py:64-93` (`:80`), `app/core/config.py:27-28`, `app/features/auth/service.py:90-125` | Confirmado |
| CR-05 | Crítico | Account takeover: cambio de email de registro pendiente sin verificación de posesión | `app/features/auth/service.py:365-408` (`:396-402`) | Confirmado |
| CR-06 | Crítico | IDOR no autenticado en `/api/games/attempts` (lectura/escritura y puntos de terceros) | `app/features/user_attempts/router.py:39-99` | Confirmado |
| AL-01 | Alto | Rate limiting evadible: `X-Forwarded-For` no confiable + bypass por claim admin sin DB + sin bloqueo por cuenta | `app/core/rate_limit.py:7-56` | Confirmado |
| AL-02 | Alto | PIN de 6 dígitos como credencial permanente, sin bloqueo, comparación no constante y elegible sin validación | `app/features/auth/service.py:90-125`, `:310`, `:235-241`; `schemas.py:29` | Confirmado |
| AL-03 | Alto | JWT de 180 días sin refresh ni revocación; magic links con token en query string; no hay logout | `app/core/config.py:15`, `app/core/security.py:29-54`, `app/features/auth/service.py:181-184` | Confirmado |
| AL-04 | Alto | Enumeración de cuentas (400/403/404 diferenciales) | `app/features/auth/service.py:70-74`, `:209-229`, `:297-302`, `:344-349`, `:376-381` | Confirmado |
| AL-05 | Alto | Fuga de códigos, magic links (JWT), PIN y PII en logs | `app/features/auth/email_service.py:16-23`, `:42-44`, `:98`, `:101-107`, `:126-127` | Confirmado |
| AL-06 | Alto | Upload de imágenes sin autenticación, sin límite de tamaño en app y sin guardas anti decompression-bomb | `app/features/narrative/admin/image_service.py:38-92`; `admin/router.py:82-91` | Confirmado |
| ME-01 | Medio | CORS: `allow_origin_regex=^https?://.*$` + `allow_credentials=True` | `app/main.py:91-98` | Confirmado (riesgo real condicionado a cookies) |
| ME-02 | Medio | Tokens validados sin consultar DB en attempts/narrative → cuentas desactivadas siguen operando | `app/features/user_attempts/router.py:17-28`; `app/features/narrative/game/router.py:64-76` | Confirmado |
| ME-03 | Medio | Modo invitado `user_id=0` compartido entre todos los anónimos en el juego narrativo | `app/features/narrative/game/router.py:64-76`; `setup_service.py:117-125` | Confirmado (posible decisión de producto) |
| ME-04 | Medio | MongoDB sin autenticación interna (compose); sin exposición de puerto al host | `docker-compose.yml:72-97` | Confirmado |
| ME-05 | Medio | Fallback SMTP "simulado" que imprime códigos/enlaces en logs + `FRONTEND_URL=localhost` en `.env` | `app/features/auth/email_service.py:16-23,101-107`; `.env` | Confirmado |
| ME-06 | Medio | `/docs`, `/redoc`, `/openapi.json` y SPA `/admin` accesibles si el backend se publica directo | `app/main.py:70-78`, `:139-165` | Confirmado (mitigado por Caddy actual) |
| ME-07 | Medio | Rate limiter in-memory: por proceso, se resetea, no purga claves | `app/core/rate_limit.py:7-32` | Confirmado |
| ME-08 | Medio | Desafíos diarios públicos devuelven `config` con soluciones; sobrescribibles sin auth | `app/features/daily_challenges/service.py:37-48`; `router.py:77-83` | Confirmado |
| ME-09 | Medio | Handler de excepciones HTTP no propaga headers (`Retry-After`, `WWW-Authenticate`) | `app/main.py:104-114` | Confirmado |
| ME-10 | Medio | El propio PIN (`codigoAcceso`) viaja en respuestas de login/verificar-token y en el asunto del email | `app/features/auth/service.py:44`; `email_service.py:98` | Confirmado |
| ME-11 | Medio | Registro permite elegir el PIN sin validación (colisiones → 500 por índice único); contraseña opcional | `app/features/auth/schemas.py:28-29`; `service.py:235-241` | Confirmado |
| BA-01 | Bajo | Dependencias sin pin (`>=`) y sin lockfile | `requirements.txt:1-15` | Confirmado |
| BA-02 | Bajo | Contenedor backend corre como root y `COPY . .` sin `.dockerignore` de secretos | `Dockerfile:1-21` | Confirmado |
| BA-03 | Bajo | Caddy sin TLS/HSTS/CSP (depende de proxy frontal no auditado) | `Caddyfile:1-44` | Confirmado (riesgo condicional) |
| BA-04 | Bajo | `GET /usuario/estados` público | `app/features/usuario/router.py:48-50` | Confirmado |
| BA-05 | Bajo | `get_current_user` responde 404 vs 401 (info de usuarios borrados) | `app/core/dependencies.py:49-53` | Confirmado |
| BA-06 | Bajo | `POST /api/auth/verificar-token` sin rate limit | `app/features/auth/router.py:34-36` | Confirmado |
| BA-07 | Bajo | `password` de registro sin `min_length` (claim documental falso) | `app/features/auth/schemas.py:28` | Confirmado |
| BA-08 | Bajo | `init_indexes` falla en silencio → riesgo de PINs duplicados; seed admin en cada arranque | `app/core/database.py:103-104`; `app/main.py:38` | Sospecha / Confirmado (código) |
| BA-09 | Bajo | `MAIL_FROM` con casilla personal; `MYSQL_USER/PASSWORD` default `root/root` en config | `app/core/config.py:23`, `:35-39` | Confirmado |
| BA-10 | Bajo | Inconsistencia categoría `characters` vs `personajes` (paquete vs servicio de imágenes) | `image_service.py:18-26` vs `app/static/narrative/characters/` | Confirmado (funcional, no seguridad) |

---

## 2. Alcance, metodología y limitaciones

**Qué se revisó:** los 8 routers (`auth`, `usuario`, `progreso`, `daily_challenges`, `user_attempts`, `narrative` V1/V2, `narrative/admin`), `app/core/*`, scripts (`init_db`, seeds, migración ETL), `main.py`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `requirements.txt`, `.env.example`, `.gitignore`, `.dockerignore`, `.env` (solo higiene), tests y `docs_interna/`.

**Cómo se determinó severidad:** impacto explotable concreto (confidencialidad/integridad/disponibilidad/toma de cuenta) considerando la ruta real de exposición según `Caddyfile` y `docker-compose.yml`. Se distingue:
- **Confirmado:** verificable en el código tal como está (se indica archivo:línea).
- **Sospecha:** depende de datos/entorno no verificables estáticamente (base real, red externa, frontend).

**Limitaciones y supuestos operativos (importantes para interpretar todo el informe):**
1. No se ejecutó la app ni se consultó la base de datos real. La explotabilidad de credenciales por defecto asume que siguen vigentes en la BD (el código las repone si no existen: `main.py:38`, `init_db.py:64-93`).
2. No se inspeccionó el frontend real; según `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md:250,265,342` el token JWT se guarda en `localStorage` (no cookies), lo que **baja** el impacto actual de ME-01 y confirma que el modelo es Bearer.
3. En el `docker-compose.yml` actual, solo Caddy publica `8082`; el backend no publica puerto. Por lo tanto, `/docs`, `/redoc`, `/admin` y `/assets/narrative` **no** son alcanzables a través de Caddy (no están en la lista de prefijos proxy). Si en producción se agrega otro proxy/mapeo directo al backend, esos elementos se exponen y ME-06/BA-03 suben de severidad.
4. Se asumió que `.env` es el archivo de producción del despliegue actual (está referenciado en `docker-compose.yml:43-44`).

---

## 3. Matriz de autenticación por endpoint (confirmado en código)

| Router / Endpoint | ¿Auth? | ¿Admin? | Observación |
|---|---|---|---|
| `POST /api/auth/login-sistemas` | No (público) | — | Rate limit 5/min (evadible, AL-01) |
| `POST /api/auth/ingresar-codigo` | No (público) | — | PIN; genera token también para admins (CR-04) |
| `POST /api/auth/verificar-token` | No (público) | — | Sin rate limit (BA-06) |
| `POST /api/auth/register` | No (público) | — | Fuerza `tipo_usuario=1` (bien); PIN elegible sin validar (ME-11) |
| `POST /api/auth/verificar-codigo-registro` | No (público) | — | Código = PIN permanente; sin lockout por cuenta (AL-02) |
| `POST /api/auth/reenviar-codigo-registro` | No (público) | — | Enumeración (AL-04) |
| `POST /api/auth/modificar-email-registro` | No (público) | — | **Account takeover (CR-05)** |
| `POST /api/admin/enviar-acceso-correo` | Sí | Sí | `get_current_admin` correcto |
| `GET /usuario` | Sí | Sí | OK |
| `GET /usuario/estados` | **No** | No | Catálogo público (BA-04) |
| `POST /usuario/estados`, `PUT /usuario/estados/{id}/toggle-habilitado`, `PUT /usuario/{id}/cambiar-estado` | Sí | Sí | OK |
| `GET /usuario/{id}` | Sí | No (owner o admin) | Ownership check correcto (`router.py:85-91`) |
| `PUT /usuario/{id}/toggle-activo`, `/toggle-black`, `/suscribirse` | Sí | Sí | OK |
| `POST /usuario` | Sí | Sí | Creación admin; mass assignment controlado |
| `POST /usuario/{id}/magic-link` | Sí | Sí | Devuelve token+URL+PIN del alumno (administrativo) |
| `POST/PUT/GET /progreso/*` | Sí | No (owner o admin) | RLS implementada correctamente (`progreso/router.py:18-51`) |
| `GET /api/challenges/*` (today, month, range, date) | No | No | Público por diseño; devuelve `config` con soluciones (ME-08) |
| `POST /api/challenges` (upsert) | **No** | No | **Cualquiera sobrescribe desafíos (CR-02)** |
| `GET /api/challenges/admin/status`, `POST /api/challenges/admin/generate-month` | **No** | No | **CR-02** |
| `POST /api/games/attempts` | "Opcional" | No | **Sin token acepta `user_id` ajeno (CR-06)** |
| `GET /api/games/attempts`, `/date/{date}` | "Opcional" | No | **IDOR no autenticado (CR-06)** |
| `/api/narrative/v2/partida/*` (iniciar, elegir, decidir, avanzar, estado) | No | No | Invitado `user_id=0`; token solo identifica (ME-02/ME-03) |
| `/api/narrative/partida/*` (setup, reiniciar, modales, conversaciones) | No | No | ídem |
| `/api/narrative/admin/*` (catálogo reglas, CRUD 7 colecciones, `upload-imagen`, `sembrar-finalizaciones`, `generar-mes`) | **No** | **No** | **CRÍTICO CR-01** |

---

## 4. Hallazgos detallados

### CR-01 — Toda la API de administración del juego narrativo está sin autenticación

- **Severidad:** Crítico
- **Estado:** Confirmado
- **Ubicación:** `app/features/narrative/admin/router.py:64` (creación del router sin dependencias), endpoints en `:70-320` (p. ej. `POST /upload-imagen` `:82-91`, `POST /universos` `:108-110`, `DELETE /universos/{id}` `:112-117`, `POST /personajes|cartas|resultados|eventos|conversaciones|finalizaciones` y sus `DELETE`, `POST /universos/{id}/sembrar-finalizaciones` `:299-305`, `POST /generar-mes` `:311-320`). Ningún `Depends(get_current_admin)` ni `Depends(get_current_user)` en el archivo. Alcanzable externamente porque Caddy proxya `path /api*` (`Caddyfile:33-36`).
- **Descripción:** El módulo que la documentación llama "Torre de Control" (catálogo completo del juego narrativo) no aplica RBAC. Se apoya únicamente en que la SPA admin (estática, también sin gating server-side) oculte las llamadas. `tests/test_narrative_game.py:37-49` incluso lo consume sin credenciales, evidenciando que no es un olvido de un endpoint sino el diseño.
- **Impacto:**
  - **Integridad total del contenido:** crear/modificar/borrar universos, personajes, cartas, eventos, resultados, conversaciones y finalizaciones.
  - **Persistencia/almacenamiento:** subir imágenes sin autenticación (ver AL-06) y borrar imágenes referenciadas.
  - **DoS funcional:** `POST /generar-mes` puede regenerar 28-31 desafíos de un mes (CPU) repetidamente; borrar el catálogo rompe todas las partidas y el setup diario.
  - **Contenido no confiable consumido por la SPA de alumnos/administradores:** los textos/imágenes creados por un atacante se muestran en el juego (riesgo de phishing/contenido malicioso; XSS depende del renderizado del frontend — no verificable aquí).
- **Escenario de explotación (resumido):** `curl -X DELETE https://host/api/narrative/admin/universos/corte_medieval` sin cabecera de autenticación → 200; `curl -X POST https://host/api/narrative/admin/generar-mes?year=2026&month=11&universo_id=corte_medieval` en bucle → regeneración masiva. Con un `POST /personajes` se inyecta contenido arbitrario en el catálogo.
- **Recomendación:** aplicar dependencia a nivel de router: `APIRouter(prefix="/api/narrative/admin", dependencies=[Depends(get_current_admin)])` (o `get_current_user` según rol mínimo), y además exigir admin en `upload-imagen` y `generar-mes`. Añadir tests de autorización negativa (401/403 sin token). Como defensa en profundidad, restringir también en Caddy el prefijo `/api/narrative/admin*` a una red administrativa o exigir mTLS/VPN si aplica.

### CR-02 — Endpoints "admin" y upsert de desafíos diarios sin autenticación

- **Severidad:** Crítico
- **Estado:** Confirmado
- **Ubicación:** `app/features/daily_challenges/router.py:77-83` (`POST /api/challenges`), `:85-93` (`GET /api/challenges/admin/status`), `:95-113` (`POST /api/challenges/admin/generate-month`). Ninguno tiene dependencia de auth. La escritura llega a `upsert_challenge` (`app/features/daily_challenges/service.py:136-165`).
- **Descripción:** Cualquiera puede crear/actualizar el desafío de cualquier juego/fecha/dificultad (`$set` de `config` completo) y disparar la regeneración mensual. El mismo endpoint alimenta la colección que usa el juego narrativo (`game_id: "narrativo"`), cuyo `config` gobierna el setup diario (`app/features/narrative/game/setup_service.py:80-113`).
- **Impacto:**
  - Sobrescribir el Wordle/Sudoku/Sopa/Crucigrama del día: `config` incluye la solución (ver ME-08) → trampa masiva e integridad del juego.
  - Manipular el `config` del desafío narrativo (`universo_id`, `atributos_iniciales`, pools de eventos/cartas) → partidas rotas o alteradas para todos.
  - DoS por regeneración repetida (mismo vector que CR-01).
- **Escenario de explotación:** `POST /api/challenges` con `{"game_id":"wordle","date":"hoy","difficulty":"standard","config":{"solution":"AAAAA", ...}}` → todos los alumnos juegan el desafío manipulado.
- **Recomendación:** mover el upsert a un router admin protegido con `get_current_admin`; que Caddy o el gateway bloqueen `/api/challenges/admin*` públicamente; validar estructura de `config` por juego con modelo Pydantic específico; auditoría de cambios.

### CR-03 — `JWT_SECRET` efectivo = valor por defecto público, y `.env` embebido en la imagen Docker

- **Severidad:** Crítico
- **Estado:** Confirmado (igualdad verificada por comparación local **sin reproducir valores**; inclusión en imagen deducida de `Dockerfile` + `.dockerignore`, ver "Sospecha" al final)
- **Ubicación:**
  - `app/core/config.py:14` (secret por defecto hardcodeado, también impreso en `.env.example:10`).
  - `.env` real: verificado que su `JWT_SECRET` **es idéntico** al default público (comparación booleana en shell, sin imprimir el valor). También `JWT_EXPIRATION_DAYS=180`.
  - `Dockerfile:15` (`COPY . .`) y `.dockerignore:1-13` (excluye `.env.example` pero **no** `.env`).
  - Higiene adicional confirmada de `.env` (tipo de dato, sin citar valores): `SMTP_PASSWORD` real no-placeholder, `RAE_API_KEY` presente, `MYSQL_PASSWORD` de 4 caracteres (default-like), `ADMIN_DEFAULT_EMAIL` = `admin@sistemas.com`, `ADMIN_DEFAULT_PASSWORD` = `admin123`.
- **Descripción:** El secreto de firma JWT es un valor publicado en el propio repositorio y copiado a `.env.example`; el `.env` real no lo rotó. Además, `.dockerignore` no excluye `.env`, por lo que la imagen `mayores-actualizaciones-backend` contiene los secretos reales en una de sus capas (SMTP, RAE, MySQL, JWT). Cualquier persona con acceso a la imagen (registry, tar, capa cacheada, `docker save`) obtiene también el secreto JWT.
- **Impacto:**
  - **Falsificación de tokens de administrador**: con HS256 y secreto conocido, un atacante puede emitir `{"id": <admin_id>, "tipoUsuario": 2, "rol": 2, ...}` y usar `/usuario/*`. También puede saltarse el rate limiting (que confía en el claim `tipoUsuario`, AL-01).
  - Los secretos de terceros permiten suplantar el envío de correos (Brevo) y consumir la API RAE; las credenciales MySQL permiten atacar la base de origen del ETL si es alcanzable.
- **Escenario de explotación:** leer `config.py`/`.env.example` del repo (o extraer `.env` de la imagen) → firmar un JWT con `tipoUsuario=2` → `PUT /usuario/{id}/toggle-activo`, listar usuarios, generar magic links, etc.
- **Recomendación:**
  1. **Rotar ya** `JWT_SECRET`, `SMTP_PASSWORD`, `RAE_API_KEY` y credenciales MySQL/administrativas; la rotación del JWT invalida todos los tokens emitidos (efecto colateral sano tras este hallazgo).
  2. Eliminar el default de `config.py` (sin valor o cadena vacía + validación que aborte el arranque si no está definida; p. ej. `JWT_SECRET: str` sin default y `field_validator` que rechace longitudes débiles).
  3. Añadir `.env`, `.env.*` y `*.env` a `.dockerignore`; usar `docker secret`s o inyección por entorno en runtime; reconstruir imágenes sin secretos (`--no-cache` tras el cambio).
  4. Actualizar `.env.example` para que no contenga secretos utilizables (placeholders únicos por entorno).

### CR-04 — Credenciales de administrador por defecto activas y PIN fijo `999999` usable en el login de alumnos

- **Severidad:** Crítico
- **Estado:** Confirmado (código + comparación de `.env`)
- **Ubicación:**
  - `app/core/config.py:27-28` (`ADMIN_DEFAULT_EMAIL=admin@sistemas.com`, `ADMIN_DEFAULT_PASSWORD=admin123`), replicado en `.env.example:23-24` y documentado en `README.md:76` y `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md:367-374`.
  - `.env`: verificado que sigue siendo `admin123` / `admin@sistemas.com` (comparación booleana).
  - `app/scripts/init_db.py:64-93`: siembra el admin al arrancar (`main.py:38`) con `codigo_acceso: "999999"` (`init_db.py:80`) y `tipo_usuario: 2`.
  - `app/features/auth/service.py:90-125`: `login_codigo` no distingue rol: cualquier `codigo_acceso` que exista emite token con el rol del usuario.
- **Descripción:** El admin por defecto (credenciales conocidas) se crea automáticamente si no existe y nunca se fuerza su cambio. Su PIN de acceso es el predecible `999999`. El login por PIN no restringe que el código pertenezca a un alumno, por lo que `POST /api/auth/ingresar-codigo {"codigo":"999999"}` devuelve un **token de administrador** si el seed está activo.
- **Impacto:** Toma de control administrativa total (usuarios, activaciones, magic links, catálogos, etc.) sin necesidad de forzar JWT.
- **Escenario de explotación:** probar `999999` en `/api/auth/ingresar-codigo` (o `admin@sistemas.com`/`admin123` en `/api/auth/login-sistemas`); el rate limit no lo impide (AL-01).
- **Recomendación:** no sembrar credenciales por defecto en producción (flag `SEED_DEFAULT_ADMIN=false` o exigir `ADMIN_DEFAULT_PASSWORD` generada aleatoriamente en el primer arranque y forzar cambio); rotar/eliminar la cuenta existente; hacer que `login_codigo` rechace usuarios `tipo_usuario != 1` (o exija un segundo factor para roles administrativos); eliminar el PIN para cuentas admin.

### CR-05 — Account takeover mediante `modificar-email-registro`

- **Severidad:** Crítico
- **Estado:** Confirmado
- **Ubicación:** `app/features/auth/service.py:365-408`, en especial la actualización `:396-399` y el reenvío del código existente `:401-402`; endpoint público en `app/features/auth/router.py:73-79`.
- **Descripción:** El endpoint permite cambiar el email de cualquier cuenta con `estado_id != 2` (pendiente) conociendo el email actual. **No verifica** que quien invoca controle la casilla actual ni la nueva (no se pide código previo). Luego envía el `codigo_acceso` **preexistente** al email nuevo. Ese mismo código es el PIN de login permanente (ver AL-02).
- **Impacto:** Un atacante que conozca el email de un registro pendiente (o que registre primero a la víctima para dejar la cuenta pendiente) puede: cambiar el email a uno suyo → recibir el código → activar la cuenta → iniciar sesión y quedarse con la cuenta (incluyendo su código de acceso). También permite "secuestrar" registros ajenos antes de su activación.
- **Escenario de explotación (resumido):** `POST /api/auth/modificar-email-registro {"email_actual":"victima@dominio.com","email_nuevo":"atacante@dominio.com"}` (la cuenta debe estar PENDIENTE_VERIFICACION) → llega el código al correo del atacante → `POST /api/auth/verificar-codigo-registro` → token de la víctima.
- **Recomendación:** exigir prueba de posesión del correo actual (código de 6 dígitos enviado al email anterior antes de permitir el cambio) o eliminar el endpoint y crear un flujo de "corrección de email" con código de un solo uso y expiración; invalidar y regenerar el PIN tras cualquier cambio de email; auditar los cambios de email.

### CR-06 — IDOR no autenticado en `/api/games/attempts` (lectura/escritura de terceros y manipulación de puntos)

- **Severidad:** Crítico
- **Estado:** Confirmado
- **Ubicación:** `app/features/user_attempts/router.py:17-28` (`_extract_user_id_from_header`, solo firma JWT), `:39-46` (POST), `:59-68` (GET por fecha), `:82-99` (GET mensual). Servicio: `app/features/user_attempts/service.py:40-97` (upsert y `$inc` de puntos `:85-95`).
- **Descripción:** En los GET, `effective_user_id = user_id or token_user_id`: el **query param pisa** al del token y, si no hay token, el query param alcanza por sí solo. En el POST, sin token se acepta `req.user_id` (solo se exige que sea "truthy"). Además, el token se decodifica sin consultar la BD (`get_current_user` no se usa): un usuario desactivado sigue operando, y no hay verificación de ownership contra el usuario objetivo.
- **Impacto:**
  - Lectura del historial de partidas de cualquier `user_id` (palabras, `game_data`, resultados) sin autenticación.
  - Escritura/sobrescritura de intentos ajenos (borrado lógico del día, falseo de progreso).
  - `$inc` arbitrario de `puntos` con `score` sin cotas (`schemas.py:17`): inflar puntos propios o **decrementar** los de la víctima con score negativo; en base a `status:"completed"` se suma una vez por (user, game, date), habilitando inflación por fechas/juegos.
- **Escenario de explotación:** `GET /api/games/attempts?user_id=1&game_id=wordle&year=2026&month=10` sin token → progreso del usuario 1; `POST /api/games/attempts {"user_id":1,"date":"2026-10-19","score":999999,"status":"completed"}` sin token → puntos de la víctima alterados.
- **Recomendación:** usar `Depends(get_current_user)` en los tres endpoints; ignorar todo `user_id` provisto por el cliente (o exigir coincidencia con el token); cotas a `score/stars/attempts` (`ge`, `le`) y validación server-side del puntaje; unificar con el flujo de progreso que ya funciona.

### AL-01 — Rate limiting evadible (XFF, claim admin, sin lockout por cuenta)

- **Severidad:** Alto
- **Estado:** Confirmado
- **Ubicación:** `app/core/rate_limit.py:7-32` (estado en memoria), `:40-46` (bypass admin por claim), `:48-53` (IP desde `X-Forwarded-For`), `:55-56` (clave IP:path).
- **Descripción:**
  1. **XFF confiado a ciegas:** `request.headers.get("X-Forwarded-For")` se usa como IP de cliente sin validar que provenga de un proxy de confianza. Cualquier cliente puede enviar `X-Forwarded-For: <aleatorio>` en cada request y obtener un cubo nuevo → límite de 5/min efectivamente ilimitado.
  2. **Bypass por claim:** un token con `tipoUsuario == 2` o `rol == 2` salta el límite; el chequeo usa solo la firma, sin DB. Con CR-03 (secreto default) esto es trivial: token forjado = sin límites; con tokens legítimos de admin, tampoco hay límite para operaciones sensibles.
  3. **Sin bloqueo por cuenta:** no hay contador de intentos fallidos por usuario/PIN; el único freno es el limiter evadible.
  4. **Estado in-memory:** por proceso; se resetea al reiniciar (`docker-compose` sin `--workers`, pero un future scale/redeploy lo multiplica); `self._history` nunca purga claves → con XFF aleatorio crece sin límite (DoS de memoria).
  5. **Aplicación parcial:** solo `login-sistemas`, `ingresar-codigo`, `register`, `verificar-codigo-registro`, `reenviar-codigo-registro`, `modificar-email-registro` (`auth/router.py:18-79`). Sin límite en `verificar-token` ni en endpoints de juego/upload.
- **Impacto:** fuerza bruta de contraseñas admin (`admin123` ya es conocida) y, sobre todo, de PINs de 6 dígitos (900k combinaciones) y de códigos de activación; spam de correos de activación; agotamiento de memoria del limiter.
- **Escenario de explotación:** script que rota `X-Forwarded-For` por request contra `/api/auth/ingresar-codigo` → miles de intentos/minuto hasta acertar un PIN; el mismo truco contra `verificar-codigo-registro` con un email conocido.
- **Recomendación:** usar la IP de conexión (`request.client.host`) o configurar proxies de confianza explícitos (`TRUSTED_PROXIES` y tomar el valor correcto de XFF solo desde ellos; en Caddy configurar `trusted_proxies`/IP real); agregar contador por **cuenta** (`email`/`codigo` objetivo) además de por IP, con bloqueo exponencial; mover el limiter a Redis si habrá más de una instancia/proceso; purgar claves vencidas; quitar el bypass admin o exigirlo con `get_current_admin` real (consulta DB) y limitarlo a endpoints no sensibles.

### AL-02 — PIN de 6 dígitos como contraseña permanente: sin bloqueo, sin expiración, comparación no constante y elegible sin validación

- **Severidad:** Alto
- **Estado:** Confirmado
- **Ubicación:** `app/features/auth/service.py:90-125` (`login_codigo`), `:310` (comparación `!=` para activación), `:235-241` (PIN provisto por el usuario en el registro público), `app/features/auth/schemas.py:29` (`codigoAcceso: Optional[str] = None`, sin constraints), `:9` (login acepta 4-10 caracteres, no exige solo dígitos).
- **Descripción:** El `codigo_acceso` cumple simultáneamente de: código de activación, credencial de login permanente y (en admin) PIN fijo. Nunca expira, no se puede cambiar/rotar desde la API, y no hay bloqueo por cuenta ante intentos fallidos. La comparación del código de activación (`user.get("codigo_acceso") != code_clean`) no es de tiempo constante (posible timing oracle teórico). En el registro público, el propio usuario puede fijar su `codigoAcceso` sin ninguna validación de formato/fortaleza (por ejemplo `"1234"`: 10.000 combinaciones); si elige un código ya existente, el `insert_one` revienta con `DuplicateKeyError` no controlado → 500 (oráculo/DoS menor y mensaje de error genérico de FastAPI).
- **Impacto:** con AL-01, la fuerza bruta de PINs es práctica; PINs elegidos débiles son aún más fáciles; el PIN se filtra en respuestas y emails (ME-10). Compromiso de cuentas de alumnos a escala.
- **Escenario de explotación:** rotación de XFF + diccionario de PINs comunes (`123456`, `000000`, `999999`) contra `/api/auth/ingresar-codigo`; o timing/observación del código de activación para registros pendientes.
- **Recomendación:** separar "código de activación" (de un solo uso, expiración 15-30 min, ligado al intento de registro) del "PIN de acceso" (rotativo, regenerable por el alumno/admin); comparación con `hmac.compare_digest`; validar `codigoAcceso` generado **solo server-side** (`^\d{6}$`) y rechazar provistos por el usuario; bloqueo por cuenta tras N fallos; permitir regenerar el PIN (con invalidación) en caso de sospecha; nunca permitir login por PIN para `tipo_usuario == 2`.

### AL-03 — JWT de 180 días sin refresh ni revocación; magic links con token en la URL; no existe logout

- **Severidad:** Alto
- **Estado:** Confirmado
- **Ubicación:** `app/core/config.py:15` (`JWT_EXPIRATION_DAYS=180`), `app/core/security.py:29-54` (claims sin `jti`/`aud`/`iss`; sin control de versión), `app/features/auth/service.py:181-184` (token JWT en `?token=` del magic link), `app/features/usuario/router.py:132-140` (idem), `app/core/dependencies.py` (no consulta de revocación; `black` no se chequea).
- **Descripción:** Los access tokens duran 180 días, no hay refresh tokens, ni blacklist/jti, ni endpoint de logout; un token filtrado es una sesión válida hasta su expiración. El magic link introduce el JWT completo en una URL enviada por email (historial del navegador, `Referer` hacia terceros, proxies/logs de middleware, la propia impresión en consola cuando faltan credenciales SMTP — ver AL-05).
- **Impacto:** robo de token = 180 días de acceso; imposible revocar puntualmente (solo desactivando la cuenta, que además no corta las rutas que no usan `get_current_user`: ME-02).
- **Escenario de explotación:** acceso al correo compartido/dispositivo de un adulto mayor, o al historial del navegador, para tomar el enlace de acceso; el token sigue siendo válido aunque el alumno "cierre sesión" (no existe tal operación).
- **Recomendación:** access tokens cortos (15-60 min) + refresh tokens rotativos con almacenamiento de jti/versión y revocación; endpoint de logout que invalide el refresh; no poner JWT en query strings (usar códigos de un solo uso canjeables por POST); claims de `aud`/`iss` y verificación; documentar el ciclo de vida en la guía de frontend.

### AL-04 — Enumeración de cuentas

- **Severidad:** Alto
- **Estado:** Confirmado
- **Ubicación:** `app/features/auth/service.py:70-74` (login de no-admin → 403 "Se requieren permisos", revela cuenta existente sin validar contraseña), `:209-229` (registro de email ya activado → 400 "ya está registrado"), `:297-302` y `:344-349` (activación/reenvío → 404 si no existe), `:376-381` (modificar email → 404), `:169-173` (magic link admin-only → 404, impacto bajo). Diferencias 401 vs 403 vs 404.
- **Descripción:** Las respuestas permiten decidir si un email está o no registrado, y en el login incluso distinguir "existe y no es admin" (403 antes de validar la password, `service.py:70-76`).
- **Impacto:** identificación de alumnos para dirigir AL-02/CR-05 y campañas de phishing; violación de privacidad (plataforma de adultos mayores).
- **Escenario de explotación (resumido):** `POST /api/auth/register` con el email objetivo: 400 → existe; 200 → no existe. Y `POST /api/auth/login-sistemas` con cualquier password: 403 → existe y es alumno.
- **Recomendación:** respuestas uniformes (mismo código/mensaje/latencia) para "no existe" y "existe" en todos los flujos: registro (devolver 200 genérico y enviar email), activación/reenvío (200 genérico), modificar email (procesamiento genérico + verificación por correo). No validar rol antes de la contraseña en `login_sistemas`.

### AL-05 — Fuga de códigos, magic links (JWT) y PII en logs

- **Severidad:** Alto
- **Estado:** Confirmado
- **Ubicación:** `app/features/auth/email_service.py:16-23` (fallback sin SMTP imprime destinatario, código PIN y magic link completo con JWT), `:42-44` (error de envío: `logger.error` con link y código), `:98` (el asunto del email contiene el código de activación), `:101-107` (segundo fallback con el código), `:126-127` (error con código). Además `app/core/database.py:21` loguea `MONGODB_URL` completa (hoy sin credenciales, pero es un hábito peligroso) y `email_service` imprime `to_email`/`user_name` (PII).
- **Descripción:** Los logs de la aplicación (rotados por Docker, `docker-compose.yml:55-59`) contienen credenciales de acceso reutilizables (PIN permanente) e incluyen el token JWT de 180 días del magic link cuando el SMTP falla o la clave no está configurada. El fallback es silencioso: en producción con `SMTP_PASSWORD` ausente, "simula" el envío (usuario no recibe nada) y deja el acceso en los logs.
- **Impacto:** cualquier persona con acceso a logs (`docker logs`, stack de monitoreo, backups) puede iniciar sesión como cualquier alumno cuyo correo haya pasado por un fallo; el JWT del magic link equivale a la sesión.
- **Escenario de explotación:** provocar un fallo de SMTP (o el estado sin credenciales) y leer el log para obtener códigos/enlaces, o simplemente consultar los logs históricos.
- **Recomendación:** eliminar todo log de códigos/tokens/enlaces; loguear solo identificadores no sensibles; no poner códigos en asuntos de email; fallar ruidosamente (500) si falta la configuración SMTP en lugar de simular; revisar y purgar logs históricos; redacción de `MONGODB_URL` en `database.py:21`.

### AL-06 — Subida de imágenes sin autenticación, sin límite en la app y sin guardas anti decompression-bomb

- **Severidad:** Alto (consecuencia directa del CR-01; se mantiene separado por el vector DoS/almacenamiento)
- **Estado:** Confirmado (el agotamiento por bomba es técnicamente esperado de PIL, no verificado dinámicamente)
- **Ubicación:** `app/features/narrative/admin/image_service.py:38-92` (`await file.read()` completo `:53`, `Image.open`+`convert` `:57-61`, sin límite de tamaño ni verificación de magic bytes), endpoint `app/features/narrative/admin/router.py:82-91`. Caddy limita a 10 MB (`Caddyfile:24-26`) pero el backend directo no.
- **Descripción:** El endpoint no exige autenticación (CR-01), no valida el tamaño más allá del cap de Caddy (10 MB), no comprueba content-type real y confía en Pillow para decodificar. Pillow tiene `MAX_IMAGE_PIXELS` para bombas de descompresión (warning/error según tamaño), pero una imagen de 10 MB puede descomprimir a cientos de MB en RAM durante `convert("RGB")` → OOM/CPU. Los nombres se sanitizan correctamente (slug + uuid, `:66-69`) y las categorías tienen whitelist (`:46-51`), lo que evita path traversal en la escritura.
- **Impacto:** DoS del contenedor backend (memoria límite 1024 MB, `docker-compose.yml:64`) y abuso de almacenamiento/hosting de contenido bajo el dominio de la plataforma.
- **Escenario de explotación:** repetir `POST /api/narrative/admin/upload-imagen?categoria=cartas` con imágenes manipuladas (p. ej. WEBP bomb) en paralelo → agotamiento de RAM/CPU de instancias.
- **Recomendación:** autenticar con admin (CR-01), limitar tamaño en la app (p. ej. 5 MB), setear `Image.MAX_IMAGE_PIXELS` a un valor acotado y tratar `DecompressionBombError`, validar magic bytes, rate-limit del endpoint, considerar escaneo antivirus y almacenamiento externo (S3) con cuotas.

---

### MEDIOS

#### ME-01 — CORS: `allow_origin_regex=r"^https?://.*$"` con `allow_credentials=True`

- **Estado:** Confirmado. **Ubicación:** `app/main.py:91-98`.
- **Descripción:** Starlette refleja cualquier `Origin` que matchee el regex (`http://` o `https://` de cualquier host). Con `allow_credentials=True`, el navegador autoriza envío de credenciales a ese origen.
- **Riesgo real hoy (sin cookies):** el token se guarda en `localStorage` (según `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md:250,265`), al que un origen atacante **no** puede acceder; por lo tanto no puede hacer requests autenticadas por sí solo. El impacto directo actual es bajo: CORS no es una frontera de autenticación y la API ya es invocable sin credenciales. **Con cookies (o migración futura a `httpOnly` cookies, Basic o el patrón "recordar sesión para siempre" descripto en la guía):** cualquier sitio malicioso podría operar la API con la sesión de la víctima → CSRF-like total (Crítico).
- **Además:** `FRONTEND_URL` del `.env` es `http://localhost:5173`, por lo que la lista `origins` no incluye el dominio real de producción; el regex es lo único que "funciona", enmascarando la mala configuración.
- **Recomendación:** reemplazar por lista explícita de orígenes de producción (por environment); eliminar `allow_origin_regex` (o restringirlo con un flag de entorno de desarrollo); mantener `allow_credentials=True` solo si se usan cookies; `allow_methods`/`allow_headers` acotados; documentar que Bearer debe viajar por header y no en URL.

#### ME-02 — Validación de tokens sin consulta a la BD en attempts/narrative → cuentas desactivadas siguen operando

- **Estado:** Confirmado. **Ubicación:** `app/features/user_attempts/router.py:17-28`; `app/features/narrative/game/router.py:64-76`.
- **Descripción:** Ambos helpers usan solo `decode_access_token` (firma+exp) y nunca `get_current_user`. La desactivación (`activo=false`) o borrado de la cuenta no corta el acceso a partidas/intentos. En `_get_current_user_id` un token inválido degrada silenciosamente a invitado (0).
- **Impacto:** un usuario expulsado (o una cuenta con token robado) sigue jugando/registrando progreso por hasta 180 días; combinado con AL-01, el bypass admin del rate limiter tampoco consulta DB.
- **Recomendación:** usar `Depends(get_current_user)` en todos los endpoints autenticables; para invitados, separar explícitamente rutas públicas de las de sesión; nunca degradar silenciosamente de token inválido a invitado en endpoints con efectos persistentes.

#### ME-03 — Modo invitado con `user_id=0` compartido

- **Estado:** Confirmado (posible decisión de producto). **Ubicación:** `app/features/narrative/game/router.py:64-76`; `app/features/narrative/game/setup_service.py:103,117-125`; tests usan `user_id=0` (`tests/test_narrative_game.py:54`).
- **Descripción:** Todos los anónimos comparten la misma "run" por fecha (`user_id=0`). Cualquiera puede listar/consultar/modificar/reiniciar (`/reiniciar` borra la run) el estado de todos los invitados; dos invitados se pisan el progreso.
- **Impacto:** manipulación/DoS de la experiencia de demo; si se usara como previa sin login para usuarios reales, confusión y pérdida de progreso. No expone PII.
- **Recomendación:** si el invitado es requisito, asignar `session_id` anónimo por dispositivo (cookie firmada) y no `0` global; o exigir login.

#### ME-04 — MongoDB sin autenticación en el compose

- **Estado:** Confirmado. **Ubicación:** `docker-compose.yml:72-97` (`mongo:7.0` sin `MONGO_INITDB_ROOT_USERNAME/PASSWORD` ni `--auth`), `MONGODB_URL=mongodb://mongodb:27017` (`:46`), `.env` sin credenciales.
- **Descripción:** Aunque el puerto no está publicado al host (bien) y hay red dedicada `sipi_net`, cualquier contenedor/proceso dentro de esa red accede a la base completa sin autenticación. La doc lo declara una fortaleza ("No expuesto al exterior", `README_SEGURIDAD.md:50,67`) pero omite que no hay auth.
- **Impacto:** en caso de compromiso de cualquier contenedor de la red (p. ej. RCE en backend vía dependencias, o el propio upload/SSRF futuro), la base entera queda accesible; también un mal despliegue con `ports` publicados la expondría.
- **Recomendación:** habilitar auth de MongoDB (`--auth` + usuario/clave por secret), credenciales en el `MONGODB_URL`; mantener red interna; revisar que jamás se publique `27017`; backups con credenciales.

#### ME-05 — Fallback SMTP "simulado" y `FRONTEND_URL=localhost` en `.env`

- **Estado:** Confirmado. **Ubicación:** `app/features/auth/email_service.py:16-23,101-107`; `.env` (`FRONTEND_URL` = localhost).
- **Descripción:** Si `SMTP_PASSWORD` falta o es placeholder, el envío se "simula" (return True) y el código/enlace solo queda en logs (AL-05). En el `.env` revisado `FRONTEND_URL` apunta a localhost, con lo que los magic links generarían URLs inutilizables en producción.
- **Impacto:** cuentas que nunca activan (código no recibido) mientras el sistema responde "enviado con éxito"; enlaces rotos; operación silenciosamente degradada.
- **Recomendación:** fallar explícitamente si no hay configuración de correo en producción (health-check de configuración), tests de envío; fijar `FRONTEND_URL` real por entorno (`https://…`) y validar en el arranque.

#### ME-06 — `/docs`, `/redoc`, `/openapi.json` y SPA `/admin` accesibles si el backend se publica directo

- **Estado:** Confirmado; hoy mitigado por la topología Caddy (no rutea esos prefijos). **Ubicación:** `app/main.py:70-78` (docs abiertas), `:139-165` (SPA admin estática sin gating; fallback SPA devuelve `index.html` para cualquier 404).
- **Descripción/impacto:** documentación interactiva y panel de administración (HTML/JS) sirven sin autenticación; los datos se protegen por API (salvo CR-01), pero exponer el panel/doc facilita enumeración y ataques. En el compose actual el backend no publica puerto; si se accede directo (o se agrega Nginx apuntando al backend), quedan expuestos.
- **Recomendación:** `docs_url=None`/`redoc_url=None`/`openapi_url=None` en producción (o proteger con auth básica), servir la SPA admin solo detrás de autenticación de infraestructura (VPN/SSO) o eliminar el mount estático si la gestión migra al frontend; considerar `<meta robots>` y CSP.

#### ME-07 — Rate limiter in-memory: por proceso, se resetea, no purga claves

- **Estado:** Confirmado. **Ubicación:** `app/core/rate_limit.py:7-32`.
- **Descripción:** El estado vive en un `defaultdict(deque)` del proceso; un reinicio (compose `restart: unless-stopped`, deploy) borra contadores; un escalado a varios workers duplica el límite; las claves nunca se eliminan (cada IP/path nuevo crea entrada permanente) → con XFF aleatorio (AL-01) la memoria crece.
- **Recomendación:** Redis (o similar) con TTL por ventana; purga periódica de claves vacías; métrica de rechazos; combinado con bloqueo por cuenta.

#### ME-08 — Soluciones de los desafíos expuestas y sobrescribibles sin auth

- **Estado:** Confirmado. **Ubicación:** `app/features/daily_challenges/service.py:37-48` (serializa `config` completo), `:351` (consulta explícita de `config.solution` para Wordle), `router.py:77-83` (upsert sin auth).
- **Descripción:** `GET /api/challenges/today|date|month` devuelve `config` (incluye solución, p. ej. palabra del Wordle) a cualquiera; con CR-02 además se puede reescribir.
- **Impacto:** integridad de los juegos (trampa trivial), manipulación del contenido educativo; no es un compromiso de datos personales.
- **Recomendación:** no devolver campos sensibles en endpoints públicos (proyectar solo lo necesario), validar respuestas no iniciadas server-side, mover upsert a admin.

#### ME-09 — El handler de excepciones no propaga headers (`Retry-After`, `WWW-Authenticate`)

- **Estado:** Confirmado. **Ubicación:** `app/main.py:104-114`.
- **Descripción:** El handler personalizado construye `JSONResponse` sin `exc.headers`, por lo que los 429 del rate limiter pierden `Retry-After` y los 401 pierden `WWW-Authenticate`, aunque el limiter los setea (`rate_limit.py:24-28`, `dependencies.py:20,29,45`).
- **Impacto:** clientes legítimos no conocen el tiempo de espera; semántica HTTP degradada (no es bypass).
- **Recomendación:** propagar `exc.headers` en el `JSONResponse`.

#### ME-10 — El PIN viaja en respuestas y en el asunto del email

- **Estado:** Confirmado. **Ubicación:** `app/features/auth/service.py:44` (`format_user_response` siempre incluye `codigoAcceso`; usado en login, verificar-token, registro y perfiles), `app/features/auth/email_service.py:98` (asunto `Tu código de acceso: <PIN> - …`).
- **Descripción:** El PIN permanente se muestra en el asunto del correo (visible en notificaciones de pantalla/bloqueo) y en las respuestas `login_codigo`, `login_sistemas`, `verificar_token` y `GET /usuario/{id}` (a sí mismo/admin).
- **Impacto:** mayor superficie de fuga de la credencial permanente (capturas, logs de clientes, correo reenviado).
- **Recomendación:** no incluir el PIN en respuestas innecesarias (el login no necesita devolver `codigoAcceso`), no exponerlo en asuntos; mostrarlo solo en la pantalla de activación del propio flujo y permitir regeneración.

#### ME-11 — Registro: PIN elegible por el usuario y contraseña opcional

- **Estado:** Confirmado. **Ubicación:** `app/features/auth/schemas.py:28-29`; `app/features/auth/service.py:235-241`. Ver también BA-07.
- **Descripción:** `codigoAcceso` no tiene validación alguna (ni formato, ni dígitos, ni longitud, ni unicidad previa). El registro público lo persiste tal cual; si colisiona, el índice único (`database.py:62`) lanza `DuplicateKeyError` no capturado → 500. `password` es opcional en el registro público (`None` → hash `None`), lo cual es coherente con "sin contraseñas" pero implica que **la única credencial es el PIN** (ver AL-02).
- **Impacto:** PINs débiles elegidos por usuarios (p. ej. `1234`), errores 500 por colisión y mensajes de índice (menor), degradación del modelo de credencial.
- **Recomendación:** generar el PIN siempre server-side con CSPRNG, validar `^\d{6}$`, capturar `DuplicateKeyError` y reintentar; si se admite PIN provisto, imponer formato y listas negras (`123456`, `000000`, repetidos) + contador de intentos.

---

### BAJOS

#### BA-01 — Dependencias sin pin y sin lockfile
- **Ubicación:** `requirements.txt:1-15` (todas `>=`). **Impacto:** builds no reproducibles; una versión futura rota o comprometida de una dependencia entra sin control; `Pillow` sin cota superior. **Recomendación:** fijar versiones (o lockfile con hashes) y automatizar actualizaciones con revisión; `pip-compile`/`uv lock`.

#### BA-02 — Contenedor backend como root y `COPY . .` total
- **Ubicación:** `Dockerfile:1-21` (sin `USER`, sin `--chown`, `COPY . .`). Combinado con CR-03, la imagen incluye secretos. **Recomendación:** usuario no privilegiado, copiar solo `app/` + artefactos necesarios, `read_only`+`tmpfs` donde se pueda, secrets en runtime.

#### BA-03 — Caddy sin TLS/HSTS/CSP
- **Ubicación:** `Caddyfile:1-44` (`:8082` en claro; cabeceras buenas pero sin `Strict-Transport-Security` ni `Content-Security-Policy`). El comentario del compose sugiere un Nginx/firewall delante no auditado. **Impacto:** sin TLS (si no hay proxy frontal), interceptación/robo de tokens por HTTP. CSP ausente → mayor impacto de cualquier XSS futura. **Recomendación:** TLS en Caddy (o documentar el proxy TLS), HSTS, CSP estricta para la SPA, revisar timeouts y límites en producción.

#### BA-04 — `GET /usuario/estados` público
- **Ubicación:** `app/features/usuario/router.py:48-50`. Expone el catálogo de estados (no PII) sin auth. **Recomendación:** requerir autenticación (el frontend de alumnos no parece necesitarlo) o mover a router admin.

#### BA-05 — `get_current_user` responde 404 cuando el usuario no existe
- **Ubicación:** `app/core/dependencies.py:49-53`. Permite sondear IDs de usuarios borrados; incoherente con 401 para token inválido. **Recomendación:** devolver 401 uniforme.

#### BA-06 — `POST /api/auth/verificar-token` sin rate limit
- **Ubicación:** `app/features/auth/router.py:34-36`. Endpoint público que decodifica tokens; sin límite. **Recomendación:** agregar `rate_limit`, y no devolver `codigoAcceso` (ME-10).

#### BA-07 — `password` sin `min_length` en el registro
- **Ubicación:** `app/features/auth/schemas.py:28` (solo `max_length=128`). Contradice `README_SEGURIDAD.md:193` ("mínimo 6"). **Recomendación:** si las contraseñas existen para admins (por `POST /usuario`), validar fortaleza mínima y longitud; documentar que las cuentas de alumnos no usan contraseña.

#### BA-08 — `init_indexes` falla en silencio; seed admin en cada arranque
- **Ubicación:** `app/core/database.py:103-104` (captura `Exception` y solo warnings: si el índice único de `codigo_acceso` no se crea, pueden existir PINs duplicados y `login_codigo` resolvería el primero arbitrario — **sospecha operativa**); `app/main.py:38` + `init_db.py:64-93` reponen el admin por defecto en cada arranque si fue eliminado. **Recomendación:** fallar el arranque si los índices críticos no se crean; desacoplar el seed de credenciales del startup productivo.

#### BA-09 — Casilla personal como remitente y credenciales MySQL root por defecto
- **Ubicación:** `app/core/config.py:23` (`MAIL_FROM` con casilla personal/gmail), `:35-39` (`MYSQL_USER=root`, `MYSQL_PASSWORD=root`, base `prueba2`). Aunque el ETL no es un servicio expuesto, los defaults son peligrosos si alguien ejecuta el script con `.env` incompleto. **Recomendación:** cuenta de correo institucional, credenciales ETL dedicadas y de mínimo privilegio, sin defaults.

#### BA-10 — Categoría `characters` vs `personajes`
- **Ubicación:** `image_service.py:18-26` (categoría `personajes`) frente a `app/static/narrative/characters/*.webp` y seeds. Funcional (imágenes de personajes preexistentes quedan en otra carpeta), no de seguridad; se menciona por completitud. **Recomendación:** unificar.

---

## 5. Claims de `docs_interna` vs realidad (contraste obligatorio)

`docs_interna/README_SEGURIDAD.md` está escrito como "defensa en profundidad" aspiracional y contiene afirmaciones que el código real no respalda. Detalle:

| # | Claim documental (README_SEGURIDAD.md) | Realidad verificada | ¿Se cumple? |
|---|---|---|---|
| 1 | "Autenticación forzada en endpoints de usuarios y administración" (checklist, `:235`) | `/api/narrative/admin/*` sin ninguna dependencia (`narrative/admin/router.py:64-320`); `/api/challenges/admin/*` y `POST /api/challenges` sin auth (`daily_challenges/router.py:77-113`); `/api/games/attempts` acepta `user_id` ajeno y requests sin token (CR-06) | **NO** |
| 2 | "RLS anti-IDOR en datos de progreso y perfiles; solo el propio alumno o admin" (`:118-137`, `:236`) | Cierto para `/progreso` (`progreso/router.py:18-51`) y `GET /usuario/{id}` (`usuario/router.py:85-91`); **falso** para `/api/games/attempts` (IDOR no autenticado) y narrativo (invitado global) | **PARCIAL** |
| 3 | "Anti mass-assignment: público fuerza `tipo_usuario=1` y `black=False`" (`:140-156`) | Cierto para esos campos (`auth/service.py:246-253`), pero el público **elige su `codigoAcceso` sin validación** (`schemas.py:29`) y `password` no tiene mínimo (`schemas.py:28`) | **PARCIAL** |
| 4 | "Rate limiting 5 req/min por IP, protege PIN/login/registro" (`:159-172`, `:238`) | Implementado, pero evadible con `X-Forwarded-For` arbitrario, con bypass por claim admin sin DB, in-memory sin TTL y sin bloqueo por cuenta (`rate_limit.py:7-56`) | **ENGAÑOSO** |
| 5 | "PIN: longitud obligatoria entre 4 y 10 dígitos" (`:194`) | Son 4-10 **caracteres**; el registro no valida nada y permite `codigo` de 1+ caracteres elegido por el usuario | **NO** |
| 6 | "Contraseñas: longitud mínima de 6 y máxima de 128" (`:193`) | `RegisterRequest.password` no tiene `min_length` (`schemas.py:28`); login solo exige 1 | **NO** |
| 7 | "MongoDB: no expuesto al exterior" (`:50`) | Cierto en el compose (sin `ports`), pero **sin autenticación** dentro de la red `sipi_net` (`docker-compose.yml:72-97`) | **PARCIAL** |
| 8 | "Bloqueo perimetral de `.env`/`.git`" (`:81`, `:229`) | Caddy bloquea `*/.*` para su file_server, pero el `.env` real **no está excluido en `.dockerignore`** y queda dentro de la imagen (`Dockerfile:15`) — el vector real de fuga es otro y no está cubierto | **ENGAÑOSO** |
| 9 | "Hardening de contenedores" (`:56-67`) | Cierto: `no-new-privileges`, límites CPU/RAM, rotación de logs, red dedicada. **Pero**: backend corre como root, sin `read_only`, y la imagen contiene secretos | **PARCIAL** |
| 10 | "Caddy como cortafuegos previo con filtrado explícito" (`:71-82`) | Cierto que filtra prefijos, pero `/api*` incluye toda la superficie admin sin auth (CR-01/CR-02); `/docs` y `/admin` no se exponen por accidente, no por diseño | **PARCIAL** |
| 11 | "Sanitización `re.escape` anti-ReDoS" (`:180-189`) | Correcto en `usuario/service.py:24-29` | **SÍ** |
| 12 | "Contraseñas hasheadas con BCrypt (10 rondas)" (`:225`) | Correcto (`security.py:25`) | **SÍ** |
| 13 | "Validación de tipos y rangos con Pydantic" (`:191-196`, `:239`) | Cierto en general, pero con huecos: `codigoAcceso`, `score/attempts/stars` sin cotas, `config`/`game_data` libres, upload sin límites | **PARCIAL** |

Otras discrepancias documentales menores:
- `docs_interna/GUIA_INTEGRACION_FRONTEND_AUTH.md:7` afirma CORS "cualquier origen en desarrollo", pero `main.py:94` lo aplica también en producción.
- La misma guía (`:62-69`) documenta que un código inválido responde `404`, mientras el código real responde `401` (`auth/service.py:100-104`) y con otro mensaje.
- `README.md:76` y `GUIA_...:367-374` publican las credenciales admin por defecto, que siguen vivas (CR-04).
- El checklist (`:221-240`) marca ✅ "Autenticación forzada en endpoints …" y "RLS en datos de progreso" sin mencionar el módulo narrativo (que no tiene RLS ni RBAC) ni `user_attempts`.

---

## 6. Fortalezas confirmadas (lo que sí está bien)

- **BCrypt:** `bcrypt.checkpw` (comparación segura) y `gensalt(rounds=10)` con compatibilidad `$2a$` de Spring (`security.py:7-27`).
- **JWT:** `algorithms=["HS256"]` explícito y fijo, evitando el ataque clásico de confusión de algoritmo (`security.py:59`); claims coherentes.
- **RLS de progreso:** checks de ownership correctos en los tres endpoints (`progreso/router.py:18-51`); `get_usuario_by_id` restringe a owner/admin (`usuario/router.py:85-91`).
- **RBAC del CRUD de usuarios:** `get_current_admin` aplicado consistentemente en `/usuario` (excepto `GET /usuario/estados`, BA-04).
- **Revalidación de usuario en DB** en `get_current_user` (estado `activo`) — el enfoque correcto para que la desactivación corte sesiones, aunque rutas que no lo usan quedan fuera (ME-02).
- **Anti-mass-assignment** en el registro público para `tipo_usuario`/`black` (`auth/service.py:246-253`).
- **Anti-ReDoS:** `re.escape` en la búsqueda de la torre de control (`usuario/service.py:24-29`).
- **Índices únicos** de `email`, `codigo_acceso`, `id` (`database.py:61-63`).
- **Sin inyección NoSQL evidente** en los filtros Mongo: los modelos Pydantic tipan los valores (`str`, `int`, `List[str]`, `EmailStr`) y no se construyen filtros a partir de diccionarios crudos del cliente (revisado en auth, usuario, desafíos, narrativo, attempts). Los diccionarios libres (`config`, `game_data`) se almacenan, no se usan como filtro.
- **Upload de imágenes:** whitelist de categorías y sanitización de nombre (slug + uuid) que evita path traversal de escritura (`image_service.py:46-51,66-69`).
- **Docker/Compose:** `no-new-privileges`, límites de CPU/RAM, rotación de logs, red interna sin publicar MongoDB, `:ro` para Caddyfile/dist (`docker-compose.yml:1-104`).
- **Caddy:** oculta `Server`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, límite 10 MB y bloqueo de dotfiles para estáticos (`Caddyfile:1-31`).
- **Estáticos:** montajes `StaticFiles`/SPA sin path traversal conocido (Starlette valida), y no hay endpoints de lectura arbitraria de archivos.

---

## 7. Riesgos residuales, supuestos y preguntas abiertas

### Supuestos usados
1. El despliegue de producción usa el `docker-compose.yml` y el `.env` auditado (referenciados en `:43-44`). Si el `.env` de producción difiere (otro `JWT_SECRET`, otra `ADMIN_DEFAULT_PASSWORD`), CR-03/CR-04 bajan de severidad operativa — **pero el default público en `config.py` sigue siendo un riesgo si el archivo falta o está mal montado** (pydantic-settings cae al default sin aviso).
2. El frontend guarda el token en `localStorage` (documentado, no verificado en código del front). Si en realidad usa cookies, **ME-01 escala a Crítico** (CSRF con credenciales).
3. En el compose auditado el backend no publica puerto y Caddy no rutea `/docs`, `/admin`, `/assets`. Si hay un proxy externo o un mapeo directo en el servidor real, ME-06/BA-03 suben.
4. La base MongoDB real no fue consultada: la vigencia del admin por defecto y del PIN `999999` se infiere del código de seed + `.env`.

### Riesgos residuales clave (post-remediación)
- **Diseño de PIN permanente:** aunque se arreglen rate limiting y CR-04, un PIN de 6 dígitos como única credencial para una población vulnerable seguirá siendo débil; requiere rotación/regeneración y quizá segundo factor asistido (código por email/WhatsApp) para operaciones sensibles.
- **JWT de larga duración sin revocación:** incluso con HMAC seguro, el robo de token es indetectable; migrar a access+refresh con jti.
- **Almacenamiento local de imágenes:** sin CDN/cuotas y sin validación profunda, el upload seguirá siendo vector de abuso.
- **Logs como fuente de secretos:** mientras existan fallbacks "simulados" y logs verbosos, cualquier incidente de SMTP filtra accesos.
- **Multiplataforma de despliegue:** el hardening real depende del proxy frontal (Nginx/Firewall) no incluido en el repo; sin esa capa, TLS/HSTS/rate limiting de borde no existen.

### Preguntas abiertas (para el equipo)
1. ¿En la base de producción el admin `admin@sistemas.com` sigue con `admin123`/PIN `999999`? ¿Cuándo se rotó por última vez el `JWT_SECRET`? (No se puede saber sin acceso a la BD; **asumir que no se rotó** hasta verificar.)
2. ¿El frontend real usa `localStorage` en todos los flujos (incluido `/acceso` del magic link)? ¿Hay riesgo de XSS en la SPA que combine con token en `localStorage`?
3. ¿Existe un Nginx/firewall delante de Caddy terminando TLS, con límites de tasa y bloqueo de `/api/narrative/admin`? ¿Está documentado en algún repositorio de infraestructura (no está en este repo)?
4. ¿El modo invitado del narrativo (`user_id=0`) es intencional para demo? ¿Se espera aislar el progreso de invitados?
5. ¿La colección `user_attempts`/`puntos` tiene consumidores (rankings) que hagan de la manipulación de score un problema de negocio?
6. ¿Los códigos de activación se purgan tras activar (hoy se conservan como PIN)? ¿Se desea permitir PIN provisto por el usuario (por ejemplo por accesibilidad)?
7. ¿Hay imágenes/archivos subidos por usuarios reales que deban auditarse por contenido malicioso (ME-06/AL-06)?
8. `init_indexes` silencioso: ¿se verificó alguna vez en producción que el índice único de `codigo_acceso` existe? Si falló, ¿hay colisiones de PIN?

---

## 8. Plan de remediación priorizado (sugerido)

**Inmediato (horas):**
1. CR-01/CR-02: envolver `/api/narrative/admin/*` y `/api/challenges/admin*` + upsert con `Depends(get_current_admin)`; bloquear esos prefijos en Caddy mientras tanto.
2. CR-03: rotar `JWT_SECRET`, SMTP, RAE, MySQL; agregar `.env` a `.dockerignore` y reconstruir imagen; eliminar defaults de `config.py`.
3. CR-04: rotar/eliminar admin por defecto; desactivar seed automático en producción; quitar PIN admin o restringir rol en `login_codigo`.
4. CR-05: parchear `modificar-email-registro` (exigir código al email actual o deshabilitarlo).
5. CR-06: usar `get_current_user` en `/api/games/attempts` e ignorar `user_id` cliente.
6. AL-05/ME-05: eliminar logs de códigos/tokens; fail-fast de SMTP en producción.

**Corto plazo (días):**
7. AL-01: arreglar XFF (proxy de confianza / IP real) + bloqueo por cuenta + Redis si aplica; ME-07.
8. AL-02/ME-11: PIN server-side, separar activación de login, expiración, `compare_digest`, validación `^\d{6}$`.
9. AL-03: acortar expiración + refresh/revocación; magic link con código de un solo uso.
10. AL-04: respuestas uniformes anti-enumeración.
11. AL-06: límites de tamaño y bombas en upload.
12. ME-01: CORS explícito por entorno; ME-02: validar token contra DB en attempts/narrative.
13. ME-04: auth de MongoDB; BA-02: usuario no root en Docker.

**Mediano plazo (semanas):**
14. BA-01 pin de dependencias + lockfile; BA-03 TLS/HSTS/CSP en el borde; ME-06 cerrar docs/admin; matriz de tests de autorización (positivos y negativos) por endpoint; revisar el checklist de `README_SEGURIDAD.md` para que refleje el estado real (o marcarlo como "roadmap").
15. Auditoría dinámica (DAST) + pentest con la app en un entorno representativo, y revisión del frontend (XSS/localStorage).

---

*Fin del informe — 03-auditoria-de-seguridad.md. Análisis estático; ningún valor de secreto real fue reproducido en este documento.*
