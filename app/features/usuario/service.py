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
    new_estado_id = 2 if new_state else 3
    new_estado_codigo = "ACTIVO" if new_state else "SUSPENDIDO"

    await db["usuarios"].update_one(
        {"id": user_id},
        {"$set": {
            "activo": new_state,
            "estado_id": new_estado_id,
            "estado_codigo": new_estado_codigo
        }}
    )

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

async def get_estados_usuario(solo_habilitados: bool = False) -> Dict[str, Any]:
    """Obtiene el catálogo de estados de usuario registrados en la base de datos."""
    db = get_database()
    query = {"habilitado": {"$ne": False}} if solo_habilitados else {}
    cursor = db["estados_usuario"].find(query, {"_id": 0}).sort("id", ASCENDING)
    docs = await cursor.to_list(length=100)
    estados = []
    for doc in docs:
        doc.setdefault("habilitado", True)
        doc.setdefault("permite_login", False)
        doc.setdefault("color", "slate")
        estados.append(doc)
    return {
        "success": True,
        "estados": estados
    }

async def cambiar_estado_usuario(user_id: int, estado_id: int) -> Dict[str, Any]:
    """Cambia el estado de una cuenta de usuario a cualquiera de los estados válidos del catálogo."""
    db = get_database()
    user = await db["usuarios"].find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado"
        )

    estado = await db["estados_usuario"].find_one({"id": estado_id})
    if not estado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estado con ID {estado_id} no existe en el catálogo"
        )

    if estado.get("habilitado", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El estado '{estado.get('nombre')}' está inhabilitado en el catálogo y no puede ser asignado"
        )

    estado_codigo = estado.get("codigo", "ACTIVO")
    es_activo = bool(estado.get("permite_login", False) or estado_codigo == "ACTIVO")

    await db["usuarios"].update_one(
        {"id": user_id},
        {"$set": {
            "estado_id": estado_id,
            "estado_codigo": estado_codigo,
            "activo": es_activo
        }}
    )

    return {
        "success": True,
        "message": f"Estado del usuario '{user.get('name')}' actualizado a '{estado.get('nombre')}'.",
        "estado_id": estado_id,
        "estado_codigo": estado_codigo,
        "activo": es_activo
    }

async def crear_estado_usuario(
    nombre: str,
    codigo: Optional[str] = None,
    descripcion: Optional[str] = "",
    color: Optional[str] = "indigo",
    permite_login: bool = False
) -> Dict[str, Any]:
    """Registra un nuevo estado en el catálogo de estados_usuario."""
    db = get_database()
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre del estado no puede estar vacío"
        )

    if codigo and codigo.strip():
        cod = re.sub(r"[^A-Za-z0-9_]+", "_", codigo.strip().upper()).strip("_")
    else:
        cod = re.sub(r"[^A-Za-z0-9_]+", "_", nombre_limpio.upper()).strip("_")

    if not cod:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de estado inválido"
        )

    existente = await db["estados_usuario"].find_one({"codigo": cod})
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un estado con el código '{cod}'"
        )

    # Calcular siguiente ID
    ultimo = await db["estados_usuario"].find().sort("id", DESCENDING).limit(1).to_list(length=1)
    nuevo_id = (ultimo[0]["id"] + 1) if ultimo else 1

    nuevo_doc = {
        "id": nuevo_id,
        "codigo": cod,
        "nombre": nombre_limpio,
        "descripcion": (descripcion or "").strip(),
        "permite_login": bool(permite_login),
        "color": color or "indigo",
        "habilitado": True
    }

    await db["estados_usuario"].insert_one(nuevo_doc)

    return {
        "success": True,
        "message": f"Estado '{nombre_limpio}' creado exitosamente con código '{cod}'.",
        "estado": {k: v for k, v in nuevo_doc.items() if k != "_id"}
    }

async def toggle_habilitado_estado(estado_id: int) -> Dict[str, Any]:
    """Habilita o inhabilita un estado del catálogo."""
    if estado_id in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los estados esenciales del sistema (PENDIENTE_VERIFICACION y ACTIVO) no pueden ser inhabilitados."
        )

    db = get_database()
    estado = await db["estados_usuario"].find_one({"id": estado_id})
    if not estado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estado con ID {estado_id} no encontrado en el catálogo"
        )

    nuevo_habilitado = not estado.get("habilitado", True)
    await db["estados_usuario"].update_one(
        {"id": estado_id},
        {"$set": {"habilitado": nuevo_habilitado}}
    )

    action_text = "habilitado" if nuevo_habilitado else "inhabilitado"
    return {
        "success": True,
        "message": f"Estado '{estado.get('nombre')}' {action_text} en el catálogo.",
        "estado_id": estado_id,
        "habilitado": nuevo_habilitado
    }
