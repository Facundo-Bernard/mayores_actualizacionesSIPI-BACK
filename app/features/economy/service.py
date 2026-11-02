import re
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.features.economy.schemas import (
    EconomyConfigResponse,
    EconomyConfigUpdateRequest,
    UserEconomyResponse,
    ConsumeLifeResponse,
    BuyLivesResponse,
    BuyLivesRequest,
    RefillLivesResponse,
    GuestMigrationResponse,
    UseHintResponse,
    TiendaPaquete,
    EscalaCalificacionTiempo,
    DEFAULT_ESCALAS_TIEMPO,
)
from app.shared.clock import today_str
from app.shared.ledger import get_points_ledger

logger = logging.getLogger("EconomyService")

COLL_CONFIG = "configuracion_economia"
COLL_HINTS = "user_hints"
REFILL_LIVES_COST = 50

DEFAULT_ECONOMY_CONFIG: Dict[str, Any] = {
    "_id": "global_economy",
    "vidas_iniciales": 5,
    "costo_vida_puntos": 50,
    "costo_desbloqueo_dia_puntos": 100,
    "costo_pista_puntos": 20,
    "puntos_por_calificacion": {
        "S": 100,
        "A": 90,
        "B": 75,
        "C": 50,
        "F": 0,
    },
    "vidas_maximas": None,
    "guest_migration_max_points": 1000,
    "escalas_tiempo_por_juego": DEFAULT_ESCALAS_TIEMPO,
    "paquetes_tienda": [
        {"id": "pack_1", "vidas": 1, "puntos": 50, "popular": False, "badge": None, "descuento": None},
        {"id": "pack_3", "vidas": 3, "puntos": 120, "popular": True, "badge": "Popular", "descuento": "Ahorrá 30 pts"},
        {"id": "pack_5", "vidas": 5, "puntos": 180, "popular": False, "badge": "Mejor valor", "descuento": "Ahorrá 70 pts"},
    ],
    "puntos_por_juego": {
        "wordle": 50,
        "sopa_letras": 50,
        "sudoku": 60,
        "crucigrama": 70,
        "narrativo": 80,
    },
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


async def get_economy_config() -> EconomyConfigResponse:
    """
    Obtiene la configuración económica global de la base de datos.
    Si no existe, la siembra automáticamente con valores predeterminados seguros.
    """
    db = get_database()
    doc = await db[COLL_CONFIG].find_one({"_id": "global_economy"})
    if not doc:
        now_str = datetime.now(timezone.utc).isoformat()
        initial = dict(DEFAULT_ECONOMY_CONFIG)
        initial["updated_at"] = now_str
        await db[COLL_CONFIG].update_one(
            {"_id": "global_economy"},
            {"$setOnInsert": initial},
            upsert=True,
        )
        doc = await db[COLL_CONFIG].find_one({"_id": "global_economy"}) or initial

    paquetes = [TiendaPaquete(**p) for p in doc.get("paquetes_tienda", [])]
    raw_escalas = doc.get("escalas_tiempo_por_juego") or DEFAULT_ESCALAS_TIEMPO
    escalas_map: Dict[str, List[EscalaCalificacionTiempo]] = {}
    for gid, items in raw_escalas.items():
        escalas_map[gid] = [EscalaCalificacionTiempo(**item) for item in items]

    return EconomyConfigResponse(
        vidas_iniciales=int(doc.get("vidas_iniciales", 5)),
        costo_vida_puntos=int(doc.get("costo_vida_puntos", 50)),
        costo_desbloqueo_dia_puntos=int(doc.get("costo_desbloqueo_dia_puntos", 100)),
        costo_pista_puntos=int(doc.get("costo_pista_puntos", 20)),
        puntos_por_calificacion=doc.get("puntos_por_calificacion", DEFAULT_ECONOMY_CONFIG["puntos_por_calificacion"]),
        escalas_tiempo_por_juego=escalas_map,
        paquetes_tienda=paquetes,
        puntos_por_juego=doc.get("puntos_por_juego", DEFAULT_ECONOMY_CONFIG["puntos_por_juego"]),
        vidas_maximas=doc.get("vidas_maximas"),
        guest_migration_max_points=int(
            doc.get("guest_migration_max_points", DEFAULT_ECONOMY_CONFIG["guest_migration_max_points"])
        ),
        updated_at=str(doc.get("updated_at", "")),
    )


async def update_economy_config(req: EconomyConfigUpdateRequest) -> EconomyConfigResponse:
    """
    Actualiza la configuración económica desde la Torre de Control (Panel Administrador).
    """
    db = get_database()
    update_fields: Dict[str, Any] = {}

    if req.vidas_iniciales is not None:
        update_fields["vidas_iniciales"] = max(1, req.vidas_iniciales)
    if req.costo_vida_puntos is not None:
        update_fields["costo_vida_puntos"] = max(1, req.costo_vida_puntos)
    if req.costo_desbloqueo_dia_puntos is not None:
        update_fields["costo_desbloqueo_dia_puntos"] = max(0, req.costo_desbloqueo_dia_puntos)
    if req.paquetes_tienda is not None:
        update_fields["paquetes_tienda"] = [p.model_dump() for p in req.paquetes_tienda]
    if req.costo_pista_puntos is not None:
        update_fields["costo_pista_puntos"] = max(0, req.costo_pista_puntos)
    if req.puntos_por_calificacion is not None:
        update_fields["puntos_por_calificacion"] = req.puntos_por_calificacion
    if req.escalas_tiempo_por_juego is not None:
        update_fields["escalas_tiempo_por_juego"] = {
            gid: [item.model_dump() for item in items]
            for gid, items in req.escalas_tiempo_por_juego.items()
        }
    if req.puntos_por_juego is not None:
        update_fields["puntos_por_juego"] = req.puntos_por_juego
    if req.vidas_maximas is not None:
        update_fields["vidas_maximas"] = req.vidas_maximas
    if req.guest_migration_max_points is not None:
        update_fields["guest_migration_max_points"] = max(0, req.guest_migration_max_points)

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db[COLL_CONFIG].update_one(
        {"_id": "global_economy"},
        {"$set": update_fields},
        upsert=True,
    )
    logger.info(f"[ECONOMIA] Configuración actualizada: {list(update_fields.keys())}")
    return await get_economy_config()


async def get_user_economy(user_id: int) -> UserEconomyResponse:
    """
    Obtiene el estado económico (vidas, puntos, racha) del usuario.
    Si el usuario no tiene vidas inicializadas, le otorga las vidas por defecto.
    """
    db = get_database()
    config = await get_economy_config()
    user = await db["usuarios"].find_one({"id": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado",
        )

    # Migración/Aprovisionamiento inicial de vidas si no existía en el documento
    if "vidas" not in user:
        await db["usuarios"].update_one(
            {"id": user_id},
            {
                "$set": {"vidas": config.vidas_iniciales},
                "$setOnInsert": {"puntos": 0},
            },
        )
        user["vidas"] = config.vidas_iniciales

    vidas = int(user.get("vidas", config.vidas_iniciales))
    puntos = int(user.get("puntos", 0))
    racha = int(user.get("racha", 0))

    suscripcion = str(user.get("suscripcion", "basica")).lower()
    dias_desbloqueados = user.get("dias_desbloqueados", [])

    return UserEconomyResponse(
        user_id=user_id,
        vidas=vidas,
        puntos=puntos,
        racha=racha,
        suscripcion=suscripcion,
        dias_desbloqueados=dias_desbloqueados,
        costo_pista_puntos=int(config.costo_pista_puntos or 20),
    )


async def consume_life(
    user_id: int, game_id: Optional[str] = None, motivo: Optional[str] = "error"
) -> ConsumeLifeResponse:
    """
    Resta 1 vida global de forma estrictamente atómica.
    Lanza HTTP 400 si el usuario no tiene vidas disponibles.
    """
    db = get_database()
    config = await get_economy_config()

    # Garantizar que el campo vidas exista
    await db["usuarios"].update_one(
        {"id": user_id, "vidas": {"$exists": False}},
        {"$set": {"vidas": config.vidas_iniciales}},
    )

    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "vidas": {"$gt": 0}},
        {
            "$inc": {"vidas": -1},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        user_actual = await db["usuarios"].find_one({"id": user_id})
        vidas_actuales = user_actual.get("vidas", 0) if user_actual else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tienes vidas restantes. Podés recargar vidas en la mini-tienda usando tus puntos.",
        )

    nuevas_vidas = int(result.get("vidas", 0))
    logger.info(f"[ECONOMIA] Usuario {user_id} consumió 1 vida en {game_id or 'general'}. Restan: {nuevas_vidas}")

    return ConsumeLifeResponse(
        success=True,
        vidas_restantes=nuevas_vidas,
        consumidas=1,
        message="Vida consumida exitosamente.",
    )


async def buy_lives(user_id: int, req: BuyLivesRequest) -> BuyLivesResponse:
    """
    Canjea puntos acumulados por vidas según la tasa del catálogo o paquete elegido.
    Operación atómica fail-safe: decrementa puntos e incrementa vidas en un solo paso.
    """
    config = await get_economy_config()
    db = get_database()

    vidas_a_sumar = 1
    costo_puntos = config.costo_vida_puntos

    # El paquete define vidas y precio; la vía directa req.vidas queda ignorada.
    if req.package_id:
        paquete = next((p for p in config.paquetes_tienda if p.id == req.package_id), None)
        if not paquete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paquete de tienda '{req.package_id}' no encontrado.",
            )
        vidas_a_sumar = paquete.vidas
        costo_puntos = paquete.puntos

    max_vidas = config.vidas_maximas
    if max_vidas is not None:
        update_query: Any = [
            {
                "$set": {
                    "puntos": {"$subtract": ["$puntos", costo_puntos]},
                    "vidas": {
                        "$min": [
                            {"$add": [{"$ifNull": ["$vidas", 0]}, vidas_a_sumar]},
                            max_vidas,
                        ]
                    },
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        ]
    else:
        update_query = {
            "$inc": {"puntos": -costo_puntos, "vidas": vidas_a_sumar},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        }

    # Ejecutar transacción atómica con guarda de puntos suficientes
    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": costo_puntos}},
        update_query,
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        user_actual = await db["usuarios"].find_one({"id": user_id})
        puntos_actuales = user_actual.get("puntos", 0) if user_actual else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Puntos insuficientes. Necesitás {costo_puntos} pts y tenés {puntos_actuales} pts.",
        )

    nuevas_vidas = int(result.get("vidas", 0))
    nuevos_puntos = int(result.get("puntos", 0))

    logger.info(
        f"[ECONOMIA] Canje exitoso para usuario {user_id}: +{vidas_a_sumar} vidas por {costo_puntos} pts. "
        f"Saldo final: {nuevas_vidas} vidas, {nuevos_puntos} pts."
    )

    return BuyLivesResponse(
        success=True,
        vidas=nuevas_vidas,
        puntos=nuevos_puntos,
        compradas=vidas_a_sumar,
        costo=costo_puntos,
        message=f"¡Canje exitoso! Sumaste {vidas_a_sumar} {'vida' if vidas_a_sumar == 1 else 'vidas'}.",
    )


async def refill_lives(user_id: int) -> RefillLivesResponse:
    """
    Recarga de vidas de partida con precio y beneficio fijados por el servidor.

    Las vidas de partida son locales: el backend cobra 50 puntos y el cliente
    reinicia su contador. Cualquier cantidad, costo o vidas enviada por el
    cliente se ignora porque el endpoint no acepta body.
    """
    db = get_database()

    await db["usuarios"].update_one(
        {"id": user_id, "puntos": {"$exists": False}},
        {"$set": {"puntos": 0}},
    )

    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": REFILL_LIVES_COST}},
        {
            "$inc": {"puntos": -REFILL_LIVES_COST},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        user = await db["usuarios"].find_one({"id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {user_id} no encontrado.",
            )
        puntos_actuales = int(user.get("puntos", 0))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Puntos insuficientes. Necesitás {REFILL_LIVES_COST} pts "
                f"y tenés {puntos_actuales} pts."
            ),
        )

    nuevos_puntos = int(result.get("puntos", 0))
    logger.info(
        f"[ECONOMIA] Usuario {user_id} recargó vidas por {REFILL_LIVES_COST} pts. "
        f"Saldo restante: {nuevos_puntos} pts."
    )

    return RefillLivesResponse(
        success=True,
        puntos=nuevos_puntos,
        message=f"Vidas recargadas por {REFILL_LIVES_COST} puntos.",
    )


async def get_points_for_game(game_id: str) -> int:
    """Devuelve la cantidad de puntos configurados en el catálogo para un juego específico."""
    config = await get_economy_config()
    clave = game_id.lower().strip()
    return config.puntos_por_juego.get(clave, 50)


async def get_points_for_grade(grade: str) -> int:
    """Devuelve la cantidad de puntos configurados en el catálogo para una calificación (S, A, B, C, F)."""
    config = await get_economy_config()
    clave = grade.upper().strip() if grade else "C"
    return config.puntos_por_calificacion.get(clave, 50)


async def migrate_guest_points(user_id: int, guest_id: str, puntos_solicitados: int) -> GuestMigrationResponse:
    """
    Migra una única vez los puntos acumulados como invitado a la cuenta autenticada.

    El cliente informa cuántos puntos tenía en localStorage; el servidor aplica el
    tope configurado (``guest_migration_max_points``) y registra el movimiento en
    el ledger para auditoría. La marca ``guest_migration_applied`` en el usuario es
    la guarda atómica que impide reclamar dos veces con la misma cuenta.
    """
    db = get_database()
    config = await get_economy_config()
    tope = max(0, int(config.guest_migration_max_points))
    solicitados = max(0, int(puntos_solicitados))
    aplicado = min(solicitados, tope)

    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado",
        )

    if user.get("guest_migration_applied"):
        return GuestMigrationResponse(
            success=False,
            ya_migrado=True,
            puntos_solicitados=solicitados,
            puntos_migrados=0,
            tope=tope,
            puntos_totales=int(user.get("puntos", 0)),
            message="Esta cuenta ya reclamó puntos de invitado.",
        )

    if solicitados <= 0:
        return GuestMigrationResponse(
            success=False,
            ya_migrado=False,
            puntos_solicitados=0,
            puntos_migrados=0,
            tope=tope,
            puntos_totales=int(user.get("puntos", 0)),
            message="No hay puntos de invitado para migrar.",
        )

    now = datetime.now(timezone.utc)
    resultado = await db["usuarios"].find_one_and_update(
        {"id": user_id, "guest_migration_applied": {"$ne": True}},
        {
            "$inc": {"puntos": aplicado},
            "$set": {
                "guest_migration_applied": True,
                "guest_migration_guest_id": guest_id,
                "guest_migration_at": now,
                "updated_at": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )

    if not resultado:
        actual = await db["usuarios"].find_one({"id": user_id}) or user
        return GuestMigrationResponse(
            success=False,
            ya_migrado=True,
            puntos_solicitados=solicitados,
            puntos_migrados=0,
            tope=tope,
            puntos_totales=int(actual.get("puntos", 0)),
            message="Esta cuenta ya reclamó puntos de invitado.",
        )

    total = int(resultado.get("puntos", 0))
    await get_points_ledger().record_event(
        user_id=user_id,
        motivo="guest_migration",
        puntos=aplicado,
        idempotency_key=f"guest_migration:{user_id}",
        metadata={
            "guest_id": guest_id,
            "game_id": "guest",
            "date": today_str(),
            "difficulty": "standard",
            "solicitado": solicitados,
            "aplicado": aplicado,
            "tope": tope,
        },
        status="applied",
    )
    logger.info(
        f"[ECONOMIA] Usuario {user_id} migró {aplicado} pts de invitado {guest_id} "
        f"(solicitados {solicitados}, tope {tope}). Saldo: {total} pts."
    )

    mensaje = f"Se migraron {aplicado} puntos de invitado."
    if solicitados > aplicado:
        mensaje += f" Se aplicó el tope de {tope} puntos."

    return GuestMigrationResponse(
        success=True,
        ya_migrado=False,
        puntos_solicitados=solicitados,
        puntos_migrados=aplicado,
        tope=tope,
        puntos_totales=total,
        message=mensaje,
    )


async def find_user_by_identifier(identificador: str) -> Dict[str, Any]:
    """Busca un usuario por email (case-insensitive), código PIN o ID numérico."""
    db = get_database()
    ident = identificador.strip()
    if not ident:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe ingresar un email, código de acceso PIN o ID de usuario.",
        )

    conds = [
        {"email": {"$regex": f"^{re.escape(ident)}$", "$options": "i"}},
        {"codigo_acceso": ident},
        {"codigoAcceso": ident},
    ]
    if ident.isdigit():
        conds.append({"id": int(ident)})

    user = await db["usuarios"].find_one({"$or": conds})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún usuario con el identificador '{ident}'.",
        )

    return {
        "id": user["id"],
        "name": user.get("name", "Usuario"),
        "email": user.get("email"),
        "codigoAcceso": user.get("codigo_acceso", user.get("codigoAcceso")),
        "vidas": int(user.get("vidas", 5)),
        "puntos": int(user.get("puntos", 0)),
        "suscripcion": user.get("suscripcion", "basica"),
        "dias_desbloqueados": user.get("dias_desbloqueados", []),
    }


async def adjust_user_economy(
    identificador: str,
    vidas_sumar: Optional[int] = None,
    puntos_sumar: Optional[int] = None,
    vidas_set: Optional[int] = None,
    puntos_set: Optional[int] = None,
    suscripcion_set: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Asigna o ajusta vidas y/o puntos en un único update atómico (administración)."""
    user = await find_user_by_identifier(identificador)
    user_id = user["id"]
    db = get_database()

    set_stage: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    operations: Dict[str, Any] = {}

    if vidas_set is not None:
        set_stage["vidas"] = max(0, int(vidas_set))
        operations["vidas_set"] = int(vidas_set)
    elif vidas_sumar is not None and vidas_sumar != 0:
        set_stage["vidas"] = {
            "$max": [0, {"$add": [{"$ifNull": ["$vidas", 0]}, int(vidas_sumar)]}]
        }
        operations["vidas_sumar"] = int(vidas_sumar)

    if puntos_set is not None:
        set_stage["puntos"] = max(0, int(puntos_set))
        operations["puntos_set"] = int(puntos_set)
    elif puntos_sumar is not None and puntos_sumar != 0:
        set_stage["puntos"] = {
            "$max": [0, {"$add": [{"$ifNull": ["$puntos", 0]}, int(puntos_sumar)]}]
        }
        operations["puntos_sumar"] = int(puntos_sumar)

    if suscripcion_set:
        set_stage["suscripcion"] = suscripcion_set.lower().strip()
        operations["suscripcion_set"] = suscripcion_set.lower().strip()

    if not operations:
        return {
            "success": True,
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "codigoAcceso": user["codigoAcceso"],
            "vidas": user["vidas"],
            "puntos": user["puntos"],
            "message": "Sin cambios solicitados.",
        }

    updated = await db["usuarios"].find_one_and_update(
        {"id": user_id},
        [{"$set": set_stage}],
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} no encontrado.",
        )

    final_vidas = int(updated.get("vidas", 0))
    final_puntos = int(updated.get("puntos", 0))

    try:
        await get_points_ledger().record_event(
            user_id=user_id,
            motivo="admin_adjust",
            puntos=int(puntos_sumar or 0),
            idempotency_key=f"admin_adjust:{uuid.uuid4().hex}",
            metadata={
                "actor": actor_id,
                "operations": operations,
                "saldo_despues": final_puntos,
            },
            status="applied",
        )
    except Exception as e:
        logger.warning(f"No se pudo auditar el ajuste admin de {user_id}: {e}")

    logger.info(
        f"[ECONOMIA ADMIN] Ajuste realizado a usuario {user_id} ({user.get('name')}) "
        f"por actor {actor_id}: {final_vidas} vidas, {final_puntos} pts."
    )

    return {
        "success": True,
        "user_id": updated.get("id"),
        "name": updated.get("name", ""),
        "email": updated.get("email"),
        "codigoAcceso": updated.get("codigo_acceso", updated.get("codigoAcceso")),
        "vidas": final_vidas,
        "puntos": final_puntos,
        "suscripcion": updated.get("suscripcion", "basica"),
        "message": f"¡Listo! {updated.get('name', 'Usuario')} ahora tiene {final_vidas} vidas y {final_puntos} puntos.",
    }


async def unlock_historical_day(
    user_id: int,
    game_id: str,
    date_str: str,
) -> Any:
    """
    Desbloquea un desafío de un día anterior gastando puntos para usuarios Básicos,
    o de forma automática e ilimitada para usuarios Premium.
    """
    db = get_database()
    config = await get_economy_config()
    clean_game = game_id.lower().strip()
    clean_date = date_str.strip()
    unlock_key = f"{clean_game}:{clean_date}"

    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} no encontrado."
        )

    suscripcion = str(user.get("suscripcion", "basica")).lower()
    puntos_actuales = int(user.get("puntos", 0))
    dias_desbloqueados = user.get("dias_desbloqueados", [])

    # Si es Premium, siempre tiene acceso libre
    if suscripcion == "premium":
        return {
            "success": True,
            "unlocked": True,
            "puntos": puntos_actuales,
            "costo": 0,
            "date": clean_date,
            "game_id": clean_game,
            "message": "Acceso concedido por suscripción Premium.",
        }

    # Si ya fue desbloqueado previamente, no se cobra nuevamente
    if unlock_key in dias_desbloqueados:
        return {
            "success": True,
            "unlocked": True,
            "puntos": puntos_actuales,
            "costo": 0,
            "date": clean_date,
            "game_id": clean_game,
            "message": "Este desafío ya fue desbloqueado previamente.",
        }

    costo = config.costo_desbloqueo_dia_puntos

    # Intento de descuento atómico de puntos y adición a dias_desbloqueados
    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": costo}},
        {
            "$inc": {"puntos": -costo},
            "$addToSet": {"dias_desbloqueados": unlock_key},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Puntos insuficientes. Necesitás {costo} pts para desbloquear este día y tenés {puntos_actuales} pts.",
        )

    nuevos_puntos = int(result.get("puntos", 0))
    logger.info(f"[DESBLOQUEO DIA] Usuario {user_id} desbloqueó '{unlock_key}' por {costo} pts. Saldo restante: {nuevos_puntos} pts.")

    return {
        "success": True,
        "unlocked": True,
        "puntos": nuevos_puntos,
        "costo": costo,
        "date": clean_date,
        "game_id": clean_game,
        "message": f"¡Desafío desbloqueado exitosamente por {costo} puntos!",
    }


async def change_user_subscription(usuario_id: int, nueva_suscripcion: str) -> Dict[str, Any]:
    """Actualiza el nivel de suscripción del usuario ('basica' o 'premium')."""
    sub = nueva_suscripcion.lower().strip()
    if sub not in ("basica", "premium"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La suscripción debe ser 'basica' o 'premium'."
        )

    db = get_database()
    updated = await db["usuarios"].find_one_and_update(
        {"id": usuario_id},
        {"$set": {"suscripcion": sub, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {usuario_id} no encontrado."
        )

    return {
        "success": True,
        "user_id": updated["id"],
        "name": updated.get("name", ""),
        "email": updated.get("email"),
        "suscripcion": sub,
        "message": f"Suscripción de {updated.get('name', 'usuario')} actualizada a '{sub}'.",
    }

async def _find_hint_challenge(db: Any, game_id: str, target_date: str, difficulty: str) -> Optional[dict]:
    challenge = await db["daily_challenges"].find_one(
        {"game_id": game_id, "date": target_date, "difficulty": difficulty}
    )
    if challenge:
        return challenge
    # Si el desafío no guarda dificultad, se acepta solo cuando es inequívoco.
    candidates = await db["daily_challenges"].find(
        {"game_id": game_id, "date": target_date}
    ).limit(2).to_list(length=2)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _resolve_hint(config: dict, game: str, req: Any) -> Tuple[Optional[str], Any, str]:
    """Devuelve (texto, valor_revelado, hint_key) sin cobrar nada."""
    pista_texto = None
    valor_revelado = None
    idx = req.hint_index or 0
    hint_key = f"hint:{idx}"

    if game == "wordle":
        hints = config.get("hints") or []
        if hints:
            idx = idx if 0 <= idx < len(hints) else 0
            pista_texto = hints[idx]
            hint_key = f"hint:{idx}"
        elif config.get("solution"):
            pista_texto = f"Empieza con la letra '{config['solution'][0]}'"
            hint_key = "letter:first"

    elif game == "sudoku":
        sol = config.get("solution")
        if (
            sol
            and req.row is not None
            and req.col is not None
            and 0 <= req.row < 9
            and 0 <= req.col < 9
        ):
            valor_revelado = sol[req.row][req.col]
            pista_texto = (
                f"El número en la fila {req.row + 1}, "
                f"columna {req.col + 1} es {valor_revelado}"
            )
            hint_key = f"cell:{req.row}:{req.col}"

    elif game == "sopa_letras":
        hints = config.get("hints") or []
        words = config.get("words") or []
        if hints and 0 <= idx < len(hints):
            pista_texto = hints[idx]
        elif words and 0 <= idx < len(words):
            pista_texto = f"Palabra a buscar: {words[idx]}"
            hint_key = f"word:{idx}"

    elif game == "crucigrama":
        words = config.get("words") or []
        if req.row is not None and req.col is not None:
            hint_key = f"cell:{req.row}:{req.col}"
            for w in words:
                coords = w.get("coords") or []
                word_str = w.get("word", "")
                for i, coord in enumerate(coords):
                    if len(coord) < 2:
                        continue
                    r, cl = coord[0], coord[1]
                    if r == req.row and cl == req.col and i < len(word_str):
                        valor_revelado = word_str[i]
                        pista_texto = (
                            f"La letra en ({req.row + 1}, {req.col + 1}) "
                            f"es '{valor_revelado}'"
                        )
                        break
                if valor_revelado is not None:
                    break
        elif words and 0 <= idx < len(words):
            pista_texto = (
                f"{words[idx].get('direction', 'Horiz.')} "
                f"{words[idx].get('number', '')}: {words[idx].get('clue', '')}"
            )
            hint_key = f"word:{idx}"

    return (pista_texto, valor_revelado, hint_key)


async def _hint_response_from_record(record: dict, user: dict, costo: int, replayed: bool) -> UseHintResponse:
    puntos_actuales = int(user.get("puntos", 0))
    return UseHintResponse(
        success=True,
        puntos_restantes=puntos_actuales,
        puntos_descontados=0,
        vidas_restantes=int(user.get("vidas") or 5),
        vidas_descontadas=0,
        pista=record.get("pista"),
        valor_revelado=record.get("valor_revelado"),
        message=(
            "Esta pista ya fue desbloqueada; no se descontaron puntos."
            if replayed
            else f"Pista desbloqueada exitosamente (-{costo} puntos)."
        ),
    )


async def use_hint(user_id: int, req: Any) -> UseHintResponse:
    """
    Entrega una pista y descuenta puntos solo si hay contenido y no se entregó antes.
    """
    db = get_database()
    config = await get_economy_config()
    costo = int(config.costo_pista_puntos or 20)

    game = req.game_id.lower().strip()
    target_date = req.date or today_str()
    difficulty = (req.difficulty or "").strip().lower() or None
    if not difficulty:
        attempt = await db["user_attempts"].find_one(
            {"user_id": user_id, "game_id": game, "date": target_date}
        )
        difficulty = str((attempt or {}).get("difficulty") or "standard").lower()
    difficulty = difficulty or "standard"

    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {user_id} no encontrado.",
        )

    # 1. Resolver contenido ANTES de cobrar
    challenge = await _find_hint_challenge(db, game, target_date, difficulty)
    pista_texto = None
    valor_revelado = None
    hint_key = f"hint:{req.hint_index or 0}"
    if challenge and "config" in challenge:
        try:
            pista_texto, valor_revelado, hint_key = _resolve_hint(
                challenge["config"] or {}, game, req
            )
        except Exception as e:
            logger.warning(f"[ECONOMIA] No se pudo resolver la pista de {game}: {e}")

    if pista_texto is None and valor_revelado is None:
        return UseHintResponse(
            success=True,
            puntos_restantes=int(user.get("puntos", 0)),
            puntos_descontados=0,
            vidas_restantes=int(user.get("vidas") or 5),
            vidas_descontadas=0,
            pista=None,
            valor_revelado=None,
            message="No hay pista disponible para este desafío; no se descontaron puntos.",
        )

    # 2. Idempotencia por (usuario, juego, fecha, dificultad, pista)
    hint_filter = {
        "user_id": user_id,
        "game_id": game,
        "date": target_date,
        "difficulty": difficulty,
        "hint_key": hint_key,
    }
    existing = await db[COLL_HINTS].find_one(hint_filter)
    if existing:
        return await _hint_response_from_record(existing, user, costo, replayed=True)

    now = datetime.now(timezone.utc)
    record = {
        **hint_filter,
        "pista": pista_texto,
        "valor_revelado": valor_revelado,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db[COLL_HINTS].insert_one(record)
    except DuplicateKeyError:
        existing = await db[COLL_HINTS].find_one(hint_filter)
        if existing:
            return await _hint_response_from_record(existing, user, costo, replayed=True)
        raise

    # 3. Descuento atómico con guarda de saldo
    result = await db["usuarios"].find_one_and_update(
        {"id": user_id, "puntos": {"$gte": costo}},
        {
            "$inc": {"puntos": -costo},
            "$set": {"updated_at": now},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        await db[COLL_HINTS].delete_one({"_id": record["_id"]})
        user_actual = await db["usuarios"].find_one({"id": user_id})
        puntos_actuales = int(user_actual.get("puntos", 0)) if user_actual else 0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Puntos insuficientes para pedir una pista. Cuesta {costo} pts "
                f"y tenés {puntos_actuales} pts."
            ),
        )

    nuevos_puntos = int(result.get("puntos", 0))
    await db[COLL_HINTS].update_one(
        {"_id": record["_id"]},
        {
            "$set": {
                "status": "applied",
                "puntos_descontados": costo,
                "saldo_despues": nuevos_puntos,
                "updated_at": now,
            }
        },
    )
    logger.info(
        f"[ECONOMIA] Usuario {user_id} consumió {costo} pts por pista en "
        f"{game}/{difficulty}/{target_date}. Restan: {nuevos_puntos} pts"
    )

    return UseHintResponse(
        success=True,
        puntos_restantes=nuevos_puntos,
        puntos_descontados=costo,
        vidas_restantes=int(result.get("vidas") or 5),
        vidas_descontadas=0,
        pista=pista_texto,
        valor_revelado=valor_revelado,
        message=f"Pista desbloqueada exitosamente (-{costo} puntos)."
    )
