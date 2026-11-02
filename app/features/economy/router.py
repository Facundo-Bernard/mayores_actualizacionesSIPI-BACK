from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.core.dependencies import get_current_user, get_current_admin
from app.features.economy.schemas import (
    EconomyConfigResponse,
    EconomyConfigUpdateRequest,
    UserEconomyResponse,
    ConsumeLifeRequest,
    ConsumeLifeResponse,
    BuyLivesRequest,
    BuyLivesResponse,
    RefillLivesResponse,
    SearchUserEconomyResponse,
    AdjustUserEconomyRequest,
    AdjustUserEconomyResponse,
    UnlockDayRequest,
    UnlockDayResponse,
    CambiarSuscripcionRequest,
    UseHintRequest,
    UseHintResponse,
    GuestMigrationRequest,
    GuestMigrationResponse,
)
from app.features.economy.service import (
    get_economy_config,
    update_economy_config,
    get_user_economy,
    consume_life,
    buy_lives,
    refill_lives,
    find_user_by_identifier,
    adjust_user_economy,
    unlock_historical_day,
    change_user_subscription,
    use_hint,
    migrate_guest_points,
)

router = APIRouter(tags=["Economía, Vidas y Mini-Tienda"])


# ==============================================================================
# Endpoints de Jugador y Consulta Pública
# ==============================================================================

@router.get(
    "/api/economy/config",
    response_model=EconomyConfigResponse,
    summary="Obtener catálogo de precios de la mini-tienda y puntos por juego (Público)",
)
async def endpoint_get_economy_config():
    """Retorna la configuración económica pública para que el frontend dibuje la tienda y recompensas."""
    return await get_economy_config()


@router.get(
    "/api/economy/me",
    response_model=UserEconomyResponse,
    summary="Obtener saldo de vidas, puntos y racha del usuario autenticado",
)
async def endpoint_get_user_economy(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = int(current_user["id"])
    return await get_user_economy(user_id)


@router.post(
    "/api/economy/consume-life",
    response_model=ConsumeLifeResponse,
    summary="Consumir 1 vida global (Al cometer un error o reiniciar desafío)",
)
async def endpoint_consume_life(
    req: ConsumeLifeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = int(current_user["id"])
    return await consume_life(user_id=user_id, game_id=req.game_id, motivo=req.motivo)


@router.post(
    "/api/economy/buy-lives",
    response_model=BuyLivesResponse,
    summary="Canjear puntos por vidas en la mini-tienda",
)
async def endpoint_buy_lives(
    req: BuyLivesRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = int(current_user["id"])
    return await buy_lives(user_id=user_id, req=req)


@router.post(
    "/api/economy/refill-lives",
    response_model=RefillLivesResponse,
    summary="Recargar las vidas de la partida actual a cambio de puntos (precio fijo del servidor)",
)
async def endpoint_refill_lives(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = int(current_user["id"])
    return await refill_lives(user_id=user_id)


@router.post(
    "/api/economy/unlock-day",
    response_model=UnlockDayResponse,
    summary="Desbloquear un día histórico con puntos o acceso Premium",
)
async def endpoint_unlock_day(
    req: UnlockDayRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = int(current_user["id"])
    return await unlock_historical_day(user_id=user_id, game_id=req.game_id, date_str=req.date)


# ==============================================================================
@router.post(
    "/api/economy/use-hint",
    response_model=UseHintResponse,
    summary="Solicitar una pista en un juego a cambio de 1 vida (Básica y Premium)",
)
async def endpoint_use_hint(
    req: UseHintRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = int(current_user["id"])
    return await use_hint(user_id=user_id, req=req)


@router.post(
    "/api/economy/guest-migration",
    response_model=GuestMigrationResponse,
    summary="Migrar por única vez los puntos acumulados como invitado a la cuenta autenticada",
)
async def endpoint_guest_migration(
    req: GuestMigrationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = int(current_user["id"])
    return await migrate_guest_points(
        user_id=user_id, guest_id=req.guest_id, puntos_solicitados=req.puntos
    )


# Endpoints de Administración (Torre de Control)
# ==============================================================================

@router.get(
    "/api/admin/economy/config",
    response_model=EconomyConfigResponse,
    summary="Consultar catálogo de economía y vidas para el panel administrador (Solo Admin)",
)
@router.get(
    "/api/economy/admin/config",
    response_model=EconomyConfigResponse,
    include_in_schema=False,
)
async def endpoint_admin_get_economy_config(admin: Dict[str, Any] = Depends(get_current_admin)):
    return await get_economy_config()


@router.put(
    "/api/admin/economy/config",
    response_model=EconomyConfigResponse,
    summary="Actualizar valores iniciales, costos de vidas y puntos por juego (Solo Admin)",
)
@router.put(
    "/api/economy/admin/config",
    response_model=EconomyConfigResponse,
    include_in_schema=False,
)
async def endpoint_admin_update_economy_config(
    req: EconomyConfigUpdateRequest,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    return await update_economy_config(req)


@router.get(
    "/api/admin/economy/user/search",
    response_model=SearchUserEconomyResponse,
    summary="Buscar saldo de vidas y puntos de un usuario por email o PIN (Solo Admin)",
)
async def endpoint_admin_search_user_economy(
    identificador: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    return await find_user_by_identifier(identificador)


@router.post(
    "/api/admin/economy/user/adjust",
    response_model=AdjustUserEconomyResponse,
    summary="Asignar o ajustar vidas y puntos a un usuario (Solo Admin / Testeo)",
)
async def endpoint_admin_adjust_user_economy(
    req: AdjustUserEconomyRequest,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    return await adjust_user_economy(
        identificador=req.identificador,
        vidas_sumar=req.vidas_sumar,
        puntos_sumar=req.puntos_sumar,
        vidas_set=req.vidas_set,
        puntos_set=req.puntos_set,
        suscripcion_set=req.suscripcion_set,
        actor_id=admin.get("id"),
    )


@router.put(
    "/api/admin/usuario/{usuario_id}/suscripcion",
    summary="Cambiar la suscripción del usuario entre 'basica' y 'premium' (Solo Admin)",
)
async def endpoint_admin_change_subscription(
    usuario_id: int,
    req: CambiarSuscripcionRequest,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    return await change_user_subscription(usuario_id=usuario_id, nueva_suscripcion=req.suscripcion)
