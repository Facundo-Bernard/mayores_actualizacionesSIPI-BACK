"""Inventario de solo lectura: disparadores y acciones realmente usados en cartas y personajes."""

import asyncio
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorClient

DB = "mayores_actualizaciones_dev"


async def main() -> None:
    db = AsyncIOMotorClient("mongodb://localhost:27017")[DB]
    for coll in ("narrative_cards", "narrative_characters"):
        docs = await db[coll].find({}, {"efectos": 1, "universo_id": 1}).to_list(None)
        disparadores: Counter = Counter()
        acciones: Counter = Counter()
        condiciones: Counter = Counter()
        firmas: Counter = Counter()
        con_efectos = 0
        total_efectos = 0
        for doc in docs:
            efectos = doc.get("efectos") or []
            if efectos:
                con_efectos += 1
            for ef in efectos:
                total_efectos += 1
                disparadores[ef.get("disparador")] += 1
                acc = ef.get("accion") or {}
                acciones[acc.get("tipo")] += 1
                for c in ef.get("condiciones") or []:
                    condiciones[c.get("tipo")] += 1
                firmas[(acc.get("tipo"), acc.get("clave"), acc.get("tipo_calculo"), acc.get("valor"))] += 1
        print(f"\n== {coll}: {len(docs)} docs, {con_efectos} con efectos, {total_efectos} efectos")
        print("  disparadores:", dict(disparadores))
        print("  tipos_accion:", dict(acciones))
        print("  tipos_condicion:", dict(condiciones))
        print("  firmas distintas (tipo,clave,calculo,valor):", len(firmas))


if __name__ == "__main__":
    asyncio.run(main())
