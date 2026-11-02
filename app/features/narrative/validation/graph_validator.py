"""
graph_validator.py
Validación estática de grafos narrativos V2: referencias, hojas, pesos y ciclos.

No toca la base de datos en ``validar_grafo``: recibe el documento y devuelve hallazgos.
``validar_grafos_almacenados`` es el adaptador para revisar las colecciones completas.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from app.features.narrative.constants import (
    COLL_V2_CONVERSATIONS,
    COLL_V2_EVENTOS_ESPECIALES,
    COLL_V2_EVENTS,
)

TIPOS_VALIDOS = ("evento", "conversacion", "evento_especial")

_COLECCION_POR_TIPO = {
    "evento": COLL_V2_EVENTS,
    "conversacion": COLL_V2_CONVERSATIONS,
    "evento_especial": COLL_V2_EVENTOS_ESPECIALES,
}

_DIRECCIONES_VALIDAS = {"lealtad", "traicion"}
_MODOS_BLOQUEO_VALIDOS = {"deshabilitada", "oculta"}


@dataclass(frozen=True)
class Hallazgo:
    codigo: str
    mensaje: str
    nodo_id: Optional[str] = None
    opcion_id: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"codigo": self.codigo, "mensaje": self.mensaje}
        if self.nodo_id is not None:
            data["nodo_id"] = self.nodo_id
        if self.opcion_id is not None:
            data["opcion_id"] = self.opcion_id
        return data


@dataclass
class ResultadoValidacion:
    tipo: str
    grafo_id: Optional[str]
    errores: List[Hallazgo] = field(default_factory=list)
    advertencias: List[Hallazgo] = field(default_factory=list)

    @property
    def valido(self) -> bool:
        return not self.errores

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo,
            "grafo_id": self.grafo_id,
            "valido": self.valido,
            "errores": [h.as_dict() for h in self.errores],
            "advertencias": [h.as_dict() for h in self.advertencias],
        }


def _as_dict(value: Any) -> Dict[str, Any]:
    """Normaliza nodos/opciones que pueden llegar como modelos Pydantic o como dict."""
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(by_alias=True)
    return {}


def _destinos(opt: Dict[str, Any]) -> List[str]:
    destinos: List[str] = []
    if opt.get("siguiente_nodo"):
        destinos.append(opt["siguiente_nodo"])
    for desenlace in opt.get("desenlaces") or []:
        destino = _as_dict(desenlace).get("nodo")
        if destino:
            destinos.append(destino)
    return destinos


def _detectar_ciclo(nodos: Dict[str, Dict[str, Any]], raiz: str) -> Optional[str]:
    """Devuelve el id de un nodo involucrado en un ciclo alcanzable, o None."""
    estado: Dict[str, int] = {}

    def visitar(nodo_id: str) -> Optional[str]:
        estado[nodo_id] = 1
        for opt in nodos[nodo_id].get("opciones") or []:
            for destino in _destinos(_as_dict(opt)):
                if destino not in nodos:
                    continue
                if estado.get(destino) == 1:
                    return destino
                if estado.get(destino, 0) == 0:
                    encontrado = visitar(destino)
                    if encontrado:
                        return encontrado
        estado[nodo_id] = 2
        return None

    return visitar(raiz) if raiz in nodos else None


def _alcanzables(nodos: Dict[str, Dict[str, Any]], raiz: str) -> Set[str]:
    if raiz not in nodos:
        return set()
    visitados: Set[str] = set()
    pendientes = [raiz]
    while pendientes:
        actual = pendientes.pop()
        if actual in visitados or actual not in nodos:
            continue
        visitados.add(actual)
        for opt in nodos[actual].get("opciones") or []:
            pendientes.extend(d for d in _destinos(_as_dict(opt)) if d in nodos)
    return visitados


def validar_grafo(grafo: Any, tipo: str = "evento") -> ResultadoValidacion:
    """Valida la estructura de un evento, conversación o evento especial V2."""
    doc = _as_dict(grafo)
    grafo_id = doc.get("_id") or doc.get("id")
    resultado = ResultadoValidacion(tipo=tipo, grafo_id=grafo_id)

    def error(codigo: str, mensaje: str, nodo_id: Optional[str] = None, opcion_id: Optional[str] = None) -> None:
        resultado.errores.append(Hallazgo(codigo, mensaje, nodo_id, opcion_id))

    def advertencia(codigo: str, mensaje: str, nodo_id: Optional[str] = None, opcion_id: Optional[str] = None) -> None:
        resultado.advertencias.append(Hallazgo(codigo, mensaje, nodo_id, opcion_id))

    if tipo not in TIPOS_VALIDOS:
        error("tipo_invalido", f"Tipo de grafo desconocido: '{tipo}'.")
        return resultado

    if tipo == "evento_especial":
        if not (doc.get("personaje_id") or "").strip():
            error("personaje_id_ausente", "Un evento especial requiere 'personaje_id'.")
        direccion = doc.get("direccion")
        if direccion not in _DIRECCIONES_VALIDAS:
            error("direccion_invalida", f"Dirección inválida: '{direccion}'. Esperado lealtad o traicion.")

    if tipo == "evento" and grafo_id:
        if grafo_id in (doc.get("requisitos_eventos_previos") or []):
            error("requisito_autorreferente", "El evento se exige a sí mismo como requisito previo.")

    nodos_crudos = doc.get("nodos") or {}
    if not isinstance(nodos_crudos, dict) or not nodos_crudos:
        error("nodos_vacios", "El grafo no tiene nodos.")
        return resultado

    nodos: Dict[str, Dict[str, Any]] = {}
    for clave, nodo_crudo in nodos_crudos.items():
        nodo = _as_dict(nodo_crudo)
        nodos[str(clave)] = nodo
        nodo_id = nodo.get("id")
        if not nodo_id:
            error("nodo_sin_id", f"El nodo '{clave}' no declara 'id'.", nodo_id=str(clave))
        elif nodo_id != clave:
            error(
                "id_nodo_inconsistente",
                f"La clave '{clave}' no coincide con el id '{nodo_id}'.",
                nodo_id=str(clave),
            )

    raiz = doc.get("nodo_raiz")
    if not raiz:
        error("nodo_raiz_ausente", "El grafo no declara 'nodo_raiz'.")
    elif raiz not in nodos:
        error("nodo_raiz_inexistente", f"El nodo raíz '{raiz}' no existe.", nodo_id=raiz)

    opciones_vistas: Set[str] = set()

    for clave, nodo in nodos.items():
        es_final = bool(nodo.get("es_final"))
        opciones = [_as_dict(o) for o in (nodo.get("opciones") or [])]

        if es_final and opciones:
            error("nodo_final_con_opciones", "Un nodo final no puede ofrecer opciones.", nodo_id=clave)
        if not es_final and not opciones:
            error("nodo_sin_opciones", "Un nodo no final debe ofrecer al menos una opción.", nodo_id=clave)
        if es_final and not (nodo.get("resultado_texto") or "").strip():
            advertencia("nodo_final_sin_texto", "El nodo final no tiene resultado_texto.", nodo_id=clave)

        for opt in opciones:
            opcion_id = opt.get("id")
            if not opcion_id:
                error("opcion_sin_id", "Una opción no declara 'id'.", nodo_id=clave)
                continue
            if opcion_id in opciones_vistas:
                error("opcion_duplicada", f"La opción '{opcion_id}' está repetida.", nodo_id=clave, opcion_id=opcion_id)
            opciones_vistas.add(opcion_id)

            siguiente = opt.get("siguiente_nodo")
            desenlaces = [_as_dict(d) for d in (opt.get("desenlaces") or [])]

            if not siguiente and not desenlaces:
                error("opcion_sin_destino", "La opción no apunta a ningún nodo.", nodo_id=clave, opcion_id=opcion_id)
            if siguiente and desenlaces:
                advertencia(
                    "opcion_con_destino_y_desenlaces",
                    "La opción define 'siguiente_nodo' y 'desenlaces'; se usará el sorteo ponderado.",
                    nodo_id=clave,
                    opcion_id=opcion_id,
                )
            if siguiente and siguiente not in nodos:
                error(
                    "referencia_inexistente",
                    f"'siguiente_nodo' apunta a '{siguiente}', que no existe.",
                    nodo_id=clave,
                    opcion_id=opcion_id,
                )

            if desenlaces:
                suma_pesos = 0.0
                for desenlace in desenlaces:
                    destino = desenlace.get("nodo")
                    if not destino:
                        error("desenlace_sin_nodo", "Un desenlace no declara 'nodo'.", nodo_id=clave, opcion_id=opcion_id)
                        continue
                    if destino not in nodos:
                        error(
                            "referencia_inexistente",
                            f"El desenlace apunta a '{destino}', que no existe.",
                            nodo_id=clave,
                            opcion_id=opcion_id,
                        )
                    try:
                        peso = float(desenlace.get("peso", 1.0))
                    except (TypeError, ValueError):
                        error("peso_invalido", f"Peso no numérico para '{destino}'.", nodo_id=clave, opcion_id=opcion_id)
                        continue
                    if peso <= 0:
                        error("peso_no_positivo", f"Peso no positivo para '{destino}'.", nodo_id=clave, opcion_id=opcion_id)
                    else:
                        suma_pesos += peso
                if suma_pesos <= 0:
                    error(
                        "desenlaces_sin_peso_positivo",
                        "Ningún desenlace tiene peso positivo; el sorteo no puede resolverse.",
                        nodo_id=clave,
                        opcion_id=opcion_id,
                    )

            modo = opt.get("bloqueo_modo", "deshabilitada")
            if modo not in _MODOS_BLOQUEO_VALIDOS:
                advertencia(
                    "bloqueo_modo_desconocido",
                    f"bloqueo_modo '{modo}' desconocido; se tratará como 'deshabilitada'.",
                    nodo_id=clave,
                    opcion_id=opcion_id,
                )

    if raiz in nodos:
        if bool(nodos[raiz].get("es_final")):
            error("raiz_es_final", "El nodo raíz no puede ser un nodo final.", nodo_id=raiz)

        ciclo = _detectar_ciclo(nodos, raiz)
        if ciclo:
            error("ciclo_detectado", f"El grafo contiene un ciclo alcanzable en '{ciclo}'.", nodo_id=ciclo)

        alcanzables = _alcanzables(nodos, raiz)
        if not any(bool(nodos[n].get("es_final")) for n in alcanzables):
            error("sin_final_alcanzable", "No hay ningún nodo final alcanzable desde la raíz.", nodo_id=raiz)
        for nodo_id in sorted(set(nodos) - alcanzables):
            advertencia("nodo_inalcanzable", "El nodo no es alcanzable desde la raíz.", nodo_id=nodo_id)

    return resultado


async def validar_grafos_almacenados(
    db=None,
    *,
    tipos: Optional[Sequence[str]] = None,
    grafo_id: Optional[str] = None,
    universo_id: Optional[str] = None,
    limite: int = 500,
) -> List[ResultadoValidacion]:
    """Valida los grafos persistidos. ``db`` se inyecta en tests; en runtime usa la global."""
    if db is None:
        from app.core.database import get_database

        db = get_database()

    tipos_a_validar = list(tipos) if tipos else list(TIPOS_VALIDOS)
    invalidos = [t for t in tipos_a_validar if t not in _COLECCION_POR_TIPO]
    if invalidos:
        raise ValueError(f"Tipos de grafo inválidos: {invalidos}")

    resultados: List[ResultadoValidacion] = []
    for tipo in tipos_a_validar:
        query: Dict[str, Any] = {}
        if grafo_id:
            query["_id"] = grafo_id
        if universo_id:
            query["universo_id"] = universo_id
        cursor = db[_COLECCION_POR_TIPO[tipo]].find(query).limit(limite)
        async for documento in cursor:
            resultados.append(validar_grafo(documento, tipo))
    return resultados
