from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.scripts.init_db import seed_default_admin
from app.features.auth.router import router as auth_router
from app.features.usuario.router import router as usuario_router
from app.features.progreso.router import router as progreso_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AppMain")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Conectar a MongoDB, inicializar índices y sembrar superadmin
    logger.info("Iniciando aplicación Mayores Actualizaciones (FastAPI)...")
    await connect_to_mongo()
    await seed_default_admin()
    logger.info(f"Servidor listo en el puerto {settings.PORT}.")
    yield
    # Shutdown: Cerrar conexiones
    logger.info("Deteniendo aplicación y cerrando conexiones...")
    await close_mongo_connection()

app = FastAPI(
    title="Mayores Actualizaciones API",
    description="Backend en FastAPI + MongoDB para la plataforma educativa de adultos mayores",
    version="2.0.0",
    lifespan=lifespan
)

# Configuración de CORS amplia para desarrollo y producción
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*", # Permite localhost, duckdns, ip local y dominios en produccion
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusión de routers modulares
app.include_router(auth_router)
app.include_router(usuario_router)
app.include_router(progreso_router)

@app.get("/", tags=["Estado"])
async def root():
    return {
        "status": "online",
        "service": "Mayores Actualizaciones API (FastAPI + MongoDB)",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["Estado"])
@app.get("/actuator/health", tags=["Estado"])
async def health_check():
    return {"status": "UP"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
