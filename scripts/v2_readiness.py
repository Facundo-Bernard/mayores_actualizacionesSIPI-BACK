"""
v2_readiness.py
Dry-run de readiness del motor narrativo V2 contra ``mayores_actualizaciones_test``.

Simula 12 meses de una partida por universo usando los grafos realmente
sembrados: sortea eventos/conversaciones con la misma lógica del motor, recorre
cada grafo eligiendo opciones válidas y registra:

- eventos y conversaciones usados (y repeticiones),
- grafos inválidos según ``graph_validator``,
- soft-locks (mes sin eventos elegibles o nodo sin opciones disponibles),
- nodos sin salida / destinos inexistentes / ciclos,
- problemas de renderizado para el frontend actual (textos vacíos).

No es un test: es un script operativo. Sale con código 0 solo si todos los
universos completan los 12 meses sin errores. Nunca corre contra otra base que
no sea la de test.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

TEST_DB_NAME = "mayores_actualizaciones_test"
MESES_POR_DEFECTO = 12
MAX_PASOS_GRAFO = 500


# ============================================================================
# RECORRIDO PURO DE GRAFOS (testeable sin DB)
# ============================================================================

@dataclass
class RecorridoGrafo:
    visitados: list[str] = field(default_factory=list)
    problema: Optional[str] = None
    errores_render: list[str] = field(default_factory=list)
    final_alcanzado: bool = False

    @property
    def ok(self) -> bool:
        return self.problema is None and self.final_alcanzado and not self.errores_render


def siguiente_nodo(opcion: dict[str, Any], rng: random.Random) -> Optional[str]:
    """Resuelve el destino de una opción igual que ``graph_engine.avanzar_nodo``."""
    desenlaces = [
        (str(d.get("nodo")), float(d.get("peso", 0)))
        for d in (opcion.get("desenlaces") or [])
        if isinstance(d, dict) and d.get("nodo") and float(d.get("peso", 0)) > 0
    ]
    if desenlaces:
        destinos = [nodo for nodo, _ in desenlaces]
        pesos = [peso for _, peso in desenlaces]
        return rng.choices(destinos, weights=pesos, k=1)[0]
    destino = opcion.get("siguiente_nodo")
    return destino if isinstance(destino, str) and destino else None


def caminar_grafo(
    grafo: dict[str, Any],
    rng: random.Random,
    *,
    puede_elegir: Optional[Callable[[dict[str, Any], dict[str, Any]], bool]] = None,
) -> RecorridoGrafo:
    """
    Recorre un grafo desde su raíz eligiendo opciones disponibles.

    ``puede_elegir(nodo, opcion)`` permite simular condiciones de estado; si se
    omite, todas las opciones estructuralmente válidas son elegibles.
    """
    nodos = grafo.get("nodos") or {}
    actual = grafo.get("nodo_raiz")
    recorrido = RecorridoGrafo()

    while True:
        if not isinstance(actual, str) or not actual:
            recorrido.problema = "nodo_raiz_ausente"
            return recorrido
        if actual in recorrido.visitados:
            recorrido.problema = f"ciclo:{actual}"
            return recorrido
        if len(recorrido.visitados) >= MAX_PASOS_GRAFO:
            recorrido.problema = "grafo_demasiado_largo"
            return recorrido

        nodo = nodos.get(actual)
        if not isinstance(nodo, dict):
            recorrido.problema = f"nodo_inexistente:{actual}"
            return recorrido
        recorrido.visitados.append(actual)

        texto = str(nodo.get("texto") or "").strip()
        if not texto and not nodo.get("es_final"):
            recorrido.errores_render.append(f"texto_vacio:{actual}")

        if nodo.get("es_final"):
            if not str(nodo.get("resultado_texto") or "").strip():
                recorrido.errores_render.append(f"resultado_vacio:{actual}")
            recorrido.final_alcanzado = True
            return recorrido

        opciones = [
            opcion
            for opcion in (nodo.get("opciones") or [])
            if isinstance(opcion, dict)
            and str(opcion.get("id") or "").strip()
            and str(opcion.get("texto") or "").strip()
            and (puede_elegir is None or puede_elegir(nodo, opcion))
        ]
        ocultas_o_invalidas = len(nodo.get("opciones") or []) - len(opciones)
        if not opciones:
            recorrido.problema = f"soft_lock:{actual}" if ocultas_o_invalidas else f"nodo_sin_opciones:{actual}"
            return recorrido

        elegida = rng.choice(opciones)
        actual = siguiente_nodo(elegida, rng)
        if actual is None:
            recorrido.problema = f"opcion_sin_destino:{nodo.get('id')}:{elegida.get('id')}"
            return recorrido


def aplicar_impactos(nodo: Optional[dict[str, Any]], run: dict[str, Any]) -> None:
    """Aplica impactos terminales al estado sintético para que las condiciones sigan siendo realistas."""
    if not isinstance(nodo, dict):
        return
    recursos = run.setdefault("recursos", {})
    for impacto in nodo.get("impactos_recursos") or []:
        clave = str(impacto.get("recurso", "")).strip().lower()
        if clave in recursos:
            delta = int(impacto.get("delta", 0))
            recursos[clave] = max(0, min(100, int(recursos[clave]) + delta))

    afinidad = run.setdefault("afinidad", {})
    for impacto in nodo.get("impactos_afinidad") or []:
        personaje_id = impacto.get("personaje_id")
        if personaje_id:
            delta = int(impacto.get("delta", 0))
            afinidad[personaje_id] = max(0, min(100, int(afinidad.get(personaje_id, 50)) + delta))

    tags = run.setdefault("tags_activos", [])
    for tag in nodo.get("impactos_tags") or []:
        if tag and tag not in tags:
            tags.append(tag)


# ============================================================================
# REPORTE
# ============================================================================

@dataclass
class ReporteUniverso:
    universo_id: str
    eventos_disponibles: int
    meses_objetivo: int
    meses_jugados: int = 0
    eventos_usados: list[str] = field(default_factory=list)
    eventos_repetidos: list[str] = field(default_factory=list)
    conversaciones_usadas: list[str] = field(default_factory=list)
    soft_locks: list[str] = field(default_factory=list)
    errores_grafo: list[str] = field(default_factory=list)
    errores_render: list[str] = field(default_factory=list)
    grafos_invalidos: list[str] = field(default_factory=list)
    reciclajes: int = 0

    @property
    def ok(self) -> bool:
        return (
            self.meses_jugados == self.meses_objetivo
            and not self.soft_locks
            and not self.errores_grafo
            and not self.errores_render
            and not self.grafos_invalidos
            and (not self.eventos_repetidos or self.reciclajes > 0)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "universo_id": self.universo_id,
            "ok": self.ok,
            "eventos_disponibles": self.eventos_disponibles,
            "meses_jugados": self.meses_jugados,
            "meses_objetivo": self.meses_objetivo,
            "eventos_usados": self.eventos_usados,
            "eventos_repetidos": self.eventos_repetidos,
            "conversaciones_usadas": self.conversaciones_usadas,
            "soft_locks": self.soft_locks,
            "errores_grafo": self.errores_grafo,
            "errores_render": self.errores_render,
            "grafos_invalidos": self.grafos_invalidos,
            "reciclajes": self.reciclajes,
        }


# ============================================================================
# SIMULACIÓN CONTRA LA BASE DE TEST
# ============================================================================

async def _simular_grafo(
    grafo: dict[str, Any],
    tipo: str,
    run: dict[str, Any],
    rng: random.Random,
    reporte: ReporteUniverso,
    etiqueta: str,
) -> None:
    from app.features.narrative.validation.graph_validator import validar_grafo

    validacion = validar_grafo(grafo, tipo)
    if not validacion.valido:
        reporte.grafos_invalidos.append(etiqueta)

    recorrido = caminar_grafo(
        grafo,
        rng,
        puede_elegir=lambda _nodo, opcion: _puede_elegir(opcion, run),
    )
    if recorrido.problema:
        reporte.errores_grafo.append(f"{etiqueta}: {recorrido.problema}")
    if not recorrido.final_alcanzado and not recorrido.problema:
        reporte.errores_grafo.append(f"{etiqueta}: sin final alcanzable")
    reporte.errores_render.extend(f"{etiqueta}: {error}" for error in recorrido.errores_render)

    if recorrido.visitados:
        nodo_final = (grafo.get("nodos") or {}).get(recorrido.visitados[-1])
        aplicar_impactos(nodo_final, run)


def _puede_elegir(opcion: dict[str, Any], run: dict[str, Any]) -> bool:
    from app.features.narrative.engine.rule_engine import evaluar_condicion

    for condicion in opcion.get("condiciones") or []:
        if not evaluar_condicion(condicion, run):
            return False
    return True


async def _estado_sintetico(db, universo_id: str) -> dict[str, Any]:
    from app.features.narrative.constants import COLL_CARDS, COLL_CHARACTERS
    from app.features.narrative.game.universe_resources import obtener_mapa_recursos_universo

    mapa = await obtener_mapa_recursos_universo(universo_id)
    claves = list(mapa.keys()) or ["oro", "pueblo", "ejercito", "fe"]
    personajes = await db[COLL_CHARACTERS].find({"universo_id": universo_id}).to_list(None)
    cartas = await db[COLL_CARDS].find({"universo_id": universo_id}).to_list(None)

    return {
        "universo_id": universo_id,
        "mes_actual": 1,
        "fase_actual": "BALANCE_MES",
        "status": "in_progress",
        "recursos": {clave: 50 for clave in claves},
        "afinidad": {p["_id"]: 50 for p in personajes},
        "cartas_en_mano": [c["_id"] for c in cartas],
        "tags_activos": [],
        "eventos_jugados": [],
        "conversaciones_jugadas": [],
        "historial_mensual": [],
    }


async def simular_universo(
    db,
    universo_id: str,
    *,
    meses: int = MESES_POR_DEFECTO,
    seed: int = 7,
    reciclar: bool = False,
) -> ReporteUniverso:
    from app.features.narrative.constants import COLL_V2_EVENTS
    from app.features.narrative.game.motor_v2.graph_engine import graph_engine

    eventos_disponibles = await db[COLL_V2_EVENTS].count_documents({"universo_id": universo_id})
    reporte = ReporteUniverso(
        universo_id=universo_id,
        eventos_disponibles=eventos_disponibles,
        meses_objetivo=meses,
    )
    if not eventos_disponibles:
        reporte.soft_locks.append("universo sin eventos V2 sembrados")
        return reporte

    run = await _estado_sintetico(db, universo_id)
    run["reciclaje_eventos_v2"] = reciclar
    rng = random.Random(seed)

    for mes in range(1, meses + 1):
        run["mes_actual"] = mes
        evento = await graph_engine.sortear_evento_v2(
            run=run, pool_ids=None, universo_id=universo_id
        )
        if not evento:
            reporte.soft_locks.append(f"mes {mes}: sin eventos elegibles")
            break

        evento_id = evento["_id"]
        if evento_id in reporte.eventos_usados:
            reporte.eventos_repetidos.append(evento_id)
        reporte.eventos_usados.append(evento_id)
        await _simular_grafo(evento, "evento", run, rng, reporte, f"evento:{evento_id}")
        run["eventos_jugados"].append(evento_id)
        reporte.meses_jugados += 1

        if rng.random() < 0.40:
            conversacion = await graph_engine.sortear_conversacion_v2(
                run=run, pool_ids=None, universo_id=universo_id
            )
            if conversacion:
                conversacion_id = conversacion["_id"]
                reporte.conversaciones_usadas.append(conversacion_id)
                await _simular_grafo(
                    conversacion,
                    "conversacion",
                    run,
                    rng,
                    reporte,
                    f"conversacion:{conversacion_id}",
                )
                run["conversaciones_jugadas"].append(conversacion_id)

    reporte.reciclajes = int(run.get("reciclajes_eventos_v2", 0))
    return reporte


async def _universos_con_grafos(db) -> list[str]:
    from app.features.narrative.constants import COLL_V2_EVENTS

    return sorted(await db[COLL_V2_EVENTS].distinct("universo_id"))


async def ejecutar_dry_run(
    *,
    universo: Optional[str] = None,
    meses: int = MESES_POR_DEFECTO,
    seed: int = 7,
    reciclar: bool = False,
    keep_run: bool = False,
    sembrar: bool = False,
) -> dict[str, Any]:
    os.environ["MONGODB_DB_NAME"] = TEST_DB_NAME
    os.environ.pop("MONGO_DB_NAME", None)

    from app.core.config import settings
    from app.core.database import close_mongo_connection, connect_to_mongo, get_database
    from app.features.narrative.constants import COLL_RUNS

    if settings.effective_db_name != TEST_DB_NAME:
        raise SystemExit(
            f"El dry-run solo corre contra {TEST_DB_NAME}; configuración actual: "
            f"{settings.effective_db_name!r}."
        )
    url = settings.mongodb_connection_url
    if "localhost" not in url and "127.0.0.1" not in url:
        raise SystemExit(f"El dry-run solo corre contra MongoDB local, no contra {url!r}.")

    await connect_to_mongo()
    run_id = f"readiness_v2_{int(time.time())}"
    db = get_database()
    try:
        if sembrar:
            from app.scripts.seed_narrative_v2_graphs import seed_v2_graphs

            await seed_v2_graphs()

        # Importar el router primero respeta el orden del arranque de la app y evita
        # el ciclo graph_engine -> game.__init__ -> router -> graph_engine.
        import app.features.narrative.game.router  # noqa: F401

        universos = [universo] if universo else await _universos_con_grafos(db)
        if not universos:
            raise SystemExit("No hay universos con eventos V2 sembrados en la base de test.")

        await db[COLL_RUNS].replace_one(
            {"_id": run_id},
            {
                "_id": run_id,
                "user_id": 0,
                "date": "readiness",
                "game_id": "narrativo",
                "motor": "v2",
                "status": "readiness",
                "mes_actual": 1,
                "recursos": {},
                "afinidad": {},
                "eventos_jugados": [],
                "conversaciones_jugadas": [],
                "historial_mensual": [],
            },
            upsert=True,
        )

        reportes = []
        for universo_id in universos:
            reporte = await simular_universo(
                db, universo_id, meses=meses, seed=seed, reciclar=reciclar
            )
            reportes.append(reporte)
            await db[COLL_RUNS].update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "universo_id": universo_id,
                        "mes_actual": reporte.meses_jugados,
                        "eventos_jugados": reporte.eventos_usados,
                        "conversaciones_jugadas": reporte.conversaciones_usadas,
                    }
                },
            )

        return {
            "db": TEST_DB_NAME,
            "run_id": run_id,
            "meses": meses,
            "seed": seed,
            "reciclaje": reciclar,
            "ok": all(reporte.ok for reporte in reportes),
            "universos": [reporte.as_dict() for reporte in reportes],
        }
    finally:
        if not keep_run:
            await db[COLL_RUNS].delete_one({"_id": run_id})
        await close_mongo_connection()


def _imprimir_resumen(resultado: dict[str, Any]) -> None:
    estado = "OK" if resultado["ok"] else "FALLA"
    print(f"\n[READINESS V2] {estado} — base {resultado['db']}, {resultado['meses']} meses\n")
    for reporte in resultado["universos"]:
        marca = "OK" if reporte["ok"] else "FALLA"
        print(
            f"- {reporte['universo_id']}: {marca} | "
            f"{reporte['meses_jugados']}/{reporte['meses_objetivo']} meses | "
            f"{len(reporte['eventos_usados'])} eventos | "
            f"{len(reporte['conversaciones_usadas'])} conversaciones | "
            f"reciclajes {reporte['reciclajes']}"
        )
        for clave in (
            "soft_locks",
            "errores_grafo",
            "errores_render",
            "grafos_invalidos",
            "eventos_repetidos",
        ):
            if reporte[clave]:
                print(f"    {clave}: {reporte[clave]}")
    print()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run de readiness del narrativo V2.")
    parser.add_argument("--universo", help="Limita el dry-run a un universo_id")
    parser.add_argument("--meses", type=int, default=MESES_POR_DEFECTO)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--reciclar",
        action="store_true",
        help="Permite reiniciar eventos_jugados cuando se agotan (reciclaje explícito)",
    )
    parser.add_argument(
        "--keep-run",
        action="store_true",
        help="Conserva la run de readiness en la base de test para inspección",
    )
    parser.add_argument(
        "--sembrar",
        action="store_true",
        help="Siembra los grafos V2 idempotentes en la base de test antes del dry-run",
    )
    parser.add_argument("--json", action="store_true", help="Imprime el reporte completo en JSON")
    args = parser.parse_args(argv)

    resultado = asyncio.run(
        ejecutar_dry_run(
            universo=args.universo,
            meses=args.meses,
            seed=args.seed,
            reciclar=args.reciclar,
            keep_run=args.keep_run,
            sembrar=args.sembrar,
        )
    )
    _imprimir_resumen(resultado)
    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
