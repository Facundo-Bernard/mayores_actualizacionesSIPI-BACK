"""
testing_lab/generate_mongo_cleanup.py
Script de simulación (dry-run) y generación de comandos para depurar la base de datos MongoDB:
1. Eliminar colecciones obsoletas (ej: 'estados_usuario').
2. Remover campos huérfanos de cursos y estados en 'usuarios' ($unset).
3. Inventario de colecciones de catálogos V1 ('narrative_events', 'narrative_conversations', 'narrative_results').
"""

import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import get_database
from app.core.config import settings

async def main(execute_changes=False):
    print("=== MONGODB CLEANUP DRY-RUN & ANALYSIS ===")
    print(f"Base de datos: {settings.MONGODB_DB_NAME}")
    print(f"Modo ejecución real: {execute_changes}\n")

    db = get_database()
    colls = await db.list_collection_names()

    # 1. Colecciones a eliminar
    colls_to_drop = []
    if "estados_usuario" in colls:
        count = await db["estados_usuario"].count_documents({})
        colls_to_drop.append({"collection": "estados_usuario", "count": count, "motivo": "Dominio delegado a Autenticador"})

    print("1. Colecciones a Eliminar (Drop):")
    for item in colls_to_drop:
        print(f"  - db.{item['collection']}.drop() -> {item['count']} documentos. Motivo: {item['motivo']}")

    # 2. Campos huérfanos en 'usuarios'
    print("\n2. Campos Huérfanos a Remover en 'usuarios' ($unset):")
    usuarios_cursor = db["usuarios"].find({})
    usuarios = await usuarios_cursor.to_list(length=500)
    
    campos_a_remover = ["progresos", "date_start", "date_end", "estado_id", "estado_codigo", "black"]
    
    impacto_campos = {k: 0 for k in campos_a_remover}
    for u in usuarios:
        for k in campos_a_remover:
            if k in u:
                impacto_campos[k] += 1

    for k, cnt in impacto_campos.items():
        print(f"  - '{k}': presente en {cnt} de {len(usuarios)} usuarios.")

    mongo_unset_query = {k: "" for k in campos_a_remover}
    print(f"\nComando MongoDB propuesto:\n  db.usuarios.updateMany({{}}, {{ $unset: {json.dumps(mongo_unset_query)} }})")

    # 3. Colecciones de Catálogo V1 (Planos)
    v1_catalogs = ["narrative_events", "narrative_conversations", "narrative_results"]
    print("\n3. Catálogos Narrativos V1 (Candidatos a archivo/depuración tras migración V2):")
    for vc in v1_catalogs:
        if vc in colls:
            count = await db[vc].count_documents({})
            print(f"  - db.{vc} -> {count} documentos (Reemplazado por narrative_v2_events, v2_conversaciones y desenlaces)")

    # 4. Guardar plan de depuración en JSON
    output_path = os.path.join(os.path.dirname(__file__), "mongodb_cleanup_plan.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "colls_to_drop": colls_to_drop,
            "usuarios_unset_fields": impacto_campos,
            "v1_catalogs": [{c: await db[c].count_documents({}) if c in colls else 0} for c in v1_catalogs]
        }, f, indent=2)

    print(f"\nPlan de depuración guardado en: {output_path}")

if __name__ == "__main__":
    asyncio.run(main(execute_changes=False))
