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
from app.core.security_middleware import AbsoluteSecurityMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.features.auth.router import router as auth_router
from app.features.daily_challenges.router import router as daily_challenges_router
from app.features.daily_challenges.crucigrama_admin.router import router as crucigrama_admin_router
from app.features.user_attempts.router import router as user_attempts_router
from app.features.narrative.game.router import (
    router as narrative_router,
    router_v2 as narrative_v2_router
)
from app.features.narrative.admin.router import router as narrative_admin_router
from app.features.sso.router import router as sso_router
from app.features.economy.router import router as economy_router
from app.scripts.seed_challenges import (
    seed_wordle_challenges,
    seed_sopa_letras_challenges,
)
from app.scripts.seed_sudoku import seed_sudoku_challenges
from app.features.daily_challenges.service import ensure_current_and_next_month_generated

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AppMain")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Conectar a MongoDB, inicializar índices y catálogo esencial de estados de usuario
    logger.info("Iniciando aplicación Mayores Actualizaciones (FastAPI)...")
    await connect_to_mongo()
    import asyncio
    autogen_lock = asyncio.Lock()

    async def _generar_desafios_si_falta():
        # Serializa arranque y ciclo periódico: dos corridas superpuestas multiplican las ráfagas a la RAE.
        async with autogen_lock:
            await ensure_current_and_next_month_generated()

    async def _background_seeds():
        try:
            if settings.SEED_STATIC_CHALLENGES:
                try:
                    await seed_wordle_challenges()
                    await seed_sopa_letras_challenges()
                    await seed_sudoku_challenges()
                except Exception as e_static:
                    logger.warning(f"Aviso durante la siembra estática de desafíos: {e_static}")
            await _generar_desafios_si_falta()
            try:
                from app.scripts.seed_narrative import seed_narrative_game
                await seed_narrative_game()
            except Exception as e_seed:
                logger.warning(f"Aviso durante la siembra de narrativa: {e_seed}")
            if settings.SEED_NARRATIVE_V2:
                try:
                    from app.scripts.seed_narrative_v2_graphs import seed_v2_graphs
                    await seed_v2_graphs()
                except Exception as e_seed_v2:
                    logger.warning(f"Aviso durante la siembra de grafos V2: {e_seed_v2}")
            try:
                from app.features.narrative.admin.challenge_service import sembrar_finalizaciones_default
                await sembrar_finalizaciones_default()
            except Exception as e_fin:
                logger.warning(f"Aviso al sembrar finalizaciones por defecto: {e_fin}")
        except Exception as e:
            logger.warning(f"Aviso durante la siembra inicial en segundo plano: {e}")

        while True:
            try:
                await asyncio.sleep(43200)
                await _generar_desafios_si_falta()
            except Exception as e_loop:
                logger.warning(f"Error en ciclo periódico de desafíos: {e_loop}")

    asyncio.create_task(_background_seeds())

    async def _ledger_reconciler():
        from app.shared.ledger import reconcile_pending_ledger

        while True:
            try:
                await reconcile_pending_ledger()
            except Exception as e_ledger:
                logger.warning(f"Error al reconciliar asientos del ledger: {e_ledger}")
            await asyncio.sleep(300)

    asyncio.create_task(_ledger_reconciler())

    logger.info(f"Servidor listo en el puerto {settings.PORT}.")
    yield
    # Shutdown: Cerrar conexiones limpiamente
    logger.info("Deteniendo aplicación y cerrando conexiones...")
    await close_mongo_connection()

openapi_tags = [
    {"name": "Estado"},
    {"name": "Autenticación"},
    {"name": "Autenticación - SSO"},
    {"name": "Desafíos Diarios"},
    {"name": "Desafíos Diarios - Administración de Crucigramas"},
    {"name": "Partidas e Intentos de Usuarios"},
    {"name": "Economía, Vidas y Mini-Tienda"},
    {"name": "Narrativo - Flujo de Juego"},
    {"name": "Narrativo - Administración"},
    {"name": "Narrativo - CRUD Universos"},
    {"name": "Narrativo - CRUD Personajes"},
    {"name": "Narrativo - CRUD Cartas"},
    {"name": "Narrativo - CRUD Resultados"},
    {"name": "Narrativo - CRUD Eventos"},
    {"name": "Narrativo - CRUD Conversaciones"},
    {"name": "Narrativo - CRUD Finalizaciones"},
    {"name": "Narrativo - CRUD Eventos V2"},
    {"name": "Narrativo - CRUD Conversaciones V2"},
    {"name": "Narrativo - CRUD Eventos Especiales V2"},
    {"name": "Narrativo - Legacy V1 (Deprecado)"},
]

app = FastAPI(
    title="Mayores Actualizaciones API",
    description="Backend en FastAPI + MongoDB para la plataforma educativa de adultos mayores",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=openapi_tags,
    lifespan=lifespan
)

# DIRECTIVA DE SEGURIDAD ABSOLUTA — REGLA SUPREMA INQUEBRANTABLE (Middleware perimetral y fail-closed)
app.add_middleware(AbsoluteSecurityMiddleware)

# Límite de solicitudes por identidad en economía, intentos y narrativo
app.add_middleware(RateLimitMiddleware)

# Configuración de CORS estricta (Solo orígenes autorizados)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Guest-Credential"],
)

# Manejador de excepciones HTTP estándar con sanitización de información
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

# Inclusión de routers esenciales (Auth, Desafíos, Narrativo, Economía, SSO)
app.include_router(auth_router)
app.include_router(daily_challenges_router)
app.include_router(crucigrama_admin_router)
app.include_router(user_attempts_router)
app.include_router(economy_router)
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

# Panel de administración: SPA compilada desde frontend/admin_src con base /admin/.
static_admin_dir = os.path.join(os.path.dirname(__file__), "static", "admin")
os.makedirs(static_admin_dir, exist_ok=True)


class SPAStaticFiles(StaticFiles):
    """Sirve el build del panel y delega las rutas del cliente a index.html."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Un asset faltante es un 404 real; solo las rutas del cliente caen al index.
            if exc.status_code != 404 or os.path.splitext(path)[1]:
                raise
            return await self._index(scope)

    async def _index(self, scope):
        try:
            return await super().get_response("index.html", scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            # Sin build disponible se conserva el comportamiento previo: derivar al Autenticador.
            return RedirectResponse(url=f"{settings.AUTH_SERVICE_URL.rstrip('/')}/")


@app.get("/admin", include_in_schema=False)
async def admin_panel():
    index_path = os.path.join(static_admin_dir, "index.html")
    if not os.path.exists(index_path):
        return RedirectResponse(url=f"{settings.AUTH_SERVICE_URL.rstrip('/')}/")
    return FileResponse(index_path)


app.mount("/admin", SPAStaticFiles(directory=static_admin_dir, html=True), name="admin")

# Montar carpeta de assets estáticos de narrativa (universos, personajes, cartas, eventos, etc.)
static_narrative_dir = os.path.join(os.path.dirname(__file__), "static", "narrative")
os.makedirs(static_narrative_dir, exist_ok=True)
static_personajes_dir = os.path.join(static_narrative_dir, "personajes")
os.makedirs(static_personajes_dir, exist_ok=True)
app.mount("/assets/narrative/characters", StaticFiles(directory=static_personajes_dir), name="narrative_characters_alias")
app.mount("/assets/narrative", StaticFiles(directory=static_narrative_dir), name="narrative_assets")

if __name__ == "__main__":
    import uvicorn
    # app/data guarda la caché RAE que se reescribe durante la generación. Excluirla del
    # watcher evita reinicios si se amplía el filtro de reload (uvicorn solo vigila *.py
    # por defecto). Los estáticos también se excluyen para que el build del admin no
    # provoque detecciones innecesarias.
    app_dir = os.path.dirname(os.path.abspath(__file__))
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=[app_dir],
        reload_excludes=[
            os.path.join(app_dir, "data"),
            os.path.join(app_dir, "static"),
            "*.log",
        ],
    )
