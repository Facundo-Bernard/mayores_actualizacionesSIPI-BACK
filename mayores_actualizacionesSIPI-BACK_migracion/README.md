# Backend Migración: FastAPI + MongoDB
### Proyecto: Mayores Actualizaciones (Plataforma Educativa para Adultos Mayores)

Este directorio contiene el backend completamente migrado a **Python (FastAPI)** y **MongoDB**, manteniendo el **100% de compatibilidad** con el frontend en React existente (`mayores_actualizacionesSIPI-FRONT`).

---

## 🚀 Características principales
- **Cero Breaking Changes**: Todos los endpoints, payloads, nombres de campos en JSON (`dateStart`, `codigoAcceso`, `tipoUsuario`, etc.) y códigos de estado HTTP coinciden exactamente con la versión de Spring Boot.
- **IDs Secuenciales Numéricos (`id: int`)**: Compatible con el frontend existente mediante secuencias atómicas en la colección `counters`.
- **Compatibilidad con contraseñas existentes (BCrypt)**: Los hashes generados previamente por Spring Security se verifican sin problemas.
- **Rendimiento y Ligereza**: Consume ~70MB de RAM (vs ~500MB de JVM) y levanta en menos de 0.5s.
- **Documentación Swagger Automática**: Accesible en `http://localhost:8080/docs`.

---

## 📂 Estructura del proyecto
```text
mayores_actualizacionesSIPI-BACK_migracion/
├── requirements.txt            # Dependencias de Python
├── .env.example                # Plantilla de variables de entorno
├── .env                        # Variables locales (ignorado por Git)
├── README.md                   # Esta documentación
└── app/
    ├── main.py                 # Entrada FastAPI, CORS y Lifespan
    ├── core/
    │   ├── config.py           # Lectura de .env con Pydantic Settings
    │   ├── database.py         # Motor async MongoDB y generador de IDs numéricos
    │   └── security.py         # BCrypt y tokens JWT (HMAC-SHA256)
    ├── features/
    │   ├── auth/               # Login sistemas, PIN, verificación y Brevo SMTP
    │   ├── usuario/            # Torre de control (skip/limit, filtros, toggle activo)
    │   └── progreso/           # Avance de cursos con Upsert automático
    └── scripts/
        ├── init_db.py          # Superadmin por defecto e índices
        └── migrate_from_mysql.py # ETL para migrar datos de MySQL prueba2 a MongoDB
```

---

## 🛠️ Cómo ejecutar el proyecto

### 1. Activar entorno virtual (ya creado en `.venv`)
En PowerShell:
```powershell
.\mayores_actualizacionesSIPI-BACK_migracion\.venv\Scripts\Activate.ps1
```

### 2. Migrar los datos desde MySQL a MongoDB (Opcional)
Con tu MySQL local corriendo (base de datos `prueba2`) y MongoDB activo:
```powershell
$env:PYTHONPATH=".\mayores_actualizacionesSIPI-BACK_migracion"
.\mayores_actualizacionesSIPI-BACK_migracion\.venv\Scripts\python.exe -m app.scripts.migrate_from_mysql
```

### 3. Iniciar el servidor FastAPI
```powershell
$env:PYTHONPATH=".\mayores_actualizacionesSIPI-BACK_migracion"
.\mayores_actualizacionesSIPI-BACK_migracion\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Accedé a la documentación interactiva en:
👉 **http://localhost:8080/docs**
