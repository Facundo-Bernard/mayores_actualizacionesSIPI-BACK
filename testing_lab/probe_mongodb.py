"""
testing_lab/probe_mongodb.py
Inspecciona la base de datos MongoDB local de desarrollo para relevar:
- Colecciones activas y cantidad de documentos.
- Estructura de documentos en 'usuarios' (campos de progreso, cursos, estados).
- Contenido de 'estados_usuario' y colecciones de soporte.
- Colecciones narrativas (catálogos, runs, grafos, etc.).
"""

import asyncio
import json
import os
import sys

# Agregar el directorio raíz del backend al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import get_database
from app.core.config import settings

async def main():
    print(f"=== PROBE MONGODB LOCAL ===")
    print(f"URI: {settings.MONGODB_URL}")
    print(f"DB Name: {settings.MONGODB_DB_NAME}")

    db = get_database()
    
    # 1. Listar todas las colecciones
    collections = await db.list_collection_names()
    print(f"\nColecciones encontradas ({len(collections)}):")
    
    collection_stats = {}
    for coll_name in sorted(collections):
        count = await db[coll_name].count_documents({})
        collection_stats[coll_name] = count
        print(f"  - {coll_name}: {count} documentos")

    # 2. Analizar documento muestra de 'usuarios'
    print("\n--- ANÁLISIS DE COLECCIÓN 'usuarios' ---")
    user_sample = await db["usuarios"].find_one()
    if user_sample:
        # Sanitizar _id
        user_sample["_id"] = str(user_sample["_id"])
        print(f"Campos presentes en usuario muestra: {list(user_sample.keys())}")
        
        # Revisar campos de cursos / progreso
        has_progresos = "progresos" in user_sample
        progresos_val = user_sample.get("progresos", [])
        print(f"¿Tiene campo 'progresos'?: {has_progresos} (Elementos: {len(progresos_val) if isinstance(progresos_val, list) else type(progresos_val)})")
        
        # Revisar campos de estados
        print(f"Campos de estado: estado_id={user_sample.get('estado_id')}, estado_codigo={user_sample.get('estado_codigo')}, activo={user_sample.get('activo')}")
        print(f"Campos de juegos: puntos={user_sample.get('puntos')}, vidas={user_sample.get('vidas')}")
    else:
        print("No hay usuarios en la colección 'usuarios'.")

    # 3. Analizar 'estados_usuario'
    if "estados_usuario" in collections:
        print("\n--- ANÁLISIS DE 'estados_usuario' ---")
        cursor = db["estados_usuario"].find()
        estados = await cursor.to_list(length=100)
        for est in estados:
            print(f"  ID: {est.get('id')}, Código: {est.get('codigo')}, Nombre: {est.get('nombre')}, Habilitado: {est.get('habilitado')}")

    # 4. Analizar colecciones exclusivas de cursos (si existen)
    progreso_colls = [c for c in collections if "progreso" in c or "curso" in c]
    print(f"\nColecciones con 'progreso' o 'curso' en el nombre: {progreso_colls}")

    # Guardar resumen en JSON
    output_path = os.path.join(os.path.dirname(__file__), "mongodb_probe_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "db_name": settings.MONGODB_DB_NAME,
            "collections": collection_stats,
            "user_sample_keys": list(user_sample.keys()) if user_sample else []
        }, f, indent=2)
    print(f"\nResultados exportados a: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
