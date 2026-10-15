import re
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from app.core.database import get_database
from app.features.auth.service import format_user_response
from pymongo import ASCENDING, DESCENDING

async def get_usuarios_paginados(
    limit: int = 10,
    skip: int = 0,
    nombre: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    tipo_usuario: Optional[int] = None,
    black: Optional[bool] = None,
    activo: Optional[bool] = None,
    orden: str = "desc"
) -> Dict[str, Any]:
    db = get_database()
    query: Dict[str, Any] = {}

    # Filtro de búsqueda por nombre o email con re.escape para mitigar ReDoS
    if nombre and nombre.strip():
        term = re.escape(nombre.strip())
        query["$or"] = [
            {"name": {"$regex": term, "$options": "i"}},
            {"email": {"$regex": term, "$options": "i"}}
        ]

    # Filtro por rango de fechas (date_start)
    if fecha_desde or fecha_hasta:
        date_query = {}
        if fecha_desde:
            dt_desde = datetime.combine(fecha_desde, time.min)
            date_query["$gte"] = dt_desde
        if fecha_hasta:
            dt_hasta = datetime.combine(fecha_hasta, time.max)
            date_query["$lte"] = dt_hasta
        query["date_start"] = date_query

    # Filtro por tipo de usuario
    if tipo_usuario is not None:
        query["tipo_usuario"] = tipo_usuario

    # Filtro por estado Black
    if black is not None:
        query["black"] = black

    # Filtro por estado Activo
    if activo is not None:
        query["activo"] = activo

    total = await db["usuarios"].count_documents(query)
    
    sort_direction = DESCENDING if orden.lower() == "desc" else ASCENDING
    cursor = db["usuarios"].find(query).sort("id", sort_direction).skip(skip).limit(limit)
    
    docs = await cursor.to_list(length=limit)
    items = [format_user_response(doc) for doc in docs]

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items
    }

async def get_usuario_by_id(user_id: int) -> Dict[str, Any]:
    db = get_database()
    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado"
        )
    return format_user_response(user)

async def toggle_activo(user_id: int) -> Dict[str, Any]:
    db = get_database()
    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado"
        )

    current_state = bool(user.get("activo", True))
    new_state = not current_state

    await db["usuarios"].update_one(
        {"id": user_id},
        {"$set": {"activo": new_state}}
    )

    action_text = "activado" if new_state else "desactivado"
    message = f"Usuario '{user.get('name')}' {action_text} con éxito."

    return {
        "success": True,
        "message": message,
        "activo": new_state
    }

async def toggle_black(user_id: int) -> Dict[str, Any]:
    db = get_database()
    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado"
        )

    current_state = bool(user.get("black", False))
    new_state = not current_state

    await db["usuarios"].update_one(
        {"id": user_id},
        {"$set": {"black": new_state}}
    )

    action_text = "activada" if new_state else "desactivada"
    message = f"Suscripción Black del usuario '{user.get('name')}' {action_text} con éxito."

    return {
        "success": True,
        "message": message,
        "black": new_state
    }
