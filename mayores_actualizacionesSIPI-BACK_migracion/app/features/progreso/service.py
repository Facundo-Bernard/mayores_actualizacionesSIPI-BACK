from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.core.database import get_database, get_next_sequence_value
from app.features.progreso.schemas import ProgresoCreateRequest, ProgresoUpdateRequest

async def crear_progreso(req: ProgresoCreateRequest) -> Dict[str, Any]:
    db = get_database()
    user = await db["usuarios"].find_one({"id": req.usuarioId})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {req.usuarioId} no encontrado"
        )

    progreso_id = await get_next_sequence_value("progreso_id")
    
    nuevo_item = {
        "id": progreso_id,
        "cursoId": req.cursoId,
        "usuarioId": req.usuarioId,
        "progreso": req.progreso,
        "completado": req.completado,
        "examenPuntos": req.examenPuntos,
        "updatedAt": datetime.now(timezone.utc)
    }

    # Verificar si ya existe progreso para este curso en el usuario
    progresos = user.get("progresos", [])
    existe = False
    for i, p in enumerate(progresos):
        if p.get("cursoId") == req.cursoId:
            progresos[i] = nuevo_item
            existe = True
            break

    if existe:
        await db["usuarios"].update_one(
            {"id": req.usuarioId},
            {"$set": {"progresos": progresos}}
        )
    else:
        await db["usuarios"].update_one(
            {"id": req.usuarioId},
            {"$push": {"progresos": nuevo_item}}
        )

    return nuevo_item

async def actualizar_progreso(usuario_id: int, curso_id: int, req: ProgresoUpdateRequest) -> Dict[str, Any]:
    db = get_database()
    user = await db["usuarios"].find_one({"id": usuario_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )

    progresos = user.get("progresos", [])
    item_actualizado = None

    for i, p in enumerate(progresos):
        if p.get("cursoId") == curso_id:
            p["progreso"] = req.progreso
            p["completado"] = req.completado
            p["examenPuntos"] = req.examenPuntos
            p["updatedAt"] = datetime.now(timezone.utc)
            item_actualizado = p
            break

    # Si no existía, hacemos Upsert automático para evitar errores 500
    if not item_actualizado:
        progreso_id = await get_next_sequence_value("progreso_id")
        item_actualizado = {
            "id": progreso_id,
            "cursoId": curso_id,
            "usuarioId": usuario_id,
            "progreso": req.progreso,
            "completado": req.completado,
            "examenPuntos": req.examenPuntos,
            "updatedAt": datetime.now(timezone.utc)
        }
        progresos.append(item_actualizado)

    await db["usuarios"].update_one(
        {"id": usuario_id},
        {"$set": {"progresos": progresos}}
    )

    return item_actualizado

async def obtener_progreso_por_usuario(usuario_id: int) -> List[Dict[str, Any]]:
    db = get_database()
    user = await db["usuarios"].find_one({"id": usuario_id})
    if not user:
        return []

    progresos = user.get("progresos", [])
    # Asegurar formato estándar para cada progreso
    result = []
    for p in progresos:
        result.append({
            "id": p.get("id"),
            "progreso": p.get("progreso", 0),
            "completado": p.get("completado", False),
            "examenPuntos": p.get("examenPuntos", 0),
            "cursoId": p.get("cursoId"),
            "usuarioId": usuario_id
        })
    return result
