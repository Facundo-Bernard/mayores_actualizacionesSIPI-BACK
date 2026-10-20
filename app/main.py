import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import logging

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.scripts.init_db import seed_default_admin, seed_estados_usuario
from app.scripts.seed_challenges import seed_wordle_challenges, seed_sopa_letras_challenges
from app.scripts.seed_sudoku import seed_sudoku_challenges
from app.features.daily_challenges.service import ensure_current_and_next_month_generated
from app.features.auth.router import router as auth_router
from app.features.usuario.router import router as usuario_router
from app.features.progreso.router import router as progreso_router
from app.features.daily_challenges.router import router as daily_challenges_router
from app.features.user_attempts.router import router as user_attempts_router
from app.features.narrative.game.router import (
    router as narrative_router,
    router_v2 as narrative_v2_router
)
from app.features.narrative.admin.router import router as narrative_admin_router
from app.features.sso import router as sso_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AppMain")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Conectar a MongoDB, inicializar índices y sembrar datos
    logger.info("Iniciando aplicación Mayores Actualizaciones (FastAPI)...")
    await connect_to_mongo()
    await seed_estados_usuario()
    await seed_default_admin()
    await seed_wordle_challenges()
    await seed_sopa_letras_challenges()
    await seed_sudoku_challenges()
    await ensure_current_and_next_month_generated()

    try:
        from app.features.narrative.admin.challenge_service import sembrar_finalizaciones_default
        await sembrar_finalizaciones_default()
    except Exception as e:
        logger.warning(f"Aviso al sembrar finalizaciones por defecto: {e}")

    import asyncio
    async def _auto_check_loop():
        while True:
            try:
                await asyncio.sleep(43200)  # Chequear cada 12 horas
                await ensure_current_and_next_month_generated()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error en auto_check_loop de desafíos: {e}")
                await asyncio.sleep(3600)

    checker_task = asyncio.create_task(_auto_check_loop())
    logger.info(f"Servidor listo en el puerto {settings.PORT}.")
    yield
    # Shutdown: Cancelar tareas y cerrar conexiones
    checker_task.cancel()
    logger.info("Deteniendo aplicación y cerrando conexiones...")
    await close_mongo_connection()

app = FastAPI(
    title="Mayores Actualizaciones API",
    description="Backend en FastAPI + MongoDB para la plataforma educativa de adultos mayores",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configuración de CORS amplia para desarrollo y producción
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
    settings.FRONTEND_URL.rstrip("/"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

# Inclusión de routers modulares
app.include_router(auth_router)
app.include_router(usuario_router)
app.include_router(progreso_router)
app.include_router(daily_challenges_router)
app.include_router(user_attempts_router)
app.include_router(narrative_router)
app.include_router(narrative_v2_router)
app.include_router(narrative_admin_router)
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

from starlette.exceptions import HTTPException as StarletteHTTPException

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

static_narrative_dir = os.path.join(os.path.dirname(__file__), "static", "narrative")
os.makedirs(static_narrative_dir, exist_ok=True)
# Alias de retrocompatibilidad para URLs legacy que apuntaban a 'characters'
static_personajes_dir = os.path.join(static_narrative_dir, "personajes")
os.makedirs(static_personajes_dir, exist_ok=True)
app.mount("/assets/narrative/characters", StaticFiles(directory=static_personajes_dir), name="narrative_characters_alias")

app.mount("/assets/narrative", StaticFiles(directory=static_narrative_dir), name="narrative_assets")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
