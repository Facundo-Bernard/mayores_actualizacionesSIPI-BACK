import random
import logging
from typing import List, Dict, Any, Optional

from app.features.narrative.engine.rule_engine import evaluar_condicion, evaluar_condiciones
from app.features.narrative.schemas.game_schemas import (
    ProbabilidadDesenlaceCalculada,
    OpcionEventoCalculadaResponse
)

logger = logging.getLogger(__name__)

def seleccionar_evento_mes(
    eventos_candidatos: List[Dict[str, Any]],
    run_data: Dict[str, Any],
    personajes_activos: List[Dict[str, Any]],
    cartas_activas: List[Dict[str, Any]],
    eventos_jugados: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Selecciona 1 evento del pool disponible mediante Selección Ponderada (Weighted Random Selection),
    aplicando sinergias con la corte elegida, cartas del inventario y situaciones de crisis.
    """
    disponibles = [e for e in eventos_candidatos if e.get("_id") not in eventos_jugados]
    if not disponibles:
        # Si se agotaron todos los eventos del pool, permite reciclar
        disponibles = eventos_candidatos

    if not disponibles:
        return None

    pesos = []
    # Extraer tags de la corte y cartas activas
    tags_corte = set()
    for p in personajes_activos:
        for t in p.get("tags", []):
            tags_corte.add(t.lower())

    tags_cartas = set()
    for c in cartas_activas:
        for t in c.get("tags", []):
            tags_cartas.add(t.lower())

    recursos = run_data.get("recursos", {})
    recursos_en_crisis = {k.lower() for k, v in recursos.items() if float(v) < 25.0}

    for evento in disponibles:
        peso = float(evento.get("peso_base", 100.0))
        tags_evento = {t.lower() for t in evento.get("tags_tematicos", [])}

        # 1. Sinergia con Personajes de la Corte (x2.0 si comparte al menos un tag)
        if tags_corte.intersection(tags_evento):
            peso *= 2.0

        # 2. Sinergia con Cartas del Inventario (x2.5 si comparte al menos un tag)
        if tags_cartas.intersection(tags_evento):
            peso *= 2.5

        # 3. Modificador de Urgencia (x3.0 si un recurso crítico coincide con el evento)
        if recursos_en_crisis.intersection(tags_evento):
            peso *= 3.0

        pesos.append(max(1.0, peso))

    seleccionado = random.choices(disponibles, weights=pesos, k=1)[0]
    return seleccionado

def calcular_opciones_evento(
    evento_data: Dict[str, Any],
    run_data: Dict[str, Any],
    resultados_dict: Dict[str, Dict[str, Any]]
) -> List[OpcionEventoCalculadaResponse]:
    """
    Calcula para cada opción del evento si está bloqueada (en caso de ser secreta)
    y desglosa los porcentajes y explicaciones de cada desenlace posible.
    """
    opciones_calculadas = []

    for op in evento_data.get("opciones", []):
        op_id = op.get("id")
        texto = op.get("texto", "")
        es_secreta = bool(op.get("es_secreta", False))
        condiciones = op.get("condiciones", [])

        # Verificar si cumple los requisitos (para opción secreta o condicional)
        cumple_condiciones = evaluar_condiciones(condiciones, run_data)
        bloqueada = es_secreta and not cumple_condiciones

        # Calcular probabilidades de cada desenlace
        resultados_posibles = op.get("resultados_posibles", [])
        pesos_finales = []
        info_resultados = []

        for rp in resultados_posibles:
            res_id = rp.get("resultado_id")
            peso_base = float(rp.get("peso_base", 50.0))
            explicaciones = []

            for mod in rp.get("modificadores_probabilidad", []):
                cond = mod.get("condicion")
                if cond and evaluar_condicion(cond, run_data):
                    delta = float(mod.get("delta_peso", 0.0))
                    peso_base += delta
                    explicacion = mod.get("explicacion")
                    if explicacion:
                        explicaciones.append(explicacion)

            peso_efectivo = max(0.0, peso_base)
            pesos_finales.append(peso_efectivo)

            res_doc = resultados_dict.get(res_id, {})
            titulo_res = res_doc.get("titulo", res_id)

            info_resultados.append({
                "resultado_id": res_id,
                "titulo": titulo_res,
                "explicaciones": explicaciones
            })

        suma_pesos = sum(pesos_finales)
        probabilidades_dto = []
        for i, info in enumerate(info_resultados):
            if suma_pesos > 0:
                pct = round((pesos_finales[i] / suma_pesos) * 100.0, 1)
            else:
                pct = 0.0

            probabilidades_dto.append(ProbabilidadDesenlaceCalculada(
                resultado_id=info["resultado_id"],
                titulo=info["titulo"],
                porcentaje=pct,
                explicaciones=info["explicaciones"]
            ))

        opciones_calculadas.append(OpcionEventoCalculadaResponse(
            id=op_id,
            texto=texto,
            es_secreta=es_secreta,
            bloqueada=bloqueada,
            probabilidades=probabilidades_dto
        ))

    return opciones_calculadas

def sortear_resultado_opcion(
    opcion_data: Dict[str, Any],
    run_data: Dict[str, Any]
) -> str:
    """
    Ejecuta la tirada ponderada de los resultados posibles de una opción
    según las cartas y corte vivas del jugador. Retorna el resultado_id ganador.
    """
    resultados_posibles = opcion_data.get("resultados_posibles", [])
    if not resultados_posibles:
        raise ValueError("La opción no tiene resultados posibles definidos.")

    ids = []
    pesos = []

    for rp in resultados_posibles:
        res_id = rp.get("resultado_id")
        peso_base = float(rp.get("peso_base", 50.0))

        for mod in rp.get("modificadores_probabilidad", []):
            cond = mod.get("condicion")
            if cond and evaluar_condicion(cond, run_data):
                delta = float(mod.get("delta_peso", 0.0))
                peso_base += delta

        ids.append(res_id)
        pesos.append(max(0.1, peso_base))

    ganador_id = random.choices(ids, weights=pesos, k=1)[0]
    return ganador_id
