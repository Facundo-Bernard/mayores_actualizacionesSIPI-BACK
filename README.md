# Mayores Actualizaciones — Backend API

Backend del sistema **Mayores Actualizaciones** (plataforma educativa para adultos mayores), desarrollado en **Python (FastAPI)** y **MongoDB**.

Diseñado para mantener **100% de compatibilidad** con el frontend en React (`mayores_actualizacionesSIPI-FRONT`).

---

## 🚀 Características principales

- **FastAPI + Asincronismo**: Respuestas rápidas y no bloqueantes con Motor (driver async oficial de MongoDB).
- **Cero Breaking Changes**: Todos los endpoints, payloads, nombres de campos en JSON (`dateStart`, `codigoAcceso`, `tipoUsuario`, etc.) y contratos de autenticación coinciden exactamente con la versión original de Spring Boot.
- **IDs Secuenciales Numéricos (`id: int`)**: Compatible con el frontend existente mediante secuencias atómicas en la colección `counters`.
- **Compatibilidad con contraseñas existentes (BCrypt)**: Los hashes generados previamente por Spring Security se verifican directamente mediante `bcrypt`.
- **Ligero y Eficiente**: Bajo consumo de recursos y tiempo de arranque menor a 0.5 segundos.
- **Seguridad Multicapa (Defensa en Profundidad)**: Hardening en Docker, proxy Caddy con cabeceras de seguridad, control de acceso por roles (RBAC), Row-Level Security (RLS) anti-IDOR y rate limiting anti-fuerza bruta.
- **Documentación de Seguridad Completa**: Disponible en [`docs_interna/README_SEGURIDAD.md`](docs_interna/README_SEGURIDAD.md).

---

## 📂 Estructura del Proyecto

```text
.
├── app/
│   ├── main.py                 # Punto de entrada FastAPI, CORS y ciclo de vida (Lifespan)
│   ├── core/
│   │   ├── config.py           # Variables de entorno con Pydantic Settings
│   │   ├── database.py         # Conexión async a MongoDB y generador de secuencias atómicas
│   │   ├── dependencies.py     # Dependencias de autenticación (get_current_user, get_current_admin)
│   │   ├── rate_limit.py       # Limitador de tasa por IP anti-fuerza bruta en memoria
│   │   └── security.py         # Criptografía BCrypt y tokens JWT (HMAC-SHA256)
│   ├── features/
│   │   ├── auth/               # Login sistemas, PIN de alumnos, Brevo SMTP y auto-registro
│   │   ├── usuario/            # Torre de control (filtros, paginación, toggles) [Solo Admin]
│   │   └── progreso/           # Avance de cursos con RLS (solo el propio alumno o admin)
│   └── scripts/
│       ├── init_db.py          # Creación de superadmin inicial e índices
│       └── migrate_from_mysql.py # ETL para migrar MySQL a MongoDB
├── docs_interna/
│   ├── README_SEGURIDAD.md     # Guía detallada de la arquitectura de seguridad implementada
│   ├── GUIA_INTEGRACION_FRONTEND_AUTH.md
│   └── GUIA_PROGRESO_USUARIO.md
├── Caddyfile                   # Servidor web, proxy inverso y cabeceras de seguridad
├── requirements.txt            # Dependencias de Python
├── Dockerfile                  # Imagen optimizada Python 3.12-slim
├── docker-compose.yml          # Orquestación hardened (Caddy + FastAPI + MongoDB)
├── .env.example                # Plantilla de variables de entorno
└── README.md                   # Esta documentación
```

---

## 🛠️ Instalación y Ejecución Local

### 1. Requisitos previos
- **Python 3.12+**
- **MongoDB** corriendo localmente en el puerto `27017` (o mediante Docker).

### 2. Configurar entorno virtual
En Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
Copiá el archivo de ejemplo:
```powershell
Copy-Item .env.example .env
```
Ajustá las credenciales de MongoDB, Brevo SMTP y JWT si es necesario.

### 4. Inicializar datos / Migrar (Opcional)
Para crear el superadmin inicial (`admin@sistemas.com` / `admin123`):
```powershell
python -m app.scripts.init_db
```

Para migrar datos desde MySQL `prueba2` a MongoDB `mayores_actualizaciones`:
```powershell
python -m app.scripts.migrate_from_mysql
```

### 5. Iniciar el servidor de desarrollo
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Accedé a la documentación interactiva en:
👉 **http://localhost:8080/docs**

---

## 🐳 Ejecución con Docker Compose

Para levantar tanto el backend como MongoDB en un entorno aislado:

```powershell
docker compose up --build -d
```

Para ver los logs:
```powershell
docker compose logs -f backend
```

Para detener los servicios:
```powershell
docker compose down
```
