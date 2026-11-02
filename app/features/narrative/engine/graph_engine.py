"""
graph_engine.py
Motor Narrativo Genérico V2 basado en Grafos de Decisión.
Agnóstico al tipo de contenido (Eventos o Conversaciones), resuelve la navegación
paso a paso (heurística sin spoilers), valida transiciones y aplica consecuencias atómicas en MongoDB.
Incorpora reactividad de estado con condiciones dinámicas por opción y sorteo ponderado por sinergias.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import HTTPException

from app.core.database import get_database
from app.features.narrative.constants import (
    COLL_V2_EVENTS,
    COLL_V2_CONVERSATIONS,
    COLL_V2_EVENTOS_ESPECIALES,
    COLL_RUNS,
    COLL_CHARACTERS,
    COLL_CARDS,
    AFINIDAD_UMBRAL_LEALTAD,
    AFINIDAD_UMBRAL_TRAICION
)
from app.features.narrative.enums import RunPhaseEnum
from app.features.narrative.schemas.v2_graph_schemas import (
    NodoNarrativoSchema,
    NodoClienteSchema,
    EstadoGrafoV2Response
)

logger = logging.getLogger(__name__)

class GraphTraversalEngine:
    def __init__(self):
        pass

    def _get_collection_for_tipo(self, tipo: str):
        db = get_database()
        if tipo == "evento":
            return db[COLL_V2_EVENTS]
        elif tipo == "conversacion":
            return db[COLL_V2_CONVERSATIONS]
        elif tipo == "evento_especial":
            return db[COLL_V2_EVENTOS_ESPECIALES]
        else:
            raise ValueError(f"Tipo de grafo desconocido: '{tipo}'. Debe ser 'evento', 'conversacion' o 'evento_especial'.")

    async def obtener_grafo(self, tipo: str, grafo_id: str) -> Optional[Dict[str, Any]]:
        """Recupera un grafo completo desde la colección correspondiente."""
        col = self._get_collection_for_tipo(tipo)
        return await col.find_one({"_id": grafo_id})

    async def sortear_evento_v2(
        self,
        run: Dict[str, Any],
        pool_ids: Optional[List[str]] = None,
        universo_id: str = "corte_medieval"
    ) -> Optional[Dict[str, Any]]:
        """
        Sortea un evento V2 elegible respetando:
        1. Universo y pool de IDs del mes (si se proporciona).
        2. Que no se haya jugado ya en esta partida (run['eventos_jugados']).
        3. Que se cumplan los 'requisitos_eventos_previos' (cadenas de eventos / arcos narrativos).
        4. Que se cumplan los 'requisitos_personajes' (consejeros requeridos en corte).
        5. Que se cumplan las 'condiciones_disparo' (recursos mínimos, crisis, afinidad, etc.).
        6. Sorteo ponderado por sinergia con corte activa, cartas en inventario y situaciones de crisis.
        """
        db = get_database()
        query: Dict[str, Any] = {"universo_id": universo_id}
        if pool_ids:
            query["_id"] = {"$in": pool_ids}

        candidatos = await db[COLL_V2_EVENTS].find(query).to_list(None)
        if not candidatos:
            return None

        eventos_jugados = set(run.get("eventos_jugados", []))
        corte_activa = set(run.get("afinidad", {}).keys()) or set(run.get("corte_activa", []))

        # 1. Obtener tags de la corte activa
        tags_corte = set()
        if corte_activa:
            pjs_docs = await db[COLL_CHARACTERS].find({"_id": {"$in": list(corte_activa)}}).to_list(None)
            for p in pjs_docs:
                for t in p.get("tags", []):
                    tags_corte.add(t.lower())

        # 2. Obtener tags de cartas en mano / inventario
        tags_cartas = set()
        cartas_mano = run.get("cartas_en_mano", [])
        if cartas_mano:
            cartas_docs = await db[COLL_CARDS].find({"_id": {"$in": cartas_mano}}).to_list(None)
            for c in cartas_docs:
                for t in c.get("tags", []):
                    tags_cartas.add(t.lower())

        # 3. Detectar recursos en crisis (< 25)
        recursos = run.get("recursos", {})
        recursos_en_crisis = {k.lower() for k, v in recursos.items() if float(v) < 25.0}

        from app.features.narrative.engine.rule_engine import evaluar_condiciones

        disponibles = []
        pesos = []

        for evt in candidatos:
            evt_id = evt.get("_id")
            if evt_id in eventos_jugados:
                continue

            # Validar requisitos de eventos previos (Arcos Narrativos)
            requisitos_previos = evt.get("requisitos_eventos_previos", [])
            if requisitos_previos and not set(requisitos_previos).issubset(eventos_jugados):
                continue

            # Validar requisitos de personajes de la corte
            requisitos_personajes = evt.get("requisitos_personajes", [])
            if requisitos_personajes and not set(requisitos_personajes).issubset(corte_activa):
                continue

            # Validar condiciones de disparo del estado del reino
            condiciones_disparo = evt.get("condiciones_disparo", [])
            if condiciones_disparo and not evaluar_condiciones(condiciones_disparo, run):
                continue

            # Cálculo de peso ponderado (sinergias con corte, cartas y urgencia)
            peso = float(evt.get("peso_base", 100.0))
            tags_evento = {t.lower() for t in evt.get("tags_tematicos", [])}

            if tags_corte.intersection(tags_evento):
                peso *= 2.0

            if tags_cartas.intersection(tags_evento):
                peso *= 2.5

            if recursos_en_crisis.intersection(tags_evento):
                peso *= 3.0

            disponibles.append(evt)
            pesos.append(max(1.0, peso))

        if not disponibles:
            return None

        return random.choices(disponibles, weights=pesos, k=1)[0]

    async def sortear_conversacion_v2(
        self,
        run: Dict[str, Any],
        pool_ids: Optional[List[str]] = None,
        universo_id: str = "corte_medieval"
    ) -> Optional[Dict[str, Any]]:
        """
        Sortea una conversación V2 elegible respetando:
        1. Universo y pool de IDs del mes.
        2. Que no se haya jugado ya en esta partida (run['conversaciones_jugadas']).
        3. Que todos los consejeros requeridos estén activos en la corte del jugador.
        4. Que se cumplan las condiciones_disparo si existen.
        """
        db = get_database()
        query: Dict[str, Any] = {"universo_id": universo_id}
        if pool_ids:
            query["_id"] = {"$in": pool_ids}

        candidatas = await db[COLL_V2_CONVERSATIONS].find(query).to_list(None)
        if not candidatas:
            return None

        convs_jugadas = set(run.get("conversaciones_jugadas", []))
        corte_activa = set(run.get("afinidad", {}).keys()) or set(run.get("corte_activa", []))

        from app.features.narrative.engine.rule_engine import evaluar_condiciones

        validas = []
        for conv in candidatas:
            conv_id = conv.get("_id")
            if conv_id in convs_jugadas:
                continue

            requisitos = conv.get("requisitos", [])
            if not set(requisitos).issubset(corte_activa):
                continue

            condiciones_disparo = conv.get("condiciones_disparo", [])
            if condiciones_disparo and not evaluar_condiciones(condiciones_disparo, run):
                continue

            validas.append(conv)

        if not validas:
            return None

        return random.choice(validas)

    async def iniciar_grafo_en_partida(
        self,
        run: Dict[str, Any],
        grafo: Dict[str, Any],
        tipo: str,
        fase: str
    ) -> EstadoGrafoV2Response:
        """
        Inicia un grafo en la partida, fijando el nodo raíz y devolviendo el estado inicial sanitizado y evaluado.
        """
        db = get_database()
        grafo_id = grafo["_id"]
        nodo_raiz_id = grafo["nodo_raiz"]
        nodos = grafo.get("nodos", {})

        nodo_raiz_dict = nodos.get(nodo_raiz_id)
        if not nodo_raiz_dict:
            raise HTTPException(status_code=500, detail=f"El grafo '{grafo_id}' no contiene su nodo raíz '{nodo_raiz_id}'.")

        nodo_schema = NodoNarrativoSchema(**nodo_raiz_dict)
        nodo_cliente = nodo_schema.to_cliente_schema(run)

        # Actualizar partida
        run["grafo_activo"] = {
            "tipo": tipo,
            "grafo_id": grafo_id,
            "nodo_actual_id": nodo_raiz_id
        }
        run["fase_actual"] = fase

        await db[COLL_RUNS].update_one(
            {"_id": run["_id"]},
            {"$set": {
                "grafo_activo": run["grafo_activo"],
                "fase_actual": run["fase_actual"]
            }}
        )

        return EstadoGrafoV2Response(
            fase_actual=fase,
            grafo_id=grafo_id,
            tipo=tipo,
            titulo=grafo.get("titulo", ""),
            imagen=grafo.get("imagen", ""),
            nodo_actual=nodo_cliente,
            status=run.get("status", "CONTINUA")
        )

    def _detectar_cruces_afinidad(
        self,
        afinidad_before: Dict[str, Any],
        afinidad_after: Dict[str, Any]
    ) -> List[tuple]:
        """
        Detecta personajes que cruzaron un umbral de afinidad al aplicar deltas:
        - 'lealtad': pasó de estar por debajo de AFINIDAD_UMBRAL_LEALTAD a alcanzarlo o superarlo.
        - 'traicion': pasó de estar en o por encima de AFINIDAD_UMBRAL_TRAICION a caer por debajo.
        """
        cruces: List[tuple] = []
        for pj_id, valor_actual in afinidad_after.items():
            valor_previo = afinidad_before.get(pj_id)
            if valor_previo is None:
                continue
            if valor_previo < AFINIDAD_UMBRAL_LEALTAD and valor_actual >= AFINIDAD_UMBRAL_LEALTAD:
                cruces.append((pj_id, "lealtad"))
            if valor_previo >= AFINIDAD_UMBRAL_TRAICION and valor_actual < AFINIDAD_UMBRAL_TRAICION:
                cruces.append((pj_id, "traicion"))
        return cruces

    async def _obtener_evento_especial(
        self,
        personaje_id: str,
        direccion: str,
        universo_id: str
    ) -> Optional[Dict[str, Any]]:
        """Recupera el grafo de evento especial para un personaje y dirección de umbral."""
        db = get_database()
        return await db[COLL_V2_EVENTOS_ESPECIALES].find_one({
            "universo_id": universo_id,
            "personaje_id": personaje_id,
            "direccion": direccion
        })

    async def _encadenar_especial_pendiente(
        self,
        run: Dict[str, Any]
    ) -> Optional[EstadoGrafoV2Response]:
        """Desencola y encadena el próximo evento especial de afinidad pendiente, si hay grafo disponible."""
        pendientes = run.get("especiales_pendientes", [])
        if not pendientes:
            return None

        while pendientes:
            item = pendientes.pop(0)
            grafo = await self._obtener_evento_especial(
                item["personaje_id"],
                item["direccion"],
                run.get("universo_id", "corte_medieval")
            )
            if grafo:
                return await self.iniciar_grafo_en_partida(
                    run=run,
                    grafo=grafo,
                    tipo="evento_especial",
                    fase=RunPhaseEnum.TOMA_DECISION_EVENTO.value
                )
        return None

    async def avanzar_nodo(
        self,
        run: Dict[str, Any],
        opcion_id: str
    ) -> EstadoGrafoV2Response:
        """
        Avanza un paso en el grafo activo de la partida.
        Valida que la opción seleccionada cumpla con las condiciones dinámicas requeridas.
        Si el siguiente nodo es intermedio, actualiza el puntero y lo devuelve sin spoilers.
        Si es final, aplica impactos en recursos y afinidad, evalúa fin de partida y avanza la fase.
        """
        grafo_activo = run.get("grafo_activo")
        if not grafo_activo:
            raise HTTPException(
                status_code=409,
                detail="No hay ningún grafo (evento o conversación) activo en la partida para avanzar."
            )

        tipo = grafo_activo["tipo"]
        grafo_id = grafo_activo["grafo_id"]
        nodo_actual_id = grafo_activo["nodo_actual_id"]

        grafo = await self.obtener_grafo(tipo, grafo_id)
        if not grafo:
            raise HTTPException(
                status_code=409,
                detail=f"El grafo activo '{grafo_id}' de tipo '{tipo}' ya no existe en la base de datos."
            )

        nodos_dict = grafo.get("nodos", {})
        nodo_actual_data = nodos_dict.get(nodo_actual_id)
        if not nodo_actual_data:
            raise HTTPException(
                status_code=409,
                detail=f"El nodo actual '{nodo_actual_id}' no existe en el grafo '{grafo_id}'."
            )

        nodo_actual = NodoNarrativoSchema(**nodo_actual_data)

        # Buscar la opción seleccionada dentro del nodo actual
        opcion_elegida = next((opt for opt in nodo_actual.opciones if opt.id == opcion_id), None)
        if not opcion_elegida:
            raise HTTPException(
                status_code=400,
                detail=f"La opción '{opcion_id}' no es válida para el nodo '{nodo_actual_id}'."
            )

        # Validar si la opción cumplía las condiciones requeridas
        if opcion_elegida.condiciones:
            from app.features.narrative.engine.rule_engine import evaluar_condicion
            for cond in opcion_elegida.condiciones:
                cond_dict = cond.model_dump() if hasattr(cond, "model_dump") else cond
                if not evaluar_condicion(cond_dict, run):
                    motivo = NodoNarrativoSchema._generar_motivo_bloqueo(cond)
                    raise HTTPException(
                        status_code=400,
                        detail=f"La opción '{opcion_id}' está bloqueada: {motivo}."
                    )

        # Resolver el nodo destino: desenlaces ponderados (si los hay) o destino fijo
        if opcion_elegida.desenlaces:
            nodos_destino = [d.nodo for d in opcion_elegida.desenlaces]
            pesos = [max(0.0, float(d.peso)) for d in opcion_elegida.desenlaces]
            siguiente_nodo_id = random.choices(nodos_destino, weights=pesos, k=1)[0]
        else:
            siguiente_nodo_id = opcion_elegida.siguiente_nodo

        if not siguiente_nodo_id:
            raise HTTPException(
                status_code=400,
                detail=f"La opción '{opcion_id}' no define un nodo destino (siguiente_nodo ni desenlaces)."
            )

        siguiente_nodo_data = nodos_dict.get(siguiente_nodo_id)
        if not siguiente_nodo_data:
            raise HTTPException(
                status_code=500,
                detail=f"El nodo destino '{siguiente_nodo_id}' configurado en la opción '{opcion_id}' no existe en el grafo."
            )

        siguiente_nodo = NodoNarrativoSchema(**siguiente_nodo_data)
        nodo_cliente = siguiente_nodo.to_cliente_schema(run)
        db = get_database()

        # ====================================================================
        # CASO 1: NODO INTERMEDIO (es_final == False)
        # ====================================================================
        if not siguiente_nodo.es_final:
            grafo_activo["nodo_actual_id"] = siguiente_nodo_id
            turno = run.setdefault("turno_actual", {})
            turno["opcion_elegida_id"] = opcion_id
            await db[COLL_RUNS].update_one(
                {"_id": run["_id"]},
                {"$set": {"grafo_activo": grafo_activo, "turno_actual": turno}}
            )

            return EstadoGrafoV2Response(
                fase_actual=run["fase_actual"],
                grafo_id=grafo_id,
                tipo=tipo,
                titulo=grafo.get("titulo", ""),
                imagen=grafo.get("imagen", ""),
                nodo_actual=nodo_cliente,
                status=run.get("status", "CONTINUA")
            )

        # ====================================================================
        # CASO 2: NODO TERMINAL (es_final == True)
        # ====================================================================
        from app.features.narrative.game.endings_service import (
            verificar_colapso_recursos,
            sincronizar_intento_usuario
        )
        from app.features.narrative.game.setup_service import _obtener_mapa_recursos_universo

        recursos = run.get("recursos", {"oro": 50, "pueblo": 50, "ejercito": 50, "fe": 50})
        afinidad = run.get("afinidad", {})

        # Límites min/max de recursos configurados para el universo
        recursos_mapa = await _obtener_mapa_recursos_universo(run.get("universo_id", "corte_medieval"))

        # 1. Aplicar Impactos de Recursos
        for imp_rec in siguiente_nodo.impactos_recursos:
            rec_clave = imp_rec.recurso.lower()
            if rec_clave in recursos:
                meta = recursos_mapa.get(rec_clave, {})
                limite_min = meta.get("min", 0)
                limite_max = meta.get("max", 100)
                recursos[rec_clave] = max(limite_min, min(limite_max, recursos[rec_clave] + imp_rec.delta))

        # 2. Aplicar Impactos de Afinidad
        afinidad_before = dict(afinidad)
        for imp_af in siguiente_nodo.impactos_afinidad:
            pj_id = imp_af.personaje_id
            if pj_id in afinidad:
                afinidad[pj_id] = max(0, min(100, afinidad[pj_id] + imp_af.delta))
        cruces_afinidad = self._detectar_cruces_afinidad(afinidad_before, afinidad)

        # 2.5 Aplicar Tags permanentes otorgados al reino
        for tag in siguiente_nodo.impactos_tags:
            tags_activos = run.setdefault("tags_activos", [])
            if tag not in tags_activos:
                tags_activos.append(tag)

        # 3. Registrar en historial de jugados
        if tipo == "evento":
            run.setdefault("eventos_jugados", []).append(grafo_id)
        elif tipo == "conversacion":
            run.setdefault("conversaciones_jugadas", []).append(grafo_id)
        elif tipo == "evento_especial":
            run.setdefault("eventos_especiales_jugados", []).append(grafo_id)

        # 4. Persistir la última decisión y limpiar el grafo activo
        turno = run.setdefault("turno_actual", {})
        turno["opcion_elegida_id"] = opcion_id
        turno["resultado_obtenido_id"] = siguiente_nodo_id
        run["grafo_activo"] = None

        # 5. Comprobar Derrota por colapso de recursos (epílogo + sincronización de intento)
        derrota = await verificar_colapso_recursos(run)
        if derrota:
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
            await sincronizar_intento_usuario(run)

            return EstadoGrafoV2Response(
                fase_actual=run["fase_actual"],
                grafo_id=grafo_id,
                tipo=tipo,
                titulo=grafo.get("titulo", ""),
                imagen=grafo.get("imagen", ""),
                nodo_actual=nodo_cliente,
                afinidad=afinidad,
                recursos=recursos,
                finalizacion=run.get("finalizacion"),
                status=run.get("status", "game_over")
            )

        # 5.5 Encadenar evento especial de afinidad (lealtad/traición) si se cruzó un umbral
        if cruces_afinidad:
            pendientes = run.setdefault("especiales_pendientes", [])
            claves_pendientes = {(p["personaje_id"], p["direccion"]) for p in pendientes}
            for pj_id, direccion in cruces_afinidad:
                if (pj_id, direccion) not in claves_pendientes:
                    pendientes.append({"personaje_id": pj_id, "direccion": direccion})
                    claves_pendientes.add((pj_id, direccion))

        estado_especial = await self._encadenar_especial_pendiente(run)
        if estado_especial is not None:
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
            return estado_especial

        # 6. (solo tras un evento) Conversación incidental de corte con 40% de probabilidad
        if tipo == "evento" and random.random() < 0.40:
            conv = await self.sortear_conversacion_v2(
                run=run,
                pool_ids=None,
                universo_id=run.get("universo_id", "corte_medieval")
            )
            if conv:
                run.setdefault("turno_actual", {})["conversacion_actual_id"] = conv["_id"]
                estado_conv = await self.iniciar_grafo_en_partida(
                    run=run,
                    grafo=conv,
                    tipo="conversacion",
                    fase=RunPhaseEnum.RESOLVER_CONVERSACION.value
                )
                run["updated_at"] = datetime.now(timezone.utc).isoformat()
                await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)
                return estado_conv

        # 7. Transición de Fase a balance mensual
        run["fase_actual"] = RunPhaseEnum.BALANCE_MES.value
        run["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLL_RUNS].replace_one({"_id": run["_id"]}, run)

        return EstadoGrafoV2Response(
            fase_actual=run["fase_actual"],
            grafo_id=grafo_id,
            tipo=tipo,
            titulo=grafo.get("titulo", ""),
            imagen=grafo.get("imagen", ""),
            nodo_actual=nodo_cliente,
            afinidad=afinidad,
            recursos=recursos,
            status=run.get("status", "CONTINUA")
        )

# Instancia singleton del motor
graph_engine = GraphTraversalEngine()
