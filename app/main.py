import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.scripts.init_db import seed_default_admin, seed_estados_usuario
from app.features.auth.router import router as auth_router
from app.features.usuario.router import router as usuario_router
from app.features.progreso.router import router as progreso_router
from app.features.sso.router import router as sso_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AppMain")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Conectar a MongoDB, inicializar índices y sembrar datos esenciales de autenticación/usuarios
    logger.info("Iniciando aplicación Mayores Actualizaciones (FastAPI)...")
    await connect_to_mongo()
    await seed_estados_usuario()
    await seed_default_admin()
    logger.info(f"Servidor listo en el puerto {settings.PORT}.")
    yield
    # Shutdown: Cerrar conexiones limpiamente
    logger.info("Deteniendo aplicación y cerrando conexiones...")
    await close_mongo_connection()

# Hardening: Desactivar /docs, /redoc y openapi.json en producción
app = FastAPI(
    title="Mayores Actualizaciones API",
    description="Backend en FastAPI + MongoDB para la plataforma educativa de adultos mayores",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan
)

# Configuración de CORS estricta (Sin allow_origin_regex permisivo)
origins = [
    "https://mayoresactualizaciones.asistodo.com.ar",
    "http://mayoresactualizaciones.asistodo.com.ar:8082",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if settings.FRONTEND_URL:
    fe_url = settings.FRONTEND_URL.rstrip("/")
    if fe_url and fe_url not in origins:
        origins.append(fe_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Manejador de excepciones HTTP estándar
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": exc.detail,
            "message": msg
        }
    )

# DIRECTIVA DE SEGURIDAD ABSOLUTA (FAIL-CLOSED):
# Interceptor global para excepciones no controladas. Nunca expone stack traces ni detalles del servidor.
@app.exception_handler(Exception)
async def global_fail_closed_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error interno no controlado en {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": "Solicitud no permitida."
        }
    )

# Inclusión de routers esenciales (Auth, Usuarios, Progreso de Cursos, SSO)
app.include_router(auth_router)
app.include_router(usuario_router)
app.include_router(progreso_router)
app.include_router(sso_router)

@app.get("/", tags=["Estado"])
async def root():
    return {
        "status": "online",
        "service": "Mayores Actualizaciones API (FastAPI + MongoDB)",
        "version": "2.0.0"
    }

@app.get("/health", tags=["Estado"])
@app.get("/actuator/health", tags=["Estado"])
async def health_check():
    return {"status": "UP"}

# Montar Torre de Control (Panel de Administración SPA)
static_admin_dir = os.path.join(os.path.dirname(__file__), "static", "admin")
os.makedirs(static_admin_dir, exist_ok=True)

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
            if response.status_code == 404:
                index_path = os.path.join(self.directory, "index.html")
                if os.path.exists(index_path):
                    return FileResponse(index_path)
            return response
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                index_path = os.path.join(self.directory, "index.html")
                if os.path.exists(index_path):
                    return FileResponse(index_path)
            raise ex

@app.get("/admin", include_in_schema=False)
async def admin_redirect():
    return RedirectResponse(url="/admin/")

app.mount("/admin", SPAStaticFiles(directory=static_admin_dir, html=True), name="admin")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
