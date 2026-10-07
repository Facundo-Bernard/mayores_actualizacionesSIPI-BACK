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
- **Documentación Swagger Automática**: Accesible en `http://localhost:8080/docs`.

---

## 📂 Estructura del Proyecto

```text
.
├── app/
│   ├── main.py                 # Punto de entrada FastAPI, CORS y ciclo de vida (Lifespan)
│   ├── core/
│   │   ├── config.py           # Variables de entorno con Pydantic Settings
│   │   ├── database.py         # Conexión async a MongoDB y generador de secuencias atómicas
│   │   └── security.py         # Criptografía BCrypt y tokens JWT (HMAC-SHA256)
│   ├── features/
│   │   ├── auth/               # Login sistemas, validación de PIN, Brevo SMTP
│   │   ├── usuario/            # Torre de control (filtros, paginación, toggles)
│   │   └── progreso/           # Avance de cursos con upsert embebido en usuarios
│   └── scripts/
│       ├── init_db.py          # Creación de superadmin inicial e índices
│       └── migrate_from_mysql.py # ETL para migrar MySQL a MongoDB
├── requirements.txt            # Dependencias de Python
├── Dockerfile                  # Imagen optimizada Python 3.12-slim
├── docker-compose.yml          # Orquestación de Backend + MongoDB
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
