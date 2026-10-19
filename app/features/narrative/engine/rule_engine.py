import logging
from typing import List, Dict, Any, Optional

from app.features.narrative.enums import (
    DisparadorEnum,
    OperadorEnum,
    TipoCondicionEnum,
    TipoAccionEnum,
    TipoCalculoEnum
)
from app.features.narrative.schemas.rules_schemas import CondicionSchema, AccionSchema, EfectoSchema

logger = logging.getLogger(__name__)

def evaluar_condicion(condicion: Any, run_data: Dict[str, Any]) -> bool:
    """
    Evalúa una condición individual contra el estado vivo de la partida.
    Acepta tanto una instancia de CondicionSchema como un dict de MongoDB.
    """
    if isinstance(condicion, dict):
        condicion = CondicionSchema(**condicion)

    tipo = condicion.tipo

    # 1. Comparación de Recurso Numérico (ej: "oro" >= 50)
    if tipo == TipoCondicionEnum.COMPARAR_RECURSO:
        clave = condicion.clave
        if not clave:
            return False
        recursos = run_data.get("recursos", {})
        valor_actual = float(recursos.get(clave, 0))
        valor_objetivo = float(condicion.valor or 0)
        return _comparar_valores(valor_actual, condicion.operador, valor_objetivo)

    # 2. Posesión de Personaje en la Corte Activa
    elif tipo == TipoCondicionEnum.TIENE_PERSONAJE:
        corte = list(run_data.get("afinidad", {}).keys()) or run_data.get("corte_activa", [])
        return condicion.personaje_id in corte

    # 3. Nivel de Afinidad con Personaje
    elif tipo == TipoCondicionEnum.AFINIDAD_PERSONAJE:
        personaje_id = condicion.personaje_id
        if not personaje_id:
            return False
        afinidades = run_data.get("afinidad", {})
        afinidad_actual = float(afinidades.get(personaje_id, 50))
        valor_objetivo = float(condicion.valor or 0)
        return _comparar_valores(afinidad_actual, condicion.operador, valor_objetivo)

    # 4. Posesión de un Tag Activo (de cartas o perks)
    elif tipo == TipoCondicionEnum.TIENE_TAG:
        tags = run_data.get("tags_activos", [])
        return condicion.tag in tags

    # 5. Posesión de Carta en Mano / Inventario
    elif tipo == TipoCondicionEnum.TIENE_CARTA:
        cartas = run_data.get("cartas_en_mano", [])
        return condicion.carta_id in cartas

    return False

def evaluar_condiciones(condiciones: List[Any], run_data: Dict[str, Any]) -> bool:
    """
    Evalúa una lista de condiciones bajo operador lógico AND.
    Si la lista está vacía, se considera True.
    """
    if not condiciones:
        return True
    return all(evaluar_condicion(c, run_data) for c in condiciones)

def _comparar_valores(actual: float, operador: Optional[OperadorEnum], objetivo: float) -> bool:
    """
    Compara dos valores flotantes utilizando el operador relacional provisto.
    """
    if operador == OperadorEnum.MAYOR_IGUAL:
        return actual >= objetivo
    elif operador == OperadorEnum.MENOR_IGUAL:
        return actual <= objetivo
    elif operador == OperadorEnum.MAYOR:
        return actual > objetivo
    elif operador == OperadorEnum.MENOR:
        return actual < objetivo
    elif operador == OperadorEnum.IGUAL:
        return actual == objetivo
    elif operador == OperadorEnum.DISTINTO:
        return actual != objetivo
    return False

def ejecutar_accion(
    accion: Any,
    run_data: Dict[str, Any],
    recursos_definicion: Optional[Dict[str, Dict[str, Any]]] = None
) -> None:
    """
    Modifica el estado en memoria de run_data según el tipo de acción.
    Acepta tanto AccionSchema como dict de MongoDB.
    """
    if isinstance(accion, dict):
        accion = AccionSchema(**accion)

    tipo = accion.tipo

    # 1. Modificar Recurso
    if tipo == TipoAccionEnum.MODIFICAR_RECURSO:
        clave = accion.clave
        if not clave:
            return
        recursos = run_data.setdefault("recursos", {})
        valor_actual = float(recursos.get(clave, 0))

        if accion.tipo_calculo == TipoCalculoEnum.PORCENTUAL:
            delta = valor_actual * (float(accion.valor or 0) / 100.0)
        else:
            delta = float(accion.valor or 0)

        nuevo_valor = round(valor_actual + delta)

        # Clamping de límites min / max según el universo
        if recursos_definicion and clave in recursos_definicion:
            limite_min = recursos_definicion[clave].get("min", 0)
            limite_max = recursos_definicion[clave].get("max", 100)
            nuevo_valor = max(limite_min, min(limite_max, nuevo_valor))

        recursos[clave] = int(nuevo_valor)

    # 2. Modificar Afinidad con Personaje
    elif tipo == TipoAccionEnum.MODIFICAR_AFINIDAD:
        personaje_id = accion.personaje_id
        if not personaje_id:
            return
        afinidades = run_data.setdefault("afinidad", {})
        actual = int(afinidades.get(personaje_id, 50))
        delta = int(accion.valor or 0)
        afinidades[personaje_id] = max(0, min(100, actual + delta))

    # 3. Otorgar Tag Pasivo
    elif tipo == TipoAccionEnum.OTORGAR_TAG:
        tag = accion.tag
        if tag:
            tags = run_data.setdefault("tags_activos", [])
            if tag not in tags:
                tags.append(tag)

def despachar_efectos(
    disparador: DisparadorEnum,
    run_data: Dict[str, Any],
    efectos: List[Any],
    recursos_definicion: Optional[Dict[str, Dict[str, Any]]] = None
) -> None:
    """
    Filtra los efectos por el disparador solicitado, evalúa sus condiciones
    y ejecuta las acciones correspondientes mutando run_data.
    """
    for efecto in efectos:
        if isinstance(efecto, dict):
            efecto = EfectoSchema(**efecto)
        if efecto.disparador == disparador:
            if evaluar_condiciones(efecto.condiciones, run_data):
                ejecutar_accion(efecto.accion, run_data, recursos_definicion)
