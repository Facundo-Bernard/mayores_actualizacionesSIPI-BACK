# 🛡️ Guía de Arquitectura y Buenas Prácticas de Seguridad (SIPI)

Este documento detalla la arquitectura de seguridad multicapa (**Defensa en Profundidad**) implementada en el proyecto **Mayores Actualizaciones (SIPI)**, abarcando desde la infraestructura de contenedores hasta la lógica interna del Backend (FastAPI) y la comunicación con el Frontend (React).

---

## 📑 Tabla de Contenidos

1. [Arquitectura de Seguridad: Defensa en Profundidad](#1-arquitectura-de-seguridad-defensa-en-profundidad)
2. [Capa 1: Hardening de Contenedores (Docker Compose)](#2-capa-1-hardening-de-contenedores-docker-compose)
3. [Capa 2: Seguridad Perimetral y Servidor Web (Caddy)](#3-capa-2-seguridad-perimetral-y-servidor-web-caddy)
4. [Capa 3: Autenticación y Autorización por Roles (RBAC)](#4-capa-3-autenticación-y-autorización-por-roles-rbac)
5. [Capa 4: Row-Level Security (RLS) y Mitigación de IDOR](#5-capa-4-row-level-security-rls-y-mitigación-de-idor)
6. [Capa 5: Prevención de Escalada de Privilegios (Anti-Mass Assignment)](#6-capa-5-prevención-de-escalada-de-privilegios-anti-mass-assignment)
7. [Capa 6: Rate Limiting & Anti-Fuerza Bruta](#7-capa-6-rate-limiting--anti-fuerza-bruta)
8. [Capa 7: Validación de Entradas y Mitigación de ReDoS](#8-capa-7-validación-de-entradas-y-mitigación-de-redos)
9. [Capa 8: Integración de Cabeceras en el Frontend](#9-capa-8-integración-de-cabeceras-en-el-frontend)

---

## 1. Arquitectura de Seguridad: Defensa en Profundidad

La seguridad del sistema está estructurada en capas independientes. Si una capa llegara a verse comprometida o eludida, las capas subsiguientes contienen y mitigan el impacto:

```
[ Tráfico Exterior / Internet ]
             │
             ▼
┌───────────────────────────────────────────────┐
│ 1. Red / Proxy Perimetral (Caddy)             │  -> Oculta Server, headers seguros, bloquea .env/.git, límite 10MB
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│ 2. Contenedores Docker (Hardening Host)       │  -> No-new-privileges, :ro, límites CPU/RAM, rotación logs, red sipi_net
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│ 3. API Gateway / FastApi Core                 │  -> Rate limiting (anti-bruteforce), validación Pydantic, escape ReDoS
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│ 4. Control de Acceso y RLS                    │  -> get_current_user, get_current_admin, RLS en progreso y perfiles
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│ 5. Datos y Persistencia (MongoDB)             │  -> No expuesto al exterior, contraseñas hasheadas con BCrypt
└───────────────────────────────────────────────┘
```

---

## 2. Capa 1: Hardening de Contenedores (Docker Compose)

**Archivo:** `docker-compose.yml`

| Directiva | Propósito de Seguridad | Implementación |
|---|---|---|
| **`security_opt: - no-new-privileges:true`** | Impide que cualquier proceso dentro del contenedor pueda elevar privilegios a `root` del host mediante binarios SUID/SGID. | Aplicado en `caddy`, `backend` y `mongodb`. |
| **Volúmenes en solo lectura (`:ro`)** | Evita que un atacante pueda inyectar código en el frontend compilado o modificar el archivo de configuración del proxy. | `./Caddyfile:/etc/caddy/Caddyfile:ro`<br/>`./dist:/srv:ro` |
| **Rotación de logs (`logging`)** | En servidores 24/7, los logs sin rotación llenan el disco rígido de la máquina virtual y corrompen bases de datos. | `driver: json-file`, `max-size: 10m/20m`, `max-file: 3/5`. |
| **Límites de CPU y Memoria (`deploy.resources`)** | Protege la máquina virtual Windows contra caídas totales por desbordamiento de memoria o bucles infinitos. | Backend: max 1.5 CPU, 1024MB RAM.<br/>MongoDB: max 1.0 CPU, 1024MB RAM.<br/>Caddy: max 0.5 CPU, 256MB RAM. |
| **Healthchecks encadenados** | Evita arranques desordenados y errores `502 Bad Gateway`. Caddy espera al backend y el backend espera al ping de MongoDB. | Caddy espera `backend: condition: service_healthy`.<br/>Backend espera `mongodb: condition: service_healthy`. |
| **Red dedicada (`networks: sipi_net`)** | Aísla los tres servicios en un bridge privado. Ningún otro contenedor ajeno en la máquina host puede conectarse al puerto `27017` de MongoDB. | `networks: sipi_net: driver: bridge`. |

---

## 3. Capa 2: Seguridad Perimetral y Servidor Web (Caddy)

**Archivo:** `Caddyfile`

* **Ocultación de firma (`-Server`):** No revela versión ni tecnología de servidor para entorpecer el escaneo automatizado de vulnerabilidades de día cero.
* **`X-Content-Type-Options "nosniff"`:** Obliga al navegador a respetar estrictamente los tipos MIME declarados, impidiendo que archivos subidos se interpreten como scripts ejecutables.
* **`X-Frame-Options "DENY"`:** Bloquea totalmente la incrustación del sitio dentro de `<iframe>` o `<frame>`, anulando vectores de **Clickjacking**.
* **`Referrer-Policy "strict-origin-when-cross-origin"`:** Previene la fuga de rutas internas o identificadores sensibles en la cabecera `Referer` hacia dominios externos.
* **`Permissions-Policy "camera=(), microphone=(), geolocation=()"`:** Deshabilita el acceso a hardware sensible en el navegador del usuario.
* **`request_body { max_size 10MB }`:** Limita las peticiones entrantes para mitigar ataques de denegación de servicio (DoS) por sobrecarga de memoria en el servidor.
* **Bloqueo de archivos ocultos (`@hidden path */.*`):** Responde automáticamente `404 Not Found` ante intentos de acceder a archivos como `.env`, directorios `.git`, `.vscode`, etc.
* **Proxy Inverso con filtrado explícito:** Caddy solo redirige a FastAPI los prefijos declarados (`/api*`, `/usuario*`, `/progreso*`, `/health*`), actuando como cortafuegos previo.

---

## 4. Capa 3: Autenticación y Autorización por Roles (RBAC)

**Archivo:** `app/core/dependencies.py`

Se implementaron dos dependencias estándar de FastAPI basadas en `HTTPBearer`:

### `get_current_user`
1. Extrae el token JWT del encabezado HTTP `Authorization: Bearer <token>`.
2. Decodifica la firma HMAC-SHA256 y verifica expiración temporal (`exp`).
3. Busca al usuario en la colección `usuarios` de MongoDB por `id` o `email`.
4. Comprueba que `activo == True`. Si fue dado de baja, retorna `403 Forbidden`.
5. Inyecta el objeto del usuario autenticado en la función del endpoint.

### `get_current_admin`
1. Consume `get_current_user`.
2. Verifica estrictamente que `user["tipo_usuario"] == 2` (Operador de Sistemas / Administrador).
3. Si el rol es alumno (`tipo_usuario == 1`), bloquea inmediatamente la petición con:
   ```json
   {
     "detail": "Acceso restringido: Se requieren permisos de Operador de Sistemas / Administrador."
   }
   ```

### Endpoints Protegidos
* **Listado de usuarios:** `GET /usuario` -> Requiere `get_current_admin`.
* **Activar/Desactivar cuenta:** `PUT /usuario/{id}/toggle-activo` -> Requiere `get_current_admin`.
* **Alternar Membresía Black:** `PUT /usuario/{id}/toggle-black` -> Requiere `get_current_admin`.
* **Creación administrativa:** `POST /usuario` -> Requiere `get_current_admin`.
* **Despacho de Magic Links:** `POST /api/admin/enviar-acceso-correo` -> Requiere `get_current_admin`.

---

## 5. Capa 4: Row-Level Security (RLS) y Mitigación de IDOR

**Archivos:** `app/features/progreso/router.py` y `app/features/usuario/router.py`

### Problema Anterior (IDOR - Insecure Direct Object References)
Cualquier cliente podía invocar `/progreso/obtenerUsuario/5` o `/progreso/actualizar/5/1` y alterar los registros de cualquier alumno simplemente modificando el parámetro de la URL.

### Solución Implementada
En cada operación que involucra un recurso individual:
```python
# RLS / IDOR: Solo el propio alumno o un admin puede acceder/modificar
if current_user.get("tipo_usuario") != 2 and current_user.get("id") != usuario_id:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes autorización para acceder a los datos de este usuario."
    )
```
* Un alumno **únicamente** puede consultar y guardar su propio avance.
* Un administrador conserva la capacidad de auditar y dar soporte a cualquier alumno.

---

## 6. Capa 5: Prevención de Escalada de Privilegios (Anti-Mass Assignment)

**Archivo:** `app/features/auth/service.py`

### Problema Anterior (Mass Assignment)
El modelo de registro aceptaba campos como `tipoUsuario: 2` (Admin), `black: true` y `activo: true` directamente del cuerpo JSON enviado por el navegador. Cualquier usuario anónimo podía auto-otorgarse rango de Administrador.

### Solución Implementada
La función `register_usuario` ahora recibe la bandera `is_admin_creation: bool = False`:
```python
tipo_usuario = req.tipoUsuario if (is_admin_creation and req.tipoUsuario is not None) else 1
black = bool(req.black) if (is_admin_creation and req.black is not None) else False
activo = bool(req.activo) if (is_admin_creation and req.activo is not None) else True
```
* **Ruta pública (`POST /api/auth/register`):** Siempre fuerza `tipo_usuario = 1` (Alumno) y `black = False`.
* **Ruta interna (`POST /usuario`):** Exige `get_current_admin` y solo allí permite asignar roles y estados especiales.

---

## 7. Capa 6: Rate Limiting & Anti-Fuerza Bruta

**Archivo:** `app/core/rate_limit.py`

Se implementó un limitador de peticiones por ventana deslizante en memoria (`InMemoryRateLimiter`), seguro para concurrencia (`threading.Lock`) y sin dependencias pesadas de terceros.

### Configuración de Tasa
* **Límite:** **5 peticiones por minuto por dirección IP**.
* **Endpoints protegidos:**
  * `POST /api/auth/ingresar-codigo`: Protege el PIN de 6 dígitos de los alumnos contra ataques de diccionario o fuerza bruta automatizada (900.000 combinaciones posibles).
  * `POST /api/auth/login-sistemas`: Protege el inicio de sesión de operadores de sistemas.
  * `POST /api/auth/register`: Evita creación masiva de cuentas fantasma (Spam).
* **Respuesta ante exceso:** Código HTTP `429 Too Many Requests` con la cabecera `Retry-After: <segundos>`.
* **Soporte de Proxy:** Detecta la IP original a través de la cabecera `X-Forwarded-For` inyectada por Caddy.

---

## 8. Capa 7: Validación de Entradas y Mitigación de ReDoS

**Archivos:** `app/features/auth/schemas.py`, `app/features/progreso/schemas.py` y `app/features/usuario/service.py`

### 1. Mitigación de ReDoS (Regular Expression Denial of Service)
En el buscador de la torre de control de usuarios, el término ingresado por el operador se procesa con `re.escape()` antes de construir la expresión regular de MongoDB:
```python
term = re.escape(nombre.strip())
query["$or"] = [
    {"name": {"$regex": term, "$options": "i"}},
    {"email": {"$regex": term, "$options": "i"}}
]
```
Esto impide que caracteres como `.*`, `(a+)+` o repeticiones catastróficas congelen el motor de consultas de MongoDB.

### 2. Restricciones en Modelos Pydantic
* **Nombres:** Longitud mínima de 2 y máxima de 100 caracteres.
* **Contraseñas:** Longitud mínima de 6 y máxima de 128 caracteres.
* **PIN de Acceso:** Longitud obligatoria entre 4 y 10 dígitos.
* **Progreso de Cursos:** Rango numérico acotado con `ge=0, le=100`.
* **Puntaje de Examen:** Rango numérico acotado con `ge=0, le=1000`.

---

## 9. Capa 8: Integración de Cabeceras en el Frontend

**Archivos:** `src/CURSOS_FIXED/services/courseProgressService.js` y `src/PAGINAPRINCIPAL/NAVBAR.jsx`

Para garantizar total compatibilidad con los endpoints ahora autenticados:
1. Se implementó la función auxiliar `getAuthHeaders()`:
   ```javascript
   const getAuthHeaders = () => {
     const token = localStorage.getItem('token');
     const headers = { 'Content-Type': 'application/json' };
     if (token && token !== 'undefined' && token !== 'null') {
       headers['Authorization'] = `Bearer ${token}`;
     }
     return headers;
   };
   ```
2. Todas las llamadas a `obtenerProgresoUsuario`, `actualizar` y `crear` transmiten el Bearer Token en cada solicitud HTTP.
3. El panel de administración (`PanelAltasSistemas.jsx`) ya incluía `Authorization: Bearer <token>` en sus peticiones a `/usuario`.

---

## ✅ Checklist de Cumplimiento Final

| Directiva | Estado |
|---|:---:|
| Contraseñas hasheadas con BCrypt (10 rondas de salt) | ✅ |
| Ocultamiento de cabeceras de servidor (`-Server`) | ✅ |
| Encabezados de seguridad (`X-Frame-Options`, `nosniff`, `Referrer-Policy`) | ✅ |
| Restricción de payloads DoS (`max_size 10MB`) | ✅ |
| Bloqueo perimetral de archivos ocultos (`.env`, `.git`) | ✅ |
| Contenedores con `no-new-privileges: true` | ✅ |
| Volúmenes de frontend y proxy montados en solo lectura (`:ro`) | ✅ |
| Límite y rotación de logs en Docker | ✅ |
| Cuotas de CPU y RAM por contenedor | ✅ |
| Red bridge dedicada (`sipi_net`) | ✅ |
| Autenticación forzada en endpoints de usuarios y administración | ✅ |
| Row-Level Security (RLS) en datos de progreso de alumnos | ✅ |
| Bloqueo de escalada de privilegios (anti-mass assignment) | ✅ |
| Rate Limiting anti-fuerza bruta en PIN y login (5 req/min) | ✅ |
| Validación de tipos y rangos de datos con Pydantic | ✅ |
| Sanitización de regex (`re.escape`) anti-ReDoS | ✅ |
