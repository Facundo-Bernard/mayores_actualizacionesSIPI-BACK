import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import HTTPException
from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_ACTIONS,
    COLL_FREQUENCIES,
    COLL_CARDS,
    COLL_CHARACTERS,
)
from app.features.narrative.schemas.rules_schemas import (
    AccionCatalogoCreateRequest,
    AccionCatalogoUpdateRequest,
    AccionCatalogoResponse,
    FrecuenciasUniversoDocument,
    FrecuenciasUniversoUpdateRequest,
    ItemFrecuenciaSchema,
    PrimitivaOperacionEnum,
)

logger = logging.getLogger(__name__)

# Catálogo canónico de primitivas soportadas por el motor
CATALOGO_PRIMITIVAS: List[Dict[str, Any]] = [
    {
        "primitiva": PrimitivaOperacionEnum.MODIFICAR_RECURSO.value,
        "nombre": "Modificar recurso",
        "descripcion": "Aumenta o disminuye el valor de un recurso numérico del universo (positivo suma, negativo resta).",
        "parametros_requeridos": ["clave", "valor", "tipo_calculo"],
        "soporta_calculo": ["fijo", "porcentual"],
        "permitido_en": ["carta", "personaje"],
    },
    {
        "primitiva": PrimitivaOperacionEnum.MODIFICAR_AFINIDAD.value,
        "nombre": "Modificar afinidad",
        "descripcion": "Modifica la afinidad (0 a 100) con el personaje portador o uno específico.",
        "parametros_requeridos": ["destino", "valor"],
        "opciones_destino": ["portador", "personaje"],
        "permitido_en": ["carta", "personaje"],
    },
    {
        "primitiva": PrimitivaOperacionEnum.OTORGAR_TAG.value,
        "nombre": "Otorgar tag pasivo",
        "descripcion": "Otorga un tag pasivo permanente al estado vivo de la partida.",
        "parametros_requeridos": ["tag"],
        "permitido_en": ["carta", "personaje"],
    },
    {
        "primitiva": PrimitivaOperacionEnum.REMOVER_TAG.value,
        "nombre": "Remover tag",
        "descripcion": "Remueve un tag activo del estado de la partida.",
        "parametros_requeridos": ["tag"],
        "permitido_en": ["carta", "personaje"],
    },
    {
        "primitiva": PrimitivaOperacionEnum.AMORTIGUAR_DANIO.value,
        "nombre": "Amortiguar daño de recurso",
        "descripcion": "Registra un modificador pasivo que reduce porcentualmente las pérdidas de un recurso.",
        "parametros_requeridos": ["clave", "valor"],
        "permitido_en": ["carta", "personaje"],
    },
]

# Eventos soportados por el ciclo de vida del motor
EVENTOS_MOTOR: List[Dict[str, Any]] = [
    {
        "evento_motor": "al_obtener",
        "nombre": "Al obtener",
        "descripcion": "Se ejecuta de inmediato cuando la carta entra en mano o el personaje es reclutado.",
        "soporta_intervalo": False,
    },
    {
        "evento_motor": "inicio_mes",
        "nombre": "Inicio de cada mes",
        "descripcion": "Se evalúa al inicio de cada mes. Puede configurarse periodicidad (ej. cada 1, 2 meses) relativa a la adquisición.",
        "soporta_intervalo": True,
        "opciones_conteo": ["adquisicion", "inicio_partida"],
    },
]


def _frecuencias_default(universo_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "al_obtener",
            "nombre": "Al obtener",
            "evento_motor": "al_obtener",
            "cada": 1,
            "desfase": 0,
            "conteo_desde": "adquisicion",
            "activo": True,
        },
        {
            "id": "mensual",
            "nombre": "Cada mes",
            "evento_motor": "inicio_mes",
            "cada": 1,
            "desfase": 0,
            "conteo_desde": "inicio_partida",
            "activo": True,
        },
        {
            "id": "cada_2_meses",
            "nombre": "Cada 2 meses desde adquisición",
            "evento_motor": "inicio_mes",
            "cada": 2,
            "desfase": 0,
            "conteo_desde": "adquisicion",
            "activo": True,
        },
    ]


async def crear_accion(payload: AccionCatalogoCreateRequest) -> AccionCatalogoResponse:
    db = get_database()
    col = db[COLL_ACTIONS]

    # Verificar existencia previa
    existente = await col.find_one({"_id": payload.id, "universo_id": payload.universo_id})
    if existente:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una acción con ID '{payload.id}' en el universo '{payload.universo_id}'.",
        )

    doc = {
        "_id": payload.id,
        "universo_id": payload.universo_id,
        "nombre": payload.nombre,
        "descripcion": payload.descripcion or "",
        "primitiva": payload.primitiva.value,
        "permitido_en": payload.permitido_en,
        "activo": payload.activo,
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await col.insert_one(doc)
    return AccionCatalogoResponse(**doc)


async def listar_acciones(universo_id: Optional[str] = None) -> List[AccionCatalogoResponse]:
    db = get_database()
    col = db[COLL_ACTIONS]
    filtro: Dict[str, Any] = {}
    if universo_id:
        filtro["universo_id"] = universo_id
    docs = await col.find(filtro).sort("nombre", 1).to_list(None)
    return [AccionCatalogoResponse(**d) for d in docs]


async def obtener_accion_por_id(accion_id: str, universo_id: Optional[str] = None) -> AccionCatalogoResponse:
    db = get_database()
    col = db[COLL_ACTIONS]
    filtro: Dict[str, Any] = {"_id": accion_id}
    if universo_id:
        filtro["universo_id"] = universo_id
    doc = await col.find_one(filtro)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Acción '{accion_id}' no encontrada.")
    return AccionCatalogoResponse(**doc)


async def actualizar_accion(
    accion_id: str,
    payload: AccionCatalogoUpdateRequest,
    universo_id: Optional[str] = None,
) -> AccionCatalogoResponse:
    db = get_database()
    col = db[COLL_ACTIONS]
    filtro: Dict[str, Any] = {"_id": accion_id}
    if universo_id:
        filtro["universo_id"] = universo_id

    doc = await col.find_one(filtro)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Acción '{accion_id}' no encontrada.")

    # Control de concurrencia optimista (OCC)
    if payload.expected_version is not None and doc.get("version", 1) != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflicto de concurrencia: la versión esperada ({payload.expected_version}) no coincide con la actual ({doc.get('version', 1)}).",
        )

    updates: Dict[str, Any] = {
        "version": doc.get("version", 1) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.nombre is not None:
        updates["nombre"] = payload.nombre
    if payload.descripcion is not None:
        updates["descripcion"] = payload.descripcion
    if payload.primitiva is not None:
        updates["primitiva"] = payload.primitiva.value
    if payload.permitido_en is not None:
        updates["permitido_en"] = payload.permitido_en
    if payload.activo is not None:
        updates["activo"] = payload.activo

    await col.update_one(filtro, {"$set": updates})
    doc.update(updates)
    return AccionCatalogoResponse(**doc)


async def obtener_usos_accion(accion_id: str) -> Dict[str, Any]:
    db = get_database()
    col_cartas = db[COLL_CARDS]
    col_personajes = db[COLL_CHARACTERS]

    filtro = {
        "$or": [
            {"efectos.acciones.accion_id": accion_id},
            {"efectos.accion.tipo": accion_id},
        ]
    }
    cartas = await col_cartas.find(filtro, {"_id": 1, "nombre": 1, "universo_id": 1}).to_list(None)
    personajes = await col_personajes.find(filtro, {"_id": 1, "nombre": 1, "universo_id": 1}).to_list(None)

    return {
        "accion_id": accion_id,
        "total_usos": len(cartas) + len(personajes),
        "cartas": [{"id": str(c["_id"]), "nombre": c.get("nombre", str(c["_id"])), "universo_id": c.get("universo_id")} for c in cartas],
        "personajes": [{"id": str(p["_id"]), "nombre": p.get("nombre", str(p["_id"])), "universo_id": p.get("universo_id")} for p in personajes],
    }


async def eliminar_accion(accion_id: str, universo_id: Optional[str] = None) -> Dict[str, Any]:
    db = get_database()
    col = db[COLL_ACTIONS]
    filtro: Dict[str, Any] = {"_id": accion_id}
    if universo_id:
        filtro["universo_id"] = universo_id

    doc = await col.find_one(filtro)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Acción '{accion_id}' no encontrada.")

    # Validar integridad referencial: bloqueo si está en uso
    usos = await obtener_usos_accion(accion_id)
    if usos["total_usos"] > 0:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar la acción '{accion_id}' porque está referenciada en {usos['total_usos']} entidad(es). Desactívela en su lugar.",
        )

    await col.delete_one(filtro)
    return {"message": f"Acción '{accion_id}' eliminada exitosamente.", "id": accion_id}


async def obtener_frecuencias_universo(universo_id: str) -> FrecuenciasUniversoDocument:
    db = get_database()
    col = db[COLL_FREQUENCIES]
    doc_id = f"frecuencias_{universo_id}"
    doc = await col.find_one({"_id": doc_id})

    if not doc:
        # Inicializar frecuencias predeterminadas para este universo
        items_def = _frecuencias_default(universo_id)
        doc = {
            "_id": doc_id,
            "universo_id": universo_id,
            "version": 1,
            "items": items_def,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await col.insert_one(doc)

    return FrecuenciasUniversoDocument(**doc)


async def actualizar_frecuencias_universo(
    universo_id: str,
    payload: FrecuenciasUniversoUpdateRequest,
) -> FrecuenciasUniversoDocument:
    db = get_database()
    col = db[COLL_FREQUENCIES]
    doc_id = f"frecuencias_{universo_id}"
    doc = await col.find_one({"_id": doc_id})

    if not doc:
        doc = {
            "_id": doc_id,
            "universo_id": universo_id,
            "version": 0,
            "items": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # OCC
    if payload.expected_version is not None and doc.get("version", 1) != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflicto de concurrencia: versión esperada {payload.expected_version} difiere de la actual {doc.get('version', 1)}.",
        )

    # Validar unicidad de IDs en el array
    vistos = set()
    items_dict = []
    for item in payload.items:
        if item.id in vistos:
            raise HTTPException(status_code=422, detail=f"ID de frecuencia duplicado en el catálogo: '{item.id}'.")
        vistos.add(item.id)
        items_dict.append(item.model_dump())

    updates = {
        "version": doc.get("version", 1) + 1,
        "items": items_dict,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await col.update_one({"_id": doc_id}, {"$set": updates}, upsert=True)
    doc.update(updates)
    return FrecuenciasUniversoDocument(**doc)


async def obtener_usos_frecuencia(frecuencia_id: str, universo_id: Optional[str] = None) -> Dict[str, Any]:
    db = get_database()
    col_cartas = db[COLL_CARDS]
    col_personajes = db[COLL_CHARACTERS]

    filtro: Dict[str, Any] = {
        "$or": [
            {"efectos.frecuencia_id": frecuencia_id},
            {"efectos.disparador": frecuencia_id},
        ]
    }
    if universo_id:
        filtro["universo_id"] = universo_id

    cartas = await col_cartas.find(filtro, {"_id": 1, "nombre": 1, "universo_id": 1}).to_list(None)
    personajes = await col_personajes.find(filtro, {"_id": 1, "nombre": 1, "universo_id": 1}).to_list(None)

    return {
        "frecuencia_id": frecuencia_id,
        "total_usos": len(cartas) + len(personajes),
        "cartas": [{"id": str(c["_id"]), "nombre": c.get("nombre", str(c["_id"])), "universo_id": c.get("universo_id")} for c in cartas],
        "personajes": [{"id": str(p["_id"]), "nombre": p.get("nombre", str(p["_id"])), "universo_id": p.get("universo_id")} for p in personajes],
    }
